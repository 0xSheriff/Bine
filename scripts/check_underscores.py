#!/usr/bin/env python3
"""
Verify that zero underscore characters ('_') appear in any visible text node,
aria-label, title tooltip, placeholder, alt text, or document.title across all
routes and interactive states (light & dark), excluding [data-raw-code] blocks.
Covers:
- Open glass panel ([data-glass-panel]) on every route (/, /guard, /refusals, /receipts, /integrate)
- Expanded receipt row on /receipts
- Developers "Try it" live result on /integrate
- Every title tooltip and aria-label attribute
"""

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

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


SCAN_JS = r"""
(() => {
  const offenders = [];

  if (document.title && document.title.includes('_')) {
    offenders.push({ kind: 'document.title', value: document.title, selector: 'title' });
  }

  const isInsideRawCode = (el) => {
    if (!el || !el.closest) return false;
    return Boolean(el.closest('[data-raw-code]'));
  };

  const isVisible = (el) => {
    if (!el || !(el instanceof Element)) return false;
    if (el.closest('script, style, noscript, svg, template')) return false;
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
      return false;
    }
    return true;
  };

  let textNodesScanned = 0;
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let node;
  while ((node = walker.nextNode())) {
    const text = (node.nodeValue || '').trim();
    if (!text) continue;
    const parent = node.parentElement;
    if (!parent) continue;
    if (isInsideRawCode(parent)) continue;
    if (!isVisible(parent)) continue;
    textNodesScanned += 1;
    if (text.includes('_')) {
      offenders.push({
        kind: 'text',
        value: text.slice(0, 140),
        tag: parent.tagName.toLowerCase(),
        className: (parent.className || '').toString().slice(0, 80),
      });
    }
  }

  const attrs = ['aria-label', 'title', 'placeholder', 'alt'];
  let titlesScanned = 0;
  let ariaLabelsScanned = 0;
  const allElements = document.querySelectorAll('*');
  for (const el of allElements) {
    if (isInsideRawCode(el)) continue;
    for (const attr of attrs) {
      const val = el.getAttribute(attr);
      if (val !== null && val !== '') {
        if (attr === 'title') titlesScanned += 1;
        if (attr === 'aria-label') ariaLabelsScanned += 1;
        if (val.includes('_')) {
          offenders.push({
            kind: `attr:${attr}`,
            value: val.slice(0, 140),
            tag: el.tagName.toLowerCase(),
          });
        }
      }
    }
  }

  const glassPanel = document.querySelector('[data-glass-panel]');
  const tryItLive = Boolean(
    Array.from(document.querySelectorAll('span')).find(
      s => (s.textContent || '').includes('Live response for NVDA')
    )
  );
  const receiptExpanded = Boolean(document.querySelector('[id^="receipt-details-"]'));

  return {
    offenders,
    textNodesScanned,
    titlesScanned,
    ariaLabelsScanned,
    glassPanelOpen: Boolean(glassPanel),
    tryItLive,
    receiptExpanded,
  };
})()
"""


