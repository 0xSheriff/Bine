"""BINE Pre-Trade Guard FastAPI application.

Core Endpoints:
  GET  /api/quote                 : Frozen Phase 1 pre-trade guard contract (`schema_version: "1"`)
  POST /api/execute               : Transaction API `/simulate` dry-run + gated Agentic Wallet execution
  GET  /api/decisions             : Audit trail from `decision_log`
  GET  /api/decisions/{id}        : Full receipt for a single decision
  GET  /api/tickers               : Autocomplete list of tokenized stock tickers on BSC (`ondo` + `bstock`)
  GET  /api/health                : Liveness + configuration summary
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import time as _time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Literal

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bine.client import BinanceClient, maybe_enable_dev_dns_fallback
from bine.config import get_settings
from bine.database import AsyncSessionLocal, init_db
from bine.errors import AuthError
from bine.execution import execute_trade_pipeline
from bine.models import DecisionLog, TokenSample
from bine.quality import (
    DUAL_ISSUER_TICKERS,
    assess_sample_row,
    find_dual_issuer_tickers,
)
from bine.quote_engine import (
    DEFAULT_QUOTE_WALLET,
    SCHEMA_VERSION,
    build_verdict,
    fetch_live_issuer_quote_and_liquidity,
    fetch_live_rwa_catalog,
    parse_rwa_token_item,
)

logger = logging.getLogger(__name__)


# ── Frozen Phase 1 Pydantic Models (shown in FastAPI /docs) ────────────────────

class QuoteTokenModel(BaseModel):
    symbol: str = Field(..., examples=["NVDAB"])
    address: str = Field(..., examples=["0x9ce827e7d3eb11b35ab2b03e6f631d219d2b57fc"])
    issuer: Literal["ondo", "bstock"] = Field(..., examples=["bstock"])


class QuoteRefusalModel(BaseModel):
    code: Literal[
        "amount_over_cap",
        "below_issuer_minimum",
        "market_closed",
        "reference_stale",
        "depth_thin",
        "slippage_too_high",
        "quality_unreliable",
        "unknown_ticker",
    ]
    message: str = Field(
        ...,
        examples=["Ondo would fill you about 41% above the market price ($1,087.43 vs $772.52 reference). Not buying."],
    )


class QuoteAlternativeModel(BaseModel):
    symbol: str = Field(..., examples=["NVDAon"])
    issuer: Literal["ondo", "bstock"] = Field(..., examples=["ondo"])
    eligible: bool = Field(..., examples=[True])
    note: str = Field(
        ...,
        examples=["Either works (within 5 bps). Also checked NVDAon on Ondo: $0.02 per share more."],
    )


class QuoteMarketModel(BaseModel):
    status: str = Field(..., examples=["overnight"])
    open: bool = Field(..., examples=[True])


class QuoteResponseModel(BaseModel):
    schema_version: str = Field(SCHEMA_VERSION, examples=["1"])
    ticker: str = Field(..., examples=["NVDA"])
    amount_usd: float = Field(..., examples=[5.0])
    quoted_at: str = Field(..., examples=["2026-10-02T00:30:00Z"])
    verdict: Literal["BUY", "REFUSE"] = Field(..., examples=["BUY"])
    token: QuoteTokenModel | None = None
    shares: float | None = Field(None, examples=[0.021614])
    all_in_price_per_share: float | None = Field(None, examples=[231.33])
    reference_price_per_share: float | None = Field(None, examples=[231.21])
    spread_pct: float | None = Field(None, examples=[0.05])
    refusal: QuoteRefusalModel | None = None
    alternative: QuoteAlternativeModel | None = None
    market: QuoteMarketModel


# ── Rate Limiting (Phase 4 Public Deploy Safety) ───────────────────────────────

_RATE_BUCKETS: dict[str, deque[float]] = defaultdict(deque)
QUOTE_RATE_LIMIT_PER_MIN = 20
EXECUTE_RATE_LIMIT_PER_MIN = 20


def reset_rate_limits() -> None:
    """Clear in-memory rate-limit buckets (used in tests)."""
    _RATE_BUCKETS.clear()


def _extract_client_ip(request: Request) -> str:
    peer_ip = (request.client.host if request.client else None) or "local"
    if peer_ip == "local":
        return "local"
    try:
        settings = get_settings()
        trusted = {ip.strip() for ip in settings.trusted_proxies.split(",") if ip.strip()}
    except Exception:
        trusted = {"127.0.0.1", "::1"}

    if peer_ip in trusted:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first_hop = xff.split(",")[0].strip()
            if first_hop:
                return first_hop
        x_real_ip = request.headers.get("x-real-ip")
        if x_real_ip:
            rip = x_real_ip.strip()
            if rip:
                return rip
    return peer_ip


def _check_rate_limit(request: Request, bucket_prefix: str, max_per_minute: int) -> None:
    client_ip = _extract_client_ip(request)
    key = f"{bucket_prefix}:{client_ip}"
    now = _time.monotonic()
    window = _RATE_BUCKETS[key]
    while window and (now - window[0]) > 60.0:
        window.popleft()
    if len(window) >= max_per_minute:
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({max_per_minute} requests per minute). Please wait briefly.",
        )
    window.append(now)


def _is_public_demo_or_vercel(settings: Settings) -> bool:
    return bool(
        os.environ.get("VERCEL")
        or settings.bine_public_demo
        or os.environ.get("BINE_PUBLIC_DEMO", "").strip().lower() in ("1", "true", "yes")
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    try:
        settings = get_settings()
        maybe_enable_dev_dns_fallback(settings.dev_dns_fallback)
    except Exception:
        pass
    yield


def _configured_cors_origins() -> list[str]:
    try:
        raw = get_settings().bine_cors_origins
        origins = [o.strip() for o in raw.split(",") if o.strip()]
        if origins:
            return origins
    except Exception:
        pass
    return [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]


app = FastAPI(
    title="Bine: Pre-Trade Guard for Tokenized Stocks on BSC",
    description=(
        "Before a person or an agent buys a tokenized stock on BNB Smart Chain (`chainId=56`), "
        "Bine answers: is it safe right now, what will I really get, and if not, why not."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_configured_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Bine-Admin-Token"],
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def _iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_to_dict(row: TokenSample, dual_tickers: set[str] | None = None) -> dict[str, Any]:
    qc = assess_sample_row(row)
    dual_set = dual_tickers if dual_tickers is not None else set(DUAL_ISSUER_TICKERS)
    return {
        "id": row.id,
        "sampled_at": _iso_utc(row.sampled_at),
        "platform_id": row.platform_id,
        "token_contract_address": row.token_contract_address,
        "underlying_ticker": row.underlying_ticker,
        "token_symbol": row.token_symbol,
        "ok": row.ok,
        "error_msg": row.error_msg,
        "api_latency_ms": row.api_latency_ms,
        "token_price": row.token_price,
        "reference_price": row.reference_price,
        "token_to_share_ratio": row.token_to_share_ratio,
        "price_gap_pct": row.price_gap_pct,
        "open_state": row.open_state,
        "market_status": row.market_status,
        "reason_code": row.reason_code,
        "volume_24h": row.volume_24h,
        "market_cap": row.market_cap,
        "quality_status": qc.status,
        "quality_reason": qc.reason,
        "is_dual_issuer": row.underlying_ticker.upper() in dual_set,
    }


async def _latest_rows_from_db(session: AsyncSession) -> list[TokenSample]:
    """Fallback query for latest TokenSample rows when running offline DB-seeded tests."""
    sub = (
        select(
            TokenSample.token_contract_address,
            func.max(TokenSample.sampled_at).label("max_at"),
        )
        .where(TokenSample.ok == True)  # noqa: E712
        .group_by(TokenSample.token_contract_address)
        .subquery()
    )
    q = (
        select(TokenSample)
        .join(
            sub,
            (TokenSample.token_contract_address == sub.c.token_contract_address)
            & (TokenSample.sampled_at == sub.c.max_at),
        )
        .where(TokenSample.ok == True)  # noqa: E712
        .order_by(TokenSample.underlying_ticker.asc(), TokenSample.platform_id.asc())
    )
    result = await session.execute(q)
    return list(result.scalars().all())


async def _resolve_ticker_samples(
    client: BinanceClient,
    ticker_upper: str,
) -> list[TokenSample]:
    """Fetch live `/rwa/tokens` (60s in-memory cache) and return matching issuer tokens.

    Falls back to `TokenSample` rows in `AsyncSessionLocal` if `/rwa/tokens` is not
    mocked in offline DB-seeded unit tests.
    """
    try:
        _, catalog = await fetch_live_rwa_catalog(client)
        matches = [
            r for r in catalog
            if r.underlying_ticker.upper() == ticker_upper or r.token_symbol.upper() == ticker_upper
        ]
        if matches:
            return matches
        # If catalog succeeded and has tokens, but ticker is not in catalog -> unknown_ticker
        if catalog:
            return []
    except AuthError:
        raise
    except Exception as exc:
        logger.debug("Live /rwa/tokens fetch fell back to DB (%s: %s)", type(exc).__name__, exc)

    try:
        async with AsyncSessionLocal() as session:
            sub = (
                select(
                    TokenSample.platform_id,
                    func.max(TokenSample.sampled_at).label("max_at"),
                )
                .where(
                    (func.upper(TokenSample.underlying_ticker) == ticker_upper)
                    | (func.upper(TokenSample.token_symbol) == ticker_upper),
                    TokenSample.ok == True,  # noqa: E712
                )
                .group_by(TokenSample.platform_id)
                .subquery()
            )
            q = (
                select(TokenSample)
                .join(
                    sub,
                    (TokenSample.platform_id == sub.c.platform_id)
                    & (TokenSample.sampled_at == sub.c.max_at),
                )
                .where(
                    (func.upper(TokenSample.underlying_ticker) == ticker_upper)
                    | (func.upper(TokenSample.token_symbol) == ticker_upper),
                    TokenSample.ok == True,  # noqa: E712
                )
                .order_by(TokenSample.platform_id.asc())
            )
            result = await session.execute(q)
            return list(result.scalars().all())
    except Exception as exc:
        logger.warning("DB fallback in _resolve_ticker_samples failed: %s", exc)
        return []


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health() -> dict[str, Any]:
    settings = get_settings()
    count, oldest, newest = 0, None, None
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(TokenSample.id), func.min(TokenSample.sampled_at), func.max(TokenSample.sampled_at))
            )
            count, oldest, newest = result.one()
    except Exception as exc:
        logger.warning("health DB query failed: %s", exc)
    effective_live = False if _is_public_demo_or_vercel(settings) else bool(settings.bine_live_mode)
    has_keys = bool(settings.binance_api_key.strip() and settings.binance_secret_key.strip())
    return {
        "status": "ok",
        "schema_version": SCHEMA_VERSION,
        "live_mode": effective_live,
        "binance_credentials_present": has_keys,
        "max_trade_usd": settings.bine_max_trade_usd,
        "daily_cap_usd": settings.bine_daily_cap_usd,
        "sample_count": count or 0,
        "oldest_sample": _iso_utc(oldest),
        "newest_sample": _iso_utc(newest),
        "now": _iso_utc(datetime.now(timezone.utc)),
    }


@app.get("/api/tickers")
async def list_tickers() -> dict[str, Any]:
    """Return all tokenized stock tickers on BSC (`ondo` + `bstock`) for autocomplete."""
    settings = get_settings()
    maybe_enable_dev_dns_fallback(settings.dev_dns_fallback)
    rows: list[TokenSample] = []
    try:
        async with BinanceClient(
            api_key=settings.binance_api_key,
            secret_key=settings.binance_secret_key,
        ) as client:
            _, rows = await fetch_live_rwa_catalog(client)
    except Exception:
        pass

    if not rows:
        # Offline fallback: load recorded fixtures if present
        fixtures_dir = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
        now = datetime.now(timezone.utc)
        for fname in ("rwa_tokens_ondo_bsc.json", "rwa_tokens_bstock_bsc.json"):
            fpath = fixtures_dir / fname
            if fpath.exists():
                data = json.loads(fpath.read_text()).get("data") or []
                rows.extend(parse_rwa_token_item(item, now) for item in data if item.get("tokenContractAddress"))

    by_ticker: dict[str, list[str]] = {}
    for r in rows:
        tkr = r.underlying_ticker.upper()
        if tkr:
            by_ticker.setdefault(tkr, [])
            if r.platform_id not in by_ticker[tkr]:
                by_ticker[tkr].append(r.platform_id)

    items = [
        {
            "ticker": tkr,
            "issuers": sorted(issuers),
            "dual": len(issuers) >= 2,
        }
        for tkr, issuers in sorted(by_ticker.items())
    ]

    # Discover live catalog examples for /refusals (share-ratio trap & session-unsupported/closed)
    ratio_candidates = [
        r for r in rows
        if (r.token_price or 0) >= 1.0 and r.token_to_share_ratio is not None and r.underlying_ticker.upper() != "ENLV"
    ]
    ratio_candidates.sort(key=lambda r: abs((r.token_to_share_ratio or 1.0) - 1.0), reverse=True)
    share_ratio_row = ratio_candidates[0] if ratio_candidates else None

    single_issuer_closed = [
        r for r in rows
        if len(by_ticker.get(r.underlying_ticker.upper(), [])) == 1
        and assess_sample_row(r).reliable
        and (r.open_state is not True or (r.reason_code is not None and r.reason_code != "TRADING") or r.market_status in ("paused", "closed"))
    ]
    single_issuer_closed.sort(
        key=lambda r: (
            0 if r.reason_code == "UNSUPPORTED" else (1 if r.underlying_ticker.upper() == "ICHR" else 2),
            r.underlying_ticker.upper(),
        )
    )
    closed_row = single_issuer_closed[0] if single_issuer_closed else None

    return {
        "count": len(items),
        "tickers": items,
        "catalog_examples": {
            "share_ratio": {
                "ticker": share_ratio_row.underlying_ticker.upper() if share_ratio_row else "KLAC",
                "symbol": share_ratio_row.token_symbol if share_ratio_row else "KLACon",
                "token_to_share_ratio": round(share_ratio_row.token_to_share_ratio or 10.0261, 4) if share_ratio_row else 10.0261,
            },
            "session_closed": {
                "ticker": closed_row.underlying_ticker.upper() if closed_row else "ICHR",
                "symbol": closed_row.token_symbol if closed_row else "ICHRon",
                "market_status": (closed_row.market_status if closed_row else "closed") or "closed",
                "reason_code": (closed_row.reason_code if closed_row else "UNSUPPORTED") or "UNSUPPORTED",
            },
        },
    }


_QUOTE_CACHE: dict[tuple[str, float, bool, int], tuple[float, dict[str, Any]]] = {}
_QUOTE_CACHE_TTL_SEC = 15.0


@app.get(
    "/api/quote",
    response_model=QuoteResponseModel,
    summary="Pre-trade guard check for a tokenized stock on BSC (Frozen Schema v1)",
)
async def quote_stock(
    request: Request,
    ticker: str = Query(..., description="Underlying stock ticker (e.g. NVDA, AAPL, SPY, TSLA)"),
    amount_usd: float = Query(5.5, description="USD amount to spend (USDT on BSC; default 5.50)"),
    details: bool = Query(
        False,
        include_in_schema=False,
        description="When true, includes technical issuer breakdown under 'details' for the UI disclosure.",
    ),
) -> Any:
    """Evaluate whether buying `amount_usd` of `ticker` on BSC is safe right now.

    Fetches `/api/v1/dex/market/rwa/tokens` live (60s in-memory cache), queries
    `/api/v1/dex/aggregator/quote` and `/api/v1/dex/market/token/top-liquidity` for
    each available issuer on BSC, checks all 8 deterministic refusal rules, applies
    the 5 bps tie band (`Either works`), and returns the frozen `schema_version: "1"`
    response.
    """
    _check_rate_limit(request, "quote", QUOTE_RATE_LIMIT_PER_MIN)
    ticker_upper = ticker.strip().upper()
    cache_key = (ticker_upper, round(float(amount_usd), 4), bool(details), id(AsyncSessionLocal))
    cached = _QUOTE_CACHE.get(cache_key)
    if cached and (_time.monotonic() - cached[0]) < _QUOTE_CACHE_TTL_SEC:
        return JSONResponse(content=cached[1])

    settings = get_settings()
    maybe_enable_dev_dns_fallback(settings.dev_dns_fallback)
    wallet = settings.bine_wallet_address or DEFAULT_QUOTE_WALLET
    effective_live = False if os.environ.get("VERCEL") else bool(settings.bine_live_mode)

    try:
        async with BinanceClient(
            api_key=settings.binance_api_key,
            secret_key=settings.binance_secret_key,
        ) as client:
            rows = await _resolve_ticker_samples(client, ticker_upper)
            if rows:
                evaluations = list(
                    await asyncio.gather(
                        *(
                            fetch_live_issuer_quote_and_liquidity(
                                client=client,
                                sample=row,
                                amount_usd=amount_usd,
                                wallet_address=wallet,
                            )
                            for row in rows
                        )
                    )
                )
            else:
                evaluations = []
    except AuthError as exc:
        raise HTTPException(
            status_code=503,
            detail="Binance API keys missing or rejected",
        ) from exc

    verdict_resp = build_verdict(
        ticker=ticker_upper,
        amount_usd=amount_usd,
        evaluations=evaluations,
        max_live_trade_usd=settings.bine_max_trade_usd,
        live_mode=effective_live,
    )
    payload = verdict_resp.to_dict(include_details=details)
    _QUOTE_CACHE[cache_key] = (_time.monotonic(), payload)
    return JSONResponse(content=payload)


class ExecuteRequest(BaseModel):
    ticker: str = Field(..., description="Underlying stock ticker, e.g. NVDA")
    amount_usd: float = Field(5.5, description="USD amount to swap (USDT on BSC; default 5.50)")
    execute_live: bool = Field(
        False,
        description="False = dry-run simulation only. True = dry-run first, then execute via Agentic Wallet if BINE_LIVE_MODE=true, BINE_ADMIN_TOKEN matches, and within cap.",
    )
    admin_token: str | None = Field(
        None,
        description="Required when execute_live=True (can also be sent via X-Bine-Admin-Token header).",
    )


@app.post("/api/execute")
async def execute_stock_trade(
    req: ExecuteRequest,
    request: Request,
    x_bine_admin_token: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run the pre-trade guard, simulate on-chain via `/api/v1/dex/pre-transaction/simulate`,
    and (only if `execute_live=True`, `BINE_ADMIN_TOKEN` matches, `BINE_LIVE_MODE=true`, and
    within `BINE_MAX_TRADE_USD`) execute via Binance Agentic Wallet (`baw`).
    """
    _check_rate_limit(request, "execute", EXECUTE_RATE_LIMIT_PER_MIN)
    settings = get_settings()
    maybe_enable_dev_dns_fallback(settings.dev_dns_fallback)
    demo_locked = _is_public_demo_or_vercel(settings)
    effective_live = False if demo_locked else bool(settings.bine_live_mode)

    supplied_token = x_bine_admin_token if x_bine_admin_token is not None else req.admin_token
    if req.execute_live and not demo_locked:
        if not settings.bine_admin_token or not supplied_token or not hmac.compare_digest(
            supplied_token, settings.bine_admin_token
        ):
            raise HTTPException(
                status_code=403,
                detail="execute_live=true requires a valid BINE_ADMIN_TOKEN (via X-Bine-Admin-Token header or admin_token field).",
            )

    ticker_upper = req.ticker.strip().upper()
    wallet = settings.bine_wallet_address or DEFAULT_QUOTE_WALLET

    async with BinanceClient(
        api_key=settings.binance_api_key,
        secret_key=settings.binance_secret_key,
    ) as client:
        rows = await _resolve_ticker_samples(client, ticker_upper)
        if rows:
            evaluations = list(
                await asyncio.gather(
                    *(
                        fetch_live_issuer_quote_and_liquidity(
                            client=client,
                            sample=row,
                            amount_usd=req.amount_usd,
                            wallet_address=wallet,
                        )
                        for row in rows
                    )
                )
            )
        else:
            evaluations = []

        verdict_resp = build_verdict(
            ticker=ticker_upper,
            amount_usd=req.amount_usd,
            evaluations=evaluations,
            max_live_trade_usd=settings.bine_max_trade_usd,
            live_mode=effective_live,
        )

        async with AsyncSessionLocal() as session:
            return await execute_trade_pipeline(
                session=session,
                client=client,
                verdict_resp=verdict_resp,
                evaluations=evaluations,
                settings=settings,
                execute_live=req.execute_live,
                admin_token=supplied_token,
                require_admin_token=req.execute_live and not demo_locked,
            )


