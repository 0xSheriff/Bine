"""Bine CLI — Pre-trade guard for tokenized stocks on BSC (`chainId="56"`).

Usage:
    bine check NVDA 5.50        # One plain-English line (BUY or REFUSE + reason)
    bine check NVDA 5.50 --json # Raw frozen schema_version="1" JSON
    bine buy NVDA 5.50          # Check + dry-run + y/N prompt + live swap (if BINE_LIVE_MODE=true)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

import httpx

from bine.app import _resolve_ticker_samples
from bine.client import BinanceClient, maybe_enable_dev_dns_fallback
from bine.config import Settings, get_settings
from bine.database import AsyncSessionLocal, init_db
from bine.execution import execute_trade_pipeline
from bine.quote_engine import (
    DEFAULT_QUOTE_WALLET,
    build_verdict,
    fetch_live_issuer_quote_and_liquidity,
)


def _should_use_hosted_api(cfg: Settings) -> bool:
    """Use hosted BINE_API_URL when no local Binance keys are set, or when BINE_API_URL is explicitly set in env."""
    if os.environ.get("BINE_API_URL"):
        return True
    return not bool(cfg.binance_api_key.strip() and cfg.binance_secret_key.strip())


def format_plain_check_line(result: dict[str, Any]) -> str:
    """Format a Phase 1 quote result as one plain-English line."""
    verdict = result.get("verdict")
    ticker = result.get("ticker", "")
    amount_usd = float(result.get("amount_usd") or 0.0)
    if verdict == "REFUSE":
        refusal = result.get("refusal") or {}
        code = refusal.get("code") or "refused"
        msg = refusal.get("message") or "Trade refused."
        return f"REFUSE [{code}]: {msg}"

    shares = float(result.get("shares") or 0.0)
    all_in = float(result.get("all_in_price_per_share") or 0.0)
    spread = float(result.get("spread_pct") or 0.0)
    token = result.get("token") or {}
    symbol = token.get("symbol") or ticker
    issuer = token.get("issuer") or "unknown"
    issuer_label = "Ondo" if issuer == "ondo" else "bStocks" if issuer == "bstock" else issuer
    direction = "under reference" if spread < 0 else "above reference"
    line = (
        f"BUY: Buy {shares:.4f} {ticker} ({symbol} via {issuer_label}) for ${amount_usd:.2f}. "
        f"All-in ${all_in:.2f} per share, {abs(spread):.2f}% {direction}."
    )
    alt = result.get("alternative")
    if isinstance(alt, dict) and alt.get("note"):
        line += f" ({alt['note']})"
    return line


async def run_check(
    ticker: str,
    amount_usd: float = 5.50,
    *,
    settings: Settings | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    """Run the pre-trade quote check (direct mode when keys exist, hosted BINE_API_URL otherwise)."""
    cfg = settings or get_settings()
    ticker_upper = ticker.strip().upper()

    if settings is None and _should_use_hosted_api(cfg):
        base = cfg.bine_api_url.rstrip("/")
        params: dict[str, Any] = {"ticker": ticker_upper, "amount_usd": amount_usd}
        if include_details:
            params["details"] = "true"
        async with httpx.AsyncClient(timeout=15.0) as hc:
            resp = await hc.get(f"{base}/api/quote", params=params)
            resp.raise_for_status()
            return dict(resp.json())

    maybe_enable_dev_dns_fallback(cfg.dev_dns_fallback)
    wallet = cfg.bine_wallet_address or DEFAULT_QUOTE_WALLET

    async with BinanceClient(
        api_key=cfg.binance_api_key,
        secret_key=cfg.binance_secret_key,
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

    verdict_resp = build_verdict(
        ticker=ticker_upper,
        amount_usd=amount_usd,
        evaluations=evaluations,
        max_live_trade_usd=cfg.bine_max_trade_usd,
        live_mode=cfg.bine_live_mode,
    )
    return verdict_resp.to_dict(include_details=include_details)


async def run_buy_step(
    ticker: str,
    amount_usd: float = 5.50,
    *,
    execute_live: bool = False,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Run check + dry-run (or live swap when execute_live=True) and persist to decision_log."""
    cfg = settings or get_settings()
    ticker_upper = ticker.strip().upper()

    if settings is None and not execute_live and _should_use_hosted_api(cfg):
        base = cfg.bine_api_url.rstrip("/")
        async with httpx.AsyncClient(timeout=20.0) as hc:
            resp = await hc.post(
                f"{base}/api/execute",
                json={"ticker": ticker_upper, "amount_usd": amount_usd, "execute_live": False},
            )
            resp.raise_for_status()
            return dict(resp.json())

    maybe_enable_dev_dns_fallback(cfg.dev_dns_fallback)
    await init_db()
    wallet = cfg.bine_wallet_address or DEFAULT_QUOTE_WALLET

    async with BinanceClient(
        api_key=cfg.binance_api_key,
        secret_key=cfg.binance_secret_key,
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

        verdict_resp = build_verdict(
            ticker=ticker_upper,
            amount_usd=amount_usd,
            evaluations=evaluations,
            max_live_trade_usd=cfg.bine_max_trade_usd,
            live_mode=cfg.bine_live_mode,
        )

        async with AsyncSessionLocal() as session:
            return await execute_trade_pipeline(
                session=session,
                client=client,
                verdict_resp=verdict_resp,
                evaluations=evaluations,
                settings=cfg,
                execute_live=execute_live,
                admin_token=cfg.bine_admin_token,
                require_admin_token=False,
            )


def _cmd_check(args: argparse.Namespace) -> int:
    result = asyncio.run(run_check(args.ticker, args.amount_usd, include_details=False))
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(format_plain_check_line(result))
    return 0 if result.get("verdict") == "BUY" else 2


def _cmd_buy(args: argparse.Namespace) -> int:
    settings = get_settings()
    dry_result = asyncio.run(
        run_buy_step(args.ticker, args.amount_usd, execute_live=False, settings=settings)
    )
    quote = dry_result.get("quote") or {}
    print(format_plain_check_line(quote))

    if dry_result.get("verdict") == "REFUSE":
        return 2

    sim = dry_result.get("simulation") or {}
    exec_obj = dry_result.get("execution") or {}
    sim_summary = sim.get("summary") or exec_obj.get("detail") or "Dry-run complete."
    print(f"Dry-run: {sim_summary}")

    if not sim.get("passed"):
        return 2

    if not settings.bine_live_mode:
        print("Live trading is off on this server (BINE_LIVE_MODE=false). Stopping after dry-run.")
        return 0

    if not args.yes:
        try:
            answer = input(f"Proceed with live swap of ${args.amount_usd:.2f} into {args.ticker.upper()}? [y/N]: ")
        except EOFError:
            answer = "n"
        if answer.strip().lower() not in ("y", "yes"):
            print("Cancelled.")
            return 1

    live_result = asyncio.run(
        run_buy_step(args.ticker, args.amount_usd, execute_live=True, settings=settings)
    )
    live_exec = live_result.get("execution") or {}
    print(f"Execution status: {live_exec.get('status')} — {live_exec.get('detail')}")
    if live_exec.get("tx_hash"):
        print(f"tx_hash: {live_exec['tx_hash']}")
    if live_exec.get("bsctrace_url"):
        print(f"BscTrace: {live_exec['bsctrace_url']}")
    return 0 if live_exec.get("status") == "LIVE_SUBMITTED" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bine",
        description="Bine — Pre-trade guard for tokenized stocks on BSC (uses hosted BINE_API_URL when no Binance keys are set).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Check whether a tokenized stock is safe to buy right now")
    p_check.add_argument("ticker", type=str, help="Underlying stock ticker (e.g. NVDA, AAPL, SPY)")
    p_check.add_argument("amount_usd", type=float, nargs="?", default=5.50, help="USD order amount (default: 5.50)")
    p_check.add_argument("--json", action="store_true", help="Print the frozen schema_version=1 JSON")
    p_check.set_defaults(func=_cmd_check)

    p_buy = sub.add_parser("buy", help="Run pre-trade check + dry-run simulation, then prompt for live swap")
    p_buy.add_argument("ticker", type=str, help="Underlying stock ticker (e.g. NVDA)")
    p_buy.add_argument("amount_usd", type=float, nargs="?", default=5.50, help="USD order amount (default: 5.50)")
    p_buy.add_argument("-y", "--yes", action="store_true", help="Skip interactive confirmation prompt")
    p_buy.set_defaults(func=_cmd_buy)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
