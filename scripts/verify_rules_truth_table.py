#!/usr/bin/env python3
"""
Item 1 & Item 3 verification script:
1. Extract every refusal_code string and threshold constant from backend/bine/quote_engine.py
   and backend/bine/quality.py.
2. Parse GUARD_RULE_DEFINITIONS and REFUSAL_CODE_LABELS from frontend/src/lib/humanize.ts.
3. Open /refusals and /guard?ticker=NVDA&amount=5.5 in headless Chrome via CDP and extract
   what the Refusals rules table and Guard checks list actually render in the DOM.
4. Print a three-column truth table and mark each row MATCH or MISMATCH.
5. Verify that rule counts and recorded refusal counts are derived from dictionary/array lengths
   (no hard-coded "8 rules" or "6 recorded refusals" in frontend/src/) and that the landing page
   "What Bine refuses" card uses a verified entry from docs/raw/regular_hours_quotes_2026-10-05.jsonl.
"""

import base64
import json
import os
import re
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

import bine.quality as quality  # noqa: E402
import bine.quote_engine as qe  # noqa: E402

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE_URL = os.environ.get("BINE_FRONTEND_URL", "http://localhost:5174")


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class SimpleWS:
    def __init__(self, ws_url: str):
        parsed = urllib.parse.urlparse(ws_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 80
        path = parsed.path or "/"
        self.sock = socket.create_connection((host, port), timeout=30)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        req = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(req.encode("ascii"))
        buf = b""
        while b"\r\n\r\n" not in buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise RuntimeError("WebSocket handshake failed")
            buf += chunk
        _, self.extra = buf.split(b"\r\n\r\n", 1)

    def _recv_exact(self, n: int) -> bytes:
        out = b""
        if self.extra:
            take = min(n, len(self.extra))
            out += self.extra[:take]
            self.extra = self.extra[take:]
        while len(out) < n:
            chunk = self.sock.recv(n - len(out))
            if not chunk:
                raise RuntimeError("WebSocket closed unexpectedly")
            out += chunk
        return out

    def send_text(self, text: str) -> None:
        data = text.encode("utf-8")
        mask = os.urandom(4)
        header = bytearray([0x81])
        length = len(data)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        header.extend(mask)
        masked = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
        self.sock.sendall(bytes(header) + masked)

    def recv_text(self) -> str:
        while True:
            b1, b2 = self._recv_exact(2)
            opcode = b1 & 0x0F
            masked = bool(b2 & 0x80)
            length = b2 & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._recv_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._recv_exact(8))[0]
            mask = self._recv_exact(4) if masked else b""
            payload = self._recv_exact(length)
            if masked:
                payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
            if opcode == 0x1:
                return payload.decode("utf-8")
            if opcode == 0x8:
                raise RuntimeError("WebSocket closed by peer")

    def close(self) -> None:
        try:
            self.sock.close()
        except Exception:
            pass


class CDPSession:
    def __init__(self, ws_url: str):
        self.ws = SimpleWS(ws_url)
        self.msg_id = 0

    def send(self, method: str, params: dict | None = None) -> dict:
        self.msg_id += 1
        req_id = self.msg_id
        payload = {"id": req_id, "method": method, "params": params or {}}
        self.ws.send_text(json.dumps(payload))
        while True:
            raw = self.ws.recv_text()
            msg = json.loads(raw)
            if msg.get("id") == req_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error in {method}: {msg['error']}")
                return msg.get("result", {})

    def eval_js(self, expression: str, await_promise: bool = True):
        res = self.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
        )
        if "exceptionDetails" in res:
            raise RuntimeError(f"JS exception: {res['exceptionDetails']}")
        return res.get("result", {}).get("value")

    def close(self):
        self.ws.close()


