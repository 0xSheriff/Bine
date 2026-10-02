"""Unit tests for the BINE Atlas sampler using recorded fixtures."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bine.client import BinanceClient
from bine.models import Base, TokenSample
from tools.collect_evidence import sample_platform

FIXTURES = Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@respx.mock
@pytest.mark.asyncio
async def test_sample_platform_success_records_exact_fields(db_session):
    """Sampler stores exact fields from recorded bstock fixture, keeping null fields null."""
    payload = json.loads((FIXTURES / "rwa_tokens_bstock_bsc.json").read_text())
    respx.get("https://web3.binance.com/build/api/v1/dex/market/rwa/tokens").mock(
        return_value=httpx.Response(200, json=payload)
    )

    now = datetime.now(timezone.utc)
    async with BinanceClient(api_key="test-key", secret_key="test-secret") as client:
        await sample_platform(client, "bstock", now, db_session)
        await db_session.commit()

    result = await db_session.execute(select(TokenSample))
    rows = result.scalars().all()
    assert len(rows) == len(payload["data"])
    first = rows[0]
    assert first.ok is True
    assert first.platform_id == "bstock"
    assert first.market_status is None  # bstock returns null marketStatus
    assert first.open_state is True
    assert first.token_price is not None


@respx.mock
@pytest.mark.asyncio
async def test_sample_platform_failure_records_failure_row(db_session):
    """When API returns an error, sampler writes an explicit failure row (ok=False) instead of skipping."""
    respx.get("https://web3.binance.com/build/api/v1/dex/market/rwa/tokens").mock(
        return_value=httpx.Response(200, json={"code": 40001, "msg": "Upstream error"})
    )

    now = datetime.now(timezone.utc)
    async with BinanceClient(api_key="test-key", secret_key="test-secret", max_retries=1) as client:
        await sample_platform(client, "ondo", now, db_session)
        await db_session.commit()

    result = await db_session.execute(select(TokenSample))
    rows = result.scalars().all()
    assert len(rows) == 1
    fail = rows[0]
    assert fail.ok is False
    assert fail.platform_id == "ondo"
    assert fail.token_price is None
    assert fail.reference_price is None
    assert "40001" in (fail.error_msg or "")
