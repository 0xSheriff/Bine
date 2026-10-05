# Optional Hosting Guide (Bine)

> **Optional**: Bine runs locally on `http://localhost:8000` by default (`BINE_API_URL=http://localhost:8000`). Hosting is optional and only needed if you want to share a single read-only Bine backend across multiple machines.

Bine runs as a **single stateless FastAPI web service** (`uvicorn bine.app:app`) with an optional SQLite or Postgres database used only for the `decision_log` audit table. No background sampler or worker process is required — `/api/quote` fetches RWA token metadata live on demand with a 60-second in-memory cache.

---

## 1. Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `BINANCE_API_KEY` | Yes | — | Binance Web3 Open API key (`X-MBX-APIKEY`) |
| `BINANCE_SECRET_KEY` | Yes | — | Binance Web3 Open API HMAC-SHA256 secret |
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./bine.db` | SQLite file or `postgresql://...` for `decision_log` |
| `BINE_LIVE_MODE` | No | `false` | Keep `false` on public deployments; set `true` only for verified live Agentic Wallet swaps |
| `BINE_MAX_TRADE_USD` | No | `6.0` | Hard USD cap per quote and execution |
| `BINE_ADMIN_TOKEN` | Conditional | `""` | Required via `X-Bine-Admin-Token` header whenever `execute_live=true` |
| `BINE_CORS_ORIGINS` | No | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated allowed browser origins |

---

## 2. Deploy on Railway / Render / Fly.io (Single Service)

1. Point a single **Web Service** at `/backend`:
   - **Build Command**: `pip install -e .` (add `pip install asyncpg` if using Postgres)
   - **Start Command**: `uvicorn bine.app:app --host 0.0.0.0 --port ${PORT:-8000}`
2. Set `BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, and `BINE_LIVE_MODE=false` in the service environment.
3. Optional: attach a small SQLite volume or managed Postgres (`DATABASE_URL`) to persist `decision_log` across restarts.

---

## 3. Deploy on a Linux VM (`systemd`)

```bash
cd /opt/bine/backend
python3 -m venv .venv
.venv/bin/pip install -e .
BINE_LIVE_MODE=false .venv/bin/uvicorn bine.app:app --host 0.0.0.0 --port 8000
```

---

## 4. Dry-Run Router (`0xB44446b0...`) vs. Live `baw` Router (`0xb300000b...`)

- **Transaction API Dry-Run (`POST /api/v1/dex/pre-transaction/simulate`)**: Simulates the raw calldata returned by `GET /api/v1/dex/aggregator/swap` (and `GET /api/v1/dex/aggregator/approve-transaction`), which targets the DEX aggregator router `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5` (`docs/dry_run_nvda_2usd.json`).
- **Live Execution (`baw market-order swap`)**: Executes on-chain through `@binance/agentic-wallet`'s own router contract `0xb300000b72DEAEb607a12d5f54773D1C19c7028d`, as shown by the on-chain evidence in `docs/live_swap_nvda_2usd.json`, `docs/live_swap_nvda_2usd_second_2026-10-05.json`, and `docs/raw/usdt_allowance_2026-10-05.txt`:
  - **Approve tx (`0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`)**: Approved `uint256.max` (`0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff`) on-chain to spender `0xb300000b72DEAEb607a12d5f54773D1C19c7028d` (leaving `115792089237316195423570985008687907853269984665640564039453584007913129639935` wei = `uint256.max - 4 * 10^18` after the two `$2` swaps, while `allowance` to the dry-run simulation spender `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5` is `0`).
  - **First swap tx (`0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`) & second swap tx (`0xa3693383a9493600df08ae10a6a64faa6a7543e3bde9f6bbca3fd7acfc2a3e75`)**: Both sent `from` wallet `0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730` `to` contract `0xb300000b72deaeb607a12d5f54773d1c19c7028d`; the second swap sent no `approve` tx (only one transaction was sent on `2026-10-05`).

