import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  executeTrade,
  fetchDecisions,
  fetchHealth,
  fetchQuote,
  fetchTickers,
} from '../api'
import {
  TopHeader,
  formatCompactUsd,
  formatSecondsAgo,
  shortAddress,
} from '../components/shared'
import type { ExecuteTradeResponse, QuoteVerdictResponse } from '../types'

function formatSimStatus(status: string | null | undefined) {
  if (!status) return <span>N/A</span>
  if (status === 'REQUIRES_APPROVAL') {
    return (
      <span
        title="The dry-run simulates against router 0xB444.... Live swaps through baw use router 0xb300.... See README."
        className="underline decoration-dotted cursor-help"
      >
        Sim router needs allowance
      </span>
    )
  }
  return <span>{status}</span>
}

function formatBuyHeadline(q: QuoteVerdictResponse): string {
  const shares = q.shares !== null ? q.shares.toFixed(4) : '0.0000'
  const amt = q.amount_usd.toFixed(2)
  const allIn = q.all_in_price_per_share !== null ? q.all_in_price_per_share.toFixed(2) : 'N/A'
  const spread = q.spread_pct ?? 0
  const absSpread = Math.abs(spread).toFixed(2)
  const dir =
    Math.abs(spread) < 0.005
      ? 'at reference'
      : spread < 0
        ? `${absSpread}% under reference`
        : `${absSpread}% over reference`
  return `Buy ${shares} ${q.ticker} for $${amt}. All-in $${allIn} per share, ${dir}.`
}

