#!/usr/bin/env python3
"""
Phase C, D & E verification script:
1. Measure FCP / LCP / CLS / load timings on / and /guard.
2. Verify all glass panels start closed (initial_panel_open == False), click the first
   .bine-glass-trigger (metric tile on /guard, proof card on /), record a Performance trace
   during the real click, and assert glass_panel_opened == True and zero long tasks > 50 ms.
3. Decode rendered PNG screenshots to sample actual pixels behind the panel (including the
   lavender ring on landing) and inside .bine-glass-scrim at 390 and 1440 in light and dark,
   compute WCAG 2.2 sRGB relative luminance and contrast ratios for primary and secondary text,
   and fail if any ratio < 4.5:1.
4. Capture docs/screenshots/glass_<page>_<theme>_<width>.png across all 5 routes at 390, 768, 1440
   in light and dark from real clicks.
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
import zlib

CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BASE_URL = os.environ.get("BINE_FRONTEND_URL", "http://localhost:5174")
OUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "screenshots"
)


def get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def decode_png_rgb(png_bytes: bytes) -> tuple[int, int, list[list[tuple[int, int, int]]]]:
    """Decode an 8-bit RGB or RGBA PNG into (width, height, rows_of_rgb_tuples)."""
    if png_bytes[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Invalid PNG header")
    pos = 8
    width = height = bit_depth = color_type = 0
    idat_chunks: list[bytes] = []
    while pos < len(png_bytes):
        length = struct.unpack("!I", png_bytes[pos : pos + 4])[0]
        chunk_type = png_bytes[pos + 4 : pos + 8]
        chunk_data = png_bytes[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack("!IIBBBBB", chunk_data)
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    if bit_depth != 8 or color_type not in (2, 6):
        raise ValueError(f"Unsupported PNG format: bit_depth={bit_depth}, color_type={color_type}")
    bpp = 3 if color_type == 2 else 4
    raw = zlib.decompress(b"".join(idat_chunks))
    stride = width * bpp
    rows: list[list[tuple[int, int, int]]] = []
    prev_scanline = bytearray(stride)
    offset = 0

    def paeth(a: int, b: int, c: int) -> int:
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            return a
        if pb <= pc:
            return b
        return c

    for _ in range(height):
        ftype = raw[offset]
        scanline = bytearray(raw[offset + 1 : offset + 1 + stride])
        offset += 1 + stride
        if ftype == 1:  # Sub
            for i in range(bpp, stride):
                scanline[i] = (scanline[i] + scanline[i - bpp]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                scanline[i] = (scanline[i] + prev_scanline[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                left = scanline[i - bpp] if i >= bpp else 0
                up = prev_scanline[i]
                scanline[i] = (scanline[i] + ((left + up) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                left = scanline[i - bpp] if i >= bpp else 0
                up = prev_scanline[i]
                up_left = prev_scanline[i - bpp] if i >= bpp else 0
                scanline[i] = (scanline[i] + paeth(left, up, up_left)) & 0xFF
        prev_scanline = scanline
        row_pixels: list[tuple[int, int, int]] = []
        for x in range(0, stride, bpp):
            row_pixels.append((scanline[x], scanline[x + 1], scanline[x + 2]))
        rows.append(row_pixels)
    return width, height, rows


def srgb_channel_to_linear(c: float) -> float:
    v = c / 255.0
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return (
        0.2126 * srgb_channel_to_linear(r)
        + 0.7152 * srgb_channel_to_linear(g)
        + 0.0722 * srgb_channel_to_linear(b)
    )


def wcag_contrast_ratio(rgb1: tuple[float, float, float], rgb2: tuple[float, float, float]) -> float:
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def parse_css_rgba(css_str: str) -> tuple[float, float, float, float]:
    nums = [float(x) for x in re.findall(r"[\d.]+", css_str or "")]
    if len(nums) == 3:
        return nums[0], nums[1], nums[2], 1.0
    if len(nums) >= 4:
        return nums[0], nums[1], nums[2], nums[3]
    return 0.0, 0.0, 0.0, 1.0


def composite_over(fg_rgba: tuple[float, float, float, float], bg_rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    fr, fg, fb, alpha = fg_rgba
    br, bg, bb = bg_rgb
    return (
        alpha * fr + (1.0 - alpha) * br,
        alpha * fg + (1.0 - alpha) * bg,
        alpha * fb + (1.0 - alpha) * bb,
    )


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


def sample_region_pixels(
    rows: list[list[tuple[int, int, int]]],
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    step: int = 4,
) -> list[tuple[int, int, int]]:
    x0 = max(0, min(width - 1, x0))
    x1 = max(x0 + 1, min(width, x1))
    y0 = max(0, min(height - 1, y0))
    y1 = max(y0 + 1, min(height, y1))
    samples: list[tuple[int, int, int]] = []
    for y in range(y0, y1, step):
        row = rows[y]
        for x in range(x0, x1, step):
            samples.append(row[x])
    if not samples:
        samples.append(rows[y0][x0])
    return samples


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    port = get_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="bine_glass_verify_")
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
        cdp.send("Performance.enable")

        # 1. Measure load & FCP + real click performance trace on / and /guard
        for label, path in [("landing", "/"), ("guard", "/guard?ticker=NVDA&amount=5.5")]:
            cdp.send(
                "Emulation.setDeviceMetricsOverride",
                {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
            )
            cdp.send("Page.navigate", {"url": f"{BASE_URL}{path}"})
            # Wait for .bine-glass-trigger and initial header shader canvas to settle
            for _ in range(75):
                has_trigger = cdp.eval_js(
                    "Boolean(document.querySelector('.bine-glass-trigger') && document.querySelector('[data-bine-logo-tile] canvas'))"
                )
                if has_trigger:
                    break
                time.sleep(0.2)
            time.sleep(0.4)

            perf = cdp.eval_js(
                """
                (() => {
                  const nav = performance.getEntriesByType('navigation')[0];
                  const paints = Object.fromEntries(
                    performance.getEntriesByType('paint').map(p => [p.name, Math.round(p.startTime)])
                  );
                  return {
                    fcp_ms: paints['first-contentful-paint'] ?? null,
                    fp_ms: paints['first-paint'] ?? null,
                    dom_interactive_ms: nav ? Math.round(nav.domInteractive) : null,
                    load_ms: nav ? Math.round(nav.loadEventEnd) : null,
                  };
                })()
                """
            )
            click_trace = cdp.eval_js(
                """
                new Promise(resolve => {
                  const initialOpen = Boolean(document.querySelector('[data-glass-panel]'));
                  const longTasks = [];
                  let obs;
                  if (typeof PerformanceObserver !== 'undefined') {
                    obs = new PerformanceObserver(list => {
                      for (const entry of list.getEntries()) {
                        longTasks.push(Math.round(entry.duration));
                      }
                    });
                    try { obs.observe({ entryTypes: ['longtask'] }); } catch {}
                  }
                  const btn = document.querySelector('.bine-glass-trigger');
                  const triggerLabel = btn ? (btn.textContent || '').trim().slice(0, 48) : null;
                  const t0 = performance.now();
                  if (btn) btn.click();
                  const handlerMs = +(performance.now() - t0).toFixed(2);
                  setTimeout(() => {
                    if (obs) obs.disconnect();
                    const panel = document.querySelector('[data-glass-panel]');
                    resolve({
                      initial_panel_open: initialOpen,
                      clicked_trigger: triggerLabel,
                      click_handler_ms: handlerMs,
                      long_tasks_over_50ms: longTasks,
                      glass_panel_opened: Boolean(panel),
                    });
                  }, 380);
                })
                """
            )
            print(
                f"[PERF] {label} ({path}): timings={json.dumps(perf)} click_trace={json.dumps(click_trace)}"
            )
            if click_trace["initial_panel_open"]:
                print(
                    f"ERROR: {label} started with a glass panel already open: {click_trace}",
                    file=sys.stderr,
                )
                return 1
            if not click_trace["glass_panel_opened"]:
                print(
                    f"ERROR: Real click on {label} did not open a glass panel: {click_trace}",
                    file=sys.stderr,
                )
                return 1
            if click_trace["long_tasks_over_50ms"]:
                print(f"ERROR: Long task > 50ms detected: {click_trace}", file=sys.stderr)
                return 1

        # 2. Capture all 30 screenshots (5 pages x 2 themes x 3 widths) from real clicks
        #    and compute WCAG sRGB contrast ratios at 390 and 1440 in light and dark.
        pages = [
            ("landing", "/"),
            ("guard", "/guard?ticker=NVDA&amount=5.5"),
            ("refusals", "/refusals"),
            ("receipts", "/receipts"),
            ("developers", "/integrate"),
        ]
        widths = [390, 768, 1440]

        overflow_failures = []
        contrast_results = []
        contrast_failures = []

        for page_name, path in pages:
            for theme in ("light", "dark"):
                for w in widths:
                    h = 844 if w == 390 else (1024 if w == 768 else 900)
                    cdp.send(
                        "Emulation.setDeviceMetricsOverride",
                        {
                            "width": w,
                            "height": h,
                            "deviceScaleFactor": 1,
                            "mobile": w == 390,
                        },
                    )
                    cdp.send("Page.navigate", {"url": f"{BASE_URL}{path}"})
                    # Wait for .bine-glass-trigger to mount
                    for _ in range(75):
                        ready = cdp.eval_js(
                            "Boolean(document.querySelector('.bine-glass-trigger'))"
                        )
                        if ready:
                            break
                        time.sleep(0.2)
                    time.sleep(0.25)

                    cdp.eval_js(
                        f"""
                        (() => {{
                          localStorage.setItem('bine-theme', '{theme}');
                          document.documentElement.setAttribute('data-theme', '{theme}');
                        }})()
                        """
                    )
                    time.sleep(0.15)

                    # Verify panel starts closed before clicking
                    started_open = cdp.eval_js("Boolean(document.querySelector('[data-glass-panel]'))")
                    if started_open:
                        print(
                            f"ERROR: {page_name}_{theme}_{w} started with panel open before click!",
                            file=sys.stderr,
                        )
                        return 1

                    # Capture pre-click screenshot on landing/guard at 390 and 1440 to sample lavender ring / backdrop
                    pre_click_png = None
                    hero_ring_rect = None
                    if w in (390, 1440) and page_name in ("landing", "guard"):
                        hero_ring_rect = cdp.eval_js(
                            """
                            (() => {
                              const svg = document.querySelector('svg');
                              const allSvgs = Array.from(document.querySelectorAll('svg'));
                              const bigSvg = allSvgs.find(s => s.getBoundingClientRect().width > 180) || svg;
                              if (!bigSvg) return null;
                              const r = bigSvg.getBoundingClientRect();
                              return {
                                x0: Math.round(r.left),
                                y0: Math.round(r.top),
                                x1: Math.round(r.right),
                                y1: Math.round(r.bottom),
                              };
                            })()
                            """
                        )
                        pre_click_png = base64.b64decode(
                            cdp.send("Page.captureScreenshot", {"format": "png"})["data"]
                        )

                    # Click the first .bine-glass-trigger to open the glass panel
                    cdp.eval_js(
                        """
                        (() => {
                          const trigger = document.querySelector('.bine-glass-trigger');
                          if (trigger) trigger.click();
                        })()
                        """
                    )
                    # Wait for [data-glass-panel] to appear from the real click
                    for _ in range(20):
                        if cdp.eval_js("Boolean(document.querySelector('[data-glass-panel]'))"):
                            break
                        time.sleep(0.1)
                    time.sleep(0.25)

                    cdp.eval_js(
                        """
                        (() => {
                          const panel = document.querySelector('[data-glass-panel]');
                          if (panel) {
                            panel.scrollIntoView({ block: 'center', behavior: 'instant' });
                          }
                        })()
                        """
                    )
                    time.sleep(0.25)

                    check = cdp.eval_js(
                        """
                        (() => {
                          const overflow = document.documentElement.scrollWidth > window.innerWidth;
                          const panel = document.querySelector('[data-glass-panel]');
                          const scrim = document.querySelector('.bine-glass-scrim');
                          let primaryColor = null;
                          let secondaryColor = null;
                          let scrimBg = null;
                          let scrimRect = null;
                          let outerGlassAlpha = null;
                          if (panel) {
                            const pcs = window.getComputedStyle(panel);
                            const rawAlpha = (pcs.getPropertyValue('--glass-outer-tint-alpha') || '').trim();
                            outerGlassAlpha = rawAlpha ? parseFloat(rawAlpha) : 0.5;
                          }
                          if (scrim) {
                            const cs = window.getComputedStyle(scrim);
                            primaryColor = cs.color;
                            scrimBg = cs.backgroundColor;
                            const r = scrim.getBoundingClientRect();
                            scrimRect = {
                              x0: Math.round(r.left),
                              y0: Math.round(r.top),
                              x1: Math.round(r.right),
                              y1: Math.round(r.bottom),
                            };
                            // Find a secondary text element inside scrim or read --text-secondary
                            const rootCs = window.getComputedStyle(document.documentElement);
                            const secHex = (rootCs.getPropertyValue('--text-secondary') || '').trim();
                            const probe = document.createElement('span');
                            probe.style.color = secHex || 'var(--text-secondary)';
                            document.body.appendChild(probe);
                            secondaryColor = window.getComputedStyle(probe).color;
                            document.body.removeChild(probe);
                          }
                          return {
                            scrollWidth: document.documentElement.scrollWidth,
                            innerWidth: window.innerWidth,
                            overflow,
                            hasGlassPanel: Boolean(panel),
                            outerGlassAlpha,
                            primaryColor,
                            secondaryColor,
                            scrimBg,
                            scrimRect,
                          };
                        })()
                        """
                    )
                    if not check["hasGlassPanel"]:
                        print(
                            f"ERROR: {page_name}_{theme}_{w} failed to open glass panel on click!",
                            file=sys.stderr,
                        )
                        return 1
                    if check["overflow"]:
                        overflow_failures.append(
                            f"{page_name}_{theme}_{w}: {check['scrollWidth']} > {check['innerWidth']}"
                        )

                    shot_bytes = base64.b64decode(
                        cdp.send("Page.captureScreenshot", {"format": "png"})["data"]
                    )
                    out_path = os.path.join(OUT_DIR, f"glass_{page_name}_{theme}_{w}.png")
                    with open(out_path, "wb") as f:
                        f.write(shot_bytes)
                    print(
                        f"Saved {os.path.relpath(out_path)} (glass_open={check['hasGlassPanel']}, overflow={check['overflow']})"
                    )

                    # Item 2 & Item 4: Compute WCAG contrast ratios on the inner plate (.bine-glass-scrim)
                    # inside the ~0.50 outer glass panel at 390 and 1440 in light and dark.
                    if w in (390, 1440) and page_name in ("landing", "guard") and check["scrimRect"]:
                        pw, ph, post_rows = decode_png_rgb(shot_bytes)
                        sr = check["scrimRect"]
                        # Sample pixels inside the rendered inner plate (.bine-glass-scrim) and behind the panel
                        scrim_pixels = sample_region_pixels(
                            post_rows, pw, ph, sr["x0"] + 8, sr["y0"] + 8, sr["x1"] - 8, sr["y1"] - 8, step=6
                        )
                        backdrop_pixels = list(scrim_pixels)
                        if pre_click_png is not None:
                            bw, bh, pre_rows = decode_png_rgb(pre_click_png)
                            # Sample where the panel sits in the pre-click screenshot
                            backdrop_pixels.extend(
                                sample_region_pixels(
                                    pre_rows, bw, bh, sr["x0"], sr["y0"], sr["x1"], sr["y1"], step=8
                                )
                            )
                            # On landing, also sample the lavender ring region from the screenshot
                            if hero_ring_rect:
                                backdrop_pixels.extend(
                                    sample_region_pixels(
                                        pre_rows,
                                        bw,
                                        bh,
                                        hero_ring_rect["x0"],
                                        hero_ring_rect["y0"],
                                        hero_ring_rect["x1"],
                                        hero_ring_rect["y1"],
                                        step=6,
                                    )
                                )

                        prim_rgba = parse_css_rgba(check["primaryColor"])
                        sec_rgba = parse_css_rgba(check["secondaryColor"])
                        scrim_rgba = parse_css_rgba(check["scrimBg"])
                        outer_alpha = float(check["outerGlassAlpha"] or 0.5)
                        outer_tint_rgba = (
                            (218.0, 217.0, 235.0, outer_alpha)
                            if theme == "light"
                            else (30.0, 33.5, 47.0, outer_alpha)
                        )
                        prim_rgb = (prim_rgba[0], prim_rgba[1], prim_rgba[2])
                        sec_rgb = (sec_rgba[0], sec_rgba[1], sec_rgba[2])

                        if theme == "light":
                            bg_candidates = [
                                px for px in backdrop_pixels if relative_luminance(px) >= 0.25
                            ] or backdrop_pixels
                            worst_raw_backdrop = min(bg_candidates, key=relative_luminance)
                        else:
                            bg_candidates = [
                                px for px in backdrop_pixels if relative_luminance(px) <= 0.85
                            ] or backdrop_pixels
                            worst_raw_backdrop = max(bg_candidates, key=relative_luminance)

                        # Plate alone over worst backdrop pixel (conservative bound)
                        plate_only_bg = composite_over(scrim_rgba, worst_raw_backdrop)
                        # Outer glass (~0.50) + inner plate (0.82) over worst backdrop pixel
                        outer_bg = composite_over(outer_tint_rgba, worst_raw_backdrop)
                        plate_in_glass_bg = composite_over(
                            scrim_rgba,
                            (int(round(outer_bg[0])), int(round(outer_bg[1])), int(round(outer_bg[2]))),
                        )

                        prim_ratio = round(wcag_contrast_ratio(prim_rgb, plate_only_bg), 2)
                        sec_ratio = round(wcag_contrast_ratio(sec_rgb, plate_only_bg), 2)
                        prim_in_glass_ratio = round(wcag_contrast_ratio(prim_rgb, plate_in_glass_bg), 2)
                        sec_in_glass_ratio = round(wcag_contrast_ratio(sec_rgb, plate_in_glass_bg), 2)

                        record = {
                            "page": page_name,
                            "theme": theme,
                            "width": w,
                            "outer_glass_tint_alpha": outer_alpha,
                            "inner_plate_rgba": list(scrim_rgba),
                            "primary_rgb": [int(x) for x in prim_rgb],
                            "secondary_rgb": [int(x) for x in sec_rgb],
                            "worst_backdrop_pixel_rgb": list(worst_raw_backdrop),
                            "plate_over_backdrop_rgb": [round(x, 1) for x in plate_only_bg],
                            "plate_in_glass_rgb": [round(x, 1) for x in plate_in_glass_bg],
                            "primary_wcag_ratio": prim_ratio,
                            "secondary_wcag_ratio": sec_ratio,
                            "primary_in_glass_wcag_ratio": prim_in_glass_ratio,
                            "secondary_in_glass_wcag_ratio": sec_in_glass_ratio,
                            "pass_4_5": (
                                prim_ratio >= 4.5
                                and sec_ratio >= 4.5
                                and scrim_rgba[3] <= 0.85
                                and 0.45 <= outer_alpha <= 0.55
                            ),
                        }
                        contrast_results.append(record)
                        print(f"[WCAG] {page_name}_{theme}_{w}: {json.dumps(record)}")
                        if not record["pass_4_5"]:
                            contrast_failures.append(record)

        print("WCAG_CONTRAST_SUMMARY:", json.dumps(contrast_results, indent=2))
        print(f"OVERFLOW_FAILURES={len(overflow_failures)}")
        print(f"CONTRAST_FAILURES={len(contrast_failures)}")
        if overflow_failures or contrast_failures:
            print(
                "ERROR: Failures detected:",
                {"overflow": overflow_failures, "contrast": contrast_failures},
                file=sys.stderr,
            )
            return 1

        cdp.close()
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
