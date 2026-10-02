# RWA Data API Reference

Source: pasted by user from https://web3.binance.com/en/dev-docs/catalog/web3-wallet/api/rest-api/rwa-data
Schema: https://web3.binance.com/en/dev-docs/catalog/web3-wallet/api/rest-api/1.0.0/schema.json

Base URL: https://web3.binance.com/build

All endpoints require signed headers (X-OC-APIKEY, X-OC-TIMESTAMP, X-OC-SIGN).

---

## 1. Get RWA Token Issuance Platforms

`GET /api/v1/dex/market/rwa/platforms`

**Query params:**
- `platformId` (optional, enum: `ondo`, `bstock`) — if omitted returns all

**Response `data[]`:**
- `platformId` (string)
- `tickerCount` (int)
- `chainDistribution[]` → `{ binanceChainId, tokenCount }`
- `website` (string|null)
- `logoUrl` (string|null)

**NOTE:** enum only has `ondo` and `bstock`. No `xstock` value. xStocks may not be in this API.

---

## 2. Get RWA Token Price

`GET /api/v1/dex/market/rwa/price`

**Query params (required):**
- `binanceChainId` (string, e.g. "56")
- `tokenContractAddresses` (string, comma-separated, max 100)

**Response `data[]`:**
- `binanceChainId`
- `tokenContractAddress`
- `platformId`
- `tokenPrice` (string, on-chain USD)
- `referencePrice` (string, USD — "per-share converted price derived from on-chain token price, not an official quote from the traditional stock market")
- `tokenPriceUpdatedAt` (int64, unix ms)

**CRITICAL NOTE:** referencePrice says "derived from the on-chain token price" — NOT an independent stock market quote. Needs verification with real data.

---

## 3. Search RWA Token

`GET /api/v1/dex/market/rwa/search`

**Query params:**
- `keyword` (required, string — ticker, company name, or contract address)
- `platformId` (optional, enum: `ondo`, `bstock`)

**Response `data[]`:**
- `ticker` (string, e.g. "NVDA")
- `companyName` (string)
- `assets[]` → `{ platformId, binanceChainId, tokenContractAddress, tokenSymbol, assetType }`
  - `assetType` enum: 1=Stock, 2=Pre-IPO, 3=ETF

---

## 4. Get RWA Underlying Info

`GET /api/v1/dex/market/rwa/underlying-profile`

**Query params (required):**
- `binanceChainId`
- `tokenContractAddress`

**Response `data`:** (single object, not array)
- `platformId`, `underlyingTicker`, `underlyingFullName`
- `assetType` (1=Stock, 2=Pre-IPO, 3=ETF)
- `tokenToShareRatio` (string, e.g. "1.003701")
- `protections` → keyed object: `{ dailyAttestationReport: { supported, url }, ... }`
- `companyInfo` → `{ ceo, website, industry, conceptsEn, descriptionEn, ... }`

---

## 5. Get RWA Token List

`GET /api/v1/dex/market/rwa/tokens`

**Query params (all optional):**
- `binanceChainId`
- `platformId` (enum: `ondo`, `bstock`)
- `tabId` (int, sector filter: 1=Serenity Call, 4=AI Chips, 9=Magnificent 7, 11=ETF, etc.)

**Response `data[]`:** (THE key endpoint for the sampler)
- `binanceChainId`, `tokenContractAddress`, `platformId`
- `assetType` (1=Stock, 2=Pre-IPO, 3=ETF)
- `tokenName`, `tokenSymbol`, `tokenLogoUrl`, `decimals`
- `underlyingTicker`, `underlyingName`
- `tokenToShareRatio` (string)
- `tags` (array|null, enum: alpha, communityRecognized, volumeSurge, volumePlunge)
- **`statusInfo`:**
  - `openState` (bool)
  - `marketStatus` (enum: premarket, regular, postmarket, overnight, closed, pause)
  - `reasonCode` (enum|null: TRADING, MARKET_CLOSED, MARKET_PAUSED, MARKET_MAINTENANCE, ASSET_PAUSED, ASSET_LIMITED, UNSUPPORTED)
  - `reasonMsg` (string|null, e.g. "Weekend or Holiday")
  - `nextOpenTime` (int64|null, unix ms)
  - `nextCloseTime` (int64|null, unix ms)
- **`tokenPrice`** (string, on-chain USD)
- **`referencePrice`** (string, USD — same caveat as /price)
- `volume24H` (string, USD)
- `marketCap` (string, USD)
- `peRatioTTM` (string|null)

---

## 6. Get RWA Underlying Market Data

`GET /api/v1/dex/market/rwa/underlying-market`

**Query params (required):**
- `binanceChainId`
- `tokenContractAddress`

**Response `data`:** (single object)
- `platformId`, `assetType`
- **`statusInfo`:** (same shape as /tokens)
- **`marketData`:**
  - `referencePrice` (string, USD — same caveat)
  - `high52W`, `low52W` (string)
  - `volumeShares24H`, `avgDailyVolume1Y` (string)
  - `totalShares`, `marketCap` (string)
  - `turnoverRate`, `amplitude` (string)
  - `peRatioTTM`, `pbRatio` (string|null) — Stock only
  - `dividendYield`, `latestDividend` (string|null)
