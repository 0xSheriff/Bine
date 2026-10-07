/**
 * Plain-English labels for backend refusal codes, decision statuses,
 * simulation statuses, and response fields.
 *
 * Standing rule: Never display raw snake_case identifiers in UI text;
 * route every backend enum or code through this module.
 */

export const REFUSAL_CODE_LABELS: Record<string, string> = {
  slippage_too_high: 'Slippage too high',
  below_issuer_minimum: 'Below issuer minimum',
  quality_unreliable: 'Share ratio or price outlier',
  depth_thin: 'Order-book depth too thin',
  session_closed: 'US market session closed',
  session_paused: 'Market session paused',
  no_supported_token: 'Ticker not in catalog',
  over_cap: 'Exceeds trade cap',
  quote_failed: 'Upstream quote unavailable',
  data_stale: 'Catalog data stale',
  rate_limited: 'Rate limit reached',
  missing_api_keys: 'Binance API keys missing',
};

export const STATUS_LABELS: Record<string, string> = {
  REQUIRES_APPROVAL: 'Sim router needs allowance',
  DRY_RUN_OK: 'Dry-run passed',
  SIMULATION_PASSED: 'Simulation passed',
  SIMULATION_FAILED: 'Simulation failed',
  LIVE_SUBMITTED: 'Live swap submitted',
  LIVE_CONFIRMED: 'Live swap confirmed',
  REFUSED: 'Refused',
  BUY: 'Buy',
  REFUSE: 'Refuse',
  LOAD_ERROR: 'Load error',
  REGULAR: 'Regular hours',
  OPEN: 'Market open',
  CLOSED: 'Market closed',
  PAUSED: 'Market paused',
  MARKET_PAUSED: 'Market paused',
  PRE_MARKET: 'Pre-market',
  AFTER_HOURS: 'After hours',
  OVERNIGHT: 'Overnight session',
  amm_pools: 'AMM pools',
  catalog_volume_24h: '24h catalog volume',
};

export const FIELD_LABELS: Record<string, string> = {
  schema_version: 'Schema version',
  ticker: 'Ticker',
  amount_usd: 'Amount in USD',
  quoted_at: 'Quoted timestamp',
  verdict: 'Verdict',
  token: 'Selected token',
  shares: 'Estimated shares',
  all_in_price_per_share: 'All-in price per share',
  reference_price_per_share: 'Reference price per share',
  spread_pct: 'Spread percentage',
  refusal: 'Refusal reason',
  alternative: 'Alternative issuer',
  market: 'Market session',
  details: 'Audit details',
  tx_hash: 'Transaction hash',
  approve_tx_hash: 'Approval transaction hash',
  dry_run_sequence: 'Dry-run sequence',
  execution_status: 'Execution status',
  simulation_status: 'Simulation status',
  refusal_code: 'Refusal rule',
  refusal_message: 'Refusal message',
  order_id: 'Order ID',
};

export function fallbackHumanize(raw: string | null | undefined): string {
  if (!raw) return '';
  const cleaned = String(raw).trim().replace(/_/g, ' ');
  if (!cleaned) return '';
  // If ALL CAPS with spaces, convert to sentence case unless it's a short known acronym
  if (cleaned === cleaned.toUpperCase() && cleaned.includes(' ')) {
    const lower = cleaned.toLowerCase();
    return lower.charAt(0).toUpperCase() + lower.slice(1);
  }
  return cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
}

export function humanizeCode(code: string | null | undefined): string {
  if (!code) return 'None';
  const trimmed = String(code).trim();
  return REFUSAL_CODE_LABELS[trimmed] ?? STATUS_LABELS[trimmed] ?? FIELD_LABELS[trimmed] ?? fallbackHumanize(trimmed);
}

export function humanizeStatus(status: string | null | undefined): string {
  if (!status) return 'Not run';
  const trimmed = String(status).trim();
  return STATUS_LABELS[trimmed] ?? REFUSAL_CODE_LABELS[trimmed] ?? fallbackHumanize(trimmed);
}

export function humanizeField(field: string | null | undefined): string {
  if (!field) return '';
  const trimmed = String(field).trim();
  return FIELD_LABELS[trimmed] ?? fallbackHumanize(trimmed);
}
