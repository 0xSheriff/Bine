"""Typed configuration from environment variables."""

from __future__ import annotations

from pathlib import Path
from pydantic_settings import BaseSettings

_REPO_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """All config comes from env vars. Never hardcode secrets."""

    binance_api_key: str = ""
    binance_secret_key: str = ""

    # Agent execution — off by default, tiny caps ($6 max so Ondo's $5 minimum works)
    bine_live_mode: bool = False
    bine_max_trade_usd: float = 6.00
    bine_daily_cap_usd: float = 10.00
    bine_admin_token: str = ""

    # CORS origins (comma-separated)
    bine_cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8000,http://127.0.0.1:8000"
    )

    # Optional evidence collector interval (minutes)
    bine_sample_interval_minutes: int = 5

    # Local dev DNS fallback (off in production by default)
    dev_dns_fallback: bool = False

    # Optional: wallet address for quote/simulation when Agentic Wallet is configured
    bine_wallet_address: str = ""

    # BSC mainnet — the only chain this project uses
    bsc_chain_id: str = "56"

    model_config = {
        "env_file": (str(_REPO_ROOT_ENV), ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
