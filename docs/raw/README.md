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
| `rwa_tokens_no_key_2026-10-05.txt` | **Captured live (`2026-10-05`)** | Raw HTTP status, `Location` header, and response body for keyless `GET /api/v1/dex/market/rwa/tokens` (`HTTP 401`, `code: 40101`) and `GET /rwa/tokens` (`HTTP 302`). |
| `regular_hours_quotes_2026-10-05.jsonl` | **Captured live (`2026-10-05T15:04Z`)** | 18 live quotes across `NVDAB`, `NVDAon`, `SPYB`, `SPYon`, `KLACon`, `NFLXon`, `PPLTon`, `CVNAon`, and `NOWon` at `$5.50` and `$25.00` during US regular trading hours (`marketStatus = "regular"`, 94 minutes after open / `11:04` New York). |
| `wallet_balance_second_swap_2026-10-05.json` | **Captured live (`2026-10-05T15:05Z`)** | Direct pipe (`tee`) of `npx --yes @binance/agentic-wallet@1.10.0 wallet balance --binanceChainId 56 --json` immediately after the second `$2.00` `NVDAB` swap (`0.016939642456644862 NVDAB`, `1.00 USDT`). |
| `market_order_list_second_swap_2026-10-05.json` | **Captured live (`2026-10-05T15:05Z`)** | Direct pipe (`tee`) of `npx --yes @binance/agentic-wallet@1.10.0 market-order list --json` showing both finished `$2.00` `NVDAB` orders (`26100500001942767719` and `26100300001937918737`). |
| `tx_history_second_swap_2026-10-05.json` | **Captured live (`2026-10-05T15:05Z`)** | Direct pipe (`tee`) of `npx --yes @binance/agentic-wallet@1.10.0 wallet tx-history --binanceChainId 56 --json` showing today's swap (`0xa3693383...3e75`) and the Oct 3 swap + approve transactions. |
| `usdt_allowance_2026-10-05.txt` | **Queried live (`2026-10-05`)** | Raw JSON-RPC `eth_call` (`0xdd62ed3e` `allowance(owner, spender)`) requests and responses against `https://bsc-dataseed.binance.org` for owner `0x34dAAbcAba08A9365C229e2Ac7b25C14c6a6b730` and spenders `0xb300000b72DEAEb607a12d5f54773D1C19c7028d` (`uint256.max - 4 * 10^18`) and `0xB44446b0c8E56988c34f7Ff73Ae904982b5FdDA5` (`0`). |

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
