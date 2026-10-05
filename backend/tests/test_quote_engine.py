"""Unit and integration tests for the Bine Pre-Trade Guard (`GET /api/quote`),
CLI (`bine check`), and MCP Server (`bine_check`, `bine_buy`).

Covers:
  - Frozen Phase 1 schema contract (`schema_version: "1"`, exact 13 top-level keys)
  - All 8 deterministic refusal rules (`amount_over_cap`, `below_issuer_minimum`,
    `market_closed`, `reference_stale`, `depth_thin`, `slippage_too_high`,
    `quality_unreliable`, `unknown_ticker`)
  - 5 bps tie band (`Either works (within 5 bps)...`) and deterministic tiebreak
    (deeper AMM liquidity -> lower minimum order -> alphabetical)
  - Any-ticker lookup (`AAPL` single-issuer Ondo-only returns `alternative: null`)
  - CLI (`bine check NVDA 25` plain English and `bine check NVDA 25 --json`)
  - MCP Server (`tools/list`, `bine_check`, and `bine_buy` with `confirm=False`)
"""

from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import respx
from httpx import ASGITransport, AsyncClient, Response

from bine.models import TokenSample
from bine.quote_engine import (
    MAX_QUOTE_USD,
    MAX_SAMPLE_AGE_SECONDS,
    MAX_SLIPPAGE_PCT,
    SCHEMA_VERSION,
    TIE_BAND_BPS,
    build_verdict,
    clear_rwa_catalog_cache,
    evaluate_issuer_quote,
)

FIXTURES = Path(__file__).parent / "fixtures"

FROZEN_PHASE1_KEYS = {
    "schema_version",
    "ticker",
    "amount_usd",
    "quoted_at",
    "verdict",
    "token",
    "shares",
    "all_in_price_per_share",
    "reference_price_per_share",
    "spread_pct",
    "refusal",
    "alternative",
    "market",
}


@pytest.fixture(autouse=True)
def _reset_caches():
    import bine.app as app_mod

    clear_rwa_catalog_cache()
    app_mod._QUOTE_CACHE.clear()
    app_mod.reset_rate_limits()
    yield
    clear_rwa_catalog_cache()
    app_mod._QUOTE_CACHE.clear()
    app_mod.reset_rate_limits()


@pytest.fixture
def nvda_ondo_quote_fixture() -> dict:
    return json.loads((FIXTURES / "quote_nvda_ondo_25usd.json").read_text())


@pytest.fixture
def nvda_bstock_quote_fixture() -> dict:
    return json.loads((FIXTURES / "quote_nvda_bstock_25usd.json").read_text())


@pytest.fixture
def nvda_ondo_liq_fixture() -> dict:
    return json.loads((FIXTURES / "liquidity_nvda_ondo.json").read_text())


@pytest.fixture
def nvda_bstock_liq_fixture() -> dict:
    return json.loads((FIXTURES / "liquidity_nvda_bstock.json").read_text())


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
        sampled_at=now - timedelta(seconds=15),
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
        sampled_at=now - timedelta(seconds=15),
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
        market_cap=None,
    )
    return ondo_sample, bstock_sample


