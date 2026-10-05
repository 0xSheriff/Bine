# Untouched `baw` Outputs (`$2.00` `NVDAB` Live Swap, `2026-10-03T21:18Z`)

This directory stores the untouched stdout payloads from `@binance/agentic-wallet@1.10.0` (`baw`) during the first live `$2.00` `NVDAB` swap on BNB Smart Chain (`chainId="56"`), along with the exact commands that produced them.

---

## 1. Initial `market-order swap` Execution (Parent `orderId`)

### Command
```bash
npx --yes @binance/agentic-wallet@1.10.0 market-order swap \
  --fromTokenQty 2 \
  --fromToken 0x55d398326f99059fF775485246999027B3197955 \
  --toToken 0x02fca66c1d1afb4e2a7884261eb00f63598a7436 \
  --binanceChainId 56 \
  --slippage 0.5 \
  --mev true \
  --gasLevel MEDIUM \
  --json
```

### Untouched stdout (`swap_stdout.json`)
```json
{
  "success": true,
  "data": {
    "orderId": "26100300001937918699"
  }
}
```

### Initial Unreconciled `execution` Object Recorded by `bine buy` (`live_swap_nvda_2usd_initial_execution.json`)
Because the first-time swap ran an `approve` transaction (`0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64`) before the `swap` transaction (`0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506`), polling `--orderId 26100300001937918699` returned an empty list and `bine buy` initially recorded:
```json
{
  "attempted": true,
  "live_mode_enabled": true,
  "status": "LIVE_TIMEOUT",
  "order_id": "26100300001937918699",
  "tx_hash": null,
  "bsctrace_url": null,
  "baw_command": "npx --yes @binance/agentic-wallet@1.10.0 market-order swap --fromTokenQty 2 --fromToken 0x55d398326f99059fF775485246999027B3197955 --toToken 0x02fca66c1d1afb4e2a7884261eb00f63598a7436 --binanceChainId 56 --slippage 0.5 --mev true --gasLevel MEDIUM --json",
  "detail": "Timed out polling `baw market-order list --orderId 26100300001937918699` after 25 attempts (50.0s).",
  "raw_output": {
    "success": true,
    "data": {
      "orderId": "26100300001937918699"
    }
  }
}
```

---

## 2. Querying `market-order list` with Parent `--orderId 26100300001937918699`

### Command
```bash
npx --yes @binance/agentic-wallet@1.10.0 market-order list --orderId 26100300001937918699 --json
```

### Untouched stdout (`market_order_list_by_parent_id.json`)
```json
{
  "success": true,
  "data": {
    "total": 0,
    "page": 1,
    "pageSize": 1,
    "list": []
  }
}
```

---

## 3. Querying `market-order list` Without `--orderId` (Child `orderId` `26100300001937918737`)

### Command
```bash
npx --yes @binance/agentic-wallet@1.10.0 market-order list --json
```

### Untouched stdout (`market_order_list_all.json`)
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

## 4. Post-Swap `wallet balance` (Share-Adjusted `NVDAB` Balance)

### Command
```bash
npx --yes @binance/agentic-wallet@1.10.0 wallet balance --binanceChainId 56 --json
```

### Untouched stdout (`wallet_balance_post_swap.json`)
```json
{
  "success": true,
  "data": [
    {
      "symbol": "NVDAB",
      "address": "0x02Fca66C1D1aFB4E2A7884261eB00F63598a7436",
      "binanceChainId": "56",
      "balance": "0.00851201289192116",
      "price": "235.07",
      "value": "2.0009188705039067"
    },
    {
      "symbol": "BNB",
      "address": "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
      "binanceChainId": "56",
      "balance": "0.000208450933066355",
      "price": "784.848679967365231827668058723732166991",
      "value": "0.16360243965509433"
    },
    {
      "symbol": "USDT",
      "address": "0x55d398326f99059fF775485246999027B3197955",
      "binanceChainId": "56",
      "balance": "3",
      "price": "0.999742434378111534231320721693088066",
      "value": "2.9992273031343344"
    }
  ]
}
```

---

## 5. Post-Swap `wallet tx-history` (`approve` + `swap` Transactions)

### Command
```bash
npx --yes @binance/agentic-wallet@1.10.0 wallet tx-history --binanceChainId 56 --json
```

### Untouched stdout (`tx_history_post_swap.json`)
```json
{
  "success": true,
  "data": {
    "list": [
      {
        "binanceChainId": "56",
        "txHash": "0x00c0fabd652f5897bde46ba8a3e3c4c6179bdf52734d870f23878363c228e506",
        "status": "SUCCESS",
        "type": "swap",
        "fromAddress": "0x34daabcaba08a9365c229e2ac7b25c14c6a6b730",
        "toAddress": "0xb300000b72deaeb607a12d5f54773d1c19c7028d",
        "feeValue": "47976548789549",
        "txTime": "1791062297"
      },
      {
        "binanceChainId": "56",
        "txHash": "0x803cda0317fd9aa667b193b958daad2ccc862d5d8532e23c6825837504aeeb64",
        "status": "SUCCESS",
        "type": "approve",
        "fromAddress": "0x34daabcaba08a9365c229e2ac7b25c14c6a6b730",
        "toAddress": "0x55d398326f99059ff775485246999027b3197955",
        "amount": "2000000000000000000",
        "feeValue": "2932518144096",
        "txTime": "1791062291"
      }
    ]
  }
}
```
