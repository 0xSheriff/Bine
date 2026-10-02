"""Bine MCP Server (stdio JSON-RPC 2.0).

Exposes two MCP tools over standard input/output without extra framework dependencies:
  - bine_check(ticker, amount_usd) -> frozen schema_version="1" pre-trade verdict
  - bine_buy(ticker, amount_usd, confirm=False) -> dry-run simulation (confirm=False) or live swap (confirm=True & BINE_LIVE_MODE=true)

Run with:
    python -m bine.mcp_server
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from bine.cli import format_plain_check_line, run_buy_step, run_check

SERVER_INFO = {
    "name": "bine-pre-trade-guard",
    "version": "1.0.0",
}

TOOLS = [
    {
        "name": "bine_check",
        "description": (
            "Pre-trade guard for tokenized stocks on BSC (chainId=56). "
            "Checks whether a tokenized stock (Ondo / bStocks) is safe to buy right now, "
            "computes true share count and all-in price per share versus stock reference price, "
            "and returns BUY or REFUSE with a plain-English reason."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Underlying stock ticker symbol (e.g. NVDA, AAPL, SPY, TSLA).",
                },
                "amount_usd": {
                    "type": "number",
                    "description": "Order size in USD (e.g. 5, 25).",
                },
            },
            "required": ["ticker", "amount_usd"],
        },
    },
    {
        "name": "bine_buy",
        "description": (
            "Run Bine pre-trade guard + Transaction API dry-run simulation for a tokenized stock on BSC. "
            "When confirm=False (default), only runs the pre-trade check and dry-run simulation. "
            "When confirm=True and BINE_LIVE_MODE=true on the server, executes via Binance Agentic Wallet."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Underlying stock ticker symbol (e.g. NVDA).",
                },
                "amount_usd": {
                    "type": "number",
                    "description": "Order size in USD (must be <= BINE_MAX_TRADE_USD).",
                },
                "confirm": {
                    "type": "boolean",
                    "default": False,
                    "description": "False (default) runs dry-run only; True requests live execution if BINE_LIVE_MODE=true.",
                },
            },
            "required": ["ticker", "amount_usd"],
        },
    },
]


async def call_mcp_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Dispatch a tool call and return an MCP CallToolResult payload."""
    if name == "bine_check":
        ticker = str(arguments.get("ticker", "")).strip().upper()
        amount_usd = float(arguments.get("amount_usd", 0.0))
        verdict = await run_check(ticker, amount_usd, include_details=False)
        summary = format_plain_check_line(verdict)
        return {
            "content": [
                {"type": "text", "text": summary},
                {"type": "text", "text": json.dumps(verdict)},
            ],
            "structuredContent": verdict,
            "isError": False,
        }

    if name == "bine_buy":
        ticker = str(arguments.get("ticker", "")).strip().upper()
        amount_usd = float(arguments.get("amount_usd", 0.0))
        confirm = bool(arguments.get("confirm", False))
        result = await run_buy_step(ticker, amount_usd, execute_live=confirm)
        exec_obj = result.get("execution") or {}
        exec_status = exec_obj.get("status") or result.get("verdict")
        exec_detail = exec_obj.get("detail") or result.get("reason")
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"{exec_status}: {exec_detail}",
                },
                {"type": "text", "text": json.dumps(result)},
            ],
            "structuredContent": result,
            "isError": exec_status in ("REFUSED", "DRY_RUN_FAILED", "LIVE_ERROR", "LIVE_BLOCKED_CAP", "LIVE_UNAUTHORIZED"),
        }

    raise ValueError(f"Unknown tool: {name}")


async def handle_jsonrpc_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Process one JSON-RPC 2.0 request and return a JSON-RPC 2.0 response (or None for notifications)."""
    method = msg.get("method")
    msg_id = msg.get("id")

    # Notifications have no id
    if msg_id is None:
        return None

    if method == "initialize":
        params = msg.get("params") or {}
        protocol_version = params.get("protocolVersion") or "2024-11-05"
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": protocol_version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        }

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {"tools": TOOLS},
        }

    if method == "tools/call":
        params = msg.get("params") or {}
        tool_name = params.get("name", "")
        arguments = params.get("arguments") or {}
        try:
            tool_result = await call_mcp_tool(tool_name, arguments)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": tool_result,
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32602, "message": str(exc)},
            }

    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


async def run_stdio_server() -> None:
    """Read newline-delimited JSON-RPC messages from stdin and write responses to stdout."""
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            err = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
            sys.stdout.write(json.dumps(err) + "\n")
            sys.stdout.flush()
            continue

        resp = await handle_jsonrpc_message(msg)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


def main() -> None:
    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
