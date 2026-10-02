"""Research utility: collect RWA token snapshots into SQLite/Postgres for offline evidence analysis.

Not required for the live Bine API or UI. Run manually when collecting research snapshots:
    PYTHONPATH=backend python tools/collect_evidence.py
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from bine.client import BinanceClient, maybe_enable_dev_dns_fallback
from bine.config import Settings
from bine.database import AsyncSessionLocal, init_db
from bine.errors import BinanceAPIError
from bine.models import TokenSample

logger = logging.getLogger(__name__)

BSC_CHAIN_ID = "56"
PLATFORMS = ["ondo", "bstock"]


def _safe_float(val: Any) -> float | None:
    """Parse a numeric string to float; return None if absent or unparseable."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _compute_gap_pct(token_price: float | None, reference_price: float | None) -> float | None:
    """(tokenPrice - referencePrice) / referencePrice * 100. None if either is missing."""
    if token_price is None or reference_price is None or reference_price == 0:
        return None
    return (token_price - reference_price) / reference_price * 100


def _row_from_token(token: dict, sampled_at: datetime, latency_ms: int) -> TokenSample:
    """Build a successful TokenSample row from a /rwa/tokens item."""
    status = token.get("statusInfo") or {}
    tp = _safe_float(token.get("tokenPrice"))
    rp = _safe_float(token.get("referencePrice"))
    return TokenSample(
        sampled_at=sampled_at,
        binance_chain_id=token.get("binanceChainId", BSC_CHAIN_ID),
        token_contract_address=token["tokenContractAddress"].lower(),
        platform_id=token["platformId"],
        underlying_ticker=token.get("underlyingTicker", ""),
        token_symbol=token.get("tokenSymbol", ""),
        ok=True,
        api_latency_ms=latency_ms,
        token_price=tp,
        reference_price=rp,
        token_to_share_ratio=_safe_float(token.get("tokenToShareRatio")),
        price_gap_pct=_compute_gap_pct(tp, rp),
        open_state=status.get("openState"),
        market_status=status.get("marketStatus"),  # may be None for bstock
        reason_code=status.get("reasonCode"),
        reason_msg=status.get("reasonMsg"),
        next_open_time_ms=status.get("nextOpenTime"),
        volume_24h=_safe_float(token.get("volume24H")),
        market_cap=_safe_float(token.get("marketCap")),
    )


def _failure_row(
    platform_id: str,
    token_contract_address: str,
    underlying_ticker: str,
    token_symbol: str,
    sampled_at: datetime,
    error_msg: str,
    latency_ms: int | None = None,
) -> TokenSample:
    """Build a failure TokenSample row. All data fields are NULL."""
    return TokenSample(
        sampled_at=sampled_at,
        binance_chain_id=BSC_CHAIN_ID,
        token_contract_address=token_contract_address,
        platform_id=platform_id,
        underlying_ticker=underlying_ticker,
        token_symbol=token_symbol,
        ok=False,
        error_msg=error_msg,
        api_latency_ms=latency_ms,
    )


async def sample_platform(
    client: BinanceClient,
    platform_id: str,
    sampled_at: datetime,
    session: AsyncSession,
) -> None:
    """Poll /rwa/tokens for one platform and write rows to the DB."""
    t0 = time.monotonic()
    try:
        resp = await client.get(
            "/api/v1/dex/market/rwa/tokens",
            params={"binanceChainId": BSC_CHAIN_ID, "platformId": platform_id},
        )
        latency_ms = round((time.monotonic() - t0) * 1000)
        tokens = resp.get("data") or []
        rows = [_row_from_token(t, sampled_at, latency_ms) for t in tokens]
        session.add_all(rows)
        logger.info(
            "Sampled %d tokens from %s (latency=%d ms)", len(rows), platform_id, latency_ms
        )
    except (BinanceAPIError, Exception) as exc:
        latency_ms = round((time.monotonic() - t0) * 1000)
        error_msg = f"{type(exc).__name__}: {exc}"
        logger.warning("Sample failed for platform %s: %s", platform_id, error_msg)
        row = _failure_row(
            platform_id=platform_id,
            token_contract_address="__platform__",
            underlying_ticker="__all__",
            token_symbol="__all__",
            sampled_at=sampled_at,
            error_msg=error_msg,
            latency_ms=latency_ms,
        )
        session.add(row)


async def run_sample_tick(settings: Settings) -> None:
    """One full sample tick: poll all platforms and write to DB."""
    maybe_enable_dev_dns_fallback(settings.dev_dns_fallback)
    sampled_at = datetime.now(timezone.utc)
    logger.info("Sample tick starting at %s", sampled_at.isoformat())

    async with BinanceClient(
        api_key=settings.binance_api_key,
        secret_key=settings.binance_secret_key,
    ) as client:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                for platform in PLATFORMS:
                    await sample_platform(client, platform, sampled_at, session)

    logger.info("Sample tick complete")


def create_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Create and configure the APScheduler for the sampler."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_sample_tick,
        trigger="interval",
        minutes=settings.bine_sample_interval_minutes,
        args=[settings],
        id="sample_tick",
        replace_existing=True,
        next_run_time=datetime.now(timezone.utc),
    )
    return scheduler


async def run_sampler_standalone() -> None:
    """Entry point for running the evidence collector as a standalone process."""
    from bine.config import get_settings

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = get_settings()
    await init_db()
    scheduler = create_scheduler(settings)
    scheduler.start()
    logger.info(
        "Evidence collector started. Interval: %d min. Press Ctrl+C to stop.",
        settings.bine_sample_interval_minutes,
    )
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, asyncio.CancelledError):
        scheduler.shutdown(wait=False)
        logger.info("Evidence collector stopped.")


if __name__ == "__main__":
    asyncio.run(run_sampler_standalone())
