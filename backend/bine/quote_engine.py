"""Deterministic Pre-Trade Guard & Quote Engine for BINE (Phases 1 & 2)."""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from bine.client import BinanceClient
from bine.errors import BinanceAPIError
from bine.models import TokenSample
from bine.quality import assess_sample_row

SCHEMA_VERSION = "1"
BSC_CHAIN_ID = "56"
PLATFORMS = ("ondo", "bstock")
USDT_BSC_ADDRESS = "0x55d398326f99059fF775485246999027B3197955"
USDT_BSC_DECIMALS = 18
DEFAULT_QUOTE_WALLET = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"

MAX_QUOTE_USD = 2500.0
RWA_CATALOG_TTL_SECONDS = 60.0
MAX_SAMPLE_AGE_SECONDS = 120.0
MAX_SLIPPAGE_PCT = 1.00
MIN_AMM_LIQUIDITY_USD = 10_000.0
MIN_RFQ_VOLUME_24H_USD = 1_000_000.0
TIE_BAND_BPS = 5.0

_RWA_CATALOG_CACHE: tuple[float, datetime, list[TokenSample]] | None = None


def clear_rwa_catalog_cache() -> None:
    global _RWA_CATALOG_CACHE
    _RWA_CATALOG_CACHE = None


def _safe_float(val: Any) -> float | None:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


def _issuer_label(platform_id: str) -> str:
    return {"ondo": "Ondo Global Markets", "bstock": "bStocks (Backed)"}.get(platform_id, platform_id)


def _short_issuer(platform_id: str) -> str:
    return {"ondo": "Ondo", "bstock": "bStocks"}.get(platform_id, platform_id)


def _issuer_min_order_usd(platform_id: str) -> float:
    return 5.0 if platform_id == "ondo" else 0.01


def _iso_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sample_age_seconds(sampled_at: datetime | None, now: datetime) -> float | None:
    if sampled_at is None:
        return None
    if sampled_at.tzinfo is None:
        sampled_at = sampled_at.replace(tzinfo=timezone.utc)
    return max(0.0, round((now - sampled_at.astimezone(timezone.utc)).total_seconds(), 1))


def parse_rwa_token_item(token: dict[str, Any], fetched_at: datetime, latency_ms: int = 0) -> TokenSample:
    status = token.get("statusInfo") or {}
    tp, rp = _safe_float(token.get("tokenPrice")), _safe_float(token.get("referencePrice"))
    gap_pct = ((tp - rp) / rp * 100.0) if (tp is not None and rp is not None and rp > 0) else None
    return TokenSample(
        sampled_at=fetched_at,
        binance_chain_id=str(token.get("binanceChainId") or BSC_CHAIN_ID),
        token_contract_address=str(token["tokenContractAddress"]).lower(),
        platform_id=str(token["platformId"]).lower(),
        underlying_ticker=str(token.get("underlyingTicker") or "").upper(),
        token_symbol=str(token.get("tokenSymbol") or ""),
        ok=True,
        api_latency_ms=latency_ms,
        token_price=tp,
        reference_price=rp,
        token_to_share_ratio=_safe_float(token.get("tokenToShareRatio")),
        price_gap_pct=gap_pct,
        open_state=status.get("openState"),
        market_status=status.get("marketStatus"),
        reason_code=status.get("reasonCode"),
        reason_msg=status.get("reasonMsg"),
        next_open_time_ms=status.get("nextOpenTime"),
        volume_24h=_safe_float(token.get("volume24H")),
        market_cap=_safe_float(token.get("marketCap")),
    )


async def fetch_live_rwa_catalog(
    client: BinanceClient, *, ttl_seconds: float = RWA_CATALOG_TTL_SECONDS, force_refresh: bool = False
) -> tuple[datetime, list[TokenSample]]:
    global _RWA_CATALOG_CACHE
    now_mono = time.monotonic()
    if not force_refresh and _RWA_CATALOG_CACHE is not None and (now_mono - _RWA_CATALOG_CACHE[0]) < ttl_seconds:
        return _RWA_CATALOG_CACHE[1], _RWA_CATALOG_CACHE[2]
    fetched_at = datetime.now(timezone.utc)

    async def _fetch_platform(platform_id: str) -> list[TokenSample]:
        t0 = time.monotonic()
        resp = await client.get("/api/v1/dex/market/rwa/tokens", params={"binanceChainId": BSC_CHAIN_ID, "platformId": platform_id})
        lat_ms = round((time.monotonic() - t0) * 1000)
        return [parse_rwa_token_item(item, fetched_at, lat_ms) for item in (resp.get("data") or []) if item.get("tokenContractAddress")]

    ondo_rows, bstock_rows = await asyncio.gather(_fetch_platform("ondo"), _fetch_platform("bstock"))
    all_rows = sorted([*ondo_rows, *bstock_rows], key=lambda r: (r.underlying_ticker.upper(), r.platform_id))
    _RWA_CATALOG_CACHE = (now_mono, fetched_at, all_rows)
    return fetched_at, all_rows


