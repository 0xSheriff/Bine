#!/usr/bin/env python3
"""Phase 0 deliverable: make one authenticated call to the RWA Data API.

Lists supported platforms and tokens, prints the real response shape, and
saves the raw response to tests/fixtures/ for use in later tests.

Usage:
    # From the backend/ directory, with .env populated:
    python -m scripts.first_call

    # Or from the repo root:
    cd backend && python -m scripts.first_call
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

import httpx

# Add parent dir to path so `bine` is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from bine.client import BinanceClient
from bine.errors import BinanceAPIError

# Load .env from repo root or backend/
for env_path in [Path(__file__).parent.parent.parent / ".env", Path(__file__).parent.parent / ".env"]:
    if env_path.exists():
        load_dotenv(env_path)
        break

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures"


def save_fixture(name: str, data: dict) -> None:
    """Save a raw API response as a test fixture."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    logger.info("Saved fixture to %s", path)


async def main() -> None:
    api_key = os.environ.get("BINANCE_API_KEY", "")
    secret_key = os.environ.get("BINANCE_SECRET_KEY", "")

    if not api_key or not secret_key:
        print(
            "\n❌  Missing credentials.\n\n"
            "1. Copy .env.example to .env:\n"
            "     cp .env.example .env\n\n"
            "2. Fill in your BINANCE_API_KEY and BINANCE_SECRET_KEY\n"
            "   (from https://web3.binance.com/en/dev-portal/project)\n\n"
            "3. Run again:\n"
            "     cd backend && python -m scripts.first_call\n"
        )
        sys.exit(1)

    print(f"\n🔑  API key loaded: {api_key[:8]}...{api_key[-4:]}")
    print("   Secret key loaded: ****\n")

    async with BinanceClient(api_key=api_key, secret_key=secret_key) as client:

        # --- Call 1: Get RWA Platforms ---
        print("━" * 60)
        print("📡  GET /api/v1/dex/market/rwa/platforms")
        print("━" * 60)
        t0 = time.monotonic()
        try:
            resp = await client.get("/api/v1/dex/market/rwa/platforms")
            latency = round((time.monotonic() - t0) * 1000)
            print(json.dumps(resp, indent=2))
            print(f"\n⏱  Latency: {latency} ms")
            save_fixture("rwa_platforms", resp)
        except BinanceAPIError as e:
            latency = round((time.monotonic() - t0) * 1000)
            print(f"\n❌  API error: [{e.code}] {e.msg}  ({latency} ms)")
            if e.code == 40102:
                print(
                    "\n💡  Signature error — the #1 cause per the docs.\n"
                    "    Check that BINANCE_SECRET_KEY is correct and that\n"
                    "    the /build prefix is included in the signed path."
                )
            return
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            latency = round((time.monotonic() - t0) * 1000)
            print(f"\n❌  Network error: {e}  ({latency} ms)")
            print(
                "\n💡  Cannot reach web3.binance.com. Try:\n"
                "    1. Check your DNS: nslookup web3.binance.com\n"
                "    2. If DNS fails, switch to Google DNS (8.8.8.8) in\n"
                "       System Preferences → Network → Wi-Fi → Details → DNS\n"
                "    3. Or add to /etc/hosts:\n"
                "       echo '108.156.221.129 web3.binance.com' | sudo tee -a /etc/hosts"
            )
            return

        # --- Call 2: Get RWA Tokens (BSC, ondo, first page) ---
        print("\n" + "━" * 60)
        print("📡  GET /api/v1/dex/market/rwa/tokens?binanceChainId=56&platformId=ondo")
        print("━" * 60)
        t0 = time.monotonic()
        try:
            resp = await client.get(
                "/api/v1/dex/market/rwa/tokens",
                params={"binanceChainId": "56", "platformId": "ondo"},
            )
            latency = round((time.monotonic() - t0) * 1000)
            tokens = resp.get("data", [])
            print(f"\n📊  Received {len(tokens)} tokens")
            if tokens:
                # Print first token as example of the response shape
                print("\nFirst token (response shape):")
                print(json.dumps(tokens[0], indent=2))
                # Show if referencePrice differs from tokenPrice
                tp = tokens[0].get("tokenPrice")
                rp = tokens[0].get("referencePrice")
                if tp and rp:
                    try:
                        gap_pct = abs(float(tp) - float(rp)) / float(rp) * 100
                        print(f"\n📐  tokenPrice={tp}, referencePrice={rp}, gap={gap_pct:.4f}%")
                    except (ValueError, ZeroDivisionError):
                        pass
            print(f"\n⏱  Latency: {latency} ms")
            save_fixture("rwa_tokens_ondo_bsc", resp)
        except BinanceAPIError as e:
            latency = round((time.monotonic() - t0) * 1000)
            print(f"\n❌  API error: [{e.code}] {e.msg}  ({latency} ms)")

        # --- Call 3: Also try bstock platform ---
        print("\n" + "━" * 60)
        print("📡  GET /api/v1/dex/market/rwa/tokens?binanceChainId=56&platformId=bstock")
        print("━" * 60)
        t0 = time.monotonic()
        try:
            resp = await client.get(
                "/api/v1/dex/market/rwa/tokens",
                params={"binanceChainId": "56", "platformId": "bstock"},
            )
            latency = round((time.monotonic() - t0) * 1000)
            tokens = resp.get("data", [])
            print(f"\n📊  Received {len(tokens)} bstock tokens")
            if tokens:
                print("\nFirst bstock token:")
                print(json.dumps(tokens[0], indent=2))
            print(f"\n⏱  Latency: {latency} ms")
            save_fixture("rwa_tokens_bstock_bsc", resp)
        except BinanceAPIError as e:
            latency = round((time.monotonic() - t0) * 1000)
            print(f"\n❌  API error: [{e.code}] {e.msg}  ({latency} ms)")

        # --- Call 4: Search for NVDA to see cross-platform coverage ---
        print("\n" + "━" * 60)
        print("📡  GET /api/v1/dex/market/rwa/search?keyword=NVDA")
        print("━" * 60)
        t0 = time.monotonic()
        try:
            resp = await client.get(
                "/api/v1/dex/market/rwa/search",
                params={"keyword": "NVDA"},
            )
            latency = round((time.monotonic() - t0) * 1000)
            results = resp.get("data", [])
            print(f"\n🔍  Found {len(results)} results for NVDA")
            if results:
                print(json.dumps(results[0], indent=2))
            print(f"\n⏱  Latency: {latency} ms")
            save_fixture("rwa_search_nvda", resp)
        except BinanceAPIError as e:
            latency = round((time.monotonic() - t0) * 1000)
            print(f"\n❌  API error: [{e.code}] {e.msg}  ({latency} ms)")

    print("\n✅  Phase 0 complete. Fixtures saved to tests/fixtures/")
    print("    Show me this output before continuing to Phase 1.\n")


if __name__ == "__main__":
    asyncio.run(main())
