"""Binance Web3 API HTTP client.

Handles:
- HMAC-SHA256 request signing (the #1 failure mode per the docs)
- GET and POST with automatic signing
- Retries with exponential backoff on 429 and 5xx
- Timeout configuration
- Rate-limit header parsing
- Latency measurement (ms) on every call
- Typed error raising via errors.py
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import anyio
import httpx

from bine.errors import BinanceAPIError, RateLimitError, raise_for_code

logger = logging.getLogger(__name__)

_orig_connect_tcp = anyio.connect_tcp
_dns_cache: dict[str, tuple[str, float]] = {}
_dns_patch_installed = False


async def _patched_connect_tcp(remote_host: str, remote_port: int, **kwargs: Any) -> Any:
    """Optional dev-only fallback: resolve web3.binance.com via 8.8.8.8 when local router DNS fails."""
    if remote_host == "web3.binance.com":
        cached = _dns_cache.get(remote_host)
        now = time.monotonic()
        if cached and now - cached[1] < 300:
            remote_host = cached[0]
        else:
            try:
                out = subprocess.check_output(
                    ["nslookup", remote_host, "8.8.8.8"], text=True, timeout=4
                )
                ips = [
                    ip
                    for ip in re.findall(r"Address:\s+(\d+\.\d+\.\d+\.\d+)", out)
                    if ip != "8.8.8.8"
                ]
                if ips:
                    _dns_cache[remote_host] = (ips[0], now)
                    remote_host = ips[0]
            except Exception:
                pass
    return await _orig_connect_tcp(remote_host, remote_port, **kwargs)


def maybe_enable_dev_dns_fallback(enabled: bool | None = None) -> None:
    """Install the 8.8.8.8 DNS fallback ONLY if DEV_DNS_FALLBACK=true.

    Off in production so standard system DNS is used without subprocess calls.
    """
    global _dns_patch_installed
    if _dns_patch_installed:
        return
    if enabled is None:
        enabled = os.environ.get("DEV_DNS_FALLBACK", "").lower() in ("1", "true", "yes")
    if enabled:
        anyio.connect_tcp = _patched_connect_tcp  # type: ignore[assignment]
        _dns_patch_installed = True
        logger.info("DEV_DNS_FALLBACK enabled: resolving web3.binance.com via 8.8.8.8")


BASE_URL = "https://web3.binance.com/build"
BUILD_PREFIX = "/build"

# Retry config
MAX_RETRIES = 3
INITIAL_BACKOFF_S = 1.0
TIMEOUT_S = 15.0


def make_timestamp() -> str:
    """ISO 8601 with millisecond precision, as the API requires.

    Example: 2026-05-11T10:08:57.715Z
    """
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def sign(
    secret_key: str,
    timestamp: str,
    method: str,
    request_path: str,
    body: str = "",
) -> str:
    """Compute HMAC-SHA256 signature per Binance Web3 API auth spec.

    The pre-hash string is: timestamp + METHOD + requestPath + body
    where requestPath MUST include the /build prefix and any query string,
    exactly as sent on the wire.

    Returns Base64-encoded signature.
    """
    pre_hash = timestamp + method.upper() + request_path + body
    sig = hmac.new(
        secret_key.encode("utf-8"),
        pre_hash.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(sig).decode("utf-8")


class BinanceClient:
    """Authenticated HTTP client for Binance Web3 API.

    Usage:
        client = BinanceClient(api_key="...", secret_key="...")
        data = await client.get("/api/v1/dex/market/rwa/platforms")
    """

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        *,
        timeout: float = TIMEOUT_S,
        max_retries: int = MAX_RETRIES,
    ):
        self._api_key = api_key
        self._secret_key = secret_key
        self._max_retries = max_retries
        self._http = httpx.AsyncClient(
            base_url=BASE_URL,
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> BinanceClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def _sign_headers(
        self, method: str, path_with_query: str, body: str = ""
    ) -> dict[str, str]:
        """Build the three required auth headers."""
        timestamp = make_timestamp()
        # requestPath in the signature MUST include /build
        signed_path = (
            path_with_query
            if path_with_query.startswith(BUILD_PREFIX)
            else BUILD_PREFIX + path_with_query
        )
        signature = sign(self._secret_key, timestamp, method, signed_path, body)
        return {
            "X-OC-APIKEY": self._api_key,
            "X-OC-TIMESTAMP": timestamp,
            "X-OC-SIGN": signature,
        }

    async def get(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Signed GET request. `path` should NOT include /build."""
        query_str = ""
        if params:
            # urlencode with quote_via to match wire encoding
            query_str = "?" + urlencode(params, quote_via=lambda s, *a, **k: s)
        full_path = path + query_str
        return await self._request_with_retry("GET", full_path)

    async def post(
        self, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Signed POST request."""
        import json as _json

        body_str = _json.dumps(body, separators=(",", ":")) if body else ""
        return await self._request_with_retry("POST", path, content=body_str)

    async def _request_with_retry(
        self,
        method: str,
        path: str,
        *,
        content: str | None = None,
    ) -> dict[str, Any]:
        """Execute request with exponential backoff on retryable errors.

        Re-signs headers on every attempt so a slow timeout on attempt 1
        never causes a [40103] Timestamp outside recv_window on attempt 2.
        """
        last_exc: Exception | None = None
        backoff = INITIAL_BACKOFF_S

        for attempt in range(1, self._max_retries + 1):
            headers = self._sign_headers(method, path, content or "")
            t0 = time.monotonic()
            try:
                if method == "GET":
                    resp = await self._http.get(path, headers=headers)
                else:
                    resp = await self._http.post(
                        path, headers=headers, content=content
                    )

                latency_ms = round((time.monotonic() - t0) * 1000)

                # Log every call with latency
                logger.info(
                    "%s %s → HTTP %d (%d ms)",
                    method,
                    path.split("?")[0],  # don't log query params (may have tokens)
                    resp.status_code,
                    latency_ms,
                )

                # HTTP 429 — rate limit at gateway level
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", backoff))
                    logger.warning(
                        "Rate limited (attempt %d/%d), retry after %.1fs",
                        attempt,
                        self._max_retries,
                        retry_after,
                    )
                    if attempt < self._max_retries:
                        await self._sleep(retry_after)
                        backoff *= 2
                        continue
                    raise RateLimitError(
                        42900, "Rate limit exceeded", retry_after=retry_after
                    )

                # 5xx — server error, retry
                if resp.status_code >= 500:
                    logger.warning(
                        "Server error %d (attempt %d/%d)",
                        resp.status_code,
                        attempt,
                        self._max_retries,
                    )
                    if attempt < self._max_retries:
                        await self._sleep(backoff)
                        backoff *= 2
                        continue

                # Parse response — all Binance responses return HTTP 200
                # with business status in the `code` field
                data = resp.json()
                code = data.get("code", -1)
                msg = data.get("msg", "unknown error")

                # Business-level rate limit (code 42900 inside HTTP 200)
                if code == 42900:
                    retry_after = float(resp.headers.get("Retry-After", backoff))
                    if attempt < self._max_retries:
                        await self._sleep(retry_after)
                        backoff *= 2
                        continue
                    raise RateLimitError(code, msg, retry_after=retry_after)

                # Raise typed errors for non-zero codes
                raise_for_code(code, msg, status_code=resp.status_code)

                return data

            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                latency_ms = round((time.monotonic() - t0) * 1000)
                logger.warning(
                    "%s %s → %s (%d ms, attempt %d/%d)",
                    method,
                    path.split("?")[0],
                    type(exc).__name__,
                    latency_ms,
                    attempt,
                    self._max_retries,
                )
                last_exc = exc
                if attempt < self._max_retries:
                    await self._sleep(backoff)
                    backoff *= 2
                    continue

            except BinanceAPIError:
                raise  # don't retry auth/business errors

        raise last_exc or RuntimeError("Request failed after retries")

    @staticmethod
    async def _sleep(seconds: float) -> None:
        """Async sleep for backoff. Extracted for easy mocking in tests."""
        import asyncio

        await asyncio.sleep(seconds)