@app.get("/api/decisions")
async def list_decisions(
    limit: int = Query(5, ge=1, le=200),
    live_only: bool = Query(False, description="When true, return only executed live trades with tx_hash"),
) -> dict[str, Any]:
    """Return recent decisions, refusals, dry-run simulations, and live swaps from `decision_log`."""
    try:
        async with AsyncSessionLocal() as session:
            q = select(DecisionLog)
            if live_only:
                q = q.where(DecisionLog.tx_hash.is_not(None), DecisionLog.tx_hash != "")
            q = q.order_by(DecisionLog.id.desc()).limit(limit)
            result = await session.execute(q)
            rows = list(result.scalars().all())
    except Exception as exc:
        logger.warning("list_decisions DB query failed (returning empty list): %s", exc)
        return {"count": 0, "decisions": []}

    items = []
    for r in rows:
        items.append(
            {
                "id": r.id,
                "created_at": _iso_utc(r.created_at),
                "ticker": r.ticker,
                "amount_usd": r.amount_usd,
                "action": r.action,
                "verdict": r.verdict,
                "recommended_platform": r.recommended_platform,
                "recommended_symbol": r.recommended_symbol,
                "recommended_contract_address": r.recommended_contract_address,
                "refusal_code": r.refusal_code,
                "reason": r.reason,
                "expected_shares": r.expected_shares,
                "all_in_price_per_share_usd": r.all_in_price_per_share_usd,
                "all_in_vs_reference_pct": r.all_in_vs_reference_pct,
                "effective_slippage_pct": r.effective_slippage_pct,
                "simulation_ran": r.simulation_ran,
                "simulation_status": r.simulation_status,
                "simulation_fail_reason": r.simulation_fail_reason,
                "approval_simulation_status": r.approval_simulation_status,
                "spender_address": r.spender_address,
                "estimated_gas_limit": r.estimated_gas_limit,
                "live_mode": r.live_mode,
                "execution_status": r.execution_status,
                "tx_hash": r.tx_hash,
                "bsctrace_url": r.bsctrace_url,
                "execution_detail": r.execution_detail,
            }
        )
    return {"count": len(items), "decisions": items}


