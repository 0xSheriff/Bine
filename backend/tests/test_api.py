"""Tests for the BINE Atlas FastAPI endpoints and Step 2 data-quality filtering.

Uses an in-memory SQLite database seeded with all 488 rows from the recorded
live fixtures (442 Ondo + 46 bStocks).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bine.app import app
from bine.models import Base, TokenSample

FIXTURES = Path(__file__).parent / "fixtures"

TEST_ENGINE = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
TestSession = async_sessionmaker(TEST_ENGINE, class_=AsyncSession, expire_on_commit=False)


@pytest_asyncio.fixture(scope="module", autouse=True)
async def setup_db():
    """Create tables and seed all 488 tokens from live fixtures."""
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ondo_tokens = json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())["data"]
    bstock_tokens = json.loads((FIXTURES / "rwa_tokens_bstock_bsc.json").read_text())["data"]
    now = datetime.now(timezone.utc)

    rows = []
    for t in ondo_tokens + bstock_tokens:
        status = t.get("statusInfo") or {}
        tp = float(t["tokenPrice"]) if t.get("tokenPrice") else None
        rp = float(t["referencePrice"]) if t.get("referencePrice") else None
        gap = (tp - rp) / rp * 100 if tp and rp and rp != 0 else None
        rows.append(TokenSample(
            sampled_at=now,
            binance_chain_id="56",
            token_contract_address=t["tokenContractAddress"].lower(),
            platform_id=t["platformId"],
            underlying_ticker=t.get("underlyingTicker", ""),
            token_symbol=t.get("tokenSymbol", ""),
            ok=True,
            api_latency_ms=500,
            token_price=tp,
            reference_price=rp,
            token_to_share_ratio=float(t["tokenToShareRatio"]) if t.get("tokenToShareRatio") else None,
            price_gap_pct=gap,
            open_state=status.get("openState"),
            market_status=status.get("marketStatus"),
            reason_code=status.get("reasonCode"),
            volume_24h=float(t["volume24H"]) if t.get("volume24H") else None,
            market_cap=float(t["marketCap"]) if t.get("marketCap") else None,
        ))

    async with TestSession() as session:
        session.add_all(rows)
        await session.commit()

    yield
    async with TEST_ENGINE.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    import bine.app as app_module
    original = app_module.AsyncSessionLocal
    app_module.AsyncSessionLocal = TestSession

    async def _no_lifespan(app):
        yield

    app.router.lifespan_context = _no_lifespan

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

    app_module.AsyncSessionLocal = original


# ── Health ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["sample_count"] == 488
    assert data["newest_sample"].endswith("Z")


# ── Universe & Data Quality (Step 2) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_universe_returns_40_dual_issuer_tickers_and_flags_enlvon(client):
    r = await client.get("/api/universe")
    assert r.status_code == 200
    data = r.json()
    assert data["dual_issuer_ticker_count"] == 40
    assert len(data["pairs"]) == 40
    assert "NVDA" in data["dual_issuer_tickers"]

    unreliable_symbols = {t["token_symbol"]: t for t in data["unreliable_tokens"]}
    assert "ENLVon" in unreliable_symbols
    assert unreliable_symbols["ENLVon"]["quality_status"] == "unreliable"
    assert "SOXSon" in unreliable_symbols


@pytest.mark.asyncio
async def test_token_list_default_is_dual_issuer_universe(client):
    r = await client.get("/api/tokens")
    assert r.status_code == 200
    data = r.json()
    # 40 tickers * 2 issuers = 80 tokens
    assert data["count"] == 80
    assert data["dual_issuer_ticker_count"] == 40
    assert data["unreliable_count"] > 0
    symbols = {t["token_symbol"] for t in data["tokens"]}
    assert "ENLVon" not in symbols
    assert "NVDAon" in symbols
    assert "NVDAB" in symbols


@pytest.mark.asyncio
async def test_token_list_filter_platform(client):
    r = await client.get("/api/tokens?platform_id=ondo")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 40
    assert all(t["platform_id"] == "ondo" for t in data["tokens"])


@pytest.mark.asyncio
async def test_token_list_can_inspect_unreliable_when_requested(client):
    r = await client.get("/api/tokens?dual_only=false&exclude_unreliable=false&ticker=ENLV")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    enlv = data["tokens"][0]
    assert enlv["token_symbol"] == "ENLVon"
    assert enlv["quality_status"] == "unreliable"
    assert enlv["quality_reason"] is not None


# ── Token latest & history ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_token_latest_found(client):
    tokens = json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())["data"]
    addr = tokens[0]["tokenContractAddress"].lower()
    r = await client.get(f"/api/tokens/{addr}/latest")
    assert r.status_code == 200
    data = r.json()
    assert data["token_contract_address"] == addr
    assert data["ok"] is True


@pytest.mark.asyncio
async def test_token_latest_not_found(client):
    r = await client.get("/api/tokens/0x0000000000000000000000000000000000000000/latest")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_token_history(client):
    tokens = json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())["data"]
    addr = tokens[0]["tokenContractAddress"].lower()
    r = await client.get(f"/api/tokens/{addr}/history")
    assert r.status_code == 200
    data = r.json()
    assert data["sample_count"] >= 1
    assert "series" in data
    assert data["failure_count"] == 0


# ── Cross-issuer compare ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compare_ticker_found(client):
    r = await client.get("/api/compare/NVDA")
    assert r.status_code == 200
    data = r.json()
    assert data["ticker"] == "NVDA"
    assert data["issuer_count"] == 2
    assert data["cross_token_price_gap_pct"] is not None


@pytest.mark.asyncio
async def test_compare_ticker_not_found(client):
    r = await client.get("/api/compare/FAKEXYZ")
    assert r.status_code == 404


# ── Weekend gap ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_weekend_gap_excludes_enlvon_outlier(client):
    r = await client.get("/api/weekend-gap")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert data["unreliable_excluded_count"] >= 1
    symbols = {t["token_symbol"] for t in data["tokens"]}
    assert "ENLVon" not in symbols


@pytest.mark.asyncio
async def test_tickers_endpoint_returns_autocomplete_catalog(client):
    r = await client.get("/api/tickers")
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 400
    tickers = {item["ticker"]: item for item in data["tickers"]}
    assert "NVDA" in tickers
    assert tickers["NVDA"]["dual"] is True
    assert "AAPL" in tickers
    assert tickers["AAPL"]["dual"] is False


