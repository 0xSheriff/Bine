"""Unit and integration tests for Step 5: Safe Execution Engine (`POST /api/execute` & `decision_log`).

Uses recorded live responses from:
  - `/api/v1/dex/aggregator/quote`
  - `/api/v1/dex/market/token/top-liquidity`
  - `/api/v1/dex/aggregator/swap`
  - `/api/v1/dex/aggregator/approve-transaction`
  - `/api/v1/dex/pre-transaction/simulate`
Verifies:
  1. Dry-run (`execute_live=False`) runs Transaction API simulation first, detects `0` USDT allowance,
     simulates the ERC-20 `approve()` transaction (`REQUIRES_APPROVAL`), returns `DRY_RUN_OK`, and logs to `decision_log`.
  2. Refused quotes (`verdict="REFUSE"`) skip Transaction API simulation, return `REFUSED`, and log to `decision_log`.
  3. Live execution over the per-trade hard cap (`$3.00`) is blocked (`LIVE_BLOCKED_CAP`) and logged to `decision_log`.
  4. Live execution with `BINE_LIVE_MODE=false` is blocked (`LIVE_DISABLED`) and logged to `decision_log`.
  5. Live execution with `BINE_LIVE_MODE=true` within cap invokes Binance Agentic Wallet (`baw`),
     saves `tx_hash` and `bsctrace_url` (`https://bsctrace.com/tx/...`) in `decision_log`, and enforces the daily cap (`BINE_DAILY_CAP_USD`).
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import bine.app as app_mod
import bine.database as db_mod
import bine.execution as exec_mod
from bine.config import Settings
from bine.models import Base, TokenSample

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def nvda_ondo_quote_2usd() -> dict:
    """Scale the recorded $25 NVDAon quote fixture down to $2.00 for $2 execution tests."""
    q = json.loads((FIXTURES / "quote_nvda_ondo_25usd.json").read_text())
    factor = 2.0 / 25.0
    q["data"][0]["fromTokenAmount"] = str(int(2.0 * (10**18)))
    q["data"][0]["toTokenAmount"] = str(int(int(q["data"][0]["toTokenAmount"]) * factor))
    return q


@pytest.fixture
def nvda_bstock_quote_2usd() -> dict:
    """Scale the recorded $25 NVDAB quote fixture down to $2.00 for $2 execution tests."""
    q = json.loads((FIXTURES / "quote_nvda_bstock_25usd.json").read_text())
    factor = 2.0 / 25.0
    q["data"][0]["fromTokenAmount"] = str(int(2.0 * (10**18)))
    q["data"][0]["toTokenAmount"] = str(int(int(q["data"][0]["toTokenAmount"]) * factor))
    return q


@pytest.fixture
def nvda_ondo_liq() -> dict:
    return json.loads((FIXTURES / "liquidity_nvda_ondo.json").read_text())


@pytest.fixture
def nvda_bstock_liq() -> dict:
    return json.loads((FIXTURES / "liquidity_nvda_bstock.json").read_text())


@pytest.fixture
def swap_fixture() -> dict:
    return json.loads((FIXTURES / "swap_nvda_bstock_2usd.json").read_text())


@pytest.fixture
def approve_fixture() -> dict:
    return json.loads((FIXTURES / "approve_usdt_bsc.json").read_text())


@pytest.fixture
def simulate_swap_fixture() -> dict:
    return json.loads((FIXTURES / "simulate_swap_nvda_bstock.json").read_text())


@pytest.fixture
def simulate_approve_fixture() -> dict:
    return json.loads((FIXTURES / "simulate_approve_usdt.json").read_text())


def _make_nvda_samples(now: datetime) -> tuple[TokenSample, TokenSample]:
    ondo_raw = next(
        t
        for t in json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())["data"]
        if t["underlyingTicker"] == "NVDA"
    )
    bstock_raw = next(
        t
        for t in json.loads((FIXTURES / "rwa_tokens_bstock_bsc.json").read_text())["data"]
        if t["underlyingTicker"] == "NVDA"
    )

    ondo_sample = TokenSample(
        id=1,
        sampled_at=now - timedelta(seconds=30),
        binance_chain_id="56",
        token_contract_address=ondo_raw["tokenContractAddress"].lower(),
        platform_id="ondo",
        underlying_ticker="NVDA",
        token_symbol=ondo_raw["tokenSymbol"],
        ok=True,
        api_latency_ms=650,
        token_price=float(ondo_raw["tokenPrice"]),
        reference_price=float(ondo_raw["referencePrice"]),
        token_to_share_ratio=float(ondo_raw["tokenToShareRatio"]),
        price_gap_pct=0.0,
        open_state=True,
        market_status="regular",
        reason_code="TRADING",
        volume_24h=float(ondo_raw["volume24H"]),
        market_cap=float(ondo_raw["marketCap"]),
    )

    bstock_sample = TokenSample(
        id=2,
        sampled_at=now - timedelta(seconds=30),
        binance_chain_id="56",
        token_contract_address=bstock_raw["tokenContractAddress"].lower(),
        platform_id="bstock",
        underlying_ticker="NVDA",
        token_symbol=bstock_raw["tokenSymbol"],
        ok=True,
        api_latency_ms=680,
        token_price=float(bstock_raw["tokenPrice"]),
        reference_price=float(bstock_raw["referencePrice"]),
        token_to_share_ratio=float(bstock_raw["tokenToShareRatio"]),
        price_gap_pct=0.0,
        open_state=True,
        market_status=None,
        reason_code="TRADING",
        volume_24h=float(bstock_raw["volume24H"]),
        market_cap=float(bstock_raw["marketCap"]),
    )
    return ondo_sample, bstock_sample


async def _setup_test_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, now: datetime):
    db_file = tmp_path / "test_exec.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(db_mod, "engine", engine)
    monkeypatch.setattr(db_mod, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(app_mod, "AsyncSessionLocal", session_factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ondo_sample, bstock_sample = _make_nvda_samples(now)
    async with session_factory() as session:
        session.add_all([ondo_sample, bstock_sample])
        await session.commit()

    return engine, session_factory, ondo_sample, bstock_sample


@pytest.fixture(autouse=True)
def _clear_exec_caches():
    from bine.quote_engine import clear_rwa_catalog_cache

    clear_rwa_catalog_cache()
    app_mod._QUOTE_CACHE.clear()
    app_mod.reset_rate_limits()
    yield
    clear_rwa_catalog_cache()
    app_mod._QUOTE_CACHE.clear()
    app_mod.reset_rate_limits()


@pytest.mark.asyncio
async def test_execute_dry_run_simulates_and_logs_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    nvda_ondo_quote_2usd: dict,
    nvda_bstock_quote_2usd: dict,
    nvda_ondo_liq: dict,
    nvda_bstock_liq: dict,
    swap_fixture: dict,
    approve_fixture: dict,
    simulate_swap_fixture: dict,
    simulate_approve_fixture: dict,
) -> None:
    """Dry-run (`execute_live=False`) builds swap calldata via `/aggregator/swap`, simulates via
    `/pre-transaction/simulate`, verifies ERC-20 approval simulation when allowance is 0, and writes a row to `decision_log`.
    """
    now = datetime.now(timezone.utc)
    engine, _, ondo_sample, _ = await _setup_test_db(monkeypatch, tmp_path, now)

    test_settings = Settings(
        binance_api_key="test-key",
        binance_secret_key="test-secret",
        bine_live_mode=False,
        bine_max_trade_usd=3.0,
        bine_daily_cap_usd=10.0,
    )
    monkeypatch.setattr(app_mod, "get_settings", lambda: test_settings)

    def _quote_router(request):
        to_addr = request.url.params.get("toTokenAddress", "").lower()
        if to_addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_quote_2usd)
        return Response(200, json=nvda_bstock_quote_2usd)

    def _liq_router(request):
        addr = request.url.params.get("tokenContractAddress", "").lower()
        if addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_liq)
        return Response(200, json=nvda_bstock_liq)

    def _sim_router(request):
        body = json.loads(request.content.decode("utf-8"))
        to_addr = body["evmTx"]["to"].lower()
        # Direct swap to LiquidMesh router reverts with allowance; USDT approve succeeds
        if to_addr == "0x55d398326f99059ff775485246999027b3197955":
            return Response(200, json=simulate_approve_fixture)
        return Response(200, json=simulate_swap_fixture)

    with respx.mock(base_url="https://web3.binance.com/build") as respx_mock:
        respx_mock.get("/api/v1/dex/aggregator/quote").mock(side_effect=_quote_router)
        respx_mock.get("/api/v1/dex/market/token/top-liquidity").mock(side_effect=_liq_router)
        respx_mock.get("/api/v1/dex/aggregator/swap").mock(return_value=Response(200, json=swap_fixture))
        respx_mock.get("/api/v1/dex/aggregator/approve-transaction").mock(
            return_value=Response(200, json=approve_fixture)
        )
        respx_mock.post("/api/v1/dex/pre-transaction/simulate").mock(side_effect=_sim_router)

        transport = ASGITransport(app=app_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.post(
                "/api/execute",
                json={"ticker": "NVDA", "amount_usd": 2.0, "execute_live": False},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "dry_run"
            assert data["verdict"] == "BUY"
            assert data["simulation"]["ran"] is True
            assert data["simulation"]["passed"] is True
            assert data["simulation"]["status"] == "REQUIRES_APPROVAL"
            assert data["simulation"]["approval_simulation_status"] == "SUCCESS"
            assert data["execution"]["status"] == "DRY_RUN_OK"
            assert data["execution"]["attempted"] is False

            # Verify row persisted in decision_log via GET /api/decisions
            dec_resp = await ac.get("/api/decisions")
            assert dec_resp.status_code == 200
            decisions = dec_resp.json()["decisions"]
            assert len(decisions) == 1
            assert decisions[0]["ticker"] == "NVDA"
            assert decisions[0]["execution_status"] == "DRY_RUN_OK"
            assert decisions[0]["simulation_status"] == "REQUIRES_APPROVAL"
            assert decisions[0]["spender_address"].lower() == "0xb44446b0c8e56988c34f7ff73ae904982b5fdda5"

    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_refused_quote_skips_simulation_and_logs_refusal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    nvda_ondo_quote_2usd: dict,
    nvda_bstock_quote_2usd: dict,
    nvda_ondo_liq: dict,
    nvda_bstock_liq: dict,
) -> None:
    """When Quote Engine refuses (e.g. amount_usd=3000 > $2,500 quote cap), Transaction API simulation
    is skipped and `decision_log` records `execution_status="REFUSED"` with `refusal_code="amount_over_cap"`.
    """
    now = datetime.now(timezone.utc)
    engine, _, ondo_sample, _ = await _setup_test_db(monkeypatch, tmp_path, now)

    test_settings = Settings(
        binance_api_key="test-key",
        binance_secret_key="test-secret",
        bine_live_mode=True,
        bine_max_trade_usd=3.0,
        bine_admin_token="test-admin-secret",
    )
    monkeypatch.setattr(app_mod, "get_settings", lambda: test_settings)

    def _quote_router(request):
        to_addr = request.url.params.get("toTokenAddress", "").lower()
        if to_addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_quote_2usd)
        return Response(200, json=nvda_bstock_quote_2usd)

    def _liq_router(request):
        addr = request.url.params.get("tokenContractAddress", "").lower()
        if addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_liq)
        return Response(200, json=nvda_bstock_liq)

    with respx.mock(base_url="https://web3.binance.com/build") as respx_mock:
        respx_mock.get("/api/v1/dex/aggregator/quote").mock(side_effect=_quote_router)
        respx_mock.get("/api/v1/dex/market/token/top-liquidity").mock(side_effect=_liq_router)

        transport = ASGITransport(app=app_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # Without admin token, execute_live=True is rejected with 403
            r_unauth = await ac.post(
                "/api/execute",
                json={"ticker": "NVDA", "amount_usd": 3000.0, "execute_live": True},
            )
            assert r_unauth.status_code == 403

            resp = await ac.post(
                "/api/execute",
                json={"ticker": "NVDA", "amount_usd": 3000.0, "execute_live": True},
                headers={"X-Bine-Admin-Token": "test-admin-secret"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["verdict"] == "REFUSE"
            assert data["refusal_code"] == "amount_over_cap"
            assert data["simulation"]["ran"] is False
            assert data["simulation"]["status"] == "SKIPPED"
            assert data["execution"]["status"] == "REFUSED"

            dec_resp = await ac.get("/api/decisions")
            decisions = dec_resp.json()["decisions"]
            assert len(decisions) == 1
            assert decisions[0]["execution_status"] == "REFUSED"
            assert decisions[0]["refusal_code"] == "amount_over_cap"

    await engine.dispose()


@pytest.mark.asyncio
async def test_execute_live_enforces_caps_and_records_tx_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    nvda_ondo_quote_2usd: dict,
    nvda_bstock_quote_2usd: dict,
    nvda_ondo_liq: dict,
    nvda_bstock_liq: dict,
    swap_fixture: dict,
    approve_fixture: dict,
    simulate_swap_fixture: dict,
    simulate_approve_fixture: dict,
) -> None:
    """Verifies:
      - `execute_live=True` without `BINE_ADMIN_TOKEN` returns HTTP 403
      - `execute_live=True` at $25 (> $3.00 per-trade cap) returns `LIVE_BLOCKED_CAP`
      - `execute_live=True` at $2 with `BINE_LIVE_MODE=false` returns `LIVE_DISABLED`
      - `execute_live=True` at $2 with `BINE_LIVE_MODE=true` invokes `baw market-order swap`,
        saves `tx_hash` + `bsctrace_url` in `decision_log`, and enforces the daily cap (`BINE_DAILY_CAP_USD`).
    """
    now = datetime.now(timezone.utc)
    engine, _, ondo_sample, _ = await _setup_test_db(monkeypatch, tmp_path, now)

    nvda_ondo_quote_25usd = json.loads((FIXTURES / "quote_nvda_ondo_25usd.json").read_text())
    nvda_bstock_quote_25usd = json.loads((FIXTURES / "quote_nvda_bstock_25usd.json").read_text())

    def _quote_router(request):
        to_addr = request.url.params.get("toTokenAddress", "").lower()
        amt = int(request.url.params.get("amount", "0"))
        is_25 = amt > 5 * (10**18)
        if to_addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_quote_25usd if is_25 else nvda_ondo_quote_2usd)
        return Response(200, json=nvda_bstock_quote_25usd if is_25 else nvda_bstock_quote_2usd)

    def _liq_router(request):
        addr = request.url.params.get("tokenContractAddress", "").lower()
        if addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_liq)
        return Response(200, json=nvda_bstock_liq)

    def _sim_router(request):
        body = json.loads(request.content.decode("utf-8"))
        to_addr = body["evmTx"]["to"].lower()
        if to_addr == "0x55d398326f99059ff775485246999027b3197955":
            return Response(200, json=simulate_approve_fixture)
        return Response(200, json=simulate_swap_fixture)

    fake_tx_hash = "0x9f8e7d6c5b4a3f2e1d0c9b8a7f6e5d4c3b2a1f0e9d8c7b6a5f4e3d2c1b0a9f8e"
    monkeypatch.setattr(exec_mod.shutil, "which", lambda cmd: "/usr/local/bin/baw")
    monkeypatch.setattr(
        exec_mod.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"code": 0, "data": {"txHash": fake_tx_hash, "status": "SUBMITTED"}}),
            stderr="",
        ),
    )

    with respx.mock(base_url="https://web3.binance.com/build") as respx_mock:
        respx_mock.get("/api/v1/dex/aggregator/quote").mock(side_effect=_quote_router)
        respx_mock.get("/api/v1/dex/market/token/top-liquidity").mock(side_effect=_liq_router)
        respx_mock.get("/api/v1/dex/aggregator/swap").mock(return_value=Response(200, json=swap_fixture))
        respx_mock.get("/api/v1/dex/aggregator/approve-transaction").mock(
            return_value=Response(200, json=approve_fixture)
        )
        respx_mock.post("/api/v1/dex/pre-transaction/simulate").mock(side_effect=_sim_router)

        transport = ASGITransport(app=app_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            auth_headers = {"X-Bine-Admin-Token": "secret-token-123"}

            # Case A: $25 exceeds $3.00 per-trade cap -> LIVE_BLOCKED_CAP
            settings_disabled = Settings(
                binance_api_key="k",
                binance_secret_key="s",
                bine_live_mode=True,
                bine_max_trade_usd=3.0,
                bine_daily_cap_usd=3.5,
                bine_admin_token="secret-token-123",
            )
            monkeypatch.setattr(app_mod, "get_settings", lambda: settings_disabled)
            r_cap = await ac.post(
                "/api/execute",
                json={"ticker": "NVDA", "amount_usd": 25.0, "execute_live": True},
                headers=auth_headers,
            )
            assert r_cap.status_code == 200
            assert r_cap.json()["execution"]["status"] == "LIVE_BLOCKED_CAP"

            # Case B: $2 within cap, but BINE_LIVE_MODE=false -> LIVE_DISABLED
            settings_off = Settings(
                binance_api_key="k",
                binance_secret_key="s",
                bine_live_mode=False,
                bine_max_trade_usd=3.0,
                bine_daily_cap_usd=3.5,
                bine_admin_token="secret-token-123",
            )
            monkeypatch.setattr(app_mod, "get_settings", lambda: settings_off)
            r_off = await ac.post(
                "/api/execute",
                json={"ticker": "NVDA", "amount_usd": 2.0, "execute_live": True},
                headers=auth_headers,
            )
            assert r_off.status_code == 200
            assert r_off.json()["execution"]["status"] == "LIVE_DISABLED"

            # Case C: $2 within cap AND BINE_LIVE_MODE=true -> LIVE_SUBMITTED with tx_hash + bsctrace_url
            settings_on = Settings(
                binance_api_key="k",
                binance_secret_key="s",
                bine_live_mode=True,
                bine_max_trade_usd=3.0,
                bine_daily_cap_usd=3.5,
                bine_admin_token="secret-token-123",
            )
            monkeypatch.setattr(app_mod, "get_settings", lambda: settings_on)
            r_live = await ac.post(
                "/api/execute",
                json={"ticker": "NVDA", "amount_usd": 2.0, "execute_live": True},
                headers=auth_headers,
            )
            assert r_live.status_code == 200
            live_data = r_live.json()
            assert live_data["execution"]["status"] == "LIVE_SUBMITTED"
            assert live_data["execution"]["tx_hash"] == fake_tx_hash
            assert live_data["execution"]["bsctrace_url"] == f"https://bsctrace.com/tx/{fake_tx_hash}"

            # Case D: Second $2 live trade today ($2 + $2 = $4.00 > $3.50 daily cap) -> LIVE_BLOCKED_CAP
            r_daily = await ac.post(
                "/api/execute",
                json={"ticker": "NVDA", "amount_usd": 2.0, "execute_live": True},
                headers=auth_headers,
            )
            assert r_daily.status_code == 200
            assert r_daily.json()["execution"]["status"] == "LIVE_BLOCKED_CAP"
            assert "daily cap" in r_daily.json()["execution"]["detail"]

            # Check all 4 decisions were logged in `decision_log`
            dec_resp = await ac.get("/api/decisions")
            assert dec_resp.json()["count"] == 4

    await engine.dispose()


def test_baw_async_order_polling_finished_failed_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies `run_agentic_wallet_swap` polls `baw market-order list --orderId <id> --json`
    and handles FINISHED (txHash), FAILED (LIVE_ERROR), and polling timeout (LIVE_TIMEOUT)."""
    monkeypatch.setattr(exec_mod.shutil, "which", lambda cmd: "/usr/local/bin/baw")
    monkeypatch.setattr(exec_mod.time, "sleep", lambda _: None)

    tx_done = "0x1111222233334444555566667777888899990000aaaabbbbccccddddeeeeffff"

    # 1. Async orderId -> PENDING -> FINISHED with txHash
    calls_finished: list[list[str]] = []

    def _mock_finished(cmd, **kwargs):
        calls_finished.append(list(cmd))
        if "swap" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"success": True, "data": {"orderId": "ord-101"}}), stderr="")
        if len(calls_finished) == 2:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"data": {"list": [{"orderId": "ord-101", "status": "PENDING"}]}}), stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"data": {"list": [{"orderId": "ord-101", "status": "FINISHED", "txHash": tx_done}]}}), stderr="")

    fake_winner = SimpleNamespace(token_contract_address="0x02fca66c1d1afb4e2a7884261eb00f63598a7436")

    monkeypatch.setattr(exec_mod.subprocess, "run", _mock_finished)
    res_ok = exec_mod.run_agentic_wallet_swap(fake_winner, 2.0, poll_attempts=3, poll_interval_seconds=0.0)
    assert res_ok.status == "LIVE_SUBMITTED"
    assert res_ok.order_id == "ord-101"
    assert res_ok.tx_hash == tx_done
    assert res_ok.bsctrace_url == f"https://bsctrace.com/tx/{tx_done}"

    # 2. Async orderId -> FAILED
    def _mock_failed(cmd, **kwargs):
        if "swap" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"success": True, "data": {"orderId": "ord-fail"}}), stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"data": {"list": [{"orderId": "ord-fail", "status": "FAILED"}]}}), stderr="")

    monkeypatch.setattr(exec_mod.subprocess, "run", _mock_failed)
    res_fail = exec_mod.run_agentic_wallet_swap(fake_winner, 2.0, poll_attempts=3, poll_interval_seconds=0.0)
    assert res_fail.status == "LIVE_ERROR"
    assert res_fail.order_id == "ord-fail"
    assert "status=FAILED" in res_fail.detail

    # 3. Async orderId -> stays PENDING across all poll_attempts -> LIVE_TIMEOUT
    def _mock_timeout(cmd, **kwargs):
        if "swap" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"success": True, "data": {"orderId": "ord-slow"}}), stderr="")
        return SimpleNamespace(returncode=0, stdout=json.dumps({"data": {"list": [{"orderId": "ord-slow", "status": "PENDING"}]}}), stderr="")

    monkeypatch.setattr(exec_mod.subprocess, "run", _mock_timeout)
    res_to = exec_mod.run_agentic_wallet_swap(fake_winner, 2.0, poll_attempts=2, poll_interval_seconds=0.0)
    assert res_to.status == "LIVE_TIMEOUT"
    assert res_to.order_id == "ord-slow"
    assert "Timed out polling" in res_to.detail