@app.get("/api/recent")
async def recent_checks(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    hours: int = Query(24, ge=1, le=168),
) -> dict[str, Any]:
    """Return live and scheduled market checks from the last 24 hours."""
    _check_rate_limit(request, "recent", QUOTE_RATE_LIMIT_PER_MIN)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    try:
        async with AsyncSessionLocal() as session:
            q = (
                select(DecisionLog)
                .where(DecisionLog.created_at >= cutoff)
                .order_by(DecisionLog.id.desc())
                .limit(limit)
            )
            result = await session.execute(q)
            rows = list(result.scalars().all())
    except Exception as exc:
        logger.warning("recent_checks DB query failed (returning empty list): %s", exc)
        return {"count": 0, "hours": hours, "checks": []}

    checks = []
    for r in rows:
        checks.append(
            {
                "id": r.id,
                "created_at": _iso_utc(r.created_at),
                "ticker": r.ticker,
                "amount_usd": r.amount_usd,
                "action": r.action,
                "verdict": r.verdict,
                "recommended_platform": r.recommended_platform,
                "recommended_symbol": r.recommended_symbol,
                "recommended_contract_address": r.recommended_contract_address,
                "refusal_code": r.refusal_code,
                "reason": r.reason,
                "expected_shares": r.expected_shares,
                "all_in_price_per_share_usd": r.all_in_price_per_share_usd,
                "all_in_vs_reference_pct": r.all_in_vs_reference_pct,
                "effective_slippage_pct": r.effective_slippage_pct,
                "tx_hash": r.tx_hash,
            }
        )
    return {"count": len(checks), "hours": hours, "checks": checks}


