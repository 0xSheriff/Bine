# CLI, MCP Server, and Agent Skill

BINE ships three local agent integration surfaces alongside the HTTP API (`backend/pyproject.toml` console scripts `bine` and `bine-mcp`, plus `skills/bine-pre-trade-guard/SKILL.md`).

All three surfaces default to `BINE_API_URL = "http://localhost:8000"` and consume the frozen `schema_version: "1"` response contract.

---

## 1. `bine` CLI (`backend/bine/cli.py`)

Install the backend package into a virtual environment:

```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e backend
```

### `bine check <TICKER> [AMOUNT_USD] [--json]`

Runs the pre-trade guard for `<TICKER>` at `[AMOUNT_USD]` (default `5.50`).

```bash
# Plain-English one-liner for humans or shell logs
bine check NVDA 5.50
# BUY: Buy 0.0232 NVDA (NVDAon on Ondo) for $5.50. All-in $237.99 per share, +0.13% vs $237.69 reference.

# Refusal one-liner
bine check AAPL 2
# REFUSE [below_issuer_minimum]: Ondo's minimum order is $5 (you entered $2.00). Try $5.50.

# Strict 13-key JSON output for scripts and agents
bine check NVDA 5.50 --json
```

**Exit codes**:
- `0`: `verdict == "BUY"`
- `2`: `verdict == "REFUSE"`
- `1`: Backend unreachable (`Cannot reach Bine backend at http://localhost:8000...`) or API keys missing/rejected (`Binance API keys missing or rejected`)

### `bine buy <TICKER> [AMOUNT_USD] [--yes] [--json]`

Runs the pre-trade guard and the Binance Transaction API dry-run (`POST /api/v1/dex/pre-transaction/simulate`):

```bash
# Dry-run simulation (default; never broadcasts a transaction)
bine buy NVDA 5.50

# Live execution (requires BINE_LIVE_MODE=true, BINE_ADMIN_TOKEN, and amount <= $6.00)
bine buy NVDA 2.00 --yes
```

> [!NOTE]
> If you set `BINE_DIRECT_MODE=true` in your shell environment, `bine check` and `bine buy` execute the async Python engine directly in-process without requiring a separate `uvicorn` server on port `8000`.

---

## 2. MCP Server (`bine-mcp`, `backend/bine/mcp_server.py`)

`bine-mcp` is a zero-dependency JSON-RPC 2.0 Model Context Protocol server over `stdio`. Add it to Claude Desktop, Cursor, or any MCP host configuration:

```json
{
  "mcpServers": {
    "bine-pre-trade-guard": {
      "command": "bine-mcp",
      "env": {
        "BINE_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### Exposed MCP Tools

1. **`bine_check`**
   - **Arguments**: `ticker` (`string`, required), `amount_usd` (`number`, default `5.5`)
   - **Returns**: Both human-readable text (`content[0].text`) and the frozen 13-key `schema_version: "1"` object in `structuredContent`.
2. **`bine_buy`**
   - **Arguments**: `ticker` (`string`, required), `amount_usd` (`number`, default `5.5`), `confirm` (`boolean`, default `false`)
   - **Behavior**: When `confirm` is `false` (default), runs the pre-trade guard and Transaction API `/simulate` dry-run only (`execute_live=false`). Even when `confirm` is `true`, live execution is blocked unless the server has `BINE_LIVE_MODE=true`, a valid `BINE_ADMIN_TOKEN`, and `amount_usd <= $6.00`.

---

## 3. Binance Agentic Wallet Skill (`skills/bine-pre-trade-guard/SKILL.md`)

Install the skill file so autonomous coding or trading agents using `@binance/agentic-wallet` (`baw`) always run `bine check` and verify the winning contract address before calling `baw market-order swap`:

```bash
mkdir -p ~/.claude/skills/bine-pre-trade-guard
cp skills/bine-pre-trade-guard/SKILL.md ~/.claude/skills/bine-pre-trade-guard/SKILL.md
```

### Mandatory Agent Rules in `SKILL.md`

1. Always run `bine check <TICKER> <AMOUNT_USD> --json` (or `GET /api/quote`) before building any swap command.
2. If `verdict` is `"REFUSE"`, stop immediately and report `refusal.code` and `refusal.message` to the user. Never attempt to bypass a refusal by calling `baw` directly.
3. Read `--toToken` strictly from `quote.token.address` in the `BUY` response (`build_baw_swap_command_from_quote()` in `backend/bine/execution.py` verifies `quote["token"]["address"]` character-for-character against the winning issuer contract address).
4. Always run a dry-run (`bine buy <TICKER> <AMOUNT_USD>`) before any live swap, and keep `baw market-order swap` parameters locked to `--binanceChainId 56 --slippage 0.5 --mev true --gasLevel MEDIUM --json`.