def test_frozen_schema_contract_and_tie_band_deterministic_tiebreak(
    nvda_ondo_quote_fixture: dict,
    nvda_bstock_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
    nvda_bstock_liq_fixture: dict,
) -> None:
    """With recorded $25 NVDA quotes, NVDAon ($231.08/sh) and NVDAB ($231.33/sh) are ~10.8 bps apart
    when using raw fixture numbers; when within 5 bps, tiebreak picks deeper AMM liquidity (bStocks)
    and sets alternative.note to 'Either works (within 5 bps)...'."""
    now = datetime.now(timezone.utc)
    ondo_sample, bstock_sample = _make_nvda_samples(now)

    ev_ondo = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=25.0,
        quote_response=nvda_ondo_quote_fixture,
        liquidity_response=nvda_ondo_liq_fixture,
        now=now,
    )
    ev_bstock = evaluate_issuer_quote(
        sample=bstock_sample,
        amount_usd=25.0,
        quote_response=nvda_bstock_quote_fixture,
        liquidity_response=nvda_bstock_liq_fixture,
        now=now,
    )

    # Case A: Recorded NVDA fixture has NVDAon ($231.5229/sh) and NVDAB ($231.5529/sh) -> 1.29 bps apart!
    # Because 1.29 bps <= 5.0 bps tie band, tiebreak triggers and picks bStocks (deeper AMM liquidity: $6.06M vs $0)
    verdict_tie = build_verdict("NVDA", 25.0, [ev_ondo, ev_bstock], now=now, tie_band_bps=TIE_BAND_BPS)
    payload_tie = verdict_tie.to_dict(include_details=False)
    assert set(payload_tie.keys()) == FROZEN_PHASE1_KEYS
    assert payload_tie["schema_version"] == SCHEMA_VERSION == "1"
    assert verdict_tie.tiebreak_applied is True
    assert payload_tie["verdict"] == "BUY"
    assert payload_tie["token"]["symbol"] == "NVDAB"
    assert payload_tie["token"]["issuer"] == "bstock"
    assert payload_tie["refusal"] is None
    assert payload_tie["alternative"]["symbol"] == "NVDAon"
    assert "Either works (within 5 bps)" in payload_tie["alternative"]["note"]

    # Case B: Outside 5 bps tie band (e.g. 25 bps gap) -> cheaper issuer (Ondo) wins outright on price
    ev_bstock_wider = copy.deepcopy(ev_bstock)
    ev_bstock_wider.all_in_price_per_share_usd = round((ev_ondo.all_in_price_per_share_usd or 231.52) + 0.60, 4)
    verdict_clear = build_verdict("NVDA", 25.0, [ev_ondo, ev_bstock_wider], now=now, tie_band_bps=TIE_BAND_BPS)
    payload_clear = verdict_clear.to_dict(include_details=False)
    assert verdict_clear.tiebreak_applied is False
    assert payload_clear["verdict"] == "BUY"
    assert payload_clear["token"]["symbol"] == "NVDAon"
    assert payload_clear["token"]["issuer"] == "ondo"
    assert payload_clear["alternative"]["symbol"] == "NVDAB"
    assert "Also checked NVDAB on bStocks" in payload_clear["alternative"]["note"]
    assert "Either works" not in payload_clear["alternative"]["note"]


def test_refusal_rule_amount_over_cap(
    nvda_ondo_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
) -> None:
    """Refuses when amount_usd exceeds MAX_QUOTE_USD or is <= 0."""
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)

    ev = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=MAX_QUOTE_USD + 500.0,
        quote_response=nvda_ondo_quote_fixture,
        liquidity_response=nvda_ondo_liq_fixture,
        now=now,
    )
    assert ev.eligible is False
    assert ev.refusal_code == "amount_over_cap"

    verdict = build_verdict("NVDA", MAX_QUOTE_USD + 500.0, [ev], now=now)
    d = verdict.to_dict()
    assert d["verdict"] == "REFUSE"
    assert d["refusal"]["code"] == "amount_over_cap"
    assert "safety limit" in d["refusal"]["message"]


def test_refusal_rule_below_issuer_minimum(
    nvda_ondo_liq_fixture: dict,
) -> None:
    """Classifies Ondo [40375] 'Minimum order amount is 5 USD' as below_issuer_minimum (not depth_thin)."""
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)

    ev = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=2.0,
        quote_response=None,
        liquidity_response=nvda_ondo_liq_fixture,
        quote_error="[40375] Minimum order amount is 5 USD.",
        now=now,
    )
    assert ev.eligible is False
    assert ev.refusal_code == "below_issuer_minimum"
    assert ev.refusal_reason == "Ondo's minimum order is $5 (you entered $2.00). Try $5.50."

    ev5 = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=5.0,
        quote_response=None,
        liquidity_response=nvda_ondo_liq_fixture,
        quote_error="[40375] Minimum order amount is 5 USD.",
        now=now,
    )
    assert ev5.eligible is False
    assert ev5.refusal_code == "below_issuer_minimum"
    assert ev5.refusal_reason == "Ondo's minimum order is $5. After conversion your $5.00 lands just under it. Try $5.50."

    verdict = build_verdict("AAPL", 2.0, [ev], now=now)
    d = verdict.to_dict()
    assert d["verdict"] == "REFUSE"
    assert d["refusal"]["code"] == "below_issuer_minimum"