@app.get("/api/decisions/{decision_id}")
async def get_decision_detail(decision_id: int) -> dict[str, Any]:
    """Return the full stored `ExecuteTradeResponse` payload for a single `decision_log` row."""
    row = None
    try:
        async with AsyncSessionLocal() as session:
            q = select(DecisionLog).where(DecisionLog.id == decision_id)
            result = await session.execute(q)
            row = result.scalar_one_or_none()
    except Exception as exc:
        logger.warning("get_decision_detail DB query failed: %s", exc)

    if row is None:
        raise HTTPException(status_code=404, detail=f"Decision #{decision_id} not found")

    try:
        payload = json.loads(row.payload_json) if row.payload_json else {}
    except Exception:
        payload = {}

    quote_obj = payload.get("quote") or {}
    return {
        "decision_id": row.id,
        "created_at": _iso_utc(row.created_at),
        "ticker": row.ticker,
        "amount_usd": row.amount_usd,
        "action": row.action,
        "verdict": row.verdict,
        "recommended_platform": row.recommended_platform,
        "recommended_symbol": row.recommended_symbol,
        "recommended_contract_address": row.recommended_contract_address,
        "refusal_code": row.refusal_code,
        "reason": row.reason,
        "why_others_lost": quote_obj.get("why_others_lost") or [],
        "simulation": payload.get("simulation") or {},
        "execution": payload.get("execution") or {},
        "quote": quote_obj,
    }


