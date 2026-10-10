"""Typed error hierarchy for Binance Web3 API responses.

Every non-zero `code` from the API becomes a specific exception so callers can
handle rate-limits, auth failures, and business errors differently.
"""

from __future__ import annotations


class BinanceAPIError(Exception):
    """Base for all Binance Web3 API errors."""

    def __init__(self, code: int, msg: str, *, status_code: int = 200):
        self.code = code
        self.msg = msg
        self.status_code = status_code
        super().__init__(f"[{code}] {msg}")


class AuthError(BinanceAPIError):
    """40101 / 40104 / HTTP 302 / HTTP 401 / HTTP 403 / non-JSON: Binance API keys missing, rejected, or permission missing."""

    def __init__(self, code: int = 40101, msg: str = "Binance API keys missing or rejected", *, status_code: int = 401):
        if (code in (40104, 403) or status_code == 403) and msg == "Binance API keys missing or rejected":
            msg = "Binance API permission missing"
        super().__init__(code, msg, status_code=status_code)


class SignatureError(AuthError):
    """40102: HMAC signature mismatch. Almost always a signing bug."""
    pass


class TimestampError(BinanceAPIError):
    """40103: Clock drift or replay."""
    pass


class RateLimitError(BinanceAPIError):
    """42900: Rate limit exceeded. Retry after `retry_after` seconds."""

    def __init__(self, code: int, msg: str, *, retry_after: float = 1.0):
        super().__init__(code, msg, status_code=429)
        self.retry_after = retry_after


class ChainNotSupportedError(BinanceAPIError):
    """40411: Chain ID not in whitelist."""
    pass


class MarketHoursError(BinanceAPIError):
    """40367/40369: Ondo/BStock unavailable outside market hours."""
    pass


class RegionBlocked(BinanceAPIError):
    """40304: Service not available due to compliance restriction."""

    def __init__(
        self,
        code: int = 40304,
        msg: str = "Binance rejected this server's region (40304)",
        *,
        status_code: int = 200,
    ):
        msg = "Binance rejected this server's region (40304)"
        super().__init__(code, msg, status_code=status_code)


# Map API error codes to exception classes
_CODE_MAP: dict[int, type[BinanceAPIError]] = {
    40101: AuthError,
    40102: SignatureError,
    40103: TimestampError,
    40104: AuthError,
    403: AuthError,
    40304: RegionBlocked,
    42900: RateLimitError,
    40411: ChainNotSupportedError,
    40367: MarketHoursError,
    40369: MarketHoursError,
}


def raise_for_code(code: int, msg: str, *, status_code: int = 200) -> None:
    """Raise the appropriate typed exception for a non-zero business code."""
    if code == 0:
        return
    exc_class = _CODE_MAP.get(code, BinanceAPIError)
    raise exc_class(code, msg, status_code=status_code)