def test_refusal_rule_quality_unreliable(
    nvda_ondo_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
) -> None:
    """Refuses when token fails data-quality filter (e.g. ENLVon reverse split outlier)."""
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)
    ondo_sample.token_symbol = "ENLVon"
    ondo_sample.underlying_ticker = "ENLV"
    ondo_sample.token_price = 1.07
    ondo_sample.reference_price = 16.05
    ondo_sample.token_to_share_ratio = 0.066667

    ev = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=25.0,
        quote_response=nvda_ondo_quote_fixture,
        liquidity_response=nvda_ondo_liq_fixture,
        now=now,
    )
    assert ev.eligible is False
    assert ev.refusal_code == "quality_unreliable"
    assert ev.refusal_reason == (
        "ENLVon has a share ratio of 0.0667 shares per token "
        "(token price $1.07 vs $16.05 reference), "
        "outside the supported 0.25–5.00x limit — not buying."
    )

    # When /quote fails with 40374 (Insufficient liquidity), depth_thin is reported first
    # and the share-ratio note is included as a second line:
    klac_sample = copy.deepcopy(ondo_sample)
    klac_sample.token_symbol = "KLACon"
    klac_sample.underlying_ticker = "KLAC"
    klac_sample.token_price = 17121.02
    klac_sample.reference_price = 1700.54
    klac_sample.token_to_share_ratio = 10.068018
    ev_klac = evaluate_issuer_quote(
        sample=klac_sample,
        amount_usd=25.0,
        quote_response=None,
        liquidity_response={"code": 0, "msg": "success", "data": []},
        quote_error="[40374] Insufficient liquidity for a quote. Please decrease the transaction amount or try again later.",
        now=now,
    )
    assert ev_klac.eligible is False
    assert ev_klac.refusal_code == "depth_thin"
    assert ev_klac.refusal_reason == (
        "No pool on BNB Chain can fill $25.00 of KLACon right now. Not buying.\n"
        "KLACon has a share ratio of 10.0680 shares per token "
        "(token price $17,121.02 vs $1,700.54 reference), "
        "outside the supported 0.25–5.00x limit — not buying."
    )
    verdict_klac = build_verdict("KLAC", 25.0, [ev_klac], now=now)
    d_klac = verdict_klac.to_dict()
    assert d_klac["verdict"] == "REFUSE"
    assert d_klac["refusal"]["code"] == "depth_thin"
    assert d_klac["refusal"]["message"].splitlines() == [
        "No pool on BNB Chain can fill $25.00 of KLACon right now. Not buying.",
        "KLACon has a share ratio of 10.0680 shares per token (token price $17,121.02 vs $1,700.54 reference), outside the supported 0.25–5.00x limit — not buying.",
    ]


def test_refusal_rule_market_closed(
    nvda_ondo_quote_fixture: dict,
    nvda_bstock_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
    nvda_bstock_liq_fixture: dict,
) -> None:
    """Refuses an issuer with code market_closed when open_state is False or reason_code != 'TRADING'."""
    now = datetime.now(timezone.utc)
    ondo_sample, bstock_sample = _make_nvda_samples(now)

    ondo_sample.open_state = False
    ondo_sample.market_status = "paused"
    ondo_sample.reason_code = "MARKET_PAUSED"

    ev_ondo = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=25.0,
        quote_response=nvda_ondo_quote_fixture,
        liquidity_response=nvda_ondo_liq_fixture,
        now=now,
    )
    ev_bstock = evaluate_issuer_quote(
        sample=bstock_sample,
        amount_usd=25.0,
        quote_response=nvda_bstock_quote_fixture,
        liquidity_response=nvda_bstock_liq_fixture,
        now=now,
    )

    assert ev_ondo.eligible is False
    assert ev_ondo.refusal_code == "market_closed"
    assert ev_bstock.eligible is True

    verdict = build_verdict("NVDA", 25.0, [ev_ondo, ev_bstock], now=now)
    d = verdict.to_dict()
    assert d["verdict"] == "BUY"
    assert d["token"]["issuer"] == "bstock"
    assert d["alternative"]["eligible"] is False
    assert "paused" in d["alternative"]["note"]


def test_refusal_rule_reference_stale(
    nvda_ondo_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
) -> None:
    """Refuses when the reference price fetch is older than MAX_SAMPLE_AGE_SECONDS (120s)."""
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)
    ondo_sample.sampled_at = now - timedelta(seconds=MAX_SAMPLE_AGE_SECONDS + 30)

    ev = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=25.0,
        quote_response=nvda_ondo_quote_fixture,
        liquidity_response=nvda_ondo_liq_fixture,
        now=now,
    )
    assert ev.eligible is False
    assert ev.refusal_code == "reference_stale"