@dataclass
class RefusalCheck:
    rule: str
    triggered: bool
    detail: str


@dataclass
class IssuerQuoteEvaluation:
    platform_id: str
    issuer_label: str
    token_symbol: str
    token_contract_address: str
    underlying_ticker: str
    sampled_at: str | None
    sample_age_seconds: float | None
    token_price: float | None
    reference_price: float | None
    token_to_share_ratio: float | None
    open_state: bool | None
    market_status: str | None
    reason_code: str | None
    volume_24h_usd: float | None
    quality_status: str
    quality_reason: str | None
    pool_count: int = 0
    top_pool_liquidity_usd: float | None = None
    total_pool_liquidity_usd: float | None = None
    depth_source: str = "none"
    quote_ok: bool = False
    quote_error: str | None = None
    quote_latency_ms: int | None = None
    quote_id: str | None = None
    vendor_name: str | None = None
    dex_name: str | None = None
    execution_mode: str | None = None
    from_token_amount_wei: str | None = None
    to_token_amount_wei: str | None = None
    quoted_token_unit_price: float | None = None
    trade_fee_usd: float | None = None
    estimate_gas_wei: str | None = None
    price_impact_pct: float | None = None
    tokens_received: float | None = None
    shares_received: float | None = None
    execution_price_per_token_usd: float | None = None
    execution_price_per_share_usd: float | None = None
    all_in_cost_usd: float | None = None
    all_in_price_per_share_usd: float | None = None
    execution_vs_reference_pct: float | None = None
    all_in_vs_reference_pct: float | None = None
    effective_slippage_pct: float | None = None
    eligible: bool = False
    refusal_code: str | None = None
    refusal_reason: str | None = None
    checks: list[RefusalCheck] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class QuoteVerdictResponse:
    schema_version: str
    ticker: str
    amount_usd: float
    quoted_at: str
    verdict: str
    token: dict[str, str] | None
    shares: float | None
    all_in_price_per_share: float | None
    reference_price_per_share: float | None
    spread_pct: float | None
    refusal: dict[str, str] | None
    alternative: dict[str, Any] | None
    market: dict[str, Any]
    recommended_platform: str | None = None
    recommended_symbol: str | None = None
    recommended_contract_address: str | None = None
    reason: str = ""
    why_others_lost: list[str] = field(default_factory=list)
    live_execution_allowed: bool = False
    max_live_trade_usd: float = 6.00
    issuers: list[dict[str, Any]] = field(default_factory=list)
    tiebreak_applied: bool = False

    def to_dict(self, *, include_details: bool = False) -> dict[str, Any]:
        base: dict[str, Any] = {
            "schema_version": self.schema_version,
            "ticker": self.ticker,
            "amount_usd": self.amount_usd,
            "quoted_at": self.quoted_at,
            "verdict": self.verdict,
            "token": self.token,
            "shares": self.shares,
            "all_in_price_per_share": self.all_in_price_per_share,
            "reference_price_per_share": self.reference_price_per_share,
            "spread_pct": self.spread_pct,
            "refusal": self.refusal,
            "alternative": self.alternative,
            "market": self.market,
        }
        if include_details:
            base["details"] = {
                "tiebreak_applied": self.tiebreak_applied,
                "live_execution_allowed": self.live_execution_allowed,
                "max_live_trade_usd": self.max_live_trade_usd,
                "issuers": [
                    {
                        "symbol": i.get("token_symbol"),
                        "issuer": i.get("platform_id"),
                        "issuer_label": i.get("issuer_label"),
                        "address": i.get("token_contract_address"),
                        "eligible": i.get("eligible"),
                        "shares": i.get("shares_received"),
                        "tokens_received": i.get("tokens_received"),
                        "token_to_share_ratio": i.get("token_to_share_ratio"),
                        "all_in_price_per_share": i.get("all_in_price_per_share_usd"),
                        "reference_price_per_share": i.get("reference_price"),
                        "spread_pct": i.get("all_in_vs_reference_pct"),
                        "slippage_pct": i.get("effective_slippage_pct"),
                        "depth_usd": i.get("total_pool_liquidity_usd") or i.get("volume_24h_usd"),
                        "depth_source": i.get("depth_source"),
                        "pool_count": i.get("pool_count"),
                        "route": f"{i.get('vendor_name')} ({i.get('dex_name') or i.get('execution_mode')})" if i.get("vendor_name") else None,
                        "execution_note": (
                            "Aggregator quote is indicative for live baw execution (Ondo uses /ondo/place-order)."
                            if i.get("platform_id") == "ondo"
                            else "Matches DEX aggregator /web-dex/agent/place-order path."
                        ),
                        "latency_ms": i.get("quote_latency_ms"),
                        "refusal_code": i.get("refusal_code"),
                        "refusal_message": i.get("refusal_reason"),
                        "bsctrace_url": f"https://bsctrace.com/token/{i.get('token_contract_address')}",
                    }
                    for i in self.issuers
                ],
            }
        return base