def test_build_baw_swap_command_from_quote_reads_token_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies `build_baw_swap_command_from_quote` reads `--toToken` directly from `quote['token']['address']`
    and rejects any address mismatch."""
    monkeypatch.setattr(exec_mod.shutil, "which", lambda cmd: "/usr/local/bin/npx" if cmd == "npx" else None)

    nvdab_addr = "0x02fca66c1d1afb4e2a7884261eb00f63598a7436"
    quote = {
        "schema_version": "1",
        "ticker": "NVDA",
        "amount_usd": 2.0,
        "verdict": "BUY",
        "token": {
            "symbol": "NVDAB",
            "address": nvdab_addr,
            "issuer": "bstock",
        },
    }
    cmd_list, cmd_str = exec_mod.build_baw_swap_command_from_quote(
        quote,
        expected_address=nvdab_addr,
    )
    to_idx = cmd_list.index("--toToken")
    assert cmd_list[to_idx + 1] == nvdab_addr
    assert f"--toToken {nvdab_addr}" in cmd_str

    # Mismatched address must raise ValueError and block run_agentic_wallet_swap before subprocess.run
    with pytest.raises(ValueError, match="Token address mismatch"):
        exec_mod.build_baw_swap_command_from_quote(
            quote,
            expected_address="0xbf0a2e3f8fd0fb9d8b6b19a2f7f2b5a2f43a5a68",
        )

    fake_wrong_winner = SimpleNamespace(token_contract_address="0xbf0a2e3f8fd0fb9d8b6b19a2f7f2b5a2f43a5a68")
    blocked = exec_mod.run_agentic_wallet_swap(fake_wrong_winner, 2.0, quote=quote)
    assert blocked.attempted is False
    assert blocked.status == "LIVE_ERROR"
    assert "Token address mismatch" in blocked.detail

    # Child orderId fallback when --orderId returns list: [] after approve+swap
    monkeypatch.setattr(exec_mod.time, "sleep", lambda _: None)
    real_tx = "0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506"

    def _mock_child_order(cmd, **kwargs):
        if "swap" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"success": True, "data": {"orderId": "26100300001937918699"}}), stderr="")
        if "--orderId" in cmd:
            return SimpleNamespace(returncode=0, stdout=json.dumps({"success": True, "data": {"total": 0, "list": []}}), stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "success": True,
                    "data": {
                        "total": 1,
                        "list": [
                            {
                                "orderId": "26100300001937918737",
                                "toToken": "0x02Fca66C1D1aFB4E2A7884261eB00F63598a7436",
                                "status": "FINISHED",
                                "txHash": real_tx,
                            }
                        ],
                    },
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(exec_mod.subprocess, "run", _mock_child_order)
    fake_nvdab_winner = SimpleNamespace(token_contract_address=nvdab_addr)
    res_child = exec_mod.run_agentic_wallet_swap(fake_nvdab_winner, 2.0, quote=quote, poll_attempts=2, poll_interval_seconds=0.0)
    assert res_child.status == "LIVE_SUBMITTED"
    assert res_child.order_id == "26100300001937918737"
    assert res_child.tx_hash == real_tx
    assert res_child.bsctrace_url == f"https://bsctrace.com/tx/{real_tx}"


@pytest.mark.asyncio
async def test_dry_run_requires_approval_summary_branches(
    nvda_bstock_quote_2usd: dict,
    nvda_bstock_liq: dict,
    swap_fixture: dict,
    approve_fixture: dict,
    simulate_swap_fixture: dict,
    simulate_approve_fixture: dict,
) -> None:
    """Verifies `run_transaction_dry_run` summary wording when `/pre-transaction/simulate` returns
    `REQUIRES_APPROVAL` on spender `0xB444...`:
      1. Wallet available and `allowance(wallet, 0xb300...)` covers amount -> prints sufficient allowance sentence.
      2. Wallet available and `allowance(wallet, 0xb300...) == 0` -> prints plain router difference wording.
      3. BSC RPC failure -> falls back to plain router difference wording and never blocks dry-run.
      4. Wallet not configured (`DEFAULT_QUOTE_WALLET`) -> prints plain router difference wording.
    """
    import httpx as _httpx
    from bine.client import BinanceClient
    from bine.quote_engine import evaluate_issuer_quote

    now = datetime.now(timezone.utc)
    _, bstock_sample = _make_nvda_samples(now)
    winner = evaluate_issuer_quote(
        sample=bstock_sample,
        amount_usd=2.0,
        quote_response=nvda_bstock_quote_2usd,
        liquidity_response=nvda_bstock_liq,
        now=now,
    )
    user_wallet = "0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730"

    def _sim_router(request):
        body = json.loads(request.content.decode("utf-8"))
        to_addr = body["evmTx"]["to"].lower()
        if to_addr == "0x55d398326f99059ff775485246999027b3197955":
            return Response(200, json=simulate_approve_fixture)
        return Response(200, json=simulate_swap_fixture)

    # Branch 1: allowance(wallet, 0xb300...) >= amount_wei (uint256.max - 4e18)
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("https://web3.binance.com/build/api/v1/dex/aggregator/swap").mock(
            return_value=Response(200, json=swap_fixture)
        )
        respx_mock.get("https://web3.binance.com/build/api/v1/dex/aggregator/approve-transaction").mock(
            return_value=Response(200, json=approve_fixture)
        )
        respx_mock.post("https://web3.binance.com/build/api/v1/dex/pre-transaction/simulate").mock(
            side_effect=_sim_router
        )
        respx_mock.post(exec_mod.BSC_PUBLIC_RPC_URL).mock(
            return_value=Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": "0xffffffffffffffffffffffffffffffffffffffffffffffffc87d2531626fffff",
                },
            )
        )
        async with BinanceClient(api_key="k", secret_key="s") as client:
            res_suff = await exec_mod.run_transaction_dry_run(
                client=client,
                winner=winner,
                amount_usd=2.0,
                wallet_address=user_wallet,
            )
        assert res_suff.passed is True
        assert res_suff.status == "REQUIRES_APPROVAL"
        assert res_suff.summary == (
            "Simulation router 0xB444... has no allowance; baw router 0xb300... "
            "already has sufficient allowance, so no approve tx is expected."
        )

        # Branch 2: allowance(wallet, 0xb300...) == 0
        respx_mock.post(exec_mod.BSC_PUBLIC_RPC_URL).mock(
            return_value=Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "result": "0x0000000000000000000000000000000000000000000000000000000000000000",
                },
            )
        )
        async with BinanceClient(api_key="k", secret_key="s") as client:
            res_zero = await exec_mod.run_transaction_dry_run(
                client=client,
                winner=winner,
                amount_usd=2.0,
                wallet_address=user_wallet,
            )
        assert res_zero.passed is True
        assert res_zero.status == "REQUIRES_APPROVAL"
        assert res_zero.summary == exec_mod.PLAIN_ROUTER_APPROVAL_SUMMARY

        # Branch 3: BSC RPC failure -> falls back to plain wording without blocking
        respx_mock.post(exec_mod.BSC_PUBLIC_RPC_URL).mock(
            side_effect=_httpx.ConnectError("BSC RPC unreachable")
        )
        async with BinanceClient(api_key="k", secret_key="s") as client:
            res_err = await exec_mod.run_transaction_dry_run(
                client=client,
                winner=winner,
                amount_usd=2.0,
                wallet_address=user_wallet,
            )
        assert res_err.passed is True
        assert res_err.status == "REQUIRES_APPROVAL"
        assert res_err.summary == exec_mod.PLAIN_ROUTER_APPROVAL_SUMMARY

        # Branch 4: Default quote placeholder wallet (no user wallet configured)
        async with BinanceClient(api_key="k", secret_key="s") as client:
            res_nowallet = await exec_mod.run_transaction_dry_run(
                client=client,
                winner=winner,
                amount_usd=2.0,
            )
        assert res_nowallet.passed is True
        assert res_nowallet.status == "REQUIRES_APPROVAL"
        assert res_nowallet.summary == exec_mod.PLAIN_ROUTER_APPROVAL_SUMMARY

