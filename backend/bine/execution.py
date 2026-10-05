"""Safe Execution Engine for BINE (`POST /api/execute`, `bine buy`, MCP `bine_buy`).

Implements the strict 4-stage pre-trade guard and execution pipeline:
  1. Run deterministic Pre-Trade Guard (`GET /api/v1/dex/aggregator/quote` + `/top-liquidity`)
     and check all 8 refusal rules. If refused, log to `decision_log` with `execution_status="REFUSED"`
     and stop immediately.
  2. Build unsigned swap transaction (`GET /api/v1/dex/aggregator/swap`) and dry-run it through
     the Binance Transaction API (`POST /api/v1/dex/pre-transaction/simulate`).
     - If the swap simulation reverts with `"BEP20: transfer amount exceeds allowance"`,
       fetch the ERC-20 approval calldata (`GET /api/v1/dex/aggregator/approve-transaction`)
       and simulate the approval via `/api/v1/dex/pre-transaction/simulate` (`status="SUCCESS"`,
       `allowanceChanges` populated), returning `status="REQUIRES_APPROVAL"`, `passed=True`
       along with the unsigned `approve_tx` payload.
  3. Only if `execute_live=True` was requested AND the dry-run passed:
     - Check admin token (`BINE_ADMIN_TOKEN`), hard per-trade cap (`BINE_MAX_TRADE_USD`, default `$6.00`),
       daily cap (`BINE_DAILY_CAP_USD`, default `$10.00`), and `BINE_LIVE_MODE=true`.
     - Execute through Binance Agentic Wallet CLI (`baw market-order swap ... --json`), and if
       `orderId` is returned, poll `baw market-order list --orderId <orderId> --json` until
       terminal status (`FINISHED` with `txHash`, or `FAILED`).
  4. Persist every decision, refusal, dry-run simulation, and tx hash in the `decision_log` table.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from bine.client import BinanceClient
from bine.config import Settings
from bine.errors import BinanceAPIError
from bine.models import DecisionLog
from bine.quote_engine import (
    DEFAULT_QUOTE_WALLET,
    USDT_BSC_ADDRESS,
    USDT_BSC_DECIMALS,
    IssuerQuoteEvaluation,
    QuoteVerdictResponse,
)

BSCTRACE_TX_URL_PREFIX = "https://bsctrace.com/tx/"
BSC_PUBLIC_RPC_URL = "https://bsc-dataseed.binance.org"
BAW_ROUTER_ADDRESS = "0xb300000b72DEAEb607a12d5f54773D1C19c7028d"
SIMULATION_ROUTER_ADDRESS = "0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5"
PLAIN_ROUTER_APPROVAL_SUMMARY = (
    "Simulation passed. Simulation router 0xB444... has no USDT allowance; "
    "live swaps via baw execute through router 0xb300...."
)
BAW_SUFFICIENT_ALLOWANCE_SUMMARY = (
    "Simulation router 0xB444... has no allowance; baw router 0xb300... "
    "already has sufficient allowance, so no approve tx is expected."
)


async def _query_usdt_allowance_wei(
    owner_address: str,
    spender_address: str = BAW_ROUTER_ADDRESS,
    *,
    rpc_url: str = BSC_PUBLIC_RPC_URL,
) -> int | None:
    """Query on-chain ERC-20 `allowance(owner, spender)` on BSC USDT via `eth_call`.
    Returns `None` on any RPC or parsing error so RPC failures never block a quote or buy.
    """
    import httpx as _httpx

    clean_owner = owner_address.strip()
    clean_spender = spender_address.strip()
    if not clean_owner.startswith("0x") or len(clean_owner) != 42:
        return None
    if not clean_spender.startswith("0x") or len(clean_spender) != 42:
        return None
    call_data = "0xdd62ed3e" + clean_owner[2:].lower().zfill(64) + clean_spender[2:].lower().zfill(64)
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": USDT_BSC_ADDRESS, "data": call_data}, "latest"],
    }
    try:
        async with _httpx.AsyncClient(timeout=3.0) as hc:
            resp = await hc.post(rpc_url, json=payload)
            resp.raise_for_status()
            body = resp.json()
            result_hex = body.get("result")
            if isinstance(result_hex, str) and result_hex.startswith("0x") and len(result_hex) > 2:
                return int(result_hex, 16)
    except Exception:
        return None
    return None


async def _build_requires_approval_summary(
    wallet_address: str | None,
    amount_wei: str,
) -> str:
    """Return the human-readable dry-run summary when `/pre-transaction/simulate` reports
    `REQUIRES_APPROVAL` on the aggregator router (`0xB444...`).
    """
    w = (wallet_address or "").strip()
    if not w or w.lower() == DEFAULT_QUOTE_WALLET.lower():
        return PLAIN_ROUTER_APPROVAL_SUMMARY
    try:
        needed_wei = max(1, int(amount_wei))
    except ValueError:
        needed_wei = 1
    allowance_wei = await _query_usdt_allowance_wei(w, BAW_ROUTER_ADDRESS)
    if allowance_wei is not None and allowance_wei >= needed_wei:
        return BAW_SUFFICIENT_ALLOWANCE_SUMMARY
    return PLAIN_ROUTER_APPROVAL_SUMMARY


@dataclass
class DryRunSimulationResult:
    ran: bool = False
    passed: bool = False
    status: str = "SKIPPED"  # "SUCCESS" | "REQUIRES_APPROVAL" | "FAILED" | "SKIPPED"
    fail_reason: str | None = None
    swap_tx_to: str | None = None
    swap_tx_value: str | None = None
    swap_tx_gas_limit: str | None = None
    swap_tx_gas_price: str | None = None
    swap_tx_calldata_bytes: int = 0
    swap_balance_changes: list[dict[str, Any]] = field(default_factory=list)
    approval_required: bool = False
    approval_simulation_status: str | None = None
    approval_spender: str | None = None
    approval_calldata: str | None = None
    approval_allowance_changes: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LiveExecutionResult:
    attempted: bool = False
    live_mode_enabled: bool = False
    status: str = "DRY_RUN_ONLY"
    order_id: str | None = None
    tx_hash: str | None = None
    bsctrace_url: str | None = None
    baw_command: str | None = None
    detail: str = ""
    raw_output: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


async def run_transaction_dry_run(
    client: BinanceClient,
    winner: IssuerQuoteEvaluation,
    amount_usd: float,
    wallet_address: str = DEFAULT_QUOTE_WALLET,
    slippage_percent: str = "0.5",
) -> DryRunSimulationResult:
    """Build unsigned swap via `/aggregator/swap` and dry-run via `/pre-transaction/simulate`."""
    user_wallet = wallet_address or DEFAULT_QUOTE_WALLET
    amount_wei = winner.from_token_amount_wei or str(
        max(1, int(round(amount_usd * (10 ** USDT_BSC_DECIMALS))))
    )
    quote_id = winner.quote_id
    if not quote_id:
        return DryRunSimulationResult(
            ran=False,
            passed=False,
            status="FAILED",
            fail_reason="Missing quoteId from Trading API quote",
            summary="Simulation failed: quote did not return a quoteId.",
        )

    # Step 1: Build unsigned swap transaction from the quoteId
    try:
        swap_resp = await client.get(
            "/api/v1/dex/aggregator/swap",
            params={
                "binanceChainId": "56",
                "quoteId": quote_id,
                "fromTokenAddress": USDT_BSC_ADDRESS,
                "toTokenAddress": winner.token_contract_address,
                "amount": amount_wei,
                "userWalletAddress": user_wallet,
                "slippagePercent": slippage_percent,
            },
        )
    except BinanceAPIError as exc:
        return DryRunSimulationResult(
            ran=True,
            passed=False,
            status="FAILED",
            fail_reason=f"[/aggregator/swap {exc.code}] {exc.msg}",
            summary=f"Simulation failed while building swap calldata: [{exc.code}] {exc.msg}",
        )
    except Exception as exc:
        return DryRunSimulationResult(
            ran=True,
            passed=False,
            status="FAILED",
            fail_reason=f"{type(exc).__name__}: {exc}",
            summary=f"Simulation failed while building swap calldata: {type(exc).__name__}: {exc}",
        )

    swap_data = swap_resp.get("data") or {}
    tx_obj = swap_data.get("tx") or {}
    if not tx_obj.get("to") or not tx_obj.get("data"):
        return DryRunSimulationResult(
            ran=True,
            passed=False,
            status="FAILED",
            fail_reason="Swap endpoint did not return EVM transaction calldata (data.tx)",
            summary="Simulation failed: /aggregator/swap did not return EVM tx calldata.",
        )

    calldata_hex = str(tx_obj.get("data") or "0x")
    calldata_bytes = max(0, (len(calldata_hex) - 2) // 2) if calldata_hex.startswith("0x") else 0

    evm_tx = {
        "from": tx_obj.get("from") or user_wallet,
        "to": tx_obj["to"],
        "value": str(tx_obj.get("value") or "0"),
        "data": calldata_hex,
    }

    # Step 2: Simulate swap transaction via POST /api/v1/dex/pre-transaction/simulate
    try:
        sim_resp = await client.post(
            "/api/v1/dex/pre-transaction/simulate",
            body={
                "binanceChainId": "56",
                "evmTx": evm_tx,
            },
        )
    except BinanceAPIError as exc:
        return DryRunSimulationResult(
            ran=True,
            passed=False,
            status="FAILED",
            fail_reason=f"[/pre-transaction/simulate {exc.code}] {exc.msg}",
            swap_tx_to=tx_obj.get("to"),
            swap_tx_value=str(tx_obj.get("value") or "0"),
            swap_tx_gas_limit=str(tx_obj.get("gas") or ""),
            swap_tx_gas_price=str(tx_obj.get("gasPrice") or ""),
            swap_tx_calldata_bytes=calldata_bytes,
            summary=f"Transaction simulation error: [{exc.code}] {exc.msg}",
        )
    except Exception as exc:
        return DryRunSimulationResult(
            ran=True,
            passed=False,
            status="FAILED",
            fail_reason=f"{type(exc).__name__}: {exc}",
            swap_tx_to=tx_obj.get("to"),
            swap_tx_value=str(tx_obj.get("value") or "0"),
            swap_tx_gas_limit=str(tx_obj.get("gas") or ""),
            swap_tx_gas_price=str(tx_obj.get("gasPrice") or ""),
            swap_tx_calldata_bytes=calldata_bytes,
            summary=f"Transaction simulation error: {type(exc).__name__}: {exc}",
        )

    sim_data = sim_resp.get("data") or {}
    sim_status = str(sim_data.get("status") or "UNKNOWN").upper()
    fail_reason = sim_data.get("failReason") or None
    balance_changes = sim_data.get("balanceChanges") or []

    res = DryRunSimulationResult(
        ran=True,
        passed=(sim_status == "SUCCESS"),
        status=sim_status,
        fail_reason=fail_reason,
        swap_tx_to=tx_obj.get("to"),
        swap_tx_value=str(tx_obj.get("value") or "0"),
        swap_tx_gas_limit=str(tx_obj.get("gas") or ""),
        swap_tx_gas_price=str(tx_obj.get("gasPrice") or ""),
        swap_tx_calldata_bytes=calldata_bytes,
        swap_balance_changes=balance_changes,
    )

    if sim_status == "SUCCESS":
        res.summary = "Simulation passed."
        return res

    # Step 3: If swap simulation reverted due to ERC-20/BEP-20 allowance,
    # fetch `/approve-transaction` and simulate the approval on-chain
    if fail_reason and "allowance" in fail_reason.lower():
        res.approval_required = True
        try:
            app_resp = await client.get(
                "/api/v1/dex/aggregator/approve-transaction",
                params={
                    "binanceChainId": "56",
                    "tokenContractAddress": USDT_BSC_ADDRESS,
                    "approveAmount": amount_wei,
                },
            )
            app_items = app_resp.get("data") or []
            if app_items:
                app_item = app_items[0]
                res.approval_spender = app_item.get("dexContractAddress")
                res.approval_calldata = app_item.get("data") or "0x"
                sim_app = await client.post(
                    "/api/v1/dex/pre-transaction/simulate",
                    body={
                        "binanceChainId": "56",
                        "evmTx": {
                            "from": user_wallet,
                            "to": USDT_BSC_ADDRESS,
                            "value": "0",
                            "data": res.approval_calldata,
                        },
                    },
                )
                app_sim_data = sim_app.get("data") or {}
                app_status = str(app_sim_data.get("status") or "UNKNOWN").upper()
                res.approval_simulation_status = app_status
                res.approval_allowance_changes = app_sim_data.get("allowanceChanges") or []
                if app_status == "SUCCESS":
                    res.passed = True
                    res.status = "REQUIRES_APPROVAL"
                    res.summary = await _build_requires_approval_summary(wallet_address, amount_wei)
                    return res
        except Exception as exc:
            res.approval_simulation_status = f"ERROR: {type(exc).__name__}"

    res.passed = False
    res.summary = f"Simulation failed: {fail_reason or 'unknown error'}"
    return res


async def get_today_live_spend_usd(session: AsyncSession) -> float:
    """Sum of `amount_usd` for `LIVE_SUBMITTED` trades in `decision_log` since 00:00 UTC today."""
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    q = select(func.coalesce(func.sum(DecisionLog.amount_usd), 0.0)).where(
        DecisionLog.execution_status == "LIVE_SUBMITTED",
        DecisionLog.created_at >= start_of_day,
    )
    result = await session.execute(q)
    return float(result.scalar_one() or 0.0)


def _extract_tx_hash(parsed: dict[str, Any] | None) -> str | None:
    if not isinstance(parsed, dict):
        return None
    data_field = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
    tx_hash = (
        data_field.get("txHash")
        or data_field.get("transactionHash")
        or data_field.get("hash")
        or parsed.get("txHash")
    )
    if tx_hash:
        return str(tx_hash)
    # Also check `data.list[0].txHash` from `baw market-order list --orderId <id> --json`
    items = data_field.get("list") if isinstance(data_field, dict) else None
    if isinstance(items, list) and items and isinstance(items[0], dict):
        if items[0].get("txHash"):
            return str(items[0]["txHash"])
    return None


def _resolve_baw_prefix() -> list[str] | None:
    if shutil.which("baw"):
        return ["baw"]
    if shutil.which("npx"):
        return ["npx", "--yes", "@binance/agentic-wallet@1.10.0"]
    return None


def build_baw_swap_command_from_quote(
    quote: dict[str, Any],
    *,
    expected_address: str | None = None,
) -> tuple[list[str], str]:
    """Build the `baw market-order swap` command directly from a `schema_version="1"` quote response dict.

    Reads `quote["token"]["address"]` and `quote["amount_usd"]` from the quote response and
    verifies character-by-character against `expected_address` when provided.
    """
    if quote.get("verdict") != "BUY":
        raise ValueError(f"Cannot build swap command for non-BUY quote (verdict={quote.get('verdict')!r}).")

    token_obj = quote.get("token")
    if not isinstance(token_obj, dict):
        raise ValueError("Quote response is missing `token` object.")

    to_address = str(token_obj.get("address") or "").strip()
    if len(to_address) != 42 or not to_address.startswith("0x"):
        raise ValueError(f"Invalid `token.address` in quote response: {to_address!r}")
    try:
        int(to_address[2:], 16)
    except ValueError as exc:
        raise ValueError(f"Non-hex `token.address` in quote response: {to_address!r}") from exc

    if expected_address is not None:
        exp_clean = expected_address.strip()
        if to_address.lower() != exp_clean.lower():
            raise ValueError(
                f"Token address mismatch: quote.token.address={to_address!r} != expected={exp_clean!r}"
            )

    amount_usd = float(quote.get("amount_usd") or 0.0)
    if amount_usd <= 0:
        raise ValueError(f"Invalid `amount_usd` in quote response: {amount_usd!r}")

    baw_prefix = _resolve_baw_prefix() or ["npx", "--yes", "@binance/agentic-wallet@1.10.0"]
    baw_args = [
        "market-order",
        "swap",
        "--fromTokenQty",
        f"{amount_usd:g}",
        "--fromToken",
        USDT_BSC_ADDRESS,
        "--toToken",
        to_address,
        "--binanceChainId",
        "56",
        "--slippage",
        "0.5",
        "--mev",
        "true",
        "--gasLevel",
        "MEDIUM",
        "--json",
    ]
    cmd_list = baw_prefix + baw_args
    return cmd_list, " ".join(cmd_list)


def run_agentic_wallet_swap(
    winner: IssuerQuoteEvaluation,
    amount_usd: float,
    *,
    quote: dict[str, Any] | None = None,
    poll_attempts: int = 25,
    poll_interval_seconds: float = 2.0,
) -> LiveExecutionResult:
    """Invoke Binance Agentic Wallet CLI (`baw market-order swap`) for a capped live swap on BSC.

    Always derives `--toToken` from `quote["token"]["address"]` (when `quote` is provided) and
    verifies character-by-character that it matches `winner.token_contract_address`.
    """
    synthetic_quote = quote or {
        "verdict": "BUY",
        "amount_usd": amount_usd,
        "token": {
            "symbol": getattr(winner, "token_symbol", ""),
            "address": winner.token_contract_address,
            "issuer": getattr(winner, "platform_id", ""),
        },
    }
    try:
        baw_cmd_list, cmd_str = build_baw_swap_command_from_quote(
            synthetic_quote,
            expected_address=winner.token_contract_address,
        )
    except ValueError as exc:
        return LiveExecutionResult(
            attempted=False,
            live_mode_enabled=True,
            status="LIVE_ERROR",
            baw_command="",
            detail=f"Blocked before swap due to token address check: {exc}",
        )

    baw_prefix = _resolve_baw_prefix()
    if not baw_prefix:
        return LiveExecutionResult(
            attempted=True,
            live_mode_enabled=True,
            status="LIVE_ERROR",
            baw_command=cmd_str,
            detail=(
                "Neither `baw` nor `npx` was found on PATH. "
                "Install `@binance/agentic-wallet@1.10.0` (`npm install -g @binance/agentic-wallet@1.10.0`) "
                "and sign in (`npx --yes @binance/agentic-wallet@1.10.0 auth signin`) before live execution."
            ),
        )

    try:
        proc = subprocess.run(
            baw_cmd_list,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
    except Exception as exc:
        return LiveExecutionResult(
            attempted=True,
            live_mode_enabled=True,
            status="LIVE_ERROR",
            baw_command=cmd_str,
            detail=f"Failed to invoke `baw`: {type(exc).__name__}: {exc}",
        )

    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()

    parsed: dict[str, Any] | None = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = {"raw_stdout": stdout}

    if proc.returncode != 0:
        return LiveExecutionResult(
            attempted=True,
            live_mode_enabled=True,
            status="LIVE_ERROR",
            baw_command=cmd_str,
            detail=f"`baw` exited with code {proc.returncode}: {stderr or stdout}",
            raw_output=parsed,
        )

    tx_hash = _extract_tx_hash(parsed)
    order_id: str | None = None
    if isinstance(parsed, dict):
        data_field = parsed.get("data") if isinstance(parsed.get("data"), dict) else parsed
        if isinstance(data_field, dict) and data_field.get("orderId"):
            order_id = str(data_field["orderId"])

    # If `baw market-order swap` returned an `orderId` without an immediate `txHash`,
    # poll `baw market-order list --orderId <orderId> --json` per `references/market-order.md`.
    # Note (empirical DevEx finding on `@binance/agentic-wallet` v1.10.0): when a swap requires an
    # ERC-20 `approve` step before the `swap` step, `swap` returns the parent/approval `orderId`
    # (e.g. `26100300001937918699`) while `market-order list` records the child swap order under a
    # subsequent `orderId` (e.g. `26100300001937918737`). When `--orderId` returns `list: []`, we
    # fall back to `baw market-order list --json` and match the child order for `toToken`.
    target_to_lower = str((synthetic_quote.get("token") or {}).get("address") or "").strip().lower()
    finished = bool(tx_hash)
    if order_id and not tx_hash and poll_attempts > 0:
        list_by_id_cmd = baw_prefix + ["market-order", "list", "--orderId", order_id, "--json"]
        list_recent_cmd = baw_prefix + ["market-order", "list", "--json"]
        for _ in range(poll_attempts):
            time.sleep(poll_interval_seconds)
            try:
                lproc = subprocess.run(
                    list_by_id_cmd,
                    capture_output=True,
                    text=True,
                    timeout=20,
                    check=False,
                )
                items: list[Any] = []
                if lproc.returncode == 0 and lproc.stdout:
                    lparsed = json.loads(lproc.stdout.strip())
                    ldata = lparsed.get("data") if isinstance(lparsed.get("data"), dict) else {}
                    raw_items = ldata.get("list") if isinstance(ldata, dict) else None
                    if isinstance(raw_items, list):
                        items = raw_items

                if not items:
                    fproc = subprocess.run(
                        list_recent_cmd,
                        capture_output=True,
                        text=True,
                        timeout=20,
                        check=False,
                    )
                    if fproc.returncode == 0 and fproc.stdout:
                        fparsed = json.loads(fproc.stdout.strip())
                        fdata = fparsed.get("data") if isinstance(fparsed.get("data"), dict) else {}
                        recent_list = fdata.get("list") if isinstance(fdata, dict) else None
                        if isinstance(recent_list, list):
                            for cand in recent_list:
                                if not isinstance(cand, dict):
                                    continue
                                cand_to = str(cand.get("toToken") or "").strip().lower()
                                cand_id = str(cand.get("orderId") or "").strip()
                                if cand_to == target_to_lower and (
                                    cand_id == order_id
                                    or (cand_id.isdigit() and order_id.isdigit() and int(cand_id) >= int(order_id))
                                ):
                                    items = [cand]
                                    break

                if items and isinstance(items[0], dict):
                    item = items[0]
                    if item.get("orderId"):
                        order_id = str(item["orderId"])
                    st = str(item.get("status") or "").upper()
                    if item.get("txHash"):
                        tx_hash = str(item["txHash"])
                    if st == "FINISHED":
                        finished = True
                        parsed = {"submit": parsed, "order": item}
                        break
                    if st == "FAILED":
                        return LiveExecutionResult(
                            attempted=True,
                            live_mode_enabled=True,
                            status="LIVE_ERROR",
                            order_id=order_id,
                            tx_hash=tx_hash,
                            baw_command=cmd_str,
                            detail=f"`baw` market order {order_id} failed on-chain (status=FAILED).",
                            raw_output={"submit": parsed, "order": item},
                        )
            except Exception:
                pass

        if not finished:
            return LiveExecutionResult(
                attempted=True,
                live_mode_enabled=True,
                status="LIVE_TIMEOUT",
                order_id=order_id,
                tx_hash=tx_hash,
                baw_command=cmd_str,
                detail=(
                    f"Timed out polling `baw market-order list --orderId {order_id}` after "
                    f"{poll_attempts} attempts ({round(poll_attempts * poll_interval_seconds, 1)}s)."
                ),
                raw_output=parsed,
            )

    bsctrace_url = f"{BSCTRACE_TX_URL_PREFIX}{tx_hash}" if tx_hash else None
    return LiveExecutionResult(
        attempted=True,
        live_mode_enabled=True,
        status="LIVE_SUBMITTED",
        order_id=order_id,
        tx_hash=tx_hash,
        bsctrace_url=bsctrace_url,
        baw_command=cmd_str,
        detail=(
            f"Live swap executed via Binance Agentic Wallet (`baw`): txHash={tx_hash}"
            if tx_hash
            else "Live swap command executed via Binance Agentic Wallet (`baw`)."
        ),
        raw_output=parsed,
    )


async def execute_trade_pipeline(
    session: AsyncSession,
    client: BinanceClient,
    verdict_resp: QuoteVerdictResponse,
    evaluations: list[IssuerQuoteEvaluation],
    settings: Settings,
    *,
    execute_live: bool = False,
    admin_token: str | None = None,
    require_admin_token: bool = False,
) -> dict[str, Any]:
    """Run the full execution pipeline (refusal check -> Transaction API dry-run -> optional capped live swap)
    and save a `DecisionLog` row in the database.
    """
    action_label = "execute" if execute_live else "dry_run"
    wallet = settings.bine_wallet_address or DEFAULT_QUOTE_WALLET

    # 1. If the Quote Engine refused the trade, log the refusal and stop immediately
    if verdict_resp.verdict == "REFUSE" or not verdict_resp.recommended_platform:
        ref_code = (
            verdict_resp.refusal.get("code")
            if isinstance(verdict_resp.refusal, dict) and verdict_resp.refusal.get("code")
            else next((e.refusal_code for e in evaluations if e.refusal_code), "refused")
        )
        ref_msg = (
            verdict_resp.refusal.get("message")
            if isinstance(verdict_resp.refusal, dict) and verdict_resp.refusal.get("message")
            else verdict_resp.reason
        )
        sim_res = DryRunSimulationResult(
            ran=False,
            passed=False,
            status="SKIPPED",
            fail_reason=ref_msg,
            summary="Simulation skipped because the pre-trade guard refused the trade.",
        )
        exec_res = LiveExecutionResult(
            attempted=False,
            live_mode_enabled=settings.bine_live_mode,
            status="REFUSED",
            detail=ref_msg,
        )
        log_row = DecisionLog(
            ticker=verdict_resp.ticker,
            amount_usd=verdict_resp.amount_usd,
            action=action_label,
            verdict=verdict_resp.verdict,
            recommended_platform=None,
            recommended_symbol=None,
            recommended_contract_address=None,
            refusal_code=ref_code,
            reason=ref_msg,
            simulation_ran=False,
            simulation_status="SKIPPED",
            simulation_fail_reason=ref_msg,
            live_mode=settings.bine_live_mode,
            execution_status="REFUSED",
            execution_detail=ref_msg,
            payload_json=json.dumps(
                {
                    "quote": verdict_resp.to_dict(include_details=True),
                    "simulation": sim_res.to_dict(),
                    "execution": exec_res.to_dict(),
                }
            ),
        )
        session.add(log_row)
        await session.commit()
        await session.refresh(log_row)
        return _format_decision_response(log_row, verdict_resp, sim_res, exec_res)

    # Find winning issuer evaluation
    winner = next(
        (e for e in evaluations if e.platform_id == verdict_resp.recommended_platform),
        evaluations[0],
    )

    # 2. Always dry-run through the Transaction API first
    sim_res = await run_transaction_dry_run(
        client=client,
        winner=winner,
        amount_usd=verdict_resp.amount_usd,
        wallet_address=wallet,
    )

    # 3. Determine execution outcome based on dry-run + admin token + live mode + hard USD caps
    quote_dict = verdict_resp.to_dict(include_details=True)
    _, baw_preview_cmd = build_baw_swap_command_from_quote(
        quote_dict,
        expected_address=winner.token_contract_address,
    )

    check_admin = require_admin_token or bool(settings.bine_admin_token)
    admin_ok = (
        not check_admin
        or (
            bool(settings.bine_admin_token)
            and bool(admin_token)
            and hmac.compare_digest(admin_token, settings.bine_admin_token)
        )
    )

    if not sim_res.passed:
        exec_res = LiveExecutionResult(
            attempted=False,
            live_mode_enabled=settings.bine_live_mode,
            status="DRY_RUN_FAILED",
            baw_command=baw_preview_cmd,
            detail=f"Blocked because simulation failed: {sim_res.summary}",
        )
    elif not execute_live:
        exec_res = LiveExecutionResult(
            attempted=False,
            live_mode_enabled=settings.bine_live_mode,
            status="DRY_RUN_OK",
            baw_command=baw_preview_cmd,
            detail=sim_res.summary,
        )
    elif not admin_ok:
        exec_res = LiveExecutionResult(
            attempted=False,
            live_mode_enabled=settings.bine_live_mode,
            status="LIVE_UNAUTHORIZED",
            baw_command=baw_preview_cmd,
            detail="Live execution rejected: valid BINE_ADMIN_TOKEN is required when execute_live=true.",
        )
    elif verdict_resp.amount_usd > settings.bine_max_trade_usd:
        exec_res = LiveExecutionResult(
            attempted=False,
            live_mode_enabled=settings.bine_live_mode,
            status="LIVE_BLOCKED_CAP",
            baw_command=baw_preview_cmd,
            detail=(
                f"Live execution refused: ${verdict_resp.amount_usd:,.2f} exceeds "
                f"per-trade cap of ${settings.bine_max_trade_usd:,.2f} (BINE_MAX_TRADE_USD)."
            ),
        )
    else:
        today_spent = await get_today_live_spend_usd(session)
        if today_spent + verdict_resp.amount_usd > settings.bine_daily_cap_usd:
            exec_res = LiveExecutionResult(
                attempted=False,
                live_mode_enabled=settings.bine_live_mode,
                status="LIVE_BLOCKED_CAP",
                baw_command=baw_preview_cmd,
                detail=(
                    f"Live execution refused: today's spend (${today_spent:,.2f}) + "
                    f"${verdict_resp.amount_usd:,.2f} exceeds daily cap of "
                    f"${settings.bine_daily_cap_usd:,.2f} (BINE_DAILY_CAP_USD)."
                ),
            )
        elif not settings.bine_live_mode:
            exec_res = LiveExecutionResult(
                attempted=False,
                live_mode_enabled=False,
                status="LIVE_DISABLED",
                baw_command=baw_preview_cmd,
                detail="Simulation passed, but live trading is off (BINE_LIVE_MODE=false).",
            )
        else:
            exec_res = await asyncio.to_thread(
                run_agentic_wallet_swap,
                winner,
                verdict_resp.amount_usd,
                quote=quote_dict,
            )

    # 4. Save audit record in `decision_log`
    log_row = DecisionLog(
        ticker=verdict_resp.ticker,
        amount_usd=verdict_resp.amount_usd,
        action=action_label,
        verdict=verdict_resp.verdict,
        recommended_platform=winner.platform_id,
        recommended_symbol=winner.token_symbol,
        recommended_contract_address=winner.token_contract_address,
        refusal_code=None,
        reason=verdict_resp.reason,
        expected_shares=winner.shares_received,
        all_in_price_per_share_usd=winner.all_in_price_per_share_usd,
        all_in_vs_reference_pct=winner.all_in_vs_reference_pct,
        effective_slippage_pct=winner.effective_slippage_pct,
        quote_id=winner.quote_id,
        execution_mode=winner.execution_mode,
        simulation_ran=sim_res.ran,
        simulation_status=sim_res.status,
        simulation_fail_reason=sim_res.fail_reason,
        approval_simulation_status=sim_res.approval_simulation_status,
        spender_address=sim_res.approval_spender or sim_res.swap_tx_to,
        estimated_gas_limit=sim_res.swap_tx_gas_limit,
        live_mode=settings.bine_live_mode,
        execution_status=exec_res.status,
        tx_hash=exec_res.tx_hash,
        bsctrace_url=exec_res.bsctrace_url,
        execution_detail=exec_res.detail,
        payload_json=json.dumps(
            {
                "quote": verdict_resp.to_dict(include_details=True),
                "simulation": sim_res.to_dict(),
                "execution": exec_res.to_dict(),
            }
        ),
    )
    session.add(log_row)
    await session.commit()
    await session.refresh(log_row)
    return _format_decision_response(log_row, verdict_resp, sim_res, exec_res)


def _format_decision_response(
    log_row: DecisionLog,
    verdict_resp: QuoteVerdictResponse,
    sim_res: DryRunSimulationResult,
    exec_res: LiveExecutionResult,
) -> dict[str, Any]:
    created_iso = (
        log_row.created_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        if log_row.created_at.tzinfo
        else log_row.created_at.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    return {
        "decision_id": log_row.id,
        "created_at": created_iso,
        "ticker": log_row.ticker,
        "amount_usd": log_row.amount_usd,
        "action": log_row.action,
        "verdict": log_row.verdict,
        "recommended_platform": log_row.recommended_platform,
        "recommended_symbol": log_row.recommended_symbol,
        "recommended_contract_address": log_row.recommended_contract_address,
        "refusal_code": log_row.refusal_code,
        "reason": log_row.reason,
        "why_others_lost": verdict_resp.why_others_lost,
        "simulation": sim_res.to_dict(),
        "execution": exec_res.to_dict(),
        "quote": verdict_resp.to_dict(include_details=True),
    }