export default function Home() {
  const urlParams = new URLSearchParams(typeof window !== 'undefined' ? window.location.search : '')
  const initialTicker = (urlParams.get('ticker') || 'NVDA').trim().toUpperCase()
  const rawAmtParam = urlParams.get('amount')
  const initialAmount = rawAmtParam ? Number(rawAmtParam) || 5.5 : 5.5

  const [tickerInput, setTickerInput] = useState<string>(initialTicker)
  const [amountInput, setAmountInput] = useState<string>(rawAmtParam || '5.50')
  const [activeTicker, setActiveTicker] = useState<string>(initialTicker)
  const [activeAmount, setActiveAmount] = useState<number>(initialAmount)
  const [confirmOpen, setConfirmOpen] = useState<boolean>(false)
  const [receipt, setReceipt] = useState<ExecuteTradeResponse | null>(null)
  const [, setNowTick] = useState<number>(0)

  const queryClient = useQueryClient()

  // Debounce input changes by 400ms
  useEffect(() => {
    const handle = window.setTimeout(() => {
      const cleanTkr = tickerInput.trim().toUpperCase()
      const parsedAmt = Number(amountInput)
      if (cleanTkr && Number.isFinite(parsedAmt) && parsedAmt > 0) {
        setActiveTicker(cleanTkr)
        setActiveAmount(parsedAmt)
      }
    }, 400)
    return () => window.clearTimeout(handle)
  }, [tickerInput, amountInput])

  // Refresh the "Quoted Xs ago" label every 5 seconds
  useEffect(() => {
    const id = window.setInterval(() => setNowTick(t => t + 1), 5000)
    return () => window.clearInterval(id)
  }, [])

  // Reset confirmation panel when ticker or amount changes
  useEffect(() => {
    setConfirmOpen(false)
    setReceipt(null)
  }, [activeTicker, activeAmount])

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  })

  const { data: tickerCatalog } = useQuery({
    queryKey: ['tickers'],
    queryFn: fetchTickers,
    staleTime: 300_000,
  })

  const {
    data: quote,
    isLoading: quoteLoading,
    isFetching: quoteFetching,
    error: quoteError,
  } = useQuery({
    queryKey: ['quote', activeTicker, activeAmount],
    queryFn: () => fetchQuote(activeTicker, activeAmount, true),
    staleTime: 15_000,
  })

  const { data: decisionsData } = useQuery({
    queryKey: ['decisions'],
    queryFn: () => fetchDecisions(5),
    refetchInterval: 20_000,
  })

  const dryRunMutation = useMutation({
    mutationFn: () => executeTrade(activeTicker, activeAmount, false),
    onSuccess: data => {
      setReceipt(data)
      setConfirmOpen(true)
      queryClient.invalidateQueries({ queryKey: ['decisions'] })
    },
  })

  const confirmLiveMutation = useMutation({
    mutationFn: () => executeTrade(activeTicker, activeAmount, true),
    onSuccess: data => {
      setReceipt(data)
      queryClient.invalidateQueries({ queryKey: ['decisions'] })
    },
  })

  const liveModeOn = Boolean(health?.live_mode)
  const isBuy = quote?.verdict === 'BUY'
  const issuerList = quote?.details?.issuers ?? []
  const recentDecisions = decisionsData?.decisions ?? []

  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden"
      style={{
        backgroundColor: 'var(--bg)',
        color: 'var(--text)',
      }}
    >
      <TopHeader />

      <main className="flex-1 max-w-3xl w-full mx-auto px-4 sm:px-6 py-8 sm:py-12 space-y-8 min-w-0">
        {/* 1. ONE INPUT ROW: Ticker + USD Amount */}
        <section
          className="rounded-lg p-5 sm:p-6"
          style={{
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="min-w-0">
              <label
                htmlFor="ticker-input"
                className="block text-sm font-medium mb-1.5"
                style={{ color: 'var(--muted)' }}
              >
                Stock ticker
              </label>
              <input
                id="ticker-input"
                type="text"
                list="bine-ticker-list"
                value={tickerInput}
                onChange={e => setTickerInput(e.target.value.toUpperCase())}
                placeholder="NVDA"
                autoComplete="off"
                className="w-full px-3.5 py-2.5 rounded border font-mono text-base focus:outline-none"
                style={{
                  backgroundColor: 'var(--bg)',
                  borderColor: 'var(--border)',
                  color: 'var(--text)',
                }}
              />
              <datalist id="bine-ticker-list">
                {(tickerCatalog?.tickers ?? []).map(item => (
                  <option key={item.ticker} value={item.ticker}>
                    {item.ticker} ({item.issuers.join(', ')})
                  </option>
                ))}
              </datalist>
            </div>

            <div className="min-w-0">
              <label
                htmlFor="amount-input"
                className="block text-sm font-medium mb-1.5"
                style={{ color: 'var(--muted)' }}
              >
                Amount (USD)
              </label>
              <div className="relative flex items-center">
                <span
                  className="absolute left-3.5 font-mono text-base pointer-events-none"
                  style={{ color: 'var(--muted)' }}
                >
                  $
                </span>
                <input
                  id="amount-input"
                  type="number"
                  step="any"
                  min="0.01"
                  value={amountInput}
                  onChange={e => setAmountInput(e.target.value)}
                  placeholder="5"
                  className="w-full pl-8 pr-3.5 py-2.5 rounded border font-mono text-base focus:outline-none"
                  style={{
                    backgroundColor: 'var(--bg)',
                    borderColor: 'var(--border)',
                    color: 'var(--text)',
                  }}
                />
              </div>
            </div>
          </div>
        </section>

        {/* 2. RESULT: One large sentence + BUY/REFUSE chip + tiebreak/alternative line + one freshness note */}
        <section
          className="rounded-lg p-6 sm:p-8 space-y-5"
          style={{
            backgroundColor: 'var(--surface)',
            border: '1px solid var(--border)',
          }}
        >
          {quoteLoading && !quote ? (
            <p className="text-base" style={{ color: 'var(--muted)' }}>
              Checking live tokenized stock quotes on BNB Chain…
            </p>
          ) : quoteError ? (
            <div className="space-y-2">
              <span
                className="inline-block px-2.5 py-0.5 rounded text-xs font-semibold tracking-wide uppercase"
                style={{
                  backgroundColor: 'var(--chip-bad-bg)',
                  color: 'var(--bad)',
                }}
              >
                ERROR
              </span>
              <p className="text-lg font-medium" style={{ color: 'var(--text)' }}>
                Could not reach the quote service right now. Please check that the backend is running.
              </p>
            </div>
          ) : quote ? (
            <>
              <div className="flex items-center gap-3 flex-wrap">
                <span
                  className="inline-flex items-center px-2.5 py-0.5 rounded text-xs font-semibold tracking-wide uppercase"
                  style={{
                    backgroundColor: isBuy ? 'var(--chip-good-bg)' : 'var(--chip-bad-bg)',
                    color: isBuy ? 'var(--good)' : 'var(--bad)',
                  }}
                >
                  {quote.verdict}
                </span>
                {quote.token && (
                  <span className="text-sm font-mono" style={{ color: 'var(--muted)' }}>
                    {quote.token.symbol} ·{' '}
                    {quote.token.issuer === 'ondo'
                      ? 'Ondo (indicative DEX quote)'
                      : 'bStocks'}
                  </span>
                )}
              </div>

              <h1
                className="font-semibold tracking-tight leading-snug m-0"
                style={{
                  fontSize: 'clamp(22px, 3vw, 28px)',
                  color: 'var(--text)',
                }}
              >
                {isBuy
                  ? formatBuyHeadline(quote)
                  : quote.refusal?.message || 'Trade refused by safety guard.'}
              </h1>

              {quote.alternative?.note && (
                <p className="text-base m-0" style={{ color: 'var(--muted)' }}>
                  {quote.alternative.note}
                </p>
              )}

              {quote.token?.issuer === 'ondo' && (
                <p className="text-xs font-mono m-0" style={{ color: 'var(--muted)' }}>
                  Indicative quote from /dex/aggregator/quote; live Agentic Wallet execution routes Ondo tokens via /ondo/place-order.
                </p>
              )}

              <p className="text-sm m-0" style={{ color: 'var(--muted)' }}>
                Quoted {formatSecondsAgo(quote.quoted_at)}
                {quoteFetching ? ' · updating…' : '.'}
              </p>

              {/* 3. ONE PRIMARY BUTTON + INLINE CONFIRM PANEL */}
              {isBuy && (
                <div className="pt-2 space-y-4">
                  {!confirmOpen ? (
                    <div className="space-y-2">
                      <button
                        type="button"
                        onClick={() => dryRunMutation.mutate()}
                        disabled={dryRunMutation.isPending}
                        className="px-5 py-2.5 rounded font-medium text-base text-white cursor-pointer disabled:opacity-60 transition-opacity"
                        style={{
                          backgroundColor: 'var(--accent)',
                          border: '1px solid var(--accent)',
                        }}
                      >
                        {dryRunMutation.isPending
                          ? 'Running dry-run…'
                          : liveModeOn
                            ? `Buy $${quote.amount_usd.toFixed(2)} safely`
                            : 'Preview trade (dry-run)'}
                      </button>
                      {!liveModeOn && (
                        <p className="text-sm m-0" style={{ color: 'var(--muted)' }}>
                          Live trading is off on this server.
                        </p>
                      )}
                    </div>
                  ) : (
                    receipt && (
                      <div
                        className="rounded-md p-4 sm:p-5 space-y-3"
                        style={{
                          backgroundColor: 'var(--bg)',
                          border: '1px solid var(--border)',
                        }}
                      >
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold uppercase"
                            style={{
                              backgroundColor: receipt.simulation.passed
                                ? 'var(--chip-good-bg)'
                                : 'var(--chip-bad-bg)',
                              color: receipt.simulation.passed ? 'var(--good)' : 'var(--bad)',
                            }}
                          >
                            {receipt.execution.status === 'LIVE_SUBMITTED'
                              ? 'Executed'
                              : receipt.simulation.passed
                                ? 'Simulation passed'
                                : 'Simulation failed'}
                          </span>
                          <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>
                            Decision #{receipt.decision_id}
                          </span>
                        </div>

                        <p className="text-base m-0 font-medium" style={{ color: 'var(--text)' }}>
                          {receipt.execution.status === 'LIVE_SUBMITTED'
                            ? receipt.execution.detail
                            : receipt.simulation.summary}
                        </p>

                        {receipt.execution.bsctrace_url && (
                          <p className="text-sm m-0">
                            <a
                              href={receipt.execution.bsctrace_url}
                              target="_blank"
                              rel="noreferrer"
                              style={{ color: 'var(--accent)' }}
                              className="font-mono underline"
                            >
                              View transaction on BscTrace →
                            </a>
                          </p>
                        )}

                        <div className="flex items-center gap-3 pt-1">
                          {liveModeOn &&
                            receipt.simulation.passed &&
                            receipt.execution.status !== 'LIVE_SUBMITTED' && (
                              <button
                                type="button"
                                onClick={() => confirmLiveMutation.mutate()}
                                disabled={confirmLiveMutation.isPending}
                                className="px-4 py-2 rounded font-medium text-sm text-white cursor-pointer disabled:opacity-60"
                                style={{
                                  backgroundColor: 'var(--good)',
                                  border: '1px solid var(--good)',
                                }}
                              >
                                {confirmLiveMutation.isPending
                                  ? 'Submitting swap…'
                                  : `Confirm $${quote.amount_usd.toFixed(2)} swap`}
                              </button>
                            )}
                          <button
                            type="button"
                            onClick={() => {
                              setConfirmOpen(false)
                              setReceipt(null)
                            }}
                            className="px-4 py-2 rounded font-medium text-sm cursor-pointer border"
                            style={{
                              backgroundColor: 'var(--surface)',
                              borderColor: 'var(--border)',
                              color: 'var(--text)',
                            }}
                          >
                            {liveModeOn && receipt.execution.status !== 'LIVE_SUBMITTED'
                              ? 'Cancel'
                              : 'Close'}
                          </button>
                        </div>
                      </div>
                    )
                  )}
                </div>
              )}
            </>
          ) : null}
        </section>

        {/* 4. COLLAPSED DETAILS DISCLOSURE (closed by default) */}
        {quote && (
          <details
            className="rounded-lg"
            style={{
              backgroundColor: 'var(--surface)',
              border: '1px solid var(--border)',
            }}
          >
            <summary
              className="px-5 py-3.5 text-sm font-medium cursor-pointer flex items-center justify-between select-none"
              style={{ color: 'var(--muted)' }}
            >
              <span>Details</span>
              <span className="font-mono text-xs">
                {issuerList.length} issuer{issuerList.length === 1 ? '' : 's'} · market{' '}
                {quote.market.status}
              </span>
            </summary>

            <div
              className="px-5 pb-5 pt-3 space-y-6 text-sm"
              style={{ borderTop: '1px solid var(--border)' }}
            >
              {/* Compact Issuer Comparison Table */}
              {issuerList.length > 0 && (
                <div className="space-y-2">
                  <h2 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                    Issuer comparison
                  </h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-sm">
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--muted)' }}>
                          <th className="py-2 pr-3 font-medium">Token</th>
                          <th className="py-2 px-3 font-medium">Shares</th>
                          <th className="py-2 px-3 font-medium">All-in / sh</th>
                          <th className="py-2 px-3 font-medium">Spread</th>
                          <th className="py-2 px-3 font-medium">Slippage</th>
                          <th className="py-2 px-3 font-medium">Depth</th>
                          <th className="py-2 pl-3 font-medium">Route / Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {issuerList.map(row => (
                          <tr
                            key={`${row.issuer}-${row.symbol}`}
                            style={{ borderBottom: '1px solid var(--border)' }}
                          >
                            <td className="py-2.5 pr-3">
                              <a
                                href={row.bsctrace_url}
                                target="_blank"
                                rel="noreferrer"
                                className="font-mono font-medium underline"
                                style={{ color: 'var(--text)' }}
                              >
                                {row.symbol}
                              </a>
                              <div className="text-xs" style={{ color: 'var(--muted)' }}>
                                {row.issuer_label} ·{' '}
                                <span className="font-mono">{shortAddress(row.address)}</span>
                              </div>
                            </td>
                            <td className="py-2.5 px-3 font-mono">
                              {row.shares !== null ? row.shares.toFixed(4) : 'N/A'}
                            </td>
                            <td className="py-2.5 px-3 font-mono">
                              {row.all_in_price_per_share !== null
                                ? `$${row.all_in_price_per_share.toFixed(2)}`
                                : 'N/A'}
                            </td>
                            <td className="py-2.5 px-3 font-mono">
                              {row.spread_pct !== null
                                ? `${row.spread_pct > 0 ? '+' : ''}${row.spread_pct.toFixed(2)}%`
                                : 'N/A'}
                            </td>
                            <td className="py-2.5 px-3 font-mono">
                              {row.slippage_pct !== null ? `${row.slippage_pct.toFixed(2)}%` : 'N/A'}
                            </td>
                            <td className="py-2.5 px-3 font-mono">
                              {formatCompactUsd(row.depth_usd)}
                            </td>
                            <td className="py-2.5 pl-3">
                              {row.eligible ? (
                                <span style={{ color: 'var(--good)' }}>
                                  {row.route || 'Eligible'}
                                </span>
                              ) : (
                                <span style={{ color: 'var(--bad)' }}>
                                  {row.refusal_code}: {row.refusal_message}
                                </span>
                              )}
                              {row.execution_note && (
                                <div className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
                                  {row.execution_note}
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Simulation & Agentic Wallet Details (when dry-run has been triggered) */}
              {receipt && (
                <div className="space-y-2">
                  <h2 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                    Simulation &amp; Agentic Wallet
                  </h2>
                  <div
                    className="rounded p-3 space-y-1.5 font-mono text-xs"
                    style={{
                      backgroundColor: 'var(--bg)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div>
                      status: {formatSimStatus(receipt.simulation.status)} · calldata:{' '}
                      {receipt.simulation.swap_tx_calldata_bytes} bytes · gas:{' '}
                      {receipt.simulation.swap_tx_gas_limit || 'N/A'}
                    </div>
                    {receipt.simulation.approval_spender && (
                      <div>
                        spender:{' '}
                        <a
                          href={`https://bsctrace.com/address/${receipt.simulation.approval_spender}`}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: 'var(--accent)' }}
                          className="underline"
                        >
                          {receipt.simulation.approval_spender}
                        </a>
                      </div>
                    )}
                    {receipt.execution.baw_command && (
                      <div className="break-all">cmd: {receipt.execution.baw_command}</div>
                    )}
                  </div>
                </div>
              )}

              {/* Last 5 Decisions */}
              {recentDecisions.length > 0 && (
                <div className="space-y-2">
                  <h2 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                    Last 5 decisions
                  </h2>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse text-sm">
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--muted)' }}>
                          <th className="py-1.5 pr-3 font-medium">ID</th>
                          <th className="py-1.5 px-3 font-medium">Trade</th>
                          <th className="py-1.5 px-3 font-medium">Verdict</th>
                          <th className="py-1.5 px-3 font-medium">Simulation</th>
                          <th className="py-1.5 pl-3 font-medium">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recentDecisions.slice(0, 5).map(d => (
                          <tr key={d.id} style={{ borderBottom: '1px solid var(--border)' }}>
                            <td className="py-2 pr-3 font-mono">#{d.id}</td>
                            <td className="py-2 px-3 font-mono">
                              ${d.amount_usd.toFixed(2)} {d.ticker}
                            </td>
                            <td className="py-2 px-3 font-mono">
                              {d.verdict}
                              {d.recommended_symbol ? ` (${d.recommended_symbol})` : ''}
                            </td>
                            <td className="py-2 px-3 font-mono">{formatSimStatus(d.simulation_status)}</td>
                            <td className="py-2 pl-3 font-mono">
                              {d.bsctrace_url ? (
                                <a
                                  href={d.bsctrace_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  style={{ color: 'var(--accent)' }}
                                  className="underline"
                                >
                                  {d.execution_status}
                                </a>
                              ) : (
                                d.execution_status
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </details>
        )}
      </main>
    </div>
  )
}
