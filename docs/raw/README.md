# `docs/raw/` Provenance & Live Re-Queries (`$2.00` `NVDAB` Swap, `2026-10-03T21:18Z` & `2026-10-05` Live Re-Queries)

## File Provenance Classification

| File | Provenance | Details |
|---|---|---|
| `swap_stdout.json` | **Transcribed from the Oct 3 log** | Written on `2026-10-04T05:47` from the `raw_output` recorded in the Oct 3 execution log (`{"success": true, "data": {"orderId": "26100300001937918699"}}`). |
| `live_swap_nvda_2usd_initial_execution.json` | **Transcribed from the Oct 3 log** | Written on `2026-10-04T05:49` from the initial unreconciled `execution` block returned by `bine buy NVDA 2 --confirm --json` on `2026-10-03T21:18Z` (`status: "LIVE_TIMEOUT"` on parent `orderId` `26100300001937918699`). |
| `market_order_list_by_parent_id.json` | **Transcribed from the Oct 3 log** | Written on `2026-10-04T05:47` from the Oct 3 terminal log of `npx --yes @binance/agentic-wallet@1.10.0 market-order list --orderId 26100300001937918699 --json`. |
| `market_order_list_all.json` | **Transcribed from the Oct 3 log** | Written on `2026-10-04T05:47` from the Oct 3 terminal log of `npx --yes @binance/agentic-wallet@1.10.0 market-order list --json` (matches `market_order_list_2026-10-05.json` byte-for-byte). |
| `wallet_balance_post_swap.json` | **Transcribed from the Oct 3 log** | Written on `2026-10-04T05:47` from the Oct 3 terminal log of `npx --yes @binance/agentic-wallet@1.10.0 wallet balance --binanceChainId 56 --json`. |
| `tx_history_post_swap.json` | **Transcribed/summarized from the Oct 3 log** | Written on `2026-10-04T05:48` as a flat summary (`data.list`) rather than the nested `data.transactions[].txHashList` structure returned by `wallet tx-history`. Replaced for raw reference by `tx_history_2026-10-05.json` below. |
| `market_order_list_2026-10-05.json` | **Captured live / re-queried today (`2026-10-05`)** | Direct pipe (`tee`) of `npx --yes @binance/agentic-wallet@1.10.0 market-order list --json` on `2026-10-05T02:40Z`. |
| `tx_history_2026-10-05.json` | **Captured live / re-queried today (`2026-10-05`)** | Direct pipe (`tee`) of `npx --yes @binance/agentic-wallet@1.10.0 wallet tx-history --binanceChainId 56 --json` on `2026-10-05T02:40Z`. |

---

## 1. Live Re-Query (`2026-10-05`): `market-order list --json` (`market_order_list_2026-10-05.json`)

### Command
```bash
npx --yes @binance/agentic-wallet@1.10.0 market-order list --json | tee docs/raw/market_order_list_2026-10-05.json
```

### Raw stdout
```json
{
  "success": true,
  "data": {
    "total": 1,
    "page": 1,
    "pageSize": 20,
    "list": [
      {
        "orderType": "market",
        "orderId": "26100300001937918737",
        "chain": "56",
        "fromToken": "0x55d398326f99059fF775485246999027B3197955",
        "fromTokenName": "USDT",
        "fromTokenQty": "2.000000000000000000",
        "toToken": "0x02Fca66C1D1aFB4E2A7884261eB00F63598a7436",
        "toTokenName": "NVDAB",
        "toTokenActualQty": "0.00851201289192116",
        "status": "FINISHED",
        "slippage": "0.5000",
        "txHash": "0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506",
        "bookTime": "2026-10-03T22:18:17+01:00",
        "updatedTime": "2026-10-03T22:18:18+01:00"
      }
    ]
  }
}
```

---

## 2. Live Re-Query (`2026-10-05`): `wallet tx-history --binanceChainId 56 --json` (`tx_history_2026-10-05.json`)

### Command
```bash
npx --yes @binance/agentic-wallet@1.10.0 wallet tx-history --binanceChainId 56 --json | tee docs/raw/tx_history_2026-10-05.json
```