def summarize_liquidity_pools(pools_data: list[dict[str, Any]] | None, volume_24h_usd: float | None) -> tuple[int, float | None, float | None, str]:
    pools = pools_data or []
    non_null = [fval for p in pools if (fval := _safe_float(p.get("liquidityUsd"))) is not None and fval > 0]
    if non_null:
        return len(pools), round(max(non_null), 2), round(sum(non_null), 2), "amm_pools"
    if pools and volume_24h_usd and volume_24h_usd > 0:
        return len(pools), None, None, "pmm_rfq_24h_volume"
    return len(pools), None, None, "none"


def _is_below_issuer_minimum_error(quote_error: str | None, platform_id: str, amount_usd: float) -> bool:
    if not quote_error:
        return False
    err_low = quote_error.lower()
    if "40375" in err_low or "minimum order amount" in err_low or "min order" in err_low:
        return True
    return platform_id == "ondo" and 0 < amount_usd < 5.0 and "no route" in err_low


def _parse_price_impact_pct(raw_val: Any) -> float | None:
    """Convert Binance `priceImpactPercent` (returned as a 0-1 fraction like '0.2974' for 29.74%) into %."""
    val = _safe_float(raw_val)
    return round(val * 100.0, 4) if val is not None else None


def evaluate_issuer_quote(
    sample: TokenSample,
    amount_usd: float,
    quote_response: dict[str, Any] | None,
    liquidity_response: dict[str, Any] | None,
    *,
    quote_error: str | None = None,
    quote_latency_ms: int | None = None,
    now: datetime | None = None,
    max_quote_usd: float = MAX_QUOTE_USD,
    max_sample_age_seconds: float = MAX_SAMPLE_AGE_SECONDS,
    max_slippage_pct: float = MAX_SLIPPAGE_PCT,
    min_amm_liquidity_usd: float = MIN_AMM_LIQUIDITY_USD,
    min_rfq_volume_24h_usd: float = MIN_RFQ_VOLUME_24H_USD,
) -> IssuerQuoteEvaluation:
    eval_now = now or datetime.now(timezone.utc)
    qc = assess_sample_row(sample)
    age_s = _sample_age_seconds(sample.sampled_at, eval_now)
    short_issuer = _short_issuer(sample.platform_id)
    pools_list = (liquidity_response or {}).get("data") if isinstance(liquidity_response, dict) else None
    pool_count, top_liq, total_liq, depth_source = summarize_liquidity_pools(pools_list, sample.volume_24h)

    ev = IssuerQuoteEvaluation(
        platform_id=sample.platform_id,
        issuer_label=_issuer_label(sample.platform_id),
        token_symbol=sample.token_symbol,
        token_contract_address=sample.token_contract_address,
        underlying_ticker=sample.underlying_ticker.upper(),
        sampled_at=_iso_utc(sample.sampled_at),
        sample_age_seconds=age_s,
        token_price=sample.token_price,
        reference_price=sample.reference_price,
        token_to_share_ratio=sample.token_to_share_ratio,
        open_state=sample.open_state,
        market_status=sample.market_status,
        reason_code=sample.reason_code,
        volume_24h_usd=sample.volume_24h,
        quality_status=qc.status,
        quality_reason=qc.reason,
        pool_count=pool_count,
        top_pool_liquidity_usd=top_liq,
        total_pool_liquidity_usd=total_liq,
        depth_source=depth_source,
        quote_latency_ms=quote_latency_ms,
    )

    routes = (quote_response or {}).get("data") if isinstance(quote_response, dict) else None
    if quote_error:
        ev.quote_ok, ev.quote_error = False, quote_error
    elif isinstance(routes, list) and routes:
        best_route = next((r for r in routes if r.get("isBest")), routes[0])
        ev.quote_ok = True
        ev.quote_id = best_route.get("quoteId")
        ev.vendor_name = best_route.get("vendorName")
        ev.execution_mode = best_route.get("executionMode")
        ev.from_token_amount_wei = best_route.get("fromTokenAmount")
        ev.to_token_amount_wei = best_route.get("toTokenAmount")
        ev.estimate_gas_wei = best_route.get("estimateGasFee")
        dex_names = [d.get("dexProtocol", {}).get("dexName") for d in (best_route.get("dexRouterList") or []) if d.get("dexProtocol", {}).get("dexName")]
        if dex_names:
            ev.dex_name = " → ".join(dex_names)

        to_tok_info = best_route.get("toToken") or {}
        ev.quoted_token_unit_price = _safe_float(to_tok_info.get("tokenUnitPrice"))
        fee_f = _safe_float(best_route.get("tradeFee"))
        ev.trade_fee_usd = round(fee_f, 4) if fee_f is not None else None
        ev.price_impact_pct = _parse_price_impact_pct(best_route.get("priceImpactPercent"))

        try:
            to_decimals = int(to_tok_info.get("decimal") or 18)
        except (TypeError, ValueError):
            to_decimals = 18
        try:
            tokens_out = int(best_route["toTokenAmount"]) / (10 ** to_decimals)
        except (KeyError, TypeError, ValueError):
            tokens_out = 0.0

        ratio = sample.token_to_share_ratio if (sample.token_to_share_ratio and sample.token_to_share_ratio > 0) else 1.0
        shares_out = tokens_out * ratio
        if tokens_out > 0 and shares_out > 0 and amount_usd > 0:
            ev.tokens_received = round(tokens_out, 8)
            ev.shares_received = round(shares_out, 8)
            ev.execution_price_per_token_usd = round(amount_usd / tokens_out, 4)
            ev.execution_price_per_share_usd = round(amount_usd / shares_out, 4)
            all_in_usd = amount_usd + (ev.trade_fee_usd or 0.0)
            ev.all_in_cost_usd = round(all_in_usd, 4)
            ev.all_in_price_per_share_usd = round(all_in_usd / shares_out, 4)
            if sample.reference_price and sample.reference_price > 0:
                exec_vs_ref = (ev.execution_price_per_share_usd - sample.reference_price) / sample.reference_price * 100.0
                all_in_vs_ref = (ev.all_in_price_per_share_usd - sample.reference_price) / sample.reference_price * 100.0
                ev.execution_vs_reference_pct = round(exec_vs_ref, 4)
                ev.all_in_vs_reference_pct = round(all_in_vs_ref, 4)
                ev.effective_slippage_pct = round(max(abs(exec_vs_ref), abs(ev.price_impact_pct or 0.0)), 4)
        else:
            ev.quote_ok, ev.quote_error = False, "Quote returned zero token output"
    else:
        ev.quote_ok, ev.quote_error = False, "No route returned by Trading API /quote"

    checks: list[RefusalCheck] = []

    # Rule 1: amount_over_cap
    over_cap = amount_usd <= 0 or amount_usd > max_quote_usd
    cap_msg = (
        f"${amount_usd:,.2f} is over the ${max_quote_usd:,.0f} safety limit for a single check. Not buying."
        if amount_usd > max_quote_usd
        else ("Trade amount must be greater than $0. Not buying." if amount_usd <= 0 else f"${amount_usd:,.2f} is within the ${max_quote_usd:,.0f} safety limit.")
    )
    checks.append(RefusalCheck(rule="amount_over_cap", triggered=over_cap, detail=cap_msg))

    # Rule 2: quality_unreliable
    unreliable = not qc.reliable
    if unreliable:
        if sample.token_price is not None and sample.token_price < 1.00:
            qual_msg = f"{sample.token_symbol} trades at ${sample.token_price:.4f} (under the $1.00 minimum price filter). Data is unreliable. Not buying."
        elif sample.reference_price is not None and sample.reference_price < 1.00:
            qual_msg = f"{sample.token_symbol} has a reference price of ${sample.reference_price:.4f} (under the $1.00 minimum). Data is unreliable. Not buying."
        elif sample.token_to_share_ratio is not None and (sample.token_to_share_ratio < 0.25 or sample.token_to_share_ratio > 5.0):
            qual_msg = (
                f"{sample.token_symbol} has a share ratio of {sample.token_to_share_ratio:.4f}. "
                f"Its token price ${(sample.token_price or 0):,.2f} is {sample.token_to_share_ratio:.4f}x "
                f"the ${(sample.reference_price or 0):,.2f} per-share reference, as the ratio predicts. "
                f"Ratios outside 0.25-5.00x are not supported by this tool, because quoted amounts for them "
                f"have not been checked against a live trade. Not buying."
            )
        elif sample.volume_24h is None or sample.volume_24h < 1_000_000:
            qual_msg = f"{sample.token_symbol} has only ${(sample.volume_24h or 0):,.0f} in 24-hour volume (under the $1M minimum). Too illiquid. Not buying."
        else:
            qual_msg = f"{sample.token_symbol} failed data quality checks ({qc.reason}). Not buying."
    else:
        qual_msg = "Token passed data quality checks."
    checks.append(RefusalCheck(rule="quality_unreliable", triggered=unreliable, detail=qual_msg))

    # Rule 3: market_closed
    quote_err_str = ev.quote_error or ""
    is_40367_or_40369 = (
        "40367" in quote_err_str
        or "40369" in quote_err_str
        or "non-trading session" in quote_err_str.lower()
    )
    market_closed = (
        is_40367_or_40369
        or sample.open_state is not True
        or (sample.reason_code is not None and sample.reason_code != "TRADING")
        or sample.market_status in ("paused", "closed")
    )
    if market_closed:
        if is_40367_or_40369:
            session_label = sample.market_status or sample.reason_code or "closed"
            open_note = ""
            if "Expected to open in " in quote_err_str:
                open_part = quote_err_str.split("Expected to open in ", 1)[1].strip().rstrip(".")
                if open_part:
                    open_note = f" Expected to open in {open_part}."
            market_msg = f"{sample.token_symbol} is in a non-trading session ({session_label}).{open_note} Not buying."
        else:
            market_msg = (
                f"{short_issuer} trading for {sample.token_symbol} is currently {sample.market_status or 'closed'} ({sample.reason_code or 'session paused'}). Not buying while the session is paused or closed."
            )
    else:
        market_msg = f"Trading is open on {short_issuer} ({sample.market_status or '24/7 DEX'})."
    checks.append(RefusalCheck(rule="market_closed", triggered=market_closed, detail=market_msg))

    # Rule 4: reference_stale
    ref_missing = sample.reference_price is None or sample.reference_price <= 0
    ref_stale = ref_missing or age_s is None or age_s > max_sample_age_seconds
    if ref_missing:
        stale_msg = f"No reference stock price is available for {sample.token_symbol} right now. Not buying."
    elif age_s is None:
        stale_msg = f"The reference price timestamp for {sample.token_symbol} is missing. Not buying."
    elif age_s > max_sample_age_seconds:
        stale_msg = f"The reference price for {sample.token_symbol} is {int(round(age_s))} seconds old (over the {int(max_sample_age_seconds)}s freshness limit). Not buying without a fresh price."
    else:
        stale_msg = f"Reference price ${sample.reference_price:,.2f} is fresh ({int(round(age_s))}s old)."
    checks.append(RefusalCheck(rule="reference_stale", triggered=ref_stale, detail=stale_msg))

    # Rule 5: below_issuer_minimum
    below_min = _is_below_issuer_minimum_error(ev.quote_error, sample.platform_id, amount_usd)
    if below_min:
        if amount_usd < 5.0:
            min_msg = f"{short_issuer}'s minimum order is $5 (you entered ${amount_usd:,.2f}). Try $5.50."
        else:
            min_msg = f"{short_issuer}'s minimum order is $5. After conversion your ${amount_usd:,.2f} lands just under it. Try $5.50."
    else:
        min_msg = f"Order size ${amount_usd:,.2f} meets {short_issuer} minimum."
    checks.append(RefusalCheck(rule="below_issuer_minimum", triggered=below_min, detail=min_msg))

    # Rule 6: depth_thin
    depth_thin = False
    if below_min:
        depth_detail = min_msg
    elif market_closed and not ev.quote_ok:
        depth_detail = market_msg
    elif not ev.quote_ok:
        depth_thin = True
        depth_detail = f"No pool on BNB Chain can fill ${amount_usd:,.2f} of {sample.token_symbol} right now. Not buying."
    elif total_liq is not None:
        if total_liq < min_amm_liquidity_usd or total_liq < amount_usd * 10:
            depth_thin = True
            depth_detail = f"Pool depth for {sample.token_symbol} on {short_issuer} is only ${total_liq:,.0f}, which is too thin for a safe ${amount_usd:,.2f} fill. Not buying."
        else:
            depth_detail = f"Pool depth is ${total_liq:,.0f} across {pool_count} pools."
    else:
        vol24 = sample.volume_24h or 0.0
        if vol24 < min_rfq_volume_24h_usd:
            depth_thin = True
            depth_detail = f"24-hour volume for {sample.token_symbol} on {short_issuer} is only ${vol24:,.0f} (under the $1M minimum). Liquidity is too thin. Not buying."
        else:
            depth_detail = f"24-hour volume is ${vol24:,.0f} across {pool_count} pools."
    checks.append(RefusalCheck(rule="depth_thin", triggered=depth_thin, detail=depth_detail))

    # Rule 7: slippage_too_high
    slip_val = ev.effective_slippage_pct
    slip_high = not ev.quote_ok or slip_val is None or slip_val > max_slippage_pct
    if not ev.quote_ok or slip_val is None:
        slip_detail = "Cannot verify slippage without a valid quote and reference price."
    elif slip_val > max_slippage_pct:
        exec_spread = ev.execution_vs_reference_pct
        if exec_spread is not None and abs(exec_spread) >= abs(ev.price_impact_pct or 0.0):
            abs_sp = abs(exec_spread)
            pct_str = f"{abs_sp:.0f}%" if abs_sp >= 5.0 else f"{abs_sp:.2f}%"
            if exec_spread < 0:
                slip_detail = (
                    f"{short_issuer} quote implies a fill about {pct_str} below the reference price "
                    f"(${ev.execution_price_per_share_usd:,.2f} vs ${sample.reference_price:,.2f} reference). "
                    f"Quotes this far in the buyer's favor usually point to a unit or pricing problem, "
                    f"and this tool does not trust it. Not buying."
                )
            else:
                slip_detail = f"{short_issuer} would fill you about {pct_str} above the market price (${ev.execution_price_per_share_usd:,.2f} vs ${sample.reference_price:,.2f} reference). Not buying."
        else:
            slip_detail = f"{short_issuer} has {slip_val:.2f}% price impact (over the {max_slippage_pct:.2f}% limit). Not buying."
    else:
        slip_detail = f"Execution spread {ev.execution_vs_reference_pct:+.2f}% is within the {max_slippage_pct:.2f}% limit."
    checks.append(RefusalCheck(rule="slippage_too_high", triggered=slip_high, detail=slip_detail))

    ev.checks = checks
    triggered = [c for c in checks if c.triggered]
    ev.eligible = not bool(triggered)
    if not triggered:
        ev.refusal_code = None
        ev.refusal_reason = None
    else:
        by_rule = {c.rule: c for c in triggered}
        is_40374 = "40374" in quote_err_str or "insufficient liquidity" in quote_err_str.lower()
        is_quarantined = (
            (sample.token_price is not None and sample.token_price < 1.00)
            or (sample.reference_price is not None and sample.reference_price < 1.00)
        )
        if "amount_over_cap" in by_rule:
            ev.refusal_code = "amount_over_cap"
            ev.refusal_reason = by_rule["amount_over_cap"].detail
        elif is_quarantined and "quality_unreliable" in by_rule:
            ev.refusal_code = "quality_unreliable"
            ev.refusal_reason = by_rule["quality_unreliable"].detail
        elif is_40367_or_40369 and "market_closed" in by_rule:
            ev.refusal_code = "market_closed"
            ev.refusal_reason = by_rule["market_closed"].detail
        elif "depth_thin" in by_rule and (is_40374 or not ev.quote_ok or "quality_unreliable" not in by_rule):
            ev.refusal_code = "depth_thin"
            ev.refusal_reason = by_rule["depth_thin"].detail
        else:
            ev.refusal_code = triggered[0].rule
            ev.refusal_reason = triggered[0].detail
    return ev


