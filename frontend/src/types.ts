// Shared API types matching the FastAPI backend schema (Frozen Phase 1 Contract).

export interface QuoteToken {
  symbol: string
  address: string
  issuer: 'ondo' | 'bstock' | string
}

export interface QuoteRefusal {
  code:
    | 'amount_over_cap'
    | 'below_issuer_minimum'
    | 'market_closed'
    | 'reference_stale'
    | 'depth_thin'
    | 'slippage_too_high'
    | 'quality_unreliable'
    | 'unknown_ticker'
    | string
  message: string
}

export interface QuoteAlternative {
  symbol: string
  issuer: 'ondo' | 'bstock' | string
  eligible: boolean
  note: string
}

export interface QuoteMarket {
  status: string
  open: boolean
}

export interface IssuerDetailRow {
  symbol: string
  issuer: string
  issuer_label: string
  address: string
  eligible: boolean
  shares: number | null
  tokens_received: number | null
  token_to_share_ratio: number | null
  all_in_price_per_share: number | null
  reference_price_per_share: number | null
  spread_pct: number | null
  slippage_pct: number | null
  depth_usd: number | null
  depth_source: string | null
  pool_count: number | null
  route: string | null
  execution_note?: string | null
  latency_ms: number | null
  refusal_code: string | null
  refusal_message: string | null
  bsctrace_url: string
}

export interface QuoteDetails {
  tiebreak_applied: boolean
  live_execution_allowed: boolean
  max_live_trade_usd: number
  issuers: IssuerDetailRow[]
}

export interface QuoteVerdictResponse {
  schema_version: string
  ticker: string
  amount_usd: number
  quoted_at: string
  verdict: 'BUY' | 'REFUSE'
  token: QuoteToken | null
  shares: number | null
  all_in_price_per_share: number | null
  reference_price_per_share: number | null
  spread_pct: number | null
  refusal: QuoteRefusal | null
  alternative: QuoteAlternative | null
  market: QuoteMarket
  details?: QuoteDetails
}

export interface TickerItem {
  ticker: string
  issuers: string[]
  dual: boolean
}

export interface TickerListResponse {
  count: number
  tickers: TickerItem[]
  catalog_examples?: {
    share_ratio: {
      ticker: string
      symbol: string
      token_to_share_ratio: number
    }
    session_closed: {
      ticker: string
      symbol: string
      market_status: string
      reason_code: string
    }
  }
}

export interface HealthResponse {
  status: string
  schema_version: string
  live_mode: boolean
  binance_credentials_present?: boolean
  max_trade_usd: number
  daily_cap_usd: number
  sample_count: number
  oldest_sample: string | null
  newest_sample: string | null
  now: string
}

export interface DryRunSimulationResult {
  ran: boolean
  passed: boolean
  status: 'SUCCESS' | 'REQUIRES_APPROVAL' | 'FAILED' | 'SKIPPED' | string
  fail_reason: string | null
  swap_tx_to: string | null
  swap_tx_value: string | null
  swap_tx_gas_limit: string | null
  swap_tx_gas_price: string | null
  swap_tx_calldata_bytes: number
  swap_balance_changes: Array<Record<string, unknown>>
  approval_required: boolean
  approval_simulation_status: string | null
  approval_spender: string | null
  approval_allowance_changes: Array<Record<string, unknown>>
  summary: string
}

export interface LiveExecutionResult {
  attempted: boolean
  live_mode_enabled: boolean
  status:
    | 'REFUSED'
    | 'DRY_RUN_OK'
    | 'DRY_RUN_FAILED'
    | 'LIVE_SUBMITTED'
    | 'LIVE_BLOCKED_CAP'
    | 'LIVE_DISABLED'
    | 'LIVE_UNAUTHORIZED'
    | 'LIVE_ERROR'
    | string
  order_id?: string | null
  tx_hash: string | null
  bsctrace_url: string | null
  baw_command: string | null
  detail: string
  raw_output: Record<string, unknown> | null
}

export interface ExecuteTradeResponse {
  decision_id: number
  created_at: string
  ticker: string
  amount_usd: number
  action: 'dry_run' | 'execute'
  verdict: 'BUY' | 'REFUSE'
  recommended_platform: string | null
  recommended_symbol: string | null
  recommended_contract_address: string | null
  refusal_code: string | null
  reason: string
  why_others_lost: string[]
  simulation: DryRunSimulationResult
  execution: LiveExecutionResult
  quote: QuoteVerdictResponse
}

export interface DecisionLogEntry {
  id: number
  created_at: string
  ticker: string
  amount_usd: number
  action: string
  verdict: string
  recommended_platform: string | null
  recommended_symbol: string | null
  recommended_contract_address: string | null
  refusal_code: string | null
  reason: string
  expected_shares: number | null
  all_in_price_per_share_usd: number | null
  all_in_vs_reference_pct: number | null
  effective_slippage_pct: number | null
  simulation_ran: boolean
  simulation_status: string | null
  simulation_fail_reason: string | null
  approval_simulation_status: string | null
  spender_address: string | null
  estimated_gas_limit: string | null
  live_mode: boolean
  execution_status: string
  tx_hash: string | null
  bsctrace_url: string | null
  execution_detail: string | null
}

export interface DecisionListResponse {
  count: number
  decisions: DecisionLogEntry[]
}
