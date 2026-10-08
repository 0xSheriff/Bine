# On-Chain Evidence & Receipts

BINE's execution pipeline (`POST /api/execute` and `bine buy`) was verified on BNB Smart Chain mainnet (`chainId = 56`) with two live `$2.00` `USDT -> NVDAB` swaps executed through the Binance Agentic Wallet CLI (`@binance/agentic-wallet@1.10.0`), plus their preceding Transaction API dry-runs.

All raw CLI outputs, transaction histories, wallet balance snapshots, and on-chain allowance checks are preserved in `docs/raw/`, `docs/live_swap_nvda_2usd.json`, `docs/live_swap_nvda_2usd_second_2026-10-05.json`, and `frontend/src/data/onchain-receipts.json`.

---

## 1. Summary of the Two Verified Live Swaps

Both swaps spent `$2.00` USDT (`0x55d398326f99059fF775485246999027B3197955`) to buy `NVDAB` (`0x02Fca66C1D1aFB4E2A7884261eB00F63598a7436`, bStocks) from wallet `0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730`. At `$2.00`, `NVDAon` (Ondo) was deterministically refused with `below_issuer_minimum` (`[40375] Minimum order amount is 5 USD.`), so `NVDAB` won both checks.

| Metric | Swap #1 (`Decision #16`, Off-Hours) | Swap #2 (`Decision #18`, US Regular Hours) |
| --- | --- | --- |
| **Preceding Dry-Run** | `Decision #15` (`2026-10-03T21:14:06Z`, `DRY_RUN_OK`) | `Decision #17` (`2026-10-05T15:05:27Z`, `DRY_RUN_OK`) |
| **Executed At (UTC)** | `2026-10-03T21:20:18Z` (`bookTime: 2026-10-03T22:18:17+01:00`) | `2026-10-05T15:05:40Z` (`bookTime: 2026-10-05T16:05:34+01:00`) |
| **Market Session** | `offhours` (`open=true`) | `regular` (`open=true`, 94 min after NY open) |
| **Amount Spent** | `$2.00` USDT (`2000000000000000000` wei) | `$2.00` USDT (`2000000000000000000` wei) |
| **Winning Token** | `NVDAB` (`0x02Fca66C1D1aFB4E2A7884261eB00F63598a7436`) | `NVDAB` (`0x02Fca66C1D1aFB4E2A7884261eB00F63598a7436`) |
| **`tokenToShareRatio`** | `1.0007782237528078` | `1.0007782237528078` |
| **Quoted Shares** | `0.00851212` shares (`0.00850550` raw `NVDAB` tokens) | `0.00842808` shares (`0.00842153` raw `NVDAB` tokens) |
| **Filled Raw Tokens (`baw` `toTokenActualQty`)** | `0.00851201289192116` `NVDAB` tokens | `0.008427629564723702` `NVDAB` tokens |
| **Filled Shares (`tokens * ratio`)** | `0.00851864` shares (`+7.7 bps` vs quoted `0.00851212` shares) | `0.00843419` shares (`+7.2 bps` vs quoted `0.00842808` shares) |
| **Quoted All-In vs Reference** | `$237.06` vs `$235.07` (`+0.85%`) | `$239.71` vs `$237.31` (`+1.01%`) |
| **`baw` Order ID** | Parent `26100300001937918699` -> Child `26100300001937918737` | `26100500001942767719` (direct single order) |
| **Swap `txHash`** | [`0x00c0fabd...c228e506`](https://bscscan.com/tx/0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506) | [`0xa3693383...fc2a3e75`](https://bscscan.com/tx/0xa3693383a9493600df08ae10a6a64faa6a7543e3bde9f6bbca3fd7acfc2a3e75) |
| **Approve `txHash`** | [`0x803cda03...504aeeb64`](https://bscscan.com/tx/0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64) | `null` (reused `uint256.max` allowance on `0xb300...028d`) |
| **BSC Block Number** | `125555002` | `125889084` |
| **Gas Paid (`BNB`)** | `0.00004798 BNB` swap + `0.00000293 BNB` approve (`0.00005091 BNB` total) | `0.00003293 BNB` |
| **Artifact File** | `docs/live_swap_nvda_2usd.json` | `docs/live_swap_nvda_2usd_second_2026-10-05.json` |

---

## 2. Dry-Run Simulation Router (`0xB444...`) vs. Live `baw` Router (`0xb300...`)

A key empirical finding verified on-chain is why the Transaction API dry-run reports `REQUIRES_APPROVAL` even after the wallet has completed a live `baw` swap:

1. **Aggregator `/swap` Router (`0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`)**:
   - `GET /api/v1/dex/aggregator/swap` builds unsigned calldata targeting spender `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5`.
   - Because the wallet never approved `0xB444...` on-chain (`allowance = 0`), `POST /api/v1/dex/pre-transaction/simulate` on the raw swap calldata returns `"execution reverted: BEP20: transfer amount exceeds allowance"`.
   - BINE then calls `GET /api/v1/dex/aggregator/approve-transaction` and simulates the ERC-20 `approve()` transaction via `/pre-transaction/simulate`, which succeeds (`approval_simulation_status = "SUCCESS"`).
2. **Agentic Wallet `baw` Router (`0xb300000b72DEAEb607a12d5f54773D1C19c7028d`)**:
   - When `baw market-order swap` executes live, it routes through `0xb300000b72DEAEb607a12d5f54773D1C19c7028d`.
   - Before Swap #1, `baw` broadcast a one-time `approve` transaction (`0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`) granting `uint256.max` USDT allowance to `0xb300...028d`.
   - After both `$2.00` swaps (`4 * 10^18` wei total), on-chain `eth_call` `allowance(0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730, 0xb300000b72DEAEb607a12d5f54773D1C19c7028d)` is `uint256.max - 4 * 10^18` = `115792089237316195423570985008687907853269984665640564039453584007913129639935` wei (`docs/raw/usdt_allowance_2026-10-05.txt`).
   - Consequently, Swap #2 (`Decision #18`) required **no** separate `approve` transaction and completed in a single on-chain transaction (`0xa3693383...fc2a3e75`).

---

## 3. Parent vs. Child `orderId` Behavior in `baw`

- On **Swap #1 (`Decision #16`)**, because a separate `approve` transaction (`0x803cda03...eeb64`) had to run before the `swap` transaction (`0x00c0fabd...c228e506`), `baw market-order swap` returned a parent `orderId` (`26100300001937918699`). Querying `baw market-order list --orderId 26100300001937918699 --json` returned an empty list (`{"list": []}`), while `baw market-order list --json` (without `--orderId`) revealed the child swap order `26100300001937918737` with `status: "FINISHED"` and `txHash: "0x00c0fabd...c228e506"`.
- BINE's `run_agentic_wallet_swap()` in `backend/bine/execution.py:558-598` handles both cases automatically: if `--orderId <id>` returns an empty list while polling, it falls back to `baw market-order list --json` and matches the child order by target token contract and order ID sequence.
- On **Swap #2 (`Decision #18`)**, because `0xb300...028d` already had `uint256.max` USDT allowance, `baw market-order swap` returned the direct order ID `26100500001942767719` (`status: "FINISHED"`) on the first poll with zero hand reconciliation.
