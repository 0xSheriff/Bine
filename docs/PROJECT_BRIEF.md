# BINE — Project Brief

## ROLE
You are a senior full-stack engineer building "BINE" for the BNB Hack: Tokenized Stocks Edition (BNB Chain + Binance Web3 Wallet). Submissions lock Sun 11 Oct 2026 12:00 UTC, so speed and a working demo matter more than breadth. Work in phases. Finish and verify each phase before starting the next. Ask me before making any decision that changes scope.

## WHAT BINE IS
A tokenized-stock intelligence layer for BSC with two parts:
1. **The Atlas**: continuously samples bStocks, Ondo and xStocks tokens and records, per token and per hour, the on-chain price, the reference price, the gap between them, pool depth, quoted slippage at fixed trade sizes, and whether the underlying market is open. It compares the same underlying across the three issuers.
2. **The Agent**: reads the Atlas and decides whether a swap is worth making right now. It dry-runs every trade with the Transaction API first, and only then executes a small live swap (a few dollars) on BSC mainnet. It is allowed to refuse a trade and must explain why in plain English.

Primary user: someone new to crypto who holds or wants tokenized stocks. The front page answers one question in plain words: "Is this stock token priced fairly right now?"

## HARD RULES (from the hackathon)
- At least one of bStocks, Ondo or xStocks must be central.
- Spot only. No perps, no leverage.
- BSC mainnet only. Dry-run with the Transaction API before any live call.
- Live amounts must be tiny and capped in config.
- Repo must be public, and the demo and deployed link must stay online through 23 Oct 2026.

## STACK
- **Backend**: Python 3.11+, FastAPI, httpx, Pydantic, APScheduler for the sampler.
- **Storage**: SQLite for local dev, Postgres (Neon or Supabase) in deployment. Use SQLAlchemy so both work.
- **Frontend**: React + Vite or Next.js, TypeScript, Tailwind, deployed on Vercel. Charts with Recharts.
- **Execution**: Binance Agentic Wallet / Wallet Skills (`npx skills add binance/binance-skills-hub/skills/binance-web3/binance-agentic-wallet`). Use it for the execution step so the project is eligible for the Agentic Wallet special prize.
- **LLM**: Groq or DeepSeek through an OpenAI-compatible client, behind one function. Its only jobs are (a) explaining a gap in plain English and (b) answering questions about the Atlas. It never decides whether a trade happens; numbers and rules decide.
- No Solidity unless I ask for it.

## DOCS: READ BEFORE CODING
Fetch and read these first. Do not guess endpoint paths, parameters or response fields. If something is unclear, say so and ask me.
- https://web3.binance.com/en/dev-docs/llms.txt
- https://web3.binance.com/en/dev-docs/llms-full.txt
- Authentication and signing: https://web3.binance.com/en/dev-docs/authentication
- RWA Data: https://web3.binance.com/en/dev-docs/catalog/web3-wallet/api/rest-api/rwa-data
- Trading API, Transaction API, Wallet API, Market data (general-data) from the same catalog
- Agentic Wallet: https://developers.binance.com/en/docs/products/agentic-wallet/welcome
- Tokenized securities use case: https://developers.binance.com/en/docs/products/agentic-wallet/use-cases/trading/stock-trading

## DEVEX FRICTION LOG
25% of the score is a Developer Experience Report that must be specific and honest. Maintain `/docs/friction-log.md`. After every API call or doc read, append an entry with: timestamp (UTC), what I tried, what happened, the exact doc page and location if the docs were wrong or unclear, exact error text, latency in ms, and how I fixed it. Record time from first doc open to first successful API call. Also log anything specific to tokenized stocks: liquidity depth, slippage, behavior when the underlying market is closed, on-chain vs reference gap, and how bStocks, Ondo and xStocks differ. Write plain factual entries. Do not summarize or polish them.

## PHASES
- **Phase 0**: Setup and First Call
- **Phase 1**: The Sampler (highest priority)
- **Phase 2**: API and Atlas
- **Phase 3**: Frontend
- **Phase 4**: The Agent
- **Phase 5**: Deploy and Submit

## WORKING STYLE
- Plan first: list the files you will create and the risks, then wait for go-ahead.
- After each phase, show what runs, what was tested, and what is still unverified.
- Keep code small and readable. Comments explain why, not what.
- If an API returns something unexpected, stop, log it in the friction log and tell instead of working around it silently.
- Be honest in all copy. No invented statistics, no fake trades, no claims the data does not support.