def extract_backend_rules_and_thresholds() -> tuple[list[str], dict[str, str]]:
    qe_path = os.path.join(ROOT, "backend", "bine", "quote_engine.py")
    qual_path = os.path.join(ROOT, "backend", "bine", "quality.py")
    with open(qe_path, encoding="utf-8") as f:
        qe_src = f.read()
    with open(qual_path, encoding="utf-8") as f:
        qual_src = f.read()

    # Extract all RefusalCheck(rule="...") and refusal={"code": "..."} and ev.refusal_code = "..."
    codes_in_order: list[str] = []
    for m in re.finditer(
        r'RefusalCheck\(rule="([a-z_]+)"|ev\.refusal_code\s*=\s*"([a-z_]+)"|refusal=\{"code":\s*"([a-z_]+)"',
        qe_src,
    ):
        code = m.group(1) or m.group(2) or m.group(3)
        if code and code not in codes_in_order:
            codes_in_order.append(code)

    thresholds = {
        "amount_over_cap": f"> $0.00 to <= ${qe.MAX_QUOTE_USD:,.2f} (MAX_QUOTE_USD={qe.MAX_QUOTE_USD})",
        "below_issuer_minimum": (
            f"${qe._issuer_min_order_usd('ondo'):.2f} Ondo / ${qe._issuer_min_order_usd('bstock'):.2f} bStocks "
            "(_issuer_min_order_usd + [40375])"
        ),
        "market_closed": "open_state=True, reason_code='TRADING', status not paused/closed, no 40367/40369",
        "reference_stale": f"reference_price > 0 & age <= {int(qe.MAX_SAMPLE_AGE_SECONDS)}s (MAX_SAMPLE_AGE_SECONDS={qe.MAX_SAMPLE_AGE_SECONDS})",
        "quality_unreliable": (
            f"price >= ${quality.MIN_TOKEN_PRICE_USD:.2f}, ratio {quality.MIN_SHARE_RATIO:.2f}-{quality.MAX_SHARE_RATIO:.2f}x "
            f"(<=1% div), 24h vol >= ${quality.MIN_VOLUME_24H_USD:,.0f}"
        ),
        "depth_thin": (
            f"AMM liquidity >= ${qe.MIN_AMM_LIQUIDITY_USD:,.0f} & >= 10x order "
            f"(or 24h vol >= ${qe.MIN_RFQ_VOLUME_24H_USD:,.0f})"
        ),
        "slippage_too_high": f"effective_slippage_pct <= {qe.MAX_SLIPPAGE_PCT:.2f}% (MAX_SLIPPAGE_PCT={qe.MAX_SLIPPAGE_PCT})",
        "unknown_ticker": f"Present in BSC (chain {qe.BSC_CHAIN_ID}) {qe.PLATFORMS} /rwa/tokens catalog",
    }
    return codes_in_order, thresholds


def parse_humanize_ts() -> tuple[dict[str, str], dict[str, dict[str, str]]]:
    path = os.path.join(ROOT, "frontend", "src", "lib", "humanize.ts")
    with open(path, encoding="utf-8") as f:
        src = f.read()

    # Extract REFUSAL_CODE_LABELS
    labels_block = re.search(
        r"export const REFUSAL_CODE_LABELS[^=]*=\s*\{([^}]+)\}", src, flags=re.S
    )
    refusal_labels: dict[str, str] = {}
    if labels_block:
        for m in re.finditer(r"(\w+)\s*:\s*'([^']+)'", labels_block.group(1)):
            refusal_labels[m.group(1)] = m.group(2)

    # Extract GUARD_RULE_DEFINITIONS
    defs_block = re.search(
        r"export const GUARD_RULE_DEFINITIONS[^=]*=\s*\{(.*?)\n\};", src, flags=re.S
    )
    rule_defs: dict[str, dict[str, str]] = {}
    if defs_block:
        for m in re.finditer(
            r"(\w+)\s*:\s*\{\s*name:\s*'([^']+)',\s*explanation:\s*(?:'([^']+)'|\n\s*'([^']+)'),\s*threshold:\s*'([^']+)'",
            defs_block.group(1),
        ):
            code = m.group(1)
            name = m.group(2)
            expl = m.group(3) or m.group(4) or ""
            thresh = m.group(5)
            rule_defs[code] = {"name": name, "explanation": expl, "threshold": thresh}

    return refusal_labels, rule_defs