def _deterministic_tiebreak_key(ev: IssuerQuoteEvaluation) -> tuple[float, float, str, str]:
    return (-(ev.total_pool_liquidity_usd or 0.0), _issuer_min_order_usd(ev.platform_id), ev.platform_id, ev.token_symbol)


def _derive_market_summary(evaluations: list[IssuerQuoteEvaluation]) -> dict[str, Any]:
    if not evaluations:
        return {"status": "unknown", "open": False}
    ondo_ev = next((e for e in evaluations if e.platform_id == "ondo" and e.market_status), None)
    any_open = any(e.open_state is True for e in evaluations)
    if ondo_ev and ondo_ev.market_status:
        status_str = str(ondo_ev.market_status)
    else:
        first_status = next((e.market_status for e in evaluations if e.market_status), None)
        status_str = str(first_status) if first_status else ("open" if any_open else "closed")
    return {"status": status_str, "open": bool(any_open)}


def build_verdict(
    ticker: str,
    amount_usd: float,
    evaluations: list[IssuerQuoteEvaluation],
    *,
    max_live_trade_usd: float = 6.00,
    live_mode: bool = False,
    now: datetime | None = None,
    tie_band_bps: float = TIE_BAND_BPS,
) -> QuoteVerdictResponse:
    eval_now = now or datetime.now(timezone.utc)
    quoted_at = _iso_utc(eval_now) or ""
    ticker_upper = ticker.strip().upper()
    market_obj = _derive_market_summary(evaluations)

    if not evaluations:
        msg = f"We couldn't find a tokenized version of {ticker_upper} on BNB Chain. Not buying."
        return QuoteVerdictResponse(
            schema_version=SCHEMA_VERSION, ticker=ticker_upper, amount_usd=round(amount_usd, 2), quoted_at=quoted_at,
            verdict="REFUSE", token=None, shares=None, all_in_price_per_share=None, reference_price_per_share=None,
            spread_pct=None, refusal={"code": "unknown_ticker", "message": msg}, alternative=None,
            market={"status": "unknown", "open": False}, reason=msg, max_live_trade_usd=max_live_trade_usd,
        )

    eligible = [e for e in evaluations if e.eligible and e.all_in_price_per_share_usd is not None]
    ineligible = [e for e in evaluations if not e.eligible]
    why_others_lost: list[str] = []

    if not eligible:
        refusal_priority = {
            "amount_over_cap": 0, "depth_thin": 1, "quality_unreliable": 2, "market_closed": 3,
            "reference_stale": 4, "slippage_too_high": 5, "below_issuer_minimum": 6,
        }
        ordered_bad = sorted(evaluations, key=lambda e: (refusal_priority.get(e.refusal_code or "", 99), _deterministic_tiebreak_key(e)))
        primary = ordered_bad[0]
        ref_code = primary.refusal_code or "depth_thin"
        ref_msg = primary.refusal_reason or f"No safe route found for {ticker_upper}. Not buying."
        alt_obj = (
            {
                "symbol": ordered_bad[1].token_symbol,
                "issuer": ordered_bad[1].platform_id,
                "eligible": False,
                "note": f"Also checked {ordered_bad[1].token_symbol} on {_short_issuer(ordered_bad[1].platform_id)}: {ordered_bad[1].refusal_reason}",
            }
            if len(ordered_bad) >= 2
            else None
        )
        why_others_lost = [f"{e.token_symbol} ({_short_issuer(e.platform_id)}): {e.refusal_reason}" for e in evaluations]
        return QuoteVerdictResponse(
            schema_version=SCHEMA_VERSION, ticker=ticker_upper, amount_usd=round(amount_usd, 2), quoted_at=quoted_at,
            verdict="REFUSE", token=None, shares=None, all_in_price_per_share=None,
            reference_price_per_share=round(primary.reference_price, 2) if primary.reference_price else None,
            spread_pct=round(primary.all_in_vs_reference_pct, 2) if primary.all_in_vs_reference_pct is not None else None,
            refusal={"code": ref_code, "message": ref_msg}, alternative=alt_obj, market=market_obj,
            reason=ref_msg, why_others_lost=why_others_lost, max_live_trade_usd=max_live_trade_usd,
            issuers=[e.to_dict() for e in evaluations],
        )

    tiebreak_applied = False
    alt_obj = None
    if len(eligible) >= 2:
        by_price = sorted(eligible, key=lambda e: (e.all_in_price_per_share_usd or float("inf"), _deterministic_tiebreak_key(e)))
        cheapest, second = by_price[0], by_price[1]
        c_price = cheapest.all_in_price_per_share_usd or 1.0
        s_price = second.all_in_price_per_share_usd or c_price
        gap_bps = ((s_price - c_price) / c_price * 10_000.0) if c_price > 0 else 0.0

        if gap_bps <= tie_band_bps:
            tiebreak_applied = True
            winner, runner = sorted(eligible, key=_deterministic_tiebreak_key)[:2]
            diff = (runner.all_in_price_per_share_usd or 0.0) - (winner.all_in_price_per_share_usd or 0.0)
            alt_note = f"Either works (within {tie_band_bps:.0f} bps). Also checked {runner.token_symbol} on {_short_issuer(runner.platform_id)}: ${abs(diff):.2f} per share {'more' if diff >= 0 else 'less'}."
        else:
            winner, runner = cheapest, second
            diff = (runner.all_in_price_per_share_usd or 0.0) - (winner.all_in_price_per_share_usd or 0.0)
            alt_note = f"Also checked {runner.token_symbol} on {_short_issuer(runner.platform_id)}: ${diff:.2f} per share more."
        alt_obj = {"symbol": runner.token_symbol, "issuer": runner.platform_id, "eligible": True, "note": alt_note}
        why_others_lost.append(alt_note)
    else:
        winner = eligible[0]
        if ineligible:
            other = ineligible[0]
            alt_note = f"Also checked {other.token_symbol} on {_short_issuer(other.platform_id)}: {other.refusal_reason}"
            alt_obj = {"symbol": other.token_symbol, "issuer": other.platform_id, "eligible": False, "note": alt_note}
            why_others_lost.append(alt_note)

    shares_val = round(winner.shares_received or 0.0, 6)
    all_in_val = round(winner.all_in_price_per_share_usd or 0.0, 2)
    ref_val = round(winner.reference_price or 0.0, 2)
    spread_val = round(winner.all_in_vs_reference_pct or 0.0, 2)
    spread_dir = "under" if spread_val < 0 else ("over" if spread_val > 0 else "at")
    spread_phrase = "at reference" if abs(spread_val) < 0.005 else f"{abs(spread_val):.2f}% {spread_dir} reference"
    reason = f"Buy {shares_val:.4f} {ticker_upper} ({winner.token_symbol} on {_short_issuer(winner.platform_id)}) for ${amount_usd:,.2f}. All-in ${all_in_val:,.2f} per share, {spread_phrase}."

    return QuoteVerdictResponse(
        schema_version=SCHEMA_VERSION, ticker=ticker_upper, amount_usd=round(amount_usd, 2), quoted_at=quoted_at,
        verdict="BUY", token={"symbol": winner.token_symbol, "address": winner.token_contract_address, "issuer": winner.platform_id},
        shares=shares_val, all_in_price_per_share=all_in_val, reference_price_per_share=ref_val, spread_pct=spread_val,
        refusal=None, alternative=alt_obj, market=market_obj, recommended_platform=winner.platform_id,
        recommended_symbol=winner.token_symbol, recommended_contract_address=winner.token_contract_address,
        reason=reason, why_others_lost=why_others_lost, live_execution_allowed=bool(live_mode and 0 < amount_usd <= max_live_trade_usd),
        max_live_trade_usd=max_live_trade_usd, issuers=[e.to_dict() for e in evaluations], tiebreak_applied=tiebreak_applied,
    )


