# BINE

Pre-trade safety check for tokenized stocks on BNB Chain.

Every US stock on BNB Chain can be issued by more than one provider (Ondo and bStocks), with different rules, minimums, trading hours and pool depth. BINE checks all of them before you or your AI agent buys, and gives one answer:

- **BUY** and which token to use, or
- **DO NOT BUY** and the exact reason in plain English.

Live demo: TODO add Vercel URL after deploy.  Demo video: TODO.

## Three real checks from BINE

```text
$ bine check AAPL 2
DO NOT BUY: Ondo requires at least $5 per order. Try $5.50.

$ bine check NVDA 5.50
BUY NVDAB (bStocks) - about 0.2% over the stock reference price.

$ bine check SPYon 250   # outside US market hours
DO NOT BUY: pool is thin right now; fill is 40% to 82% above the stock price.
```

## Proof on BNB Chain

Two live $2 test swaps were executed on BNB Smart Chain after passing BINE's checks and dry-run simulation:

- Swap 1 (off-hours, $2 -> NVDAB): [0x00c0fabd...c228e506](https://bscscan.com/tx/0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506)
- Swap 2 (US market hours, $2 -> NVDAB): [0xa3693383...fc2a3e75](https://bscscan.com/tx/0xa3693383a9493600df08ae10a6a64faa6a7543e3bde9f6bbca3fd7acfc2a3e75)

Live trading is off by default and capped at $6 per trade / $10 per day.

## Run it in 3 commands

```bash
git clone <repo-url> bine && cd bine && python3 -m venv .venv && .venv/bin/pip install -e backend
printf "BINANCE_API_KEY=<your-key>\nBINANCE_SECRET_KEY=<your-secret>\n" > .env && (.venv/bin/uvicorn bine.app:app --app-dir backend --port 8000 &)
.venv/bin/bine check NVDA 5.50
```

## Use it from anywhere

- Web app: `/guard`, `/refusals`, `/receipts`, `/integrate`
- CLI: `bine check NVDA 5.50`, `bine buy NVDA 2`
- HTTP: `GET /api/quote?ticker=NVDA&amount_usd=5.50`
- MCP server and Claude skill: see `/integrate` or the full docs in `docs-site/`

## Full documentation

- Technical docs site: `docs-site/` (`npm --prefix docs-site run docs:dev`)
- Binance Web3 DevEx evidence ledger: [`docs/devex-evidence.md`](docs/devex-evidence.md)
- On-chain receipt files: [`docs/live_swap_nvda_2usd.json`](docs/live_swap_nvda_2usd.json), [`docs/live_swap_nvda_2usd_second_2026-10-05.json`](docs/live_swap_nvda_2usd_second_2026-10-05.json)
