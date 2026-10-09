"""Typed configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """All config comes from env vars. Never hardcode secrets."""

    binance_api_key: str = ""
    binance_secret_key: str = ""

    # Local Bine backend URL used by the CLI (`bine`) and MCP server (`bine-mcp`)
    bine_api_url: str = "http://localhost:8000"

    # Agent execution: off by default, tiny caps ($6 max so Ondo's $5.50 default works)
    bine_live_mode: bool = False
    bine_max_trade_usd: float = 6.00
    bine_daily_cap_usd: float = 10.00
    bine_admin_token: str = ""

    # Public demo lock: forces live mode off and execute endpoint to dry-run only
    bine_public_demo: bool = False

    # Trusted reverse proxy IPs/CIDRs for client IP rate limiting (comma-separated)
    trusted_proxies: str = "127.0.0.1,::1"

    # CORS origins (comma-separated)
    bine_cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    # Local dev DNS fallback (off in production by default)
    dev_dns_fallback: bool = False

    # Optional: wallet address for quote/simulation when Agentic Wallet is configured
    bine_wallet_address: str = ""

    # BSC mainnet: the only chain this project uses
    bsc_chain_id: str = "56"

    @model_validator(mode="after")
    def _sanitize_and_lock(self) -> "Settings":
        if isinstance(self.binance_api_key, str):
            self.binance_api_key = self.binance_api_key.strip()
        if isinstance(self.binance_secret_key, str):
            self.binance_secret_key = self.binance_secret_key.strip()
        if (
            os.environ.get("VERCEL")
            or self.bine_public_demo
            or os.environ.get("BINE_PUBLIC_DEMO", "").strip().lower() in ("1", "true", "yes")
        ):
            self.bine_live_mode = False
        return self

    model_config = {
        "env_file": (str(_REPO_ROOT_ENV), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

