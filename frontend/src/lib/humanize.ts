/**
 * Plain-English labels for backend refusal codes, decision statuses,
 * simulation statuses, and response fields.
 *
 * Standing rule: Never display raw snake_case identifiers in UI text;
 * route every backend enum or code through this module.
 */

export const REFUSAL_CODE_LABELS: Record<string, string> = {
  amount_over_cap: 'Order size cap',
  below_issuer_minimum: 'Below issuer minimum',
  market_closed: 'Trading session closed',
  reference_stale: 'Reference price stale',
  quality_unreliable: 'Share ratio or price outlier',
  depth_thin: 'Order-book depth too thin',
  slippage_too_high: 'Slippage too high',
  unknown_ticker: 'Ticker not in catalog',
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
  CLOSED: 'Session closed',
  PAUSED: 'Session closed',
  MARKET_PAUSED: 'Session closed',
  PRE_MARKET: 'Pre-market',
  AFTER_HOURS: 'After hours',
  OVERNIGHT: 'Overnight session',
  regular: 'Regular hours',
  'regular hours': 'Regular hours',
  'after hours': 'After hours',
  offhours: 'After hours',
  overnight: 'Overnight session',
  amm_pools: 'AMM pools',
  pmm_rfq_24h_volume: '24h RFQ volume',
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

export const GUARD_RULE_DEFINITIONS: Record<
  string,
  { name: string; explanation: string; threshold: string }
> = {
  amount_over_cap: {
    name: 'Order size cap',
    explanation: 'Protects against non-positive orders or single quotes above the $2,500.00 safety limit.',
    threshold: '> $0.00 to <= $2,500.00',
  },
  below_issuer_minimum: {
    name: 'Issuer minimum order',
    explanation:
      'Blocks orders rejected by the issuer minimum ($5.00 on Ondo [40375]; $0.01 tie-break floor on bStocks, tested live at $2.00).',
    threshold: '$5.00 Ondo / $0.01 bStocks',
  },
  market_closed: {
    name: 'Trading session open',
    explanation:
      'Stops trades when openState is not true, reasonCode is not TRADING, marketStatus is paused/closed, or quote returns 40367/40369.',
    threshold: 'openState=true & TRADING (no 40367/40369)',
  },
  reference_stale: {
    name: 'Reference price freshness',
    explanation: 'Requires a positive reference stock price sampled within the 120-second freshness limit.',
    threshold: '> $0.00 & <= 120s age',
  },
  quality_unreliable: {
    name: 'Token price & ratio sanity',
    explanation:
      'Requires token and reference price >= $1.00, share ratio in 0.25-5.00x (<= 1% ratio divergence), and 24h volume >= $1,000,000.',
    threshold: '>= $1.00, 0.25-5.00x ratio, >= $1M 24h vol',
  },
  depth_thin: {
    name: 'On-chain pool depth',
    explanation:
      'Requires a valid route plus AMM pool depth >= $10,000 and >= 10x order size (or >= $1,000,000 24h volume when RFQ-only).',
    threshold: '>= $10K & >= 10x order AMM (or >= $1M 24h vol)',
  },
  slippage_too_high: {
    name: 'All-in slippage vs stock',
    explanation:
      'Refuses quotes where effective slippage (max of execution spread vs reference or price impact) exceeds 1.00%.',
    threshold: '<= 1.00% (100 bps)',
  },
  unknown_ticker: {
    name: 'Verified BSC token contract',
    explanation:
      'Only routes to tickers present in the live BNB Chain (chain 56) Ondo Global Markets or bStocks RWA catalog.',
    threshold: 'In BSC (56) Ondo / bStocks catalog',
  },
};

export const GUARD_RULES_COUNT = Object.keys(GUARD_RULE_DEFINITIONS).length;

/**
 * Derive session tag strictly from UTC timestamp.
 * US regular hours: Monday-Friday 13:30 to 20:00 UTC.
 * All other times are after hours.
 */
export function deriveSessionFromUtc(isoString: string): 'regular hours' | 'after hours' {
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return 'after hours';
  const day = d.getUTCDay(); // 0 = Sun, 1 = Mon, ..., 5 = Fri, 6 = Sat
  if (day >= 1 && day <= 5) {
    const minutes = d.getUTCHours() * 60 + d.getUTCMinutes();
    if (minutes >= 810 && minutes < 1200) {
      return 'regular hours';
    }
  }
  return 'after hours';
}

/**
 * Format timestamp in UTC with West Africa Time (WAT = UTC+1) in brackets,
 * e.g. "2026-10-05 15:04 UTC [16:04 WAT]".
 */
export function formatUtcAndWat(isoString: string): string {
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return isoString;

  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  const hhUtc = String(d.getUTCHours()).padStart(2, '0');
  const minUtc = String(d.getUTCMinutes()).padStart(2, '0');

  // WAT is UTC + 1 hour
  const watDate = new Date(d.getTime() + 60 * 60 * 1000);
  const hhWat = String(watDate.getUTCHours()).padStart(2, '0');
  const minWat = String(watDate.getUTCMinutes()).padStart(2, '0');

  return `${yyyy}-${mm}-${dd} ${hhUtc}:${minUtc} UTC [${hhWat}:${minWat} WAT]`;
}

/**
 * Live US market session status computed live from current UTC time.
 */
export function getLiveMarketSession(nowDate: Date = new Date()): {
  isRegular: boolean;
  label: string;
} {
  const day = nowDate.getUTCDay();
  const minutes = nowDate.getUTCHours() * 60 + nowDate.getUTCMinutes();
  const isRegular = day >= 1 && day <= 5 && minutes >= 810 && minutes < 1200;
  return {
    isRegular,
    label: isRegular ? 'US regular trading hours' : 'US market after-hours / closed',
  };
}


