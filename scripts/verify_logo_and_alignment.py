#!/usr/bin/env python3
"""
Phase B verification:
1. Measure nav logo and footer logo left edge x-coordinates across all 5 routes
   at 1440px in light and dark modes; assert 0px drift across routes and between
   header and footer.
2. Crop the nav logo and footer logo at 1440px in light and dark with
   prefers-reduced-motion: reduce (frozen shader), compare pixels, and print the diff.
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
import zlib

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


def decode_png_rgba(png_bytes: bytes) -> tuple[int, int, bytes]:
    """Decode an 8-bit RGBA/RGB PNG using standard library zlib."""
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    pos = 8
    width = height = bit_depth = color_type = 0
    idat_chunks = []
    while pos < len(png_bytes):
        length = struct.unpack("!I", png_bytes[pos : pos + 4])[0]
        chunk_type = png_bytes[pos + 4 : pos + 8]
        chunk_data = png_bytes[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _, _, _ = struct.unpack(
                "!IIBBBBB", chunk_data
            )
        elif chunk_type == b"IDAT":
            idat_chunks.append(chunk_data)
        elif chunk_type == b"IEND":
            break
    raw = zlib.decompress(b"".join(idat_chunks))
    bpp = 4 if color_type == 6 else 3
    stride = width * bpp
    recon = bytearray(height * stride)
    i = 0
    for y in range(height):
        filter_type = raw[i]
        i += 1
        row_start = y * stride
        for x in range(stride):
            val = raw[i]
            i += 1
            a = recon[row_start + x - bpp] if x >= bpp else 0
            b = recon[row_start - stride + x] if y > 0 else 0
            c = recon[row_start - stride + x - bpp] if (y > 0 and x >= bpp) else 0
            if filter_type == 0:
                recon[row_start + x] = val
            elif filter_type == 1:
                recon[row_start + x] = (val + a) & 0xFF
            elif filter_type == 2:
                recon[row_start + x] = (val + b) & 0xFF
            elif filter_type == 3:
                recon[row_start + x] = (val + ((a + b) >> 1)) & 0xFF
            elif filter_type == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                recon[row_start + x] = (val + pr) & 0xFF
    return width, height, bytes(recon)


def main() -> int:
    port = get_free_port()
    user_data_dir = tempfile.mkdtemp(prefix="bine_logo_verify_")
    proc = subprocess.Popen(
        [
            CHROME_BIN,
            "--headless=new",
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            "--window-size=1440,1200",
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
        cdp.send(
            "Emulation.setDeviceMetricsOverride",
            {"width": 1440, "height": 1800, "deviceScaleFactor": 1, "mobile": False},
        )
        cdp.send(
            "Emulation.setEmulatedMedia",
            {
                "features": [
                    {"name": "prefers-reduced-motion", "value": "reduce"},
                ]
            },
        )

        routes = ["/", "/guard", "/refusals", "/receipts", "/integrate"]
        x_coords = {}

        for theme in ("light", "dark"):
            for route in routes:
                cdp.send("Page.navigate", {"url": f"{BASE_URL}{route}"})
                time.sleep(1.0)
                cdp.eval_js(
                    f"""
                    (() => {{
                      localStorage.setItem('bine-theme', '{theme}');
                      document.documentElement.setAttribute('data-theme', '{theme}');
                    }})()
                    """
                )
                time.sleep(0.4)
                rects = cdp.eval_js(
                    """
                    (() => {
                      const navLockup = document.querySelector('header [data-bine-lockup]');
                      const footerLockup = document.querySelector('footer [data-bine-lockup]');
                      const navTile = document.querySelector('header [data-bine-logo-tile]');
                      const footerTile = document.querySelector('footer [data-bine-logo-tile]');
                      const rNav = navLockup.getBoundingClientRect();
                      const rFoot = footerLockup.getBoundingClientRect();
                      const tNav = navTile.getBoundingClientRect();
                      const tFoot = footerTile.getBoundingClientRect();
                      return {
                        navX: rNav.x,
                        footerX: rFoot.x,
                        navTile: { x: tNav.x, y: tNav.y + window.scrollY, width: tNav.width, height: tNav.height },
                        footerTile: { x: tFoot.x, y: tFoot.y + window.scrollY, width: tFoot.width, height: tFoot.height },
                        navLockup: { x: rNav.x, y: rNav.y + window.scrollY, width: rNav.width, height: rNav.height },
                        footerLockup: { x: rFoot.x, y: rFoot.y + window.scrollY, width: rFoot.width, height: rFoot.height },
                      };
                    })()
                    """
                )
                x_coords[f"{theme}:{route}"] = (rects["navX"], rects["footerX"])
                print(
                    f"[{theme}] route={route:<10} nav_logo_x={rects['navX']}px  footer_logo_x={rects['footerX']}px"
                )

                if route == "/":
                    nav_shot = cdp.send(
                        "Page.captureScreenshot",
                        {
                            "format": "png",
                            "captureBeyondViewport": True,
                            "clip": {
                                "x": rects["navLockup"]["x"],
                                "y": rects["navLockup"]["y"],
                                "width": rects["navLockup"]["width"],
                                "height": rects["navLockup"]["height"],
                                "scale": 1,
                            },
                        },
                    )["data"]
                    foot_shot = cdp.send(
                        "Page.captureScreenshot",
                        {
                            "format": "png",
                            "captureBeyondViewport": True,
                            "clip": {
                                "x": rects["footerLockup"]["x"],
                                "y": rects["footerLockup"]["y"],
                                "width": rects["footerLockup"]["width"],
                                "height": rects["footerLockup"]["height"],
                                "scale": 1,
                            },
                        },
                    )["data"]
                    w1, h1, b1 = decode_png_rgba(base64.b64decode(nav_shot))
                    w2, h2, b2 = decode_png_rgba(base64.b64decode(foot_shot))
                    assert (w1, h1) == (w2, h2), f"Size mismatch: {(w1,h1)} vs {(w2,h2)}"
                    diff_sum = sum(abs(x - y) for x, y in zip(b1, b2))
                    mean_abs_diff = diff_sum / len(b1)
                    max_channel_diff = max(abs(x - y) for x, y in zip(b1, b2))
                    print(
                        f"[{theme}] PIXEL_DIFF (nav vs footer lockup, {w1}x{h1}, prefers-reduced-motion: reduce): "
                        f"mean_abs_channel_diff={mean_abs_diff:.4f}/255, max_channel_diff={max_channel_diff}/255"
                    )
                    if mean_abs_diff > 1.0:
                        print("ERROR: Nav and footer logo pixel diff too high!", file=sys.stderr)
                        return 1

        all_x = {val for pair in x_coords.values() for val in pair}
        print(f"UNIQUE_LOGO_X_COORDS_AT_1440={sorted(all_x)}")
        if len(all_x) != 1:
            print(f"ERROR: Logo x-coordinates drifted: {x_coords}", file=sys.stderr)
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