### Raw stdout
```json
{
  "success": true,
  "data": {
    "transactions": [
      {
        "txType": "swap",
        "txHash": "0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506",
        "txTime": "2026-10-03T22:18:17+01:00",
        "binanceChainId": "56",
        "status": "confirmed",
        "txHashList": [
          {
            "binanceChainId": "56",
            "txHash": "0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506",
            "status": "confirmed",
            "networkFee": {
              "binanceChainId": "56",
              "feeTokenAddress": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
              "feeTokenSymbol": "BNB",
              "feeValue": "47976548789549",
              "feeTokenDecimals": 18
            },
            "instructions": {
              "send": [
                {
                  "binanceChainId": "56",
                  "amount": "2",
                  "addressInfo": {
                    "address": "0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730"
                  },
                  "tokenInfo": {
                    "binanceChainId": "56",
                    "contractAddress": "0x55d398326f99059fF775485246999027B3197955",
                    "symbol": "USDT",
                    "tokenId": null,
                    "decimals": 18
                  }
                }
              ],
              "receive": [
                {
                  "binanceChainId": "56",
                  "amount": "0.00851201289192116",
                  "addressInfo": {
                    "address": "0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730"
                  },
                  "tokenInfo": {
                    "binanceChainId": "56",
                    "contractAddress": "0x02Fca66C1D1aFB4E2A7884261eB00F63598a7436",
                    "symbol": "NVDAB",
                    "tokenId": null,
                    "decimals": 18
                  }
                }
              ]
            }
          }
        ]
      },
      {
        "txType": "approve",
        "txHash": "0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64",
        "txTime": "2026-10-03T22:18:17+01:00",
        "binanceChainId": "56",
        "status": "confirmed",
        "txHashList": [
          {
            "binanceChainId": "56",
            "txHash": "0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64",
            "status": "confirmed",
            "networkFee": {
              "binanceChainId": "56",
              "feeTokenAddress": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
              "feeTokenSymbol": "BNB",
              "feeValue": "2932518144096",
              "feeTokenDecimals": 18
            },
            "instructions": {
              "approve": {
                "binanceChainId": "56",
                "amount": "2000000000000000000",
                "to": {
                  "address": "0xb300000b72DEAEb607a12d5f54773D1C19c7028d"
                },
                "tokenInfo": {
                  "binanceChainId": "56",
                  "contractAddress": "0x55d398326f99059fF775485246999027B3197955",
                  "symbol": "USDT",
                  "tokenId": null,
                  "decimals": 18
                }
              }
            }
          }
        ]
      }
    ],
    "hasMore": false
  }
}
```

---

## 3. Earlier Files Transcribed from the Oct 3 (`2026-10-03T21:18Z`) Session Log

- `swap_stdout.json` — Transcribed from the Oct 3 log of `npx --yes @binance/agentic-wallet@1.10.0 market-order swap --fromTokenQty 2 --fromToken 0x55d398326f99059fF775485246999027B3197955 --toToken 0x02fca66c1d1afb4e2a7884261eb00f63598a7436 --binanceChainId 56 --slippage 0.5 --mev true --gasLevel MEDIUM --json`.
- `live_swap_nvda_2usd_initial_execution.json` — Transcribed from the Oct 3 log of the initial unreconciled `execution` block returned by `bine buy NVDA 2 --confirm --json` before child `orderId` fallback was added.
- `market_order_list_by_parent_id.json` — Transcribed from the Oct 3 log of `npx --yes @binance/agentic-wallet@1.10.0 market-order list --orderId 26100300001937918699 --json`.
- `market_order_list_all.json` — Transcribed from the Oct 3 log of `npx --yes @binance/agentic-wallet@1.10.0 market-order list --json`.
- `wallet_balance_post_swap.json` — Transcribed from the Oct 3 log of `npx --yes @binance/agentic-wallet@1.10.0 wallet balance --binanceChainId 56 --json`.
- `tx_history_post_swap.json` — Transcribed/summarized from the Oct 3 session log into a simplified `data.list` array; see `tx_history_2026-10-05.json` for the exact untouched `wallet tx-history` JSON output.