# ── Legacy / Data Inspection Endpoints (kept for backwards-compatible tests) ───

@app.get("/api/universe", include_in_schema=False)
async def universe() -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        all_rows = await _latest_rows_from_db(session)
    dual_tickers = find_dual_issuer_tickers(all_rows)
    by_ticker: dict[str, dict[str, TokenSample]] = {}
    unreliable_tokens: list[dict[str, Any]] = []
    for r in all_rows:
        qc = assess_sample_row(r)
        if not qc.reliable:
            unreliable_tokens.append(_row_to_dict(r, dual_tickers))
            continue
        tkr = r.underlying_ticker.upper()
        if tkr in dual_tickers:
            by_ticker.setdefault(tkr, {})[r.platform_id] = r
    pairs = []
    for tkr in sorted(by_ticker.keys()):
        pair = by_ticker[tkr]
        ondo_row = pair.get("ondo")
        bstock_row = pair.get("bstock")
        cross_ref_gap_pct = None
        if ondo_row and bstock_row and ondo_row.reference_price and bstock_row.reference_price:
            cross_ref_gap_pct = round(
                (ondo_row.reference_price - bstock_row.reference_price) / bstock_row.reference_price * 100,
                4,
            )
        pairs.append({
            "ticker": tkr,
            "cross_ref_gap_pct": cross_ref_gap_pct,
            "ondo": _row_to_dict(ondo_row, dual_tickers) if ondo_row else None,
            "bstock": _row_to_dict(bstock_row, dual_tickers) if bstock_row else None,
        })
    return {
        "dual_issuer_ticker_count": len(dual_tickers),
        "dual_issuer_tickers": sorted(dual_tickers),
        "total_sampled_tokens": len(all_rows),
        "unreliable_count": len(unreliable_tokens),
        "unreliable_tokens": unreliable_tokens,
        "pairs": pairs,
    }