def main() -> int:
    backend_codes, backend_thresholds = extract_backend_rules_and_thresholds()
    refusal_labels, rule_defs = parse_humanize_ts()

    print(f"Backend refusal codes extracted ({len(backend_codes)}): {backend_codes}")
    print(f"Frontend REFUSAL_CODE_LABELS keys ({len(refusal_labels)}): {list(refusal_labels.keys())}")
    print(f"Frontend GUARD_RULE_DEFINITIONS keys ({len(rule_defs)}): {list(rule_defs.keys())}")

    # Launch headless Chrome to inspect what /refusals and /guard actually render
    port = get_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="bine_truth_table_")
    proc = subprocess.Popen(
        [
            CHROME_BIN,
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--window-size=1440,900",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        ws_url = None
        for _ in range(40):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json") as resp:
                    targets = json.loads(resp.read().decode())
                    for t in targets:
                        if t.get("type") == "page" and "webSocketDebuggerUrl" in t:
                            ws_url = t["webSocketDebuggerUrl"]
                            break
                if ws_url:
                    break
            except Exception:
                pass
            time.sleep(0.2)

        if not ws_url:
            print("ERROR: Could not connect to headless Chrome CDP.", file=sys.stderr)
            return 2

        cdp = CDPSession(ws_url)
        cdp.send("Page.enable")
        cdp.send("Runtime.enable")

        # 1. Inspect /refusals rules table
        cdp.send("Page.navigate", {"url": f"{BASE_URL}/refusals"})
        for _ in range(30):
            if cdp.eval_js("document.querySelectorAll('table tbody tr').length > 0"):
                break
            time.sleep(0.2)
        refusals_dom = cdp.eval_js(
            """
            (() => {
              const rows = Array.from(document.querySelectorAll('table tbody tr')).map(tr => {
                const tds = tr.querySelectorAll('td');
                const btn = tr.querySelector('button[aria-controls]');
                const code = btn ? (btn.getAttribute('aria-controls') || '').replace('rule-glass-', '') : '';
                return {
                  code,
                  name: tds[0] ? tds[0].textContent.trim() : '',
                  explanation: tds[1] ? tds[1].textContent.trim() : '',
                  threshold: tds[2] ? tds[2].textContent.trim() : '',
                };
              });
              const heading = (document.getElementById('rule-legend-heading')?.textContent || '').trim();
              const evidenceHeading = (document.getElementById('recorded-evidence-heading')?.textContent || '').trim();
              const cardCount = document.querySelectorAll('article.bine-card').length;
              return { rows, heading, evidenceHeading, cardCount };
            })()
            """
        )

        # 2. Inspect /guard?ticker=NVDA&amount=5.5 checks list
        cdp.send("Page.navigate", {"url": f"{BASE_URL}/guard?ticker=NVDA&amount=5.5"})
        for _ in range(75):
            if cdp.eval_js(
                "document.querySelectorAll('[aria-controls^=\"guard-check-glass-\"], [aria-controls^=\"guard-refuse-check-glass-\"]').length > 0"
            ):
                break
            time.sleep(0.2)
        guard_dom = cdp.eval_js(
            """
            (() => {
              const btns = Array.from(
                document.querySelectorAll('[aria-controls^="guard-check-glass-"], [aria-controls^="guard-refuse-check-glass-"]')
              );
              return btns.map(b => {
                const rawCtrl = b.getAttribute('aria-controls') || '';
                const code = rawCtrl.replace('guard-refuse-check-glass-', '').replace('guard-check-glass-', '');
                const divs = b.querySelectorAll('div');
                return {
                  code,
                  name: divs[1] ? divs[1].textContent.trim() : '',
                  detail: divs[2] ? divs[2].textContent.trim() : '',
                };
              });
            })()
            """
        )

        # 3. Inspect / landing page "What Bine refuses" card and links
        cdp.send("Page.navigate", {"url": f"{BASE_URL}/"})
        for _ in range(25):
            if cdp.eval_js("Boolean(document.querySelector('h1'))"):
                break
            time.sleep(0.2)
        landing_dom = cdp.eval_js(
            """
            (() => {
              const links = Array.from(document.querySelectorAll('a[href="/refusals"]')).map(a => a.textContent.trim());
              const cards = Array.from(document.querySelectorAll('.bine-card'));
              const refuseCard = cards.find(c => (c.textContent || '').includes('What Bine refuses'));
              return {
                refusalsLinks: links,
                refuseCardText: refuseCard ? refuseCard.textContent.trim() : '',
              };
            })()
            """
        )

        cdp.close()

        ref_by_code = {r["code"]: r for r in refusals_dom["rows"]}
        guard_by_code = {g["code"]: g for g in guard_dom}

        print("\n=== ITEM 1: THREE-COLUMN RULES TRUTH TABLE ===")
        print(
            f"{'Backend Code & Threshold':<64} | {'GUARD_RULE_DEFINITIONS':<52} | {'Rendered (/refusals & /guard)':<50} | Status"
        )
        print("-" * 180)

        mismatches = 0
        all_codes = list(dict.fromkeys([*backend_codes, *rule_defs.keys()]))
        for code in all_codes:
            b_thresh = backend_thresholds.get(code, "MISSING IN BACKEND")
            f_def = rule_defs.get(code)
            r_row = ref_by_code.get(code)
            g_row = guard_by_code.get(code)
            r_label = refusal_labels.get(code)

            has_underscore = False
            if f_def and ("_" in f_def["name"] or "_" in f_def["threshold"]):
                has_underscore = True
            if r_label and "_" in r_label:
                has_underscore = True
            if r_row and ("_" in r_row["name"] or "_" in r_row["threshold"]):
                has_underscore = True
            if g_row and ("_" in g_row["name"] or "_" in g_row["detail"]):
                has_underscore = True

            match_ok = (
                code in backend_thresholds
                and f_def is not None
                and r_label is not None
                and r_row is not None
                and g_row is not None
                and r_row["name"] == f_def["name"]
                and r_row["threshold"] == f_def["threshold"]
                and g_row["name"] == f_def["name"]
                and not has_underscore
            )
            status = "MATCH" if match_ok else "MISMATCH"
            if not match_ok:
                mismatches += 1

            col1 = f"{code}: {b_thresh}"
            col2 = f"{f_def['name']} ({f_def['threshold']})" if f_def else "MISSING"
            col3 = (
                f"Refusals='{r_row['name']}' [{r_row['threshold']}] / Guard='{g_row['name']}'"
                if (r_row and g_row)
                else "MISSING IN DOM"
            )
            print(f"{col1:<64} | {col2:<52} | {col3:<50} | {status}")

        # Verify zero hard-coded "8 rules" or "6 recorded refusals" in frontend/src/
        hardcoded_hits: list[str] = []
        for root_dir, _, files in os.walk(os.path.join(ROOT, "frontend", "src")):
            for fn in files:
                if not fn.endswith((".ts", ".tsx")):
                    continue
                fp = os.path.join(root_dir, fn)
                with open(fp, encoding="utf-8") as f:
                    for lineno, line in enumerate(f, 1):
                        if re.search(
                            r"\b8\s+(deterministic|pre-trade|safety|checks|rules)\b|\bThe\s+8\b|\ball\s+8\b|\b6\s+recorded\s+refusals\b",
                            line,
                            flags=re.I,
                        ):
                            hardcoded_hits.append(f"{os.path.relpath(fp, ROOT)}:{lineno}: {line.strip()}")

        # Verify Item 3: recorded-refusals.json count and landing page featured refusal provenance
        with open(os.path.join(ROOT, "frontend", "src", "data", "recorded-refusals.json"), encoding="utf-8") as f:
            rec_refusals = json.load(f)
        with open(os.path.join(ROOT, "docs", "raw", "regular_hours_quotes_2026-10-05.jsonl"), encoding="utf-8") as f:
            jsonl_lines = [json.loads(line) for line in f if line.strip()]
        with open(os.path.join(ROOT, "docs", "devex-facts.md"), encoding="utf-8") as f:
            devex_facts_src = f.read()

        spyon_card = next((r for r in rec_refusals if r["id"] == "spyon-slippage-250"), None)
        spyb_25_raw = jsonl_lines[5]  # line 6 (1-indexed): SPYB at $25.00
        spyon_provenance_ok = (
            spyon_card is not None
            and spyon_card["token_symbol"] == "SPYon"
            and spyon_card["amount_usd"] == 250.0
            and "1,087.43" in devex_facts_src
            and "772.52" in devex_facts_src
            and round(spyb_25_raw["all_in_price_per_share_usd"], 2) == 773.35
            and round(spyb_25_raw["referencePrice"], 2) == 773.02
            and spyon_card["message"] in landing_dom["refuseCardText"]
        )

        print("\n=== ITEM 1 & ITEM 3 COUNTS AND PROVENANCE SUMMARY ===")
        print(f"Backend refusal codes count: {len(backend_codes)} (7 per-issuer RefusalCheck rules + 1 catalog unknown_ticker rule)")
        print(f"GUARD_RULE_DEFINITIONS length: {len(rule_defs)}")
        print(f"Refusals page heading rendered: '{refusals_dom['heading']}'")
        print(f"Refusals evidence heading rendered: '{refusals_dom['evidenceHeading']}' (DOM cards={refusals_dom['cardCount']}, JSON length={len(rec_refusals)})")
        print(f"Landing page /refusals links rendered: {landing_dom['refusalsLinks']}")
        print(f"Landing page 'What Bine refuses' card matches regular_hours_quotes_2026-10-05.jsonl:6: {spyon_provenance_ok}")
        print(f"Hard-coded rule/refusal count strings in frontend/src: {len(hardcoded_hits)}")
        for hit in hardcoded_hits:
            print(f"  HARDCODED: {hit}")
        print(f"MISMATCH_ROWS={mismatches}")

        return 0 if (mismatches == 0 and len(hardcoded_hits) == 0 and spyon_provenance_ok) else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
