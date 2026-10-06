import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'motion/react'
import {
  executeTrade,
  fetchDecisions,
  fetchHealth,
  fetchQuote,
  fetchTickers,
} from '../api'
import { usePrefersReducedMotion } from '../components/BineLogo'
import { HeroArt } from '../components/HeroArt'
import {
  Footer,
  TopHeader,
  formatCompactUsd,
  formatSecondsAgo,
  navigateApp,
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

  const reducedMotion = usePrefersReducedMotion()
  const queryClient = useQueryClient()

  // If URL has ?ticker=... or #guard on load, scroll to #guard
  useEffect(() => {
    if (typeof window === 'undefined') return
    if (window.location.hash === '#guard' || urlParams.has('ticker') || urlParams.has('amount')) {
      window.requestAnimationFrame(() => {
        const el = document.getElementById('guard')
        if (el) el.scrollIntoView({ behavior: 'auto', block: 'start' })
      })
    }
  }, [])

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
        backgroundColor: 'var(--bg-page)',
        color: 'var(--text)',
      }}
    >
      <TopHeader />

      <main className="flex-1">
        {/* HERO SECTION (STEP 4 & STEP 6) */}
        <section className="relative overflow-hidden md:min-h-[min(calc(100vh-80px),820px)] flex items-stretch">
          {/* Desktop / Tablet Right-Side Bleeding Art */}
          <div className="hidden md:flex absolute top-0 bottom-0 right-0 w-[62%] lg:w-[60%] items-center justify-end pointer-events-none z-0">
            <HeroArt />
          </div>

          <div className="bine-container relative z-10 flex flex-col justify-between py-10 sm:py-14 md:py-16 w-full">
            <div className="w-full max-w-[1240px] mx-auto flex-1 flex flex-col justify-between">
              {/* Top-left Headline + Pill Buttons */}
              <div className="pt-2 sm:pt-6 md:pt-10 max-w-[660px]">
                <h1 className="bine-hero-headline m-0">
                  <motion.span
                    className="block"
                    initial={reducedMotion ? false : { opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.72, delay: 0, ease: [0.22, 1, 0.36, 1] }}
                  >
                    Your Pre-Trade Guard
                  </motion.span>
                  <motion.span
                    className="block"
                    initial={reducedMotion ? false : { opacity: 0, y: 24 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.72, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
                  >
                    for Tokenized Stocks
                  </motion.span>
                </h1>

                <motion.div
                  className="mt-8 flex flex-wrap items-center gap-3.5 sm:gap-4"
                  initial={reducedMotion ? false : { opacity: 0, y: 24 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.72, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
                >
                  <a
                    href="#guard"
                    onClick={e => navigateApp('/#guard', e)}
                    className="bine-pill-primary"
                    style={{
                      height: '54px',
                      padding: '0 42px',
                    }}
                  >
                    Check a trade
                  </a>

                  <a
                    href="/refusals"
                    onClick={e => navigateApp('/refusals', e)}
                    className="bine-pill-secondary"
                    style={{
                      height: '54px',
                      padding: '0 42px',
                    }}
                  >
                    See live refusals
                  </a>
                </motion.div>
              </div>

              {/* Mobile Stacked Art at 60% Opacity (between buttons and bottom paragraph per STEP 9) */}
              <div className="md:hidden relative my-6 -mr-8 opacity-60 pointer-events-none">
                <HeroArt />
              </div>

              {/* Bottom-left Pinned Paragraph (max-width 580px) */}
              <motion.p
                className="bine-body-copy m-0 max-w-[580px] pt-6 md:pt-16"
                initial={reducedMotion ? false : { opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.75, delay: 0.28, ease: [0.22, 1, 0.36, 1] }}
              >
                Bine checks liquidity, slippage and market hours on BNB Chain before you buy a tokenized stock, and refuses the trades that would fill badly. Every decision is logged, and every refusal gives one reason.
              </motion.p>
            </div>
          </div>
        </section>

        {/* GUARD TOOL SECTION (id="guard") */}
        <section id="guard" className="scroll-mt-24 py-12 sm:py-16">
          <div className="bine-container">
            <div className="w-full max-w-[1240px] mx-auto space-y-5">
              {/* 1. INPUT CARD: Ticker + USD Amount */}
              <div className="bine-card p-6 sm:p-8">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
                  <div className="min-w-0">
                    <label
                      htmlFor="ticker-input"
                      className="block text-sm font-medium mb-2"
                      style={{ color: 'var(--text-secondary)' }}
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
                      className="w-full px-4 py-3 rounded-xl font-mono text-base transition-colors"
                      style={{
                        backgroundColor: 'var(--surface-subtle)',
                        border: '1px solid var(--border)',
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
                      className="block text-sm font-medium mb-2"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Amount (USD)
                    </label>
                    <div className="relative flex items-center">
                      <span
                        className="absolute left-4 font-mono text-base pointer-events-none"
                        style={{ color: 'var(--text-secondary)' }}
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
                        placeholder="5.50"
                        className="w-full pl-8 pr-4 py-3 rounded-xl font-mono text-base transition-colors"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--border)',
                          color: 'var(--text)',
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* 2. VERDICT CARD (Spring-in + zero-layout-shift skeleton loader) */}
              <motion.div
                key={quote ? `${quote.ticker}-${quote.amount_usd}-${quote.verdict}` : 'loading'}
                initial={reducedMotion ? false : { opacity: 0, y: 12, scale: 0.995 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={
                  reducedMotion
                    ? { duration: 0 }
                    : { type: 'spring', stiffness: 260, damping: 28 }
                }
                className="bine-card p-6 sm:p-9 min-h-[220px] flex flex-col justify-center space-y-5"
              >
                {quoteLoading && !quote ? (
                  <div className="space-y-4" aria-live="polite" aria-busy="true">
                    <div className="flex items-center gap-3">
                      <div className="bine-skeleton h-6 w-20" />
                      <div className="bine-skeleton h-5 w-36" />
                    </div>
                    <div className="bine-skeleton h-8 w-4/5" />
                    <div className="bine-skeleton h-5 w-3/5" />
                    <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                      Checking live tokenized stock quotes on BNB Chain...
                    </p>
                  </div>
                ) : quoteError ? (
                  <div className="space-y-3">
                    <span
                      className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold tracking-wide uppercase"
                      style={{
                        backgroundColor: 'var(--chip-bad-bg)',
                        color: 'var(--bad)',
                      }}
                    >
                      ERROR
                    </span>
                    <p className="text-lg font-medium m-0" style={{ color: 'var(--text)' }}>
                      Could not reach the quote service right now. Please check that the backend is running.
                    </p>
                  </div>
                ) : quote ? (
                  <>
                    <div className="flex items-center gap-3 flex-wrap">
                      <span
                        className="inline-flex items-center px-3.5 py-1 rounded-full text-xs font-semibold tracking-wide uppercase"
                        style={{
                          backgroundColor: isBuy ? 'var(--chip-good-bg)' : 'var(--chip-bad-bg)',
                          color: isBuy ? 'var(--good)' : 'var(--bad)',
                        }}
                      >
                        {quote.verdict}
                      </span>
                      {quote.token && (
                        <span className="text-sm font-mono" style={{ color: 'var(--text-secondary)' }}>
                          {quote.token.symbol} ·{' '}
                          {quote.token.issuer === 'ondo'
                            ? 'Ondo (indicative DEX quote)'
                            : 'bStocks'}
                        </span>
                      )}
                    </div>

                    <h2
                      className="font-semibold tracking-tight leading-snug m-0"
                      style={{
                        fontSize: 'clamp(22px, 2.8vw, 30px)',
                        color: 'var(--text)',
                      }}
                    >
                      {isBuy
                        ? formatBuyHeadline(quote)
                        : quote.refusal?.message || 'Trade refused by safety guard.'}
                    </h2>

                    {quote.alternative?.note && (
                      <p className="text-base m-0" style={{ color: 'var(--text-secondary)' }}>
                        {quote.alternative.note}
                      </p>
                    )}

                    {quote.token?.issuer === 'ondo' && (
                      <p className="text-xs font-mono m-0" style={{ color: 'var(--text-secondary)' }}>
                        Indicative quote from /dex/aggregator/quote; live Agentic Wallet execution routes Ondo tokens via /ondo/place-order.
                      </p>
                    )}

                    <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                      Quoted {formatSecondsAgo(quote.quoted_at)}
                      {quoteFetching ? ' · updating...' : '.'}
                    </p>

                    {/* 3. PRIMARY ACTION BUTTON + INLINE CONFIRM PANEL */}
                    {isBuy && (
                      <div className="pt-2 space-y-4">
                        {!confirmOpen ? (
                          <div className="space-y-2.5">
                            <button
                              type="button"
                              onClick={() => dryRunMutation.mutate()}
                              disabled={dryRunMutation.isPending}
                              className="bine-pill-primary disabled:opacity-60"
                              style={{
                                height: '48px',
                                padding: '0 32px',
                              }}
                            >
                              {dryRunMutation.isPending
                                ? 'Running dry-run...'
                                : liveModeOn
                                  ? `Buy $${quote.amount_usd.toFixed(2)} safely`
                                  : 'Preview trade (dry-run)'}
                            </button>
                            {!liveModeOn && (
                              <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                                Live trading is off on this server.
                              </p>
                            )}
                          </div>
                        ) : (
                          receipt && (
                            <div
                              className="rounded-2xl p-5 sm:p-6 space-y-3.5"
                              style={{
                                backgroundColor: 'var(--surface-subtle)',
                                border: '1px solid var(--border)',
                              }}
                            >
                              <div className="flex items-center justify-between gap-2 flex-wrap">
                                <span
                                  className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold uppercase"
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
                                <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
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
                                    rel="noopener noreferrer"
                                    style={{ color: 'var(--text)' }}
                                    className="font-mono underline"
                                  >
                                    View transaction on BscTrace -&gt;
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
                                      className="bine-pill-primary disabled:opacity-60"
                                      style={{
                                        height: '42px',
                                        padding: '0 24px',
                                      }}
                                    >
                                      {confirmLiveMutation.isPending
                                        ? 'Submitting swap...'
                                        : `Confirm $${quote.amount_usd.toFixed(2)} swap`}
                                    </button>
                                  )}
                                <button
                                  type="button"
                                  onClick={() => {
                                    setConfirmOpen(false)
                                    setReceipt(null)
                                  }}
                                  className="bine-pill-secondary"
                                  style={{
                                    height: '42px',
                                    padding: '0 22px',
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
              </motion.div>

              {/* 4. COLLAPSED DETAILS DISCLOSURE (closed by default) */}
              {quote && (
                <details className="bine-card overflow-hidden">
                  <summary
                    className="px-6 py-4 text-sm font-medium cursor-pointer flex items-center justify-between select-none"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    <span>Details</span>
                    <span className="font-mono text-xs">
                      {issuerList.length} issuer{issuerList.length === 1 ? '' : 's'} · market{' '}
                      {quote.market.status}
                    </span>
                  </summary>

                  <div
                    className="px-6 pb-6 pt-4 space-y-7 text-sm"
                    style={{ borderTop: '1px solid var(--hairline)' }}
                  >
                    {/* Compact Issuer Comparison Table */}
                    {issuerList.length > 0 && (
                      <div className="space-y-3">
                        <h3 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                          Issuer comparison
                        </h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left border-collapse text-sm">
                            <thead>
                              <tr
                                style={{
                                  borderBottom: '1px solid var(--hairline)',
                                  color: 'var(--text-secondary)',
                                }}
                              >
                                <th className="py-2.5 pr-3 font-medium">Token</th>
                                <th className="py-2.5 px-3 font-medium">Shares</th>
                                <th className="py-2.5 px-3 font-medium">All-in / sh</th>
                                <th className="py-2.5 px-3 font-medium">Spread</th>
                                <th className="py-2.5 px-3 font-medium">Slippage</th>
                                <th className="py-2.5 px-3 font-medium">Depth</th>
                                <th className="py-2.5 pl-3 font-medium">Route / Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {issuerList.map((row, idx) => (
                                <motion.tr
                                  key={`${row.issuer}-${row.symbol}`}
                                  initial={reducedMotion ? false : { opacity: 0, y: 4 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{
                                    duration: 0.25,
                                    delay: reducedMotion ? 0 : idx * 0.02,
                                    ease: [0.22, 1, 0.36, 1],
                                  }}
                                  style={{ borderBottom: '1px solid var(--hairline)' }}
                                >
                                  <td className="py-3 pr-3">
                                    <a
                                      href={row.bsctrace_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="font-mono font-medium underline"
                                      style={{ color: 'var(--text)' }}
                                    >
                                      {row.symbol}
                                    </a>
                                    <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                                      {row.issuer_label} ·{' '}
                                      <span className="font-mono">{shortAddress(row.address)}</span>
                                    </div>
                                  </td>
                                  <td className="py-3 px-3 font-mono">
                                    {row.shares !== null ? row.shares.toFixed(4) : 'N/A'}
                                  </td>
                                  <td className="py-3 px-3 font-mono">
                                    {row.all_in_price_per_share !== null
                                      ? `$${row.all_in_price_per_share.toFixed(2)}`
                                      : 'N/A'}
                                  </td>
                                  <td className="py-3 px-3 font-mono">
                                    {row.spread_pct !== null
                                      ? `${row.spread_pct > 0 ? '+' : ''}${row.spread_pct.toFixed(2)}%`
                                      : 'N/A'}
                                  </td>
                                  <td className="py-3 px-3 font-mono">
                                    {row.slippage_pct !== null ? `${row.slippage_pct.toFixed(2)}%` : 'N/A'}
                                  </td>
                                  <td className="py-3 px-3 font-mono">
                                    {formatCompactUsd(row.depth_usd)}
                                  </td>
                                  <td className="py-3 pl-3">
                                    {row.eligible ? (
                                      <span style={{ color: 'var(--good)' }}>
                                        {row.route || 'Eligible'}
                                      </span>
                                    ) : (
                                      <span style={{ color: 'var(--bad)' }}>
                                        <span className="font-mono">{row.refusal_code}</span>: {row.refusal_message}
                                      </span>
                                    )}
                                    {row.execution_note && (
                                      <div className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                                        {row.execution_note}
                                      </div>
                                    )}
                                  </td>
                                </motion.tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {/* Simulation & Agentic Wallet Details (when dry-run has been triggered) */}
                    {receipt && (
                      <div className="space-y-2.5">
                        <h3 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                          Simulation &amp; Agentic Wallet
                        </h3>
                        <div
                          className="rounded-xl p-4 space-y-1.5 font-mono text-xs"
                          style={{
                            backgroundColor: 'var(--surface-subtle)',
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
                                rel="noopener noreferrer"
                                style={{ color: 'var(--text)' }}
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
                      <div className="space-y-3">
                        <h3 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                          Last 5 decisions
                        </h3>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left border-collapse text-sm">
                            <thead>
                              <tr
                                style={{
                                  borderBottom: '1px solid var(--hairline)',
                                  color: 'var(--text-secondary)',
                                }}
                              >
                                <th className="py-2 pr-3 font-medium">ID</th>
                                <th className="py-2 px-3 font-medium">Trade</th>
                                <th className="py-2 px-3 font-medium">Verdict</th>
                                <th className="py-2 px-3 font-medium">Simulation</th>
                                <th className="py-2 pl-3 font-medium">Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {recentDecisions.slice(0, 5).map((d, idx) => (
                                <motion.tr
                                  key={d.id}
                                  initial={reducedMotion ? false : { opacity: 0, y: 4 }}
                                  animate={{ opacity: 1, y: 0 }}
                                  transition={{
                                    duration: 0.25,
                                    delay: reducedMotion ? 0 : idx * 0.02,
                                    ease: [0.22, 1, 0.36, 1],
                                  }}
                                  style={{ borderBottom: '1px solid var(--hairline)' }}
                                >
                                  <td className="py-2.5 pr-3 font-mono">#{d.id}</td>
                                  <td className="py-2.5 px-3 font-mono">
                                    ${d.amount_usd.toFixed(2)} {d.ticker}
                                  </td>
                                  <td className="py-2.5 px-3 font-mono">
                                    {d.verdict}
                                    {d.recommended_symbol ? ` (${d.recommended_symbol})` : ''}
                                  </td>
                                  <td className="py-2.5 px-3 font-mono">{formatSimStatus(d.simulation_status)}</td>
                                  <td className="py-2.5 pl-3 font-mono">
                                    {d.bsctrace_url ? (
                                      <a
                                        href={d.bsctrace_url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        style={{ color: 'var(--text)' }}
                                        className="underline"
                                      >
                                        {d.execution_status}
                                      </a>
                                    ) : (
                                      d.execution_status
                                    )}
                                  </td>
                                </motion.tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                </details>
              )}
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  )
}