async def fetch_live_issuer_quote_and_liquidity(
    client: BinanceClient, sample: TokenSample, amount_usd: float, wallet_address: str = DEFAULT_QUOTE_WALLET
) -> IssuerQuoteEvaluation:
    amount_wei = str(max(1, int(round(amount_usd * (10 ** USDT_BSC_DECIMALS)))))
    addr = sample.token_contract_address
    user_wallet = wallet_address or DEFAULT_QUOTE_WALLET
    quote_resp: dict[str, Any] | None = None
    quote_err: str | None = None
    quote_latency_ms: int | None = None
    liq_resp: dict[str, Any] | None = None

    async def _call_quote() -> None:
        nonlocal quote_resp, quote_err, quote_latency_ms
        qt0 = time.monotonic()
        try:
            quote_resp = await client.get(
                "/api/v1/dex/aggregator/quote",
                params={"binanceChainId": BSC_CHAIN_ID, "fromTokenAddress": USDT_BSC_ADDRESS, "toTokenAddress": addr, "amount": amount_wei, "userWalletAddress": user_wallet},
            )
            quote_latency_ms = round((time.monotonic() - qt0) * 1000)
        except BinanceAPIError as exc:
            quote_latency_ms = round((time.monotonic() - qt0) * 1000)
            quote_err = f"[{exc.code}] {exc.msg}"
        except Exception as exc:
            quote_latency_ms = round((time.monotonic() - qt0) * 1000)
            quote_err = f"{type(exc).__name__}: {exc}"

    async def _call_liquidity() -> None:
        nonlocal liq_resp
        try:
            liq_resp = await client.get("/api/v1/dex/market/token/top-liquidity", params={"binanceChainId": BSC_CHAIN_ID, "tokenContractAddress": addr})
        except Exception:
            liq_resp = None

    await asyncio.gather(_call_quote(), _call_liquidity())
    return evaluate_issuer_quote(
        sample=sample, amount_usd=amount_usd, quote_response=quote_resp, liquidity_response=liq_resp, quote_error=quote_err, quote_latency_ms=quote_latency_ms
    )