def main() -> int:
    port = get_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="bine_underscore_check_")
    proc = subprocess.Popen(
        [
            CHROME_BIN,
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--window-size=1440,900",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
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
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
        )

        states = [
            ("landing", "/"),
            ("guard_idle", "/guard"),
            ("guard_buy", "/guard?ticker=NVDA&amount=5.5"),
            ("guard_refuse", "/guard?ticker=SPYon&amount=250"),
            ("guard_below_min", "/guard?ticker=AAPL&amount=2"),
            ("refusals", "/refusals"),
            ("receipts", "/receipts"),
            ("integrate", "/integrate"),
        ]

        total_offenders = 0
        for theme in ("light", "dark"):
            for name, path in states:
                url = f"{BASE_URL}{path}"
                cdp.send("Page.navigate", {"url": url})
                time.sleep(0.25)
                # Wait for route content & triggers (auto-retry if upstream API transiently errors)
                for _ in range(90):
                    ready = cdp.eval_js(
                        """
                        (() => {
                          const retryBtn = Array.from(document.querySelectorAll('button')).find(
                            b => (b.textContent || '').trim() === 'Retry'
                          );
                          if (retryBtn) retryBtn.click();
                          return Boolean(document.querySelector('.bine-glass-trigger') || document.querySelector('h1'));
                        })()
                        """
                    )
                    if ready and ("amount=" not in path or cdp.eval_js("Boolean(document.querySelector('.bine-glass-trigger'))")):
                        break
                    time.sleep(0.25)
                time.sleep(0.3)

                cdp.eval_js(
                    f"""
                    (() => {{
                      localStorage.setItem('bine-theme', '{theme}');
                      document.documentElement.setAttribute('data-theme', '{theme}');
                    }})()
                    """
                )

                # Open a glass panel on every route/state that has .bine-glass-trigger
                cdp.eval_js(
                    """
                    (() => {
                      const trigger = document.querySelector('.bine-glass-trigger');
                      if (trigger && !document.querySelector('[data-glass-panel]')) {
                        trigger.click();
                      }
                    })()
                    """
                )
                time.sleep(0.35)

                if name == "guard_buy":
                    cdp.eval_js(
                        """
                        (() => {
                          document.querySelectorAll('details').forEach(d => d.open = true);
                          const btns = Array.from(document.querySelectorAll('button'));
                          const previewBtn = btns.find(b => (b.textContent || '').includes('Preview'));
                          if (previewBtn) previewBtn.click();
                          if (!document.querySelector('[data-glass-panel]')) {
                            const trigger = document.querySelector('.bine-glass-trigger');
                            if (trigger) trigger.click();
                          }
                        })()
                        """
                    )
                    time.sleep(1.8)
                elif name in ("guard_refuse", "guard_below_min"):
                    cdp.eval_js(
                        """
                        (() => {
                          document.querySelectorAll('details').forEach(d => d.open = true);
                          if (!document.querySelector('[data-glass-panel]')) {
                            const trigger = document.querySelector('.bine-glass-trigger');
                            if (trigger) trigger.click();
                          }
                        })()
                        """
                    )
                    time.sleep(0.35)
                elif name == "refusals":
                    cdp.eval_js(
                        """
                        (() => {
                          const btn = Array.from(document.querySelectorAll('button')).find(
                            b => (b.textContent || '').includes('Run live now')
                          );
                          if (btn) btn.click();
                        })()
                        """
                    )
                    time.sleep(1.6)
                elif name == "receipts":
                    cdp.eval_js(
                        """
                        (() => {
                          if (!document.querySelector('[data-glass-panel]')) {
                            const btn = Array.from(document.querySelectorAll('button')).find(
                              b => (b.textContent || '').includes('Show details')
                            );
                            if (btn) btn.click();
                          }
                        })()
                        """
                    )
                    time.sleep(0.4)
                elif name == "integrate":
                    cdp.eval_js(
                        """
                        (() => {
                          const btn = Array.from(document.querySelectorAll('button')).find(
                            b => (b.textContent || '').trim() === 'Try it'
                          );
                          if (btn) btn.click();
                        })()
                        """
                    )
                    # Wait for "Live response for NVDA" to appear
                    for _ in range(25):
                        if cdp.eval_js(
                            "Boolean(Array.from(document.querySelectorAll('span')).find(s => (s.textContent || '').includes('Live response for NVDA')))"
                        ):
                            break
                        time.sleep(0.2)
                    time.sleep(0.2)

                # Ensure glass panel is open if any .bine-glass-trigger exists
                if not cdp.eval_js("Boolean(document.querySelector('[data-glass-panel]'))"):
                    cdp.eval_js(
                        """
                        (() => {
                          const trigger = document.querySelector('.bine-glass-trigger');
                          if (trigger) trigger.click();
                        })()
                        """
                    )
                    time.sleep(0.35)

                scan = cdp.eval_js(SCAN_JS) or {}
                offenders = scan.get("offenders", [])
                glass_open = bool(scan.get("glassPanelOpen"))
                if name != "guard_idle" and not glass_open:
                    print(
                        f"ERROR: [{theme}] {name} ({path}) did not have glass_open=True during underscore scan!",
                        file=sys.stderr,
                    )
                    return 1
                extra = (
                    f"glass_open={glass_open} "
                    f"text_nodes={scan.get('textNodesScanned')} "
                    f"titles={scan.get('titlesScanned')} "
                    f"aria_labels={scan.get('ariaLabelsScanned')}"
                )
                if name == "receipts":
                    extra += f" receipt_expanded={scan.get('receiptExpanded')}"
                if name == "integrate":
                    extra += f" try_it_live={scan.get('tryItLive')}"
                print(f"[{theme}] {name} ({path}): {len(offenders)} underscore(s) ({extra})")
                for off in offenders:
                    total_offenders += 1
                    print(f"  OFFENDER: {json.dumps(off)}")

        cdp.close()
        print(f"TOTAL_UNDERSCORE_OFFENDERS={total_offenders}")
        return 0 if total_offenders == 0 else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
