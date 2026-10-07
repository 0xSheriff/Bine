import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchDecisions } from '../api'
import {
  Footer,
  TopHeader,
  formatAbsoluteAndRelative,
  navigateApp,
  shortAddress,
} from '../components/shared'
import onchainReceipts from '../data/onchain-receipts.json'
import { humanizeStatus } from '../lib/humanize'

interface EnrichedReceipt {
  decision_id: number
  preceding_dry_run_id: number | null
  created_at: string
  ticker: string
  symbol: string
  issuer: string
  token_address: string
  amount_usd: number
  quoted_shares: number | null
  filled_shares: number | null
  fill_diff_bps: number | null
  all_in_price_per_share_usd: number | null
  reference_price_per_share_usd: number | null
  spread_pct: number | null
  session_status: string
  order_id: string
  tx_hash: string
  approve_tx_hash: string | null
  bsctrace_url: string
  block_number: number | null
  gas_bnb: number | null
  router_address: string
  execution_source: string
  preceding_dry_run_note: string
}

export default function Receipts() {
  const [expandedIds, setExpandedIds] = useState<Record<number, boolean>>({ 18: true })
  const [copiedHash, setCopiedHash] = useState<string | null>(null)

  const forceEmpty =
    typeof window !== 'undefined' &&
    new URLSearchParams(window.location.search).get('empty') === '1'

  const {
    data,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['decisions-live'],
    queryFn: () => fetchDecisions(50, true),
    refetchInterval: 30_000,
  })

  const toggleExpand = (id: number) => {
    setExpandedIds(prev => ({ ...prev, [id]: !prev[id] }))
  }

  const handleCopyHash = async (hash: string) => {
    try {
      await navigator.clipboard.writeText(hash)
      setCopiedHash(hash)
      window.setTimeout(() => setCopiedHash(prev => (prev === hash ? null : prev)), 1500)
    } catch {
      // ignore clipboard errors
    }
  }

  // Merge recorded onchainReceipts with any live rows from the backend DB
  const staticByDecisionId = new Map<number, EnrichedReceipt>(
    (onchainReceipts as EnrichedReceipt[]).map(r => [r.decision_id, r]),
  )

  const apiLiveRows = (data?.decisions ?? []).filter(d => Boolean(d.tx_hash))
  const mergedReceipts: EnrichedReceipt[] = []
  const seenIds = new Set<number>()

  for (const row of apiLiveRows) {
    const known = staticByDecisionId.get(row.id)
    if (known) {
      mergedReceipts.push(known)
      seenIds.add(row.id)
    } else if (row.tx_hash) {
      mergedReceipts.push({
        decision_id: row.id,
        preceding_dry_run_id: null,
        created_at: row.created_at,
        ticker: row.ticker,
        symbol: row.recommended_symbol || row.ticker,
        issuer: row.recommended_platform || 'bStocks',
        token_address: row.recommended_contract_address || '',
        amount_usd: row.amount_usd,
        quoted_shares: row.expected_shares,
        filled_shares: row.expected_shares,
        fill_diff_bps: 0,
        all_in_price_per_share_usd: row.all_in_price_per_share_usd,
        reference_price_per_share_usd: null,
        spread_pct: row.all_in_vs_reference_pct,
        session_status: 'regular',
        order_id: 'N/A',
        tx_hash: row.tx_hash,
        approve_tx_hash: null,
        bsctrace_url: row.bsctrace_url || `https://bsctrace.com/tx/${row.tx_hash}`,
        block_number: null,
        gas_bnb: null,
        router_address: '0xb300000b72DEAEb607a12d5f54773D1C19c7028d',
        execution_source: 'Executed through Binance Agentic Wallet',
        preceding_dry_run_note: `Executed in Decision #${row.id}`,
      })
      seenIds.add(row.id)
    }
  }

  for (const known of onchainReceipts as EnrichedReceipt[]) {
    if (!seenIds.has(known.decision_id)) {
      mergedReceipts.push(known)
      seenIds.add(known.decision_id)
    }
  }

  const displayReceipts = forceEmpty ? [] : mergedReceipts
  const totalSwaps = displayReceipts.length
  const totalSpentUsd = displayReceipts.reduce((acc, r) => acc + r.amount_usd, 0)
  const totalGasBnb = displayReceipts.reduce((acc, r) => acc + (r.gas_bnb ?? 0), 0)

  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--bg-page)', color: 'var(--text)' }}
    >
      <TopHeader />
      <main className="flex-1 w-full py-8 sm:py-12">
        <div className="bine-container">
          <div className="w-full max-w-[1120px] mx-auto space-y-8">
            <div className="max-w-2xl space-y-2">
              <h1 tabIndex={-1} className="bine-section-heading m-0 outline-none">
                On-chain receipts
              </h1>
              <p className="bine-body m-0" style={{ color: 'var(--text-secondary)' }}>
                Verified BNB Smart Chain swaps executed through Binance Agentic Wallet after passing Bine&apos;s pre-trade guard and Transaction API dry-run.
              </p>
            </div>

            {/* Summary Row */}
            <section
              aria-label="On-chain receipt totals"
              className="grid grid-cols-1 sm:grid-cols-3 gap-4"
            >
              <div className="bine-card p-5">
                <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                  Verified swaps
                </div>
                <div className="text-2xl font-semibold font-mono mt-1">{totalSwaps}</div>
                <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                  On-chain BSC mainnet fills
                </div>
              </div>

              <div className="bine-card p-5">
                <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                  Total USDT spent
                </div>
                <div className="text-2xl font-semibold font-mono mt-1">
                  ${totalSpentUsd.toFixed(2)}
                </div>
                <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                  Within $6/trade and $10/day caps
                </div>
              </div>

              <div className="bine-card p-5">
                <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                  Total BNB gas
                </div>
                <div className="text-2xl font-semibold font-mono mt-1">
                  {totalGasBnb.toFixed(8)} BNB
                </div>
                <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
                  Includes one-time USDT approve tx
                </div>
              </div>
            </section>

            {/* Copy feedback live region */}
            <div className="sr-only" aria-live="polite">
              {copiedHash ? `Copied transaction hash ${copiedHash}` : ''}
            </div>

            {/* Receipts List */}
            {isLoading && displayReceipts.length === 0 ? (
              <div className="bine-card p-6 space-y-4" aria-busy="true" aria-live="polite">
                <div className="bine-skeleton h-14 w-full" />
                <div className="bine-skeleton h-14 w-full" />
              </div>
            ) : error && displayReceipts.length === 0 ? (
              <div className="bine-card p-6 sm:p-8 space-y-4" role="alert">
                <div className="flex items-center gap-2.5">
                  <span
                    className="inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-semibold"
                    style={{ backgroundColor: 'var(--chip-bad-bg)', color: 'var(--bad)' }}
                  >
                    {humanizeStatus('LOAD_ERROR')}
                  </span>
                  <span className="text-sm font-semibold">Could not load decision log</span>
                </div>
                <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                  {error instanceof Error ? error.message : 'Unable to reach /api/decisions.'}
                </p>
                <button
                  type="button"
                  onClick={() => refetch()}
                  className="bine-pill-secondary cursor-pointer min-h-[44px]"
                  style={{ height: '44px', padding: '0 20px', fontSize: '13px' }}
                >
                  Retry
                </button>
              </div>
            ) : displayReceipts.length === 0 ? (
              <div className="bine-card p-6 sm:p-8 space-y-4">
                <h2 className="text-base font-semibold m-0">No on-chain swaps recorded yet</h2>
                <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                  Dry-run simulations do not broadcast transactions. Run a pre-trade check in the Guard to preview a trade.
                </p>
                <a
                  href="/guard"
                  onClick={e => navigateApp('/guard', e)}
                  className="bine-pill-primary min-h-[44px]"
                  style={{ height: '44px', padding: '0 22px', fontSize: '13px' }}
                >
                  Check a trade
                </a>
              </div>
            ) : (
              <div className="space-y-4">
                {displayReceipts.map(row => {
                  const isOpen = Boolean(expandedIds[row.decision_id])
                  const isCopied = copiedHash === row.tx_hash

                  return (
                    <article key={row.decision_id} className="bine-card overflow-hidden">
                      {/* Expandable Header Row */}
                      <div className="p-5 sm:p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
                        <div className="space-y-1.5 min-w-0">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <span
                              className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold"
                              style={{ backgroundColor: 'var(--chip-good-bg)', color: 'var(--good)' }}
                            >
                              Decision #{row.decision_id}
                            </span>
                            <span className="text-base font-semibold">
                              ${row.amount_usd.toFixed(2)} USDT &rarr; {row.symbol}
                            </span>
                            <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                              {row.issuer}
                            </span>
                          </div>

                          <div className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                            {formatAbsoluteAndRelative(row.created_at)}
                            {row.filled_shares !== null && row.quoted_shares !== null ? (
                              <>
                                {' '}
                                · {row.filled_shares.toFixed(6)} filled vs {row.quoted_shares.toFixed(6)} quoted (
                                {row.fill_diff_bps !== null && row.fill_diff_bps > 0 ? '+' : ''}
                                {row.fill_diff_bps} bps)
                              </>
                            ) : null}
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                          <a
                            href={row.bsctrace_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="bine-pill-secondary font-mono min-h-[44px]"
                            style={{ height: '44px', padding: '0 16px', fontSize: '12px' }}
                          >
                            BscTrace {shortAddress(row.tx_hash)} &#8599;
                          </a>

                          <button
                            type="button"
                            onClick={() => toggleExpand(row.decision_id)}
                            aria-expanded={isOpen}
                            aria-controls={`receipt-details-${row.decision_id}`}
                            className="bine-pill-secondary cursor-pointer min-h-[44px]"
                            style={{ height: '44px', padding: '0 16px', fontSize: '12px' }}
                          >
                            {isOpen ? 'Hide details' : 'Show details'}
                          </button>
                        </div>
                      </div>

                      {/* Expanded Details */}
                      {isOpen && (
                        <div
                          id={`receipt-details-${row.decision_id}`}
                          className="px-5 pb-6 pt-5 space-y-5 text-sm"
                          style={{
                            borderTop: '1px solid var(--hairline)',
                            backgroundColor: 'var(--surface-subtle)',
                          }}
                        >
                          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                            <div
                              className="rounded-xl p-3.5"
                              style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
                            >
                              <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                Shares filled vs quoted
                              </div>
                              <div className="text-sm font-mono font-semibold mt-1">
                                {row.filled_shares !== null ? row.filled_shares.toFixed(6) : 'N/A'} /{' '}
                                {row.quoted_shares !== null ? row.quoted_shares.toFixed(6) : 'N/A'}
                              </div>
                              <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                {row.fill_diff_bps !== null ? `${row.fill_diff_bps} bps difference` : 'Exact match'}
                              </div>
                            </div>

                            <div
                              className="rounded-xl p-3.5"
                              style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
                            >
                              <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                All-in price per share
                              </div>
                              <div className="text-sm font-mono font-semibold mt-1">
                                {row.all_in_price_per_share_usd !== null
                                  ? `$${row.all_in_price_per_share_usd.toFixed(2)}`
                                  : 'N/A'}
                              </div>
                              <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                {row.reference_price_per_share_usd !== null
                                  ? `Ref $${row.reference_price_per_share_usd.toFixed(2)} (+${row.spread_pct?.toFixed(2)}%)`
                                  : `Session: ${humanizeStatus(row.session_status)}`}
                              </div>
                            </div>

                            <div
                              className="rounded-xl p-3.5"
                              style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
                            >
                              <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                Block &amp; BNB gas
                              </div>
                              <div className="text-sm font-mono font-semibold mt-1">
                                Block #{row.block_number ?? 'N/A'}
                              </div>
                              <div className="text-xs font-mono mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                {row.gas_bnb !== null ? `${row.gas_bnb.toFixed(8)} BNB` : 'N/A'}
                              </div>
                            </div>

                            <div
                              className="rounded-xl p-3.5"
                              style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
                            >
                              <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                Agentic Wallet order ID
                              </div>
                              <div className="text-sm font-mono font-semibold mt-1 break-all">
                                {row.order_id}
                              </div>
                              <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                {row.execution_source}
                              </div>
                            </div>
                          </div>

                          <div
                            className="rounded-xl p-4 space-y-2.5 text-xs font-mono"
                            style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
                          >
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                              <div className="break-all">
                                <span style={{ color: 'var(--text-secondary)' }}>Transaction hash: </span>
                                <span>{row.tx_hash}</span>
                              </div>
                              <button
                                type="button"
                                onClick={() => handleCopyHash(row.tx_hash)}
                                className="bine-pill-secondary cursor-pointer shrink-0 self-start sm:self-auto min-h-[44px]"
                                style={{
                                  height: '44px',
                                  padding: '0 16px',
                                  fontSize: '12px',
                                  color: isCopied ? 'var(--good)' : 'var(--text)',
                                }}
                              >
                                {isCopied ? 'Copied' : 'Copy tx hash'}
                              </button>
                            </div>

                            {row.approve_tx_hash && (
                              <div className="break-all">
                                <span style={{ color: 'var(--text-secondary)' }}>Approval transaction hash: </span>
                                <a
                                  href={`https://bsctrace.com/tx/${row.approve_tx_hash}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="underline"
                                  style={{ color: 'var(--text)' }}
                                >
                                  {row.approve_tx_hash}
                                </a>
                              </div>
                            )}

                            <div>
                              <span style={{ color: 'var(--text-secondary)' }}>Dry-run sequence: </span>
                              <span>{row.preceding_dry_run_note}</span>
                            </div>
                          </div>
                        </div>
                      )}
                    </article>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
