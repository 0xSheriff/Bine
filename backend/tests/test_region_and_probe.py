"""Unit and integration tests for RegionBlocked (40304) error classification,
permission error handling (40104), normal refusals, and the hosted POST /api/probe endpoint.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

import bine.cli as cli_mod
from bine.app import _QUOTE_CACHE, app, reset_rate_limits
from bine.client import BASE_URL, BinanceClient
from bine.database import AsyncSessionLocal, init_db
from bine.errors import AuthError, RegionBlocked, raise_for_code
from bine.models import DecisionLog
from bine.quote_engine import clear_rwa_catalog_cache

FIXTURES = Path(__file__).parent / "fixtures"


def test_region_blocked_error_class_and_raise_for_code():
    """Binance code 40304 raises RegionBlocked with exact error message."""
    with pytest.raises(RegionBlocked) as exc_info:
        raise_for_code(40304, "Service not available due to compliance restriction", status_code=200)
    assert exc_info.value.code == 40304
    assert exc_info.value.msg == "Binance rejected this server's region (40304)"


@pytest.mark.asyncio
async def test_region_blocked_client_and_api_endpoints_return_503(
    monkeypatch: pytest.MonkeyPatch,
):
    """Direct client raises RegionBlocked and API endpoints return HTTP 503."""
    clear_rwa_catalog_cache()
    _QUOTE_CACHE.clear()
    reset_rate_limits()

    ondo_payload = json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())

    with respx.mock(assert_all_called=False) as respx_mock:
        # Client raises RegionBlocked on 40304 from quote
        respx_mock.get(f"{BASE_URL}/api/v1/dex/market/rwa/tokens").mock(
            return_value=Response(200, json=ondo_payload)
        )
        respx_mock.get(f"{BASE_URL}/api/v1/dex/aggregator/quote").mock(
            return_value=Response(
                200,
                json={
                    "code": 40304,
                    "msg": "Service not available due to compliance restriction",
                    "data": None,
                },
            )
        )
        respx_mock.get(f"{BASE_URL}/api/v1/dex/market/token/top-liquidity").mock(
            return_value=Response(200, json={"code": 0, "msg": "success", "data": {"totalLiquidity": "1000000"}})
        )

        async with BinanceClient(api_key="k", secret_key="s") as bc:
            with pytest.raises(RegionBlocked) as exc_info:
                await bc.get("/api/v1/dex/aggregator/quote")
            assert exc_info.value.code == 40304
            assert exc_info.value.msg == "Binance rejected this server's region (40304)"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. /api/quote returns 503 with exact text
            r_quote = await ac.get("/api/quote?ticker=NVDA&amount_usd=5.50")
            assert r_quote.status_code == 503
            data = r_quote.json()
            assert "verdict" not in data
            assert data["detail"] == "Binance rejected this server's region (40304)"

            # 2. /api/execute returns 503 with exact text
            r_exec = await ac.post("/api/execute", json={"ticker": "NVDA", "amount_usd": 5.50, "execute_live": False})
            assert r_exec.status_code == 503
            data_exec = r_exec.json()
            assert data_exec["detail"] == "Binance rejected this server's region (40304)"


def test_cli_handles_region_blocked_and_prints_one_line(capsys, monkeypatch):
    """CLI prints one line and returns 1 on RegionBlocked."""
    # Test _cmd_check
    with patch("bine.cli.run_check", side_effect=RegionBlocked()):
        args = argparse.Namespace(ticker="NVDA", amount_usd=5.50, json=False, verbose=False, baw=False)
        rc = cli_mod._cmd_check(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert captured.out.strip() == "Binance rejected this server's region (40304)"

    # Test _cmd_buy
    with patch("bine.cli.run_buy_step", side_effect=RegionBlocked()):
        args = argparse.Namespace(ticker="NVDA", amount_usd=5.50, yes=False)
        rc = cli_mod._cmd_buy(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert captured.out.strip() == "Binance rejected this server's region (40304)"

    # Test _cmd_probe
    with patch("bine.cli.run_probe", side_effect=RegionBlocked()):
        args = argparse.Namespace(tickers="NVDA", amount_usd=5.50, scheduled=False)
        rc = cli_mod._cmd_probe(args)
        assert rc == 1
        captured = capsys.readouterr()
        assert captured.out.strip() == "Binance rejected this server's region (40304)"


@pytest.mark.asyncio
async def test_run_probe_aborts_and_records_nothing_on_errors(monkeypatch):
    """run_probe must abort and record zero rows on AuthError or RegionBlocked, but record on normal refusal."""
    await init_db()

    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        res_before = await session.execute(select(DecisionLog))
        count_before = len(res_before.scalars().all())

    # Case 1: RegionBlocked aborts immediately
    with patch("bine.cli.run_check", side_effect=RegionBlocked()):
        with pytest.raises(RegionBlocked):
            await cli_mod.run_probe(tickers=["NVDA"], amount_usd=5.50)

    # Case 2: AuthError (40104) aborts immediately
    with patch("bine.cli.run_check", side_effect=AuthError(40104, "API key lacks trade permission")):
        with pytest.raises(AuthError):
            await cli_mod.run_probe(tickers=["NVDA"], amount_usd=5.50)

    # Verify 0 additional rows in DecisionLog for these tests
    async with AsyncSessionLocal() as session:
        res_after = await session.execute(select(DecisionLog))
        count_after = len(res_after.scalars().all())
        assert count_after == count_before

    # Case 3: Normal refusal records to DecisionLog
    mock_refusal = {
        "verdict": "REFUSE",
        "ticker": "AAPL",
        "amount_usd": 2.0,
        "refusal": {"code": "below_issuer_minimum", "reason": "Order amount $2.00 is below minimum $5.00"},
        "recommended": None,
        "token": None,
        "alternatives": [],
    }
    with patch("bine.cli.run_check", return_value=mock_refusal):
        results = await cli_mod.run_probe(tickers=["AAPL"], amount_usd=2.0)
        assert len(results) == 1
        assert results[0]["verdict"] == "REFUSE"

        async with AsyncSessionLocal() as session:
            res_refusal = await session.execute(
                select(DecisionLog).where(DecisionLog.ticker == "AAPL", DecisionLog.action == "probe")
            )
            saved = res_refusal.scalars().all()
            assert len(saved) >= 1
            assert saved[-1].refusal_code == "below_issuer_minimum"


@pytest.mark.asyncio
async def test_hosted_probe_endpoint_auth_disabled_and_success(monkeypatch):
    """POST /api/probe auth checks, rotating ticker execution, and store persistence."""
    clear_rwa_catalog_cache()
    _QUOTE_CACHE.clear()
    reset_rate_limits()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Disabled with 404 if BINE_PROBE_SECRET is unset
        monkeypatch.delenv("BINE_PROBE_SECRET", raising=False)
        r = await ac.post("/api/probe")
        assert r.status_code == 404

        # 2. 401 if secret set but header missing or wrong
        monkeypatch.setenv("BINE_PROBE_SECRET", "super-secret-probe-key")
        r_no_auth = await ac.post("/api/probe")
        assert r_no_auth.status_code == 401

        r_bad_auth = await ac.post("/api/probe", headers={"Authorization": "Bearer wrong-key"})
        assert r_bad_auth.status_code == 401

        # 3. Successful probe with mock Upstash / KV store
        store_calls = []
        store_data = {}

        def _mock_store(request: httpx.Request) -> Response:
            store_calls.append(request)
            if request.method == "GET":
                return Response(200, json={"result": store_data.get("probe:recent_24h")})
            if request.method == "POST":
                body = json.loads(request.content)
                store_data[body[1]] = body[2]
                return Response(200, json={"result": "OK"})
            return Response(400)

        monkeypatch.setenv("UPSTASH_REDIS_REST_URL", "https://mock-redis.upstash.io")
        monkeypatch.setenv("UPSTASH_REDIS_REST_TOKEN", "mock-token")

        ondo_payload = json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())
        bstock_payload = json.loads((FIXTURES / "rwa_tokens_bstock_bsc.json").read_text())
        quote_fixture = json.loads((FIXTURES / "quote_nvda_ondo_25usd.json").read_text())
        liq_fixture = json.loads((FIXTURES / "liquidity_nvda_ondo.json").read_text())

        def _rwa_router(request):
            pid = request.url.params.get("platformId", "")
            return Response(200, json=ondo_payload if pid == "ondo" else bstock_payload)

        with respx.mock(assert_all_called=False) as respx_mock:
            respx_mock.get(f"{BASE_URL}/api/v1/dex/market/rwa/tokens").mock(side_effect=_rwa_router)
            respx_mock.get(f"{BASE_URL}/api/v1/dex/aggregator/quote").mock(return_value=Response(200, json=quote_fixture))
            respx_mock.get(f"{BASE_URL}/api/v1/dex/market/token/top-liquidity").mock(return_value=Response(200, json=liq_fixture))
            respx_mock.route(host="mock-redis.upstash.io").mock(side_effect=_mock_store)

            # Probing 2 tickers explicitly for test speed
            r_ok = await ac.post(
                "/api/probe?tickers=NVDA,AAPL",
                headers={"Authorization": "Bearer super-secret-probe-key"},
            )
            assert r_ok.status_code == 200
            resp_data = r_ok.json()
            assert resp_data["status"] == "ok"
            assert resp_data["probed_count"] == 2
            assert resp_data["tickers"] == ["NVDA", "AAPL"]

            # Verify store SET payload
            post_calls = [c for c in store_calls if c.method == "POST"]
            assert len(post_calls) == 1
            body = json.loads(post_calls[0].content)
            assert body[0] == "SET"
            assert body[1] == "probe:recent_24h"
            assert body[3] == "EX"
            assert body[4] == "86400"

            saved_doc = json.loads(body[2])
            assert saved_doc["count"] == 2
            assert len(saved_doc["checks"]) == 2
            assert saved_doc["checks"][0]["ticker"] == "NVDA"

            # 4. /api/recent reading from store
            r_recent = await ac.get("/api/recent")
            assert r_recent.status_code == 200
            recent_doc = r_recent.json()
            assert recent_doc["count"] == 2
            assert len(recent_doc["checks"]) == 2


@pytest.mark.asyncio
async def test_hosted_probe_endpoint_aborts_on_region_blocked_and_auth_error(monkeypatch):
    """POST /api/probe aborts immediately with 503 and writes nothing to store on RegionBlocked or AuthError."""
    clear_rwa_catalog_cache()
    _QUOTE_CACHE.clear()
    reset_rate_limits()

    monkeypatch.setenv("BINE_PROBE_SECRET", "super-secret-probe-key")
    monkeypatch.setenv("KV_REST_API_URL", "https://mock-kv.vercel-storage.com")
    monkeypatch.setenv("KV_REST_API_TOKEN", "mock-kv-token")

    store_posts = []

    def _mock_store(request: httpx.Request) -> Response:
        if request.method == "GET":
            return Response(200, json={"result": None})
        if request.method == "POST":
            store_posts.append(request)
            return Response(200, json={"result": "OK"})
        return Response(400)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        with respx.mock(assert_all_called=False) as respx_mock:
            respx_mock.route(host="mock-kv.vercel-storage.com").mock(side_effect=_mock_store)

            # Case 1: 40304 RegionBlocked from RWA tokens
            respx_mock.get(f"{BASE_URL}/api/v1/dex/market/rwa/tokens").mock(
                return_value=Response(
                    200,
                    json={"code": 40304, "msg": "Service not available due to compliance restriction", "data": None},
                )
            )

            r = await ac.post("/api/probe", headers={"Authorization": "Bearer super-secret-probe-key"})
            assert r.status_code == 503
            assert r.json()["detail"] == "Binance rejected this server's region (40304)"
            assert len(store_posts) == 0

            # Case 2: 40104 AuthError from RWA tokens
            clear_rwa_catalog_cache()
            _QUOTE_CACHE.clear()
            respx_mock.get(f"{BASE_URL}/api/v1/dex/market/rwa/tokens").mock(
                return_value=Response(
                    403,
                    json={"code": 40104, "msg": "API key lacks required permission", "data": None},
                )
            )

            r2 = await ac.post("/api/probe", headers={"Authorization": "Bearer super-secret-probe-key"})
            assert r2.status_code == 503
            assert "Binance API permission missing" in r2.json()["detail"]
            assert len(store_posts) == 0