@app.get("/api/tokens", include_in_schema=False)
async def token_list(
    platform_id: str | None = Query(None),
    ticker: str | None = Query(None),
    dual_only: bool = Query(True),
    exclude_unreliable: bool = Query(True),
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        all_rows = await _latest_rows_from_db(session)
    dual_tickers = find_dual_issuer_tickers(all_rows)
    unreliable_count = sum(1 for r in all_rows if not assess_sample_row(r).reliable)
    filtered: list[TokenSample] = []
    for r in all_rows:
        if platform_id and r.platform_id != platform_id:
            continue
        if ticker and r.underlying_ticker.upper() != ticker.upper():
            continue
        if exclude_unreliable and not assess_sample_row(r).reliable:
            continue
        if dual_only and r.underlying_ticker.upper() not in dual_tickers:
            continue
        filtered.append(r)
    return {
        "count": len(filtered),
        "total_sampled_count": len(all_rows),
        "unreliable_count": unreliable_count,
        "dual_issuer_ticker_count": len(dual_tickers),
        "tokens": [_row_to_dict(r, dual_tickers) for r in filtered],
    }


@app.get("/api/tokens/{address}/latest", include_in_schema=False)
async def token_latest(address: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        q = (
            select(TokenSample)
            .where(
                TokenSample.token_contract_address == address.lower(),
                TokenSample.ok == True,  # noqa: E712
            )
            .order_by(TokenSample.sampled_at.desc())
            .limit(1)
        )
        result = await session.execute(q)
        row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="No data for this token yet")
    return _row_to_dict(row)


@app.get("/api/tokens/{address}/history", include_in_schema=False)
async def token_history(
    address: str,
    limit: int = Query(288, ge=1, le=2000),
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        q = (
            select(TokenSample)
            .where(TokenSample.token_contract_address == address.lower())
            .order_by(TokenSample.sampled_at.desc())
            .limit(limit)
        )
        result = await session.execute(q)
        rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No data for this token yet")
    success = [r for r in rows if r.ok]
    return {
        "address": address.lower(),
        "sample_count": len(rows),
        "success_count": len(success),
        "failure_count": len(rows) - len(success),
        "oldest": _iso_utc(rows[-1].sampled_at),
        "newest": _iso_utc(rows[0].sampled_at),
        "series": [_row_to_dict(r) for r in rows],
    }


@app.get("/api/compare/{ticker}", include_in_schema=False)
async def compare_issuers(ticker: str) -> dict[str, Any]:
    ticker = ticker.upper()
    async with AsyncSessionLocal() as session:
        sub = (
            select(
                TokenSample.platform_id,
                func.max(TokenSample.sampled_at).label("max_at"),
            )
            .where(TokenSample.underlying_ticker == ticker, TokenSample.ok == True)  # noqa: E712
            .group_by(TokenSample.platform_id)
            .subquery()
        )
        q = (
            select(TokenSample)
            .join(
                sub,
                (TokenSample.platform_id == sub.c.platform_id)
                & (TokenSample.sampled_at == sub.c.max_at),
            )
            .where(TokenSample.underlying_ticker == ticker, TokenSample.ok == True)  # noqa: E712
        )
        result = await session.execute(q)
        rows = result.scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail=f"No data for {ticker}")
    issuers = [_row_to_dict(r) for r in rows]
    cross_gap = None
    if len(rows) == 2:
        ref_prices = [r.reference_price for r in rows if r.reference_price is not None and r.reference_price > 0]
        if len(ref_prices) == 2:
            cross_gap = (ref_prices[0] - ref_prices[1]) / ref_prices[1] * 100
    return {
        "ticker": ticker,
        "issuer_count": len(issuers),
        "cross_token_price_gap_pct": round(cross_gap, 4) if cross_gap is not None else None,
        "issuers": issuers,
    }


@app.get("/api/weekend-gap", include_in_schema=False)
async def weekend_gap(
    limit: int = Query(50, ge=1, le=200),
    exclude_unreliable: bool = Query(True),
) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        sub = (
            select(
                TokenSample.token_contract_address,
                func.max(TokenSample.sampled_at).label("max_at"),
            )
            .where(
                TokenSample.ok == True,  # noqa: E712
                TokenSample.open_state == False,  # noqa: E712
            )
            .group_by(TokenSample.token_contract_address)
            .subquery()
        )
        q = (
            select(TokenSample)
            .join(
                sub,
                (TokenSample.token_contract_address == sub.c.token_contract_address)
                & (TokenSample.sampled_at == sub.c.max_at),
            )
            .where(
                TokenSample.ok == True,  # noqa: E712
                TokenSample.open_state == False,  # noqa: E712
            )
            .order_by(TokenSample.sampled_at.desc(), TokenSample.underlying_ticker.asc())
        )
        result = await session.execute(q)
        all_closed = list(result.scalars().all())
    dual_tickers = set(DUAL_ISSUER_TICKERS)
    unreliable_excluded = sum(1 for r in all_closed if exclude_unreliable and not assess_sample_row(r).reliable)
    clean_rows = [r for r in all_closed if not (exclude_unreliable and not assess_sample_row(r).reliable)]
    return {
        "count": len(clean_rows[:limit]),
        "unreliable_excluded_count": unreliable_excluded,
        "tokens": [_row_to_dict(r, dual_tickers) for r in clean_rows[:limit]],
    }


_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> Any:
    """Serve built frontend static assets and SPA index.html fallback for deep links."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    if _FRONTEND_DIST.is_dir():
        candidate = (_FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and str(candidate).startswith(str(_FRONTEND_DIST.resolve())):
            return FileResponse(candidate)
        index_html = _FRONTEND_DIST / "index.html"
        if index_html.is_file():
            return FileResponse(index_html)
    raise HTTPException(status_code=404, detail="Frontend build not found")