def test_refusal_rule_depth_thin(
    nvda_bstock_quote_fixture: dict,
) -> None:
    """Refuses when AMM pool liquidity is below minimum threshold or /quote returns no routes."""
    now = datetime.now(timezone.utc)
    _, bstock_sample = _make_nvda_samples(now)

    thin_liq = {
        "code": 0,
        "msg": "success",
        "data": [
            {
                "pool": "NVDAB/USDT",
                "protocolName": "PancakeSwap V3",
                "liquidityUsd": "1500.00",
                "poolAddress": "0x8fb4243b553ac29ba088acf00b9b7da24bd6690c",
            }
        ],
    }
    ev_thin = evaluate_issuer_quote(
        sample=bstock_sample,
        amount_usd=25.0,
        quote_response=nvda_bstock_quote_fixture,
        liquidity_response=thin_liq,
        now=now,
    )
    assert ev_thin.eligible is False
    assert ev_thin.refusal_code == "depth_thin"

    ev_no_route = evaluate_issuer_quote(
        sample=bstock_sample,
        amount_usd=25.0,
        quote_response={"code": 0, "msg": "success", "data": []},
        liquidity_response=thin_liq,
        now=now,
    )
    assert ev_no_route.eligible is False
    assert ev_no_route.refusal_code == "depth_thin"


def test_refusal_rule_slippage_too_high(
    nvda_ondo_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
) -> None:
    """Refuses when quoted execution price deviates from reference price by > MAX_SLIPPAGE_PCT (1.0%),
    such as SPYon at $250 (+40.7% spread above reference)."""
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)

    bad_quote = copy.deepcopy(nvda_ondo_quote_fixture)
    orig_wei = int(bad_quote["data"][0]["toTokenAmount"])
    bad_quote["data"][0]["toTokenAmount"] = str(int(orig_wei * 0.70))
    bad_quote["data"][0]["priceImpactPercent"] = "0.2974289557"

    ev = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=250.0,
        quote_response=bad_quote,
        liquidity_response=nvda_ondo_liq_fixture,
        now=now,
    )
    assert ev.eligible is False
    assert ev.refusal_code == "slippage_too_high"
    assert ev.price_impact_pct == pytest.approx(29.7429, abs=0.01)
    assert (ev.effective_slippage_pct or 0) > MAX_SLIPPAGE_PCT
    assert "above the market price" in (ev.refusal_reason or "")


def test_refusal_rule_unknown_ticker() -> None:
    """Returns unknown_ticker when no issuer lists the ticker on BSC."""
    now = datetime.now(timezone.utc)
    verdict = build_verdict("NOTASTOCK", 25.0, [], now=now)
    d = verdict.to_dict()
    assert set(d.keys()) == FROZEN_PHASE1_KEYS
    assert d["verdict"] == "REFUSE"
    assert d["refusal"]["code"] == "unknown_ticker"
    assert d["alternative"] is None


def test_single_issuer_ticker_lookup_aapl(
    nvda_ondo_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
) -> None:
    """Single-issuer tickers like AAPL (Ondo-only on BSC) return verdict=BUY and alternative=None."""
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)
    ondo_sample.underlying_ticker = "AAPL"
    ondo_sample.token_symbol = "AAPLon"

    ev_aapl = evaluate_issuer_quote(
        sample=ondo_sample,
        amount_usd=25.0,
        quote_response=nvda_ondo_quote_fixture,
        liquidity_response=nvda_ondo_liq_fixture,
        now=now,
    )
    verdict = build_verdict("AAPL", 25.0, [ev_aapl], now=now)
    d = verdict.to_dict()
    assert set(d.keys()) == FROZEN_PHASE1_KEYS
    assert d["verdict"] == "BUY"
    assert d["token"]["symbol"] == "AAPLon"
    assert d["alternative"] is None


@pytest.mark.asyncio
async def test_api_quote_endpoint_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    nvda_ondo_quote_fixture: dict,
    nvda_bstock_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
    nvda_bstock_liq_fixture: dict,
) -> None:
    """End-to-end test of GET /api/quote?ticker=NVDA&amount_usd=25 verifying the frozen Phase 1 schema."""
    import bine.app as app_mod
    import bine.database as db_mod
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from bine.models import Base

    db_file = tmp_path / "test_quote.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(db_mod, "engine", engine)
    monkeypatch.setattr(db_mod, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(app_mod, "AsyncSessionLocal", session_factory)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    ondo_payload = json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())
    bstock_payload = json.loads((FIXTURES / "rwa_tokens_bstock_bsc.json").read_text())
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)

    def _rwa_router(request):
        pid = request.url.params.get("platformId", "")
        if pid == "ondo":
            return Response(200, json=ondo_payload)
        return Response(200, json=bstock_payload)

    def _quote_router(request):
        to_addr = request.url.params.get("toTokenAddress", "").lower()
        if to_addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_quote_fixture)
        return Response(200, json=nvda_bstock_quote_fixture)

    def _liq_router(request):
        addr = request.url.params.get("tokenContractAddress", "").lower()
        if addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_liq_fixture)
        return Response(200, json=nvda_bstock_liq_fixture)

    with respx.mock(base_url="https://web3.binance.com/build") as respx_mock:
        respx_mock.get("/api/v1/dex/market/rwa/tokens").mock(side_effect=_rwa_router)
        respx_mock.get("/api/v1/dex/aggregator/quote").mock(side_effect=_quote_router)
        respx_mock.get("/api/v1/dex/market/token/top-liquidity").mock(side_effect=_liq_router)

        transport = ASGITransport(app=app_mod.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            resp = await ac.get("/api/quote?ticker=NVDA&amount_usd=25")
            assert resp.status_code == 200
            data = resp.json()
            assert set(data.keys()) == FROZEN_PHASE1_KEYS
            assert data["schema_version"] == "1"
            assert data["ticker"] == "NVDA"
            assert data["amount_usd"] == 25.0
            assert data["verdict"] == "BUY"
            assert data["token"]["symbol"] == "NVDAB"
            assert data["alternative"]["symbol"] == "NVDAon"
            assert "Either works (within 5 bps)" in data["alternative"]["note"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_cli_and_mcp_server_tools(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    nvda_ondo_quote_fixture: dict,
    nvda_bstock_quote_fixture: dict,
    nvda_ondo_liq_fixture: dict,
    nvda_bstock_liq_fixture: dict,
) -> None:
    """Verifies CLI (`bine check NVDA 25` and `--json`) and MCP Server (`tools/list` and `bine_check`)."""
    from bine.cli import format_plain_check_line, main as cli_main, run_check
    from bine.mcp_server import handle_jsonrpc_message

    ondo_payload = json.loads((FIXTURES / "rwa_tokens_ondo_bsc.json").read_text())
    bstock_payload = json.loads((FIXTURES / "rwa_tokens_bstock_bsc.json").read_text())
    now = datetime.now(timezone.utc)
    ondo_sample, _ = _make_nvda_samples(now)

    def _rwa_router(request):
        pid = request.url.params.get("platformId", "")
        return Response(200, json=ondo_payload if pid == "ondo" else bstock_payload)

    def _quote_router(request):
        to_addr = request.url.params.get("toTokenAddress", "").lower()
        if to_addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_quote_fixture)
        return Response(200, json=nvda_bstock_quote_fixture)

    def _liq_router(request):
        addr = request.url.params.get("tokenContractAddress", "").lower()
        if addr == ondo_sample.token_contract_address.lower():
            return Response(200, json=nvda_ondo_liq_fixture)
        return Response(200, json=nvda_bstock_liq_fixture)

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("https://web3.binance.com/build/api/v1/dex/market/rwa/tokens").mock(side_effect=_rwa_router)
        respx_mock.get("https://web3.binance.com/build/api/v1/dex/aggregator/quote").mock(side_effect=_quote_router)
        respx_mock.get("https://web3.binance.com/build/api/v1/dex/market/token/top-liquidity").mock(side_effect=_liq_router)

        # 1. Direct async check (BINE_DIRECT_MODE=true) + CLI plain-English formatter
        monkeypatch.setenv("BINE_DIRECT_MODE", "true")
        res = await run_check("NVDA", 25.0)
        assert set(res.keys()) == FROZEN_PHASE1_KEYS
        line = format_plain_check_line(res)
        assert line.startswith("BUY: Buy ")
        assert "NVDA" in line

        # 2. Default BINE_API_URL=http://localhost:8000 check + MCP tools/list & tools/call
        monkeypatch.delenv("BINE_DIRECT_MODE", raising=False)
        respx_mock.get("http://localhost:8000/api/quote").mock(return_value=Response(200, json=res))

        list_resp = await handle_jsonrpc_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        assert list_resp is not None
        tool_names = [t["name"] for t in list_resp["result"]["tools"]]
        assert tool_names == ["bine_check", "bine_buy"]

        call_resp = await handle_jsonrpc_message(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "bine_check", "arguments": {"ticker": "NVDA", "amount_usd": 25}},
            }
        )
        assert call_resp is not None
        sc = call_resp["result"]["structuredContent"]
        assert sc["schema_version"] == "1"
        assert sc["verdict"] == "BUY"
        assert call_resp["result"]["isError"] is False


def test_cli_unreachable_backend_prints_single_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """If the backend is unreachable, `bine` prints one clear line and returns exit code 1."""
    import httpx as _httpx

    from bine.cli import main as cli_main

    monkeypatch.setenv("BINANCE_API_KEY", "")
    monkeypatch.setenv("BINANCE_SECRET_KEY", "")
    monkeypatch.delenv("BINE_API_URL", raising=False)

    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.get("http://localhost:8000/api/quote").mock(
            side_effect=_httpx.ConnectError("Connection refused")
        )
        rc = cli_main(["check", "NVDA", "5.50"])
        captured = capsys.readouterr()
        out_lines = [ln for ln in captured.out.strip().splitlines() if ln.strip()]
        assert rc == 1
        assert len(out_lines) == 1
        assert "Cannot reach Bine backend at http://localhost:8000" in out_lines[0]
        assert "uvicorn bine.app:app" in out_lines[0]


def test_missing_or_rejected_api_keys_returns_503_and_cli_single_line(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Missing or rejected Binance API keys (302/401/non-JSON) raise AuthError, return HTTP 503 on /api/quote, and print one line in CLI."""
    import asyncio
    import httpx as _httpx
    from httpx import ASGITransport, AsyncClient

    from bine.app import _QUOTE_CACHE, app, reset_rate_limits
    from bine.cli import main as cli_main
    from bine.client import BASE_URL, BinanceClient
    from bine.errors import AuthError
    from bine.quote_engine import clear_rwa_catalog_cache

    clear_rwa_catalog_cache()
    _QUOTE_CACHE.clear()
    reset_rate_limits()

    with respx.mock(assert_all_called=False) as respx_mock:
        # 1. Direct BinanceClient raises AuthError on HTTP 302 or non-JSON
        respx_mock.get(url__regex=rf"^{BASE_URL}/api/v1/dex/market/rwa/tokens.*").mock(
            return_value=_httpx.Response(
                302,
                headers={"Location": "https://web3.binance.com/en/build/rwa/tokens?chainId=56"},
                text="",
            )
        )

        async def _check_api_503() -> None:
            async with BinanceClient(api_key="", secret_key="") as bc:
                with pytest.raises(AuthError, match="Binance API keys missing or rejected"):
                    await bc.get("/api/v1/dex/market/rwa/tokens", params={"binanceChainId": "56", "platformId": "ondo"})

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                r = await ac.get("/api/quote?ticker=NVDA&amount_usd=5.50")
                assert r.status_code == 503
                assert r.json() == {"detail": "Binance API keys missing or rejected"}

        asyncio.run(_check_api_503())

        # 2. CLI prints "Binance API keys missing or rejected" as one line and exits non-zero
        monkeypatch.setenv("BINANCE_API_KEY", "")
        monkeypatch.setenv("BINANCE_SECRET_KEY", "")
        monkeypatch.delenv("BINE_API_URL", raising=False)
        respx_mock.get("http://localhost:8000/api/quote").mock(
            return_value=_httpx.Response(
                503,
                json={"detail": "Binance API keys missing or rejected"},
            )
        )
        capsys.readouterr()
        rc = cli_main(["check", "NVDA", "5.50"])
        captured = capsys.readouterr()
        out_lines = [ln for ln in captured.out.strip().splitlines() if ln.strip()]
        assert rc == 1
        assert out_lines == ["Binance API keys missing or rejected"]


