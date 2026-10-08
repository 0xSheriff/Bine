import { useEffect, useId, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { executeTrade, fetchHealth, fetchQuote, fetchTickers } from '../api'
import { usePrefersReducedMotion } from '../components/BineLogo'
import { GlassDetailPanel, runGlassViewTransition } from '../components/GlassStack'
import {
  Footer,
  LiveExecutionControl,
  LiveModeChip,
  SIM_ROUTER_TOOLTIP,
  TopHeader,
  formatCompactUsd,
  formatSimulationStatus,
  getSecondsElapsed,
  shortAddress,
} from '../components/shared'
import type {
  ExecuteTradeResponse,
  IssuerDetailRow,
  QuoteVerdictResponse,
  TickerItem,
} from '../types'
import {
  GUARD_RULE_DEFINITIONS,
  GUARD_RULES_COUNT,
  humanizeCode,
  humanizeStatus,
} from '../lib/humanize'

export { GUARD_RULE_DEFINITIONS }

const MAX_QUOTE_USD = 2500.0

const EXAMPLE_PRESETS = [
  { label: 'NVDA $5.50 buy', ticker: 'NVDA', amount: 5.5, badge: 'BUY' },
  { label: 'SPYon $250 refusal', ticker: 'SPYon', amount: 250, badge: 'REFUSE' },
  { label: 'AAPL $2 below minimum', ticker: 'AAPL', amount: 2, badge: 'MIN' },
] as const

const QUICK_AMOUNTS = [2, 5.5, 25, 250] as const

function formatBuySentence(q: QuoteVerdictResponse): string {
  const shares = q.shares !== null ? q.shares.toFixed(4) : '0.0000'
  const amt = q.amount_usd.toFixed(2)
  const allIn = q.all_in_price_per_share !== null ? q.all_in_price_per_share.toFixed(2) : 'N/A'
  const spread = q.spread_pct ?? 0
  const absSpread = Math.abs(spread).toFixed(2)
  const dir =
    Math.abs(spread) < 0.005
      ? 'at the stock reference price'
      : spread < 0
        ? `${absSpread}% below the stock reference price`
        : `${absSpread}% above the stock reference price`
  return `Buy ${shares} ${q.ticker} shares for $${amt} at $${allIn} per share (${dir}).`
}

interface DerivedRuleCheck {
  code: string
  name: string
  passed: boolean
  detail: string
}

function deriveGuardChecks(
  q: QuoteVerdictResponse,
  selectedRow: IssuerDetailRow | undefined,
): DerivedRuleCheck[] {
  const failedCode = q.verdict === 'REFUSE' ? q.refusal?.code || null : null
  const order = Object.keys(GUARD_RULE_DEFINITIONS)

  return order.map(code => {
    const def = GUARD_RULE_DEFINITIONS[code]
    const isFailed = failedCode === code
    let detail = def.threshold

    if (isFailed && q.refusal?.message) {
      detail = q.refusal.message
    } else if (q.verdict === 'BUY') {
      if (code === 'amount_over_cap') {
        detail = `$${q.amount_usd.toFixed(2)} is within the $2,500.00 quote cap`
      } else if (code === 'below_issuer_minimum') {
        const minStr = q.token?.issuer === 'ondo' ? '$5.00 Ondo minimum' : '$0.01 bStocks minimum'
        detail = `$${q.amount_usd.toFixed(2)} meets the ${minStr}`
      } else if (code === 'market_closed') {
        detail = `Session active (${humanizeStatus(q.market.status)})`
      } else if (code === 'reference_stale') {
        detail =
          q.reference_price_per_share !== null
            ? `Fresh reference ($${q.reference_price_per_share.toFixed(2)})`
            : 'Fresh reference price'
      } else if (code === 'quality_unreliable') {
        const ratio = selectedRow?.token_to_share_ratio
        detail =
          ratio !== null && ratio !== undefined
            ? `Share ratio ${ratio.toFixed(4)}x within 0.25-5.00x`
            : 'Within 0.25-5.00x ratio bounds'
      } else if (code === 'depth_thin') {
        const depthSourceLabel = selectedRow?.depth_source
          ? humanizeStatus(selectedRow.depth_source)
          : 'pool depth'
        detail = selectedRow?.depth_usd
          ? `${formatCompactUsd(selectedRow.depth_usd)} (${depthSourceLabel})`
          : 'Sufficient liquidity'
      } else if (code === 'slippage_too_high') {
        const spreadStr =
          q.spread_pct !== null
            ? `${q.spread_pct > 0 ? '+' : ''}${q.spread_pct.toFixed(2)}% vs reference (limit 1.00%)`
            : 'Within 1.00% limit'
        detail = spreadStr
      } else if (code === 'unknown_ticker') {
        detail = q.token ? `Verified ${q.token.symbol} on BNB Chain` : 'Verified in BSC catalog'
      }
    }

    return {
      code,
      name: def.name,
      passed: !isFailed,
      detail,
    }
  })
}

export default function Guard() {
  const initialParams = useMemo(() => {
    if (typeof window === 'undefined') {
      return { hasParams: false, ticker: 'NVDA', amount: 5.5 }
    }
    const sp = new URLSearchParams(window.location.search)
    const t = sp.get('ticker')?.trim().toUpperCase()
    const a = sp.get('amount')
    const parsedAmt = a !== null ? Number(a) : NaN
    if (t && Number.isFinite(parsedAmt) && parsedAmt > 0 && parsedAmt <= MAX_QUOTE_USD) {
      return { hasParams: true, ticker: t, amount: parsedAmt }
    }
    if (t) {
      return { hasParams: true, ticker: t, amount: 5.5 }
    }
    return { hasParams: false, ticker: 'NVDA', amount: 5.5 }
  }, [])

  const [tickerInput, setTickerInput] = useState<string>(initialParams.ticker)
  const [amountInput, setAmountInput] = useState<string>(
    initialParams.amount === 5.5 ? '5.50' : String(initialParams.amount),
  )
  const [submittedQuery, setSubmittedQuery] = useState<{
    ticker: string
    amount: number
  } | null>(() =>
    initialParams.hasParams
      ? { ticker: initialParams.ticker, amount: initialParams.amount }
      : null,
  )

  // WAI-ARIA 1.2 Combobox state
  const comboboxInputId = useId()
  const listboxId = useId()
  const [comboOpen, setComboOpen] = useState<boolean>(false)
  const [activeOptionIndex, setActiveOptionIndex] = useState<number>(-1)
  const comboContainerRef = useRef<HTMLDivElement | null>(null)

  // Live ticking quote age & copy toast state
  const [nowMs, setNowMs] = useState<number>(() => Date.now())
  const [copiedCurl, setCopiedCurl] = useState<boolean>(false)
  const [dryRunReceipt, setDryRunReceipt] = useState<ExecuteTradeResponse | null>(null)
  const [openMetricId, setOpenMetricId] = useState<string | null>(null)
  const [openCheckCode, setOpenCheckCode] = useState<string | null>(null)
  const metricTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const checkTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const reducedMotion = usePrefersReducedMotion()
  const queryClient = useQueryClient()

  // Tick every 1 second for live quote age ("Quoted 12s ago" -> "Quote expired, refresh" after 60s)
  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])

  // Close combobox on outside click
  useEffect(() => {
    if (!comboOpen) return
    const onPointerDown = (e: MouseEvent) => {
      if (comboContainerRef.current && !comboContainerRef.current.contains(e.target as Node)) {
        setComboOpen(false)
      }
    }
    window.addEventListener('mousedown', onPointerDown)
    return () => window.removeEventListener('mousedown', onPointerDown)
  }, [comboOpen])

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    staleTime: 30_000,
  })

  const { data: tickerCatalog } = useQuery({
    queryKey: ['tickers'],
    queryFn: fetchTickers,
    staleTime: 300_000,
  })

  const filteredTickers: TickerItem[] = useMemo(() => {
    const all = tickerCatalog?.tickers ?? []
    const q = tickerInput.trim().toUpperCase()
    if (!q) return all.slice(0, 10)
    // Match underlying ticker or issuer-suffixed symbol (e.g. SPYON, NVDAB)
    const stripped = q.replace(/(ON|B)$/i, '')
    return all
      .filter(
        item =>
          item.ticker.startsWith(q) ||
          item.ticker.includes(q) ||
          (stripped.length >= 2 && item.ticker.startsWith(stripped)),
      )
      .slice(0, 8)
  }, [tickerCatalog, tickerInput])

  // Inline validation mirroring backend limits (> $0 and <= $2,500)
  const validationError: string | null = useMemo(() => {
    const cleanTkr = tickerInput.trim()
    if (!cleanTkr) return 'Enter a stock ticker symbol (for example NVDA, AAPL, or SPYon).'
    const amt = Number(amountInput)
    if (amountInput.trim() === '' || !Number.isFinite(amt)) {
      return 'Enter a valid USD amount.'
    }
    if (amt <= 0) {
      return 'Amount must be greater than $0.00.'
    }
    if (amt > MAX_QUOTE_USD) {
      return `Amount exceeds Bine's $${MAX_QUOTE_USD.toLocaleString('en-US', { minimumFractionDigits: 2 })} single-quote safety cap.`
    }
    return null
  }, [tickerInput, amountInput])

  const {
    data: quote,
    isLoading: quoteLoading,
    isFetching: quoteFetching,
    error: quoteError,
    refetch: refetchQuote,
  } = useQuery({
    queryKey: ['quote', submittedQuery?.ticker, submittedQuery?.amount],
    queryFn: () => {
      if (!submittedQuery) throw new Error('No query')
      return fetchQuote(submittedQuery.ticker, submittedQuery.amount, true)
    },
    enabled: Boolean(submittedQuery),
    staleTime: 15_000,
    retry: false,
  })

  const dryRunMutation = useMutation({
    mutationFn: () => {
      if (!submittedQuery) throw new Error('No active trade')
      return executeTrade(submittedQuery.ticker, submittedQuery.amount, false)
    },
    onSuccess: data => {
      setDryRunReceipt(data)
      queryClient.invalidateQueries({ queryKey: ['decisions'] })
    },
  })

  const syncUrlParams = (ticker: string, amount: number) => {
    if (typeof window === 'undefined') return
    const nextUrl = `/guard?ticker=${encodeURIComponent(ticker)}&amount=${encodeURIComponent(String(amount))}`
    window.history.replaceState({}, '', nextUrl)
  }

  const submitTradeCheck = (tickerOverride?: string, amountOverride?: number) => {
    const cleanTkr = (tickerOverride ?? tickerInput).trim()
    const normalizedTkr = cleanTkr.endsWith('on')
      ? `${cleanTkr.slice(0, -2).toUpperCase()}on`
      : cleanTkr.toUpperCase()
    const amt = amountOverride ?? Number(amountInput)
    if (!normalizedTkr || !Number.isFinite(amt) || amt <= 0 || amt > MAX_QUOTE_USD) {
      return
    }
    setTickerInput(normalizedTkr)
    setAmountInput(String(amt))
    setComboOpen(false)
    setDryRunReceipt(null)
    setOpenMetricId(null)
    setOpenCheckCode(null)
    syncUrlParams(normalizedTkr, amt)
    if (
      submittedQuery &&
      submittedQuery.ticker === normalizedTkr &&
      submittedQuery.amount === amt
    ) {
      refetchQuote()
    } else {
      setSubmittedQuery({ ticker: normalizedTkr, amount: amt })
    }
  }

  const handleComboKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!comboOpen) {
        setComboOpen(true)
        setActiveOptionIndex(0)
      } else if (filteredTickers.length > 0) {
        setActiveOptionIndex(prev => (prev + 1) % filteredTickers.length)
      }
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (!comboOpen) {
        setComboOpen(true)
        setActiveOptionIndex(Math.max(0, filteredTickers.length - 1))
      } else if (filteredTickers.length > 0) {
        setActiveOptionIndex(prev => (prev - 1 + filteredTickers.length) % filteredTickers.length)
      }
    } else if (e.key === 'Home' && comboOpen && filteredTickers.length > 0) {
      e.preventDefault()
      setActiveOptionIndex(0)
    } else if (e.key === 'End' && comboOpen && filteredTickers.length > 0) {
      e.preventDefault()
      setActiveOptionIndex(filteredTickers.length - 1)
    } else if (e.key === 'Escape' && comboOpen) {
      e.preventDefault()
      setComboOpen(false)
      setActiveOptionIndex(-1)
    } else if (e.key === 'Enter' && comboOpen && activeOptionIndex >= 0 && filteredTickers[activeOptionIndex]) {
      e.preventDefault()
      const chosen = filteredTickers[activeOptionIndex]
      setTickerInput(chosen.ticker)
      setComboOpen(false)
      setActiveOptionIndex(-1)
    }
  }

  const handleCopyCurl = async () => {
    if (!submittedQuery) return
    const origin =
      typeof window !== 'undefined' && window.location.origin
        ? import.meta.env.DEV
          ? window.location.origin.replace(':5174', ':8000').replace(':5173', ':8000')
          : window.location.origin
        : 'http://localhost:8000'
    const cmd = `curl -s "${origin}/api/quote?ticker=${encodeURIComponent(submittedQuery.ticker)}&amount_usd=${submittedQuery.amount}" | jq .`
    try {
      await navigator.clipboard.writeText(cmd)
      setCopiedCurl(true)
      window.setTimeout(() => setCopiedCurl(false), 1500)
    } catch {
      setCopiedCurl(true)
      window.setTimeout(() => setCopiedCurl(false), 1500)
    }
  }

  // Determine error classification (503 vs network failure)
  const errorInfo = useMemo(() => {
    if (!quoteError) return null
    if (axios.isAxiosError(quoteError)) {
      const status = quoteError.response?.status
      const detail =
        (quoteError.response?.data as { detail?: string } | undefined)?.detail ||
        quoteError.message
      if (status === 503 || detail.includes('Binance API keys missing or rejected')) {
        return {
          kind: '503' as const,
          title: 'Binance API keys missing or rejected',
          detail,
        }
      }
    }
    return {
      kind: 'network' as const,
      title: import.meta.env.DEV
        ? 'Check that the backend is running on port 8000'
        : 'Could not reach the quote service',
      detail:
        quoteError instanceof Error
          ? quoteError.message
          : import.meta.env.DEV
            ? 'Could not reach the Bine backend on port 8000.'
            : 'Could not reach /api/quote.',
    }
  }, [quoteError])

  const issuerRows = quote?.details?.issuers ?? []
  const selectedRow = useMemo(() => {
    if (!quote?.token) return issuerRows[0]
    return (
      issuerRows.find(
        r => r.symbol === quote.token?.symbol && r.issuer === quote.token?.issuer,
      ) || issuerRows[0]
    )
  }, [quote, issuerRows])

  const quoteAgeSeconds = quote ? getSecondsElapsed(quote.quoted_at, nowMs) : 0
  const isQuoteStale = quoteAgeSeconds >= 60
  const guardChecks = useMemo(
    () => (quote ? deriveGuardChecks(quote, selectedRow) : []),
    [quote, selectedRow],
  )

  const isLoadingView = quoteLoading || (quoteFetching && !quote)
  const activeOptionId =
    comboOpen && activeOptionIndex >= 0 && filteredTickers[activeOptionIndex]
      ? `${listboxId}-opt-${activeOptionIndex}`
      : undefined

  // Suggested recovery action on REFUSE (e.g. "Try $5.50" when below_issuer_minimum)
  const suggestedTryAmount = useMemo(() => {
    if (quote?.verdict !== 'REFUSE') return null
    const msg = quote.refusal?.message || ''
    if (msg.includes('Try $5.50')) return 5.5
    if (quote.refusal?.code === 'below_issuer_minimum') return 5.5
    return null
  }, [quote])

  const liveModeOn = Boolean(health?.live_mode)

  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden"
      style={{
        backgroundColor: 'var(--bg-page)',
        color: 'var(--text)',
      }}
    >
      <TopHeader />

      <main className="flex-1 py-8 sm:py-12">
        <div className="bine-container">
          <div className="w-full max-w-[1240px] mx-auto space-y-6">
            {/* Page Heading + Live Mode Status Chip */}
            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
              <div className="space-y-1.5">
                <h1
                  tabIndex={-1}
                  className="m-0 font-semibold tracking-tight"
                  style={{
                    fontSize: 'clamp(28px, 3.2vw, 40px)',
                    letterSpacing: '-0.03em',
                    color: 'var(--text)',
                  }}
                >
                  Pre-Trade Guard
                </h1>
                <p className="text-sm sm:text-base m-0" style={{ color: 'var(--text-secondary)' }}>
                  Compare bStocks and Ondo on BNB Chain and run all {GUARD_RULES_COUNT} safety rules before you sign.
                </p>
              </div>
              <LiveModeChip />
            </div>

            {/* Split View: Left "Check a trade" panel, Right "Result" panel */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* LEFT PANEL: Check a trade */}
              <section
                aria-labelledby="guard-left-heading"
                className="lg:col-span-5 bine-card p-6 sm:p-7 space-y-6"
              >
                <div className="flex items-center justify-between gap-2">
                  <h2
                    id="guard-left-heading"
                    className="text-lg font-semibold m-0"
                    style={{ color: 'var(--text)' }}
                  >
                    Check a trade
                  </h2>
                  {tickerCatalog?.count && (
                    <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {tickerCatalog.count} tokens watched
                    </span>
                  )}
                </div>

                <form
                  onSubmit={e => {
                    e.preventDefault()
                    submitTradeCheck()
                  }}
                  noValidate
                  className="space-y-5"
                >
                  {/* WAI-ARIA APG Combobox for Stock Ticker */}
                  <div ref={comboContainerRef} className="relative">
                    <label
                      htmlFor={comboboxInputId}
                      className="block text-sm font-medium mb-2"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Stock or ETF ticker
                    </label>
                    <div className="relative">
                      <input
                        id={comboboxInputId}
                        type="text"
                        role="combobox"
                        aria-autocomplete="list"
                        aria-expanded={comboOpen}
                        aria-controls={listboxId}
                        aria-activedescendant={activeOptionId}
                        value={tickerInput}
                        onFocus={() => setComboOpen(true)}
                        onChange={e => {
                          setTickerInput(e.target.value)
                          setComboOpen(true)
                          setActiveOptionIndex(0)
                        }}
                        onKeyDown={handleComboKeyDown}
                        placeholder="NVDA, AAPL, SPYon..."
                        autoComplete="off"
                        className="w-full min-h-[48px] px-4 py-2.5 rounded-xl font-mono text-base transition-colors"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--border)',
                          color: 'var(--text)',
                        }}
                      />
                      <button
                        type="button"
                        tabIndex={-1}
                        aria-label="Toggle ticker suggestions"
                        onClick={() => setComboOpen(prev => !prev)}
                        className="absolute right-1 top-1/2 -translate-y-1/2 w-11 h-11 min-w-[44px] min-h-[44px] inline-flex items-center justify-center rounded-lg cursor-pointer bg-transparent border-0"
                        style={{ color: 'var(--text-secondary)' }}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M6 9l6 6 6-6" />
                        </svg>
                      </button>
                    </div>

                    {comboOpen && filteredTickers.length > 0 && (
                      <ul
                        id={listboxId}
                        role="listbox"
                        aria-label="Available tokenized stocks"
                        className="absolute left-0 right-0 z-30 mt-1.5 max-h-64 overflow-y-auto rounded-2xl p-1.5 m-0 list-none"
                        style={{
                          backgroundColor: 'var(--bg-card)',
                          border: '1px solid var(--hairline)',
                          boxShadow: 'var(--card-shadow)',
                        }}
                      >
                        {filteredTickers.map((item, idx) => {
                          const isActive = idx === activeOptionIndex
                          return (
                            <li
                              key={item.ticker}
                              id={`${listboxId}-opt-${idx}`}
                              role="option"
                              aria-selected={isActive}
                              onMouseDown={e => {
                                e.preventDefault()
                                setTickerInput(item.ticker)
                                setComboOpen(false)
                                setActiveOptionIndex(-1)
                              }}
                              onMouseEnter={() => setActiveOptionIndex(idx)}
                              className="flex items-center justify-between gap-2 px-3 py-2.5 min-h-[44px] rounded-xl cursor-pointer text-sm"
                              style={{
                                backgroundColor: isActive ? 'var(--surface-subtle)' : 'transparent',
                                color: 'var(--text)',
                              }}
                            >
                              <span className="font-mono font-semibold">{item.ticker}</span>
                              <span className="inline-flex items-center gap-1.5">
                                {item.issuers.map(iss => (
                                  <span
                                    key={iss}
                                    className="px-2 py-0.5 rounded-full text-[11px] font-medium"
                                    style={{
                                      backgroundColor: 'var(--surface-subtle)',
                                      color: 'var(--text-secondary)',
                                      border: '1px solid var(--hairline)',
                                    }}
                                  >
                                    {iss === 'bstock' ? 'bStocks' : 'Ondo'}
                                  </span>
                                ))}
                              </span>
                            </li>
                          )
                        })}
                      </ul>
                    )}
                  </div>

                  {/* Amount (USD) Input + Quick Amounts */}
                  <div className="space-y-2.5">
                    <label
                      htmlFor="guard-amount-input"
                      className="block text-sm font-medium"
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
                        id="guard-amount-input"
                        type="number"
                        step="any"
                        min="0.01"
                        max={MAX_QUOTE_USD}
                        value={amountInput}
                        onChange={e => setAmountInput(e.target.value)}
                        placeholder="5.50"
                        aria-invalid={Boolean(validationError)}
                        aria-describedby={validationError ? 'guard-validation-error' : undefined}
                        className="w-full min-h-[48px] pl-8 pr-4 py-2.5 rounded-xl font-mono text-base transition-colors"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: validationError
                            ? '1px solid var(--bad)'
                            : '1px solid var(--border)',
                          color: 'var(--text)',
                        }}
                      />
                    </div>

                    {/* Quick Amount Buttons */}
                    <div className="flex flex-wrap items-center gap-2 pt-0.5">
                      <span className="text-xs mr-1" style={{ color: 'var(--text-secondary)' }}>
                        Quick amount:
                      </span>
                      {QUICK_AMOUNTS.map(amt => {
                        const isSelected = Number(amountInput) === amt
                        return (
                          <button
                            key={amt}
                            type="button"
                            onClick={() => setAmountInput(amt === 5.5 ? '5.50' : String(amt))}
                            className="min-h-[44px] px-3.5 rounded-full text-xs font-mono font-medium cursor-pointer transition-colors"
                            style={{
                              backgroundColor: isSelected
                                ? 'var(--pill-primary-bg)'
                                : 'var(--surface-subtle)',
                              color: isSelected ? 'var(--pill-primary-text)' : 'var(--text)',
                              border: '1px solid var(--hairline)',
                            }}
                          >
                            ${amt === 5.5 ? '5.50' : amt}
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  {/* Inline Validation Message */}
                  {validationError && (
                    <p
                      id="guard-validation-error"
                      role="alert"
                      className="text-xs font-medium m-0 p-3 rounded-xl"
                      style={{
                        backgroundColor: 'var(--chip-bad-bg)',
                        color: 'var(--bad)',
                      }}
                    >
                      {validationError}
                    </p>
                  )}

                  {/* Primary Submit Button */}
                  <button
                    type="submit"
                    disabled={Boolean(validationError) || quoteFetching}
                    className="bine-pill-primary w-full min-h-[48px] disabled:opacity-50"
                  >
                    {quoteFetching ? 'Checking issuers...' : 'Check trade'}
                  </button>
                </form>

                {/* Try an example row (3 presets) */}
                <div
                  className="pt-4 space-y-2.5"
                  style={{ borderTop: '1px solid var(--hairline)' }}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className="text-xs font-semibold uppercase tracking-wider"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      Try an example
                    </span>
                    {submittedQuery && (
                      <button
                        type="button"
                        onClick={() => {
                          setSubmittedQuery(null)
                          setDryRunReceipt(null)
                        }}
                        className="text-xs underline bg-transparent border-0 cursor-pointer min-h-[44px] px-2"
                        style={{ color: 'var(--text-secondary)' }}
                      >
                        Clear result
                      </button>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {EXAMPLE_PRESETS.map(preset => {
                      const active =
                        submittedQuery?.ticker.toUpperCase() === preset.ticker.toUpperCase() &&
                        submittedQuery?.amount === preset.amount
                      return (
                        <button
                          key={preset.label}
                          type="button"
                          onClick={() => submitTradeCheck(preset.ticker, preset.amount)}
                          className="preset-chip inline-flex items-center gap-2 min-h-[44px] px-3.5 py-2 rounded-xl text-xs font-medium cursor-pointer transition-colors"
                          style={{
                            backgroundColor: active
                              ? 'var(--pill-primary-bg)'
                              : 'var(--surface-subtle)',
                            color: active ? 'var(--pill-primary-text)' : 'var(--text)',
                            border: '1px solid var(--hairline)',
                          }}
                        >
                          <span>{preset.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              </section>

              {/* RIGHT PANEL: Result */}
              <section
                aria-labelledby="guard-right-heading"
                aria-live="polite"
                aria-busy={isLoadingView}
                className="lg:col-span-7 bine-card p-6 sm:p-8 min-h-[420px] flex flex-col justify-between space-y-6"
              >
                <div className="flex items-center justify-between gap-3 flex-wrap">
                  <h2
                    id="guard-right-heading"
                    className="text-lg font-semibold m-0"
                    style={{ color: 'var(--text)' }}
                  >
                    Result
                  </h2>

                  {/* Live Ticking Quote Age / Stale Indicator */}
                  {quote && !isLoadingView && !errorInfo && (
                    <div className="inline-flex items-center gap-2 text-xs font-mono">
                      {isQuoteStale ? (
                        <button
                          type="button"
                          onClick={() => refetchQuote()}
                          className="inline-flex items-center gap-1.5 min-h-[44px] px-3 rounded-full font-semibold cursor-pointer"
                          style={{
                            backgroundColor: 'var(--chip-warn-bg)',
                            color: 'var(--warn)',
                            border: 'none',
                          }}
                        >
                          <span>Quote expired, refresh</span>
                        </button>
                      ) : (
                        <span style={{ color: 'var(--text-secondary)' }}>
                          Quoted {quoteAgeSeconds}s ago
                          {quoteFetching ? ' · refreshing...' : ''}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* STATE 1: IDLE (Empty State with the 3 examples) */}
                {!submittedQuery && !isLoadingView && (
                  <div className="my-auto py-8 space-y-4">
                    <div className="space-y-1.5">
                      <h3 className="text-xl font-semibold m-0" style={{ color: 'var(--text)' }}>
                        Select a ticker or try a preset
                      </h3>
                      <p className="text-sm m-0 max-w-[480px]" style={{ color: 'var(--text-secondary)' }}>
                        Bine checks live BNB Chain liquidity, issuer minimum order sizes, market sessions, and price impact against the stock reference price.
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2.5 pt-2">
                      {EXAMPLE_PRESETS.map(preset => (
                        <button
                          key={preset.label}
                          type="button"
                          onClick={() => submitTradeCheck(preset.ticker, preset.amount)}
                          className="bine-pill-secondary min-h-[44px] px-4 text-xs"
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* STATE 2: LOADING (< 400ms feedback with skeleton & "Checking issuers") */}
                {isLoadingView && (
                  <div className="my-auto py-6 space-y-5" role="status">
                    <div className="inline-flex items-center gap-2.5 text-sm font-semibold">
                      <span
                        className="w-2.5 h-2.5 rounded-full animate-ping"
                        style={{ backgroundColor: 'var(--text)' }}
                      />
                      <span>Checking issuers</span>
                    </div>
                    <div className="space-y-3">
                      <div className="bine-skeleton h-7 w-28" />
                      <div className="bine-skeleton h-9 w-4/5" />
                      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 pt-2">
                        <div className="bine-skeleton h-16 rounded-2xl" />
                        <div className="bine-skeleton h-16 rounded-2xl" />
                        <div className="bine-skeleton h-16 rounded-2xl" />
                      </div>
                    </div>
                  </div>
                )}

                {/* STATE 3: ERROR (503 keys missing OR network failure) */}
                {!isLoadingView && errorInfo && (
                  <div className="my-auto space-y-4 alert-error" role="alert">
                    <div
                      className="p-5 rounded-2xl space-y-3"
                      style={{
                        backgroundColor: 'var(--chip-bad-bg)',
                        color: 'var(--bad)',
                      }}
                    >
                      <div className="text-xs font-mono uppercase font-semibold">
                        {errorInfo.kind === '503' ? 'HTTP 503 · Setup required' : 'Connection error'}
                      </div>
                      <h3 className="text-lg font-semibold m-0" style={{ color: 'var(--text)' }}>
                        {errorInfo.title}
                      </h3>
                      <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                        {errorInfo.kind === '503'
                          ? 'The backend could not authenticate with the Binance Web3 RWA API. Configure your keys in .env and restart the backend.'
                          : import.meta.env.DEV
                            ? 'Make sure the FastAPI server is running on http://localhost:8000 and reachable from your browser.'
                            : 'Could not reach /api/quote. Check your connection and retry in a moment.'}
                      </p>
                    </div>

                    {errorInfo.kind === '503' && (
                      <div
                        className="p-4 rounded-2xl space-y-2"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--hairline)',
                        }}
                      >
                        <div className="text-xs font-semibold" style={{ color: 'var(--text)' }}>
                          Start the backend with your .env credentials:
                        </div>
                        <pre
                          data-raw-code
                          className="m-0 text-xs font-mono overflow-x-auto leading-relaxed"
                          style={{ color: 'var(--text)' }}
                        >
{`cp .env.example .env
set -a; source .env; set +a
DEV_DNS_FALLBACK=true backend/.venv/bin/uvicorn bine.app:app --app-dir backend --host 0.0.0.0 --port 8000`}
                        </pre>
                      </div>
                    )}

                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => refetchQuote()}
                        className="bine-pill-primary min-h-[44px] px-5"
                      >
                        Retry check
                      </button>
                    </div>
                  </div>
                )}

                {/* STATE 4: BUY */}
                {!isLoadingView && !errorInfo && quote && quote.verdict === 'BUY' && (
                  <motion.div
                    key={`buy-${quote.ticker}-${quote.amount_usd}`}
                    initial={reducedMotion ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.22 }}
                    className="space-y-6"
                  >
                    {/* Badge + One plain sentence */}
                    <div className="space-y-3">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span
                          className="inline-flex items-center px-3.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wide"
                          style={{
                            backgroundColor: 'var(--chip-good-bg)',
                            color: 'var(--good)',
                          }}
                        >
                          BUY
                        </span>
                        {quote.token && (
                          <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                            Best route:{' '}
                            <strong style={{ color: 'var(--text)' }}>
                              {quote.token.issuer === 'bstock' ? 'bStocks' : 'Ondo'} · {quote.token.symbol}
                            </strong>
                          </span>
                        )}
                      </div>

                      <p
                        className="font-semibold leading-snug m-0"
                        style={{
                          fontSize: 'clamp(20px, 2.3vw, 26px)',
                          color: 'var(--text)',
                        }}
                      >
                        {formatBuySentence(quote)}
                      </p>

                      {quote.alternative?.note && (
                        <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                          {quote.alternative.note}
                        </p>
                      )}
                    </div>

                    {/* 5-Metric Grid mapped to existing API fields (clickable GlassStack triggers) */}
                    {(() => {
                      const metricItems = [
                        {
                          id: 'shares',
                          label: 'You receive',
                          value: quote.shares !== null ? `${quote.shares.toFixed(4)} sh` : 'N/A',
                          title: 'Share-adjusted output calculation',
                          subtitle: `${quote.token?.symbol ?? quote.ticker} · Share ratio ${(selectedRow?.token_to_share_ratio ?? 1).toFixed(4)}x`,
                          detail: `Raw tokens received (${selectedRow?.tokens_received?.toFixed(6) ?? quote.shares?.toFixed(6) ?? '0'}) divided by the catalog share ratio (${(selectedRow?.token_to_share_ratio ?? 1).toFixed(4)}x) = ${quote.shares?.toFixed(6) ?? '0'} underlying ${quote.ticker} shares.`,
                        },
                        {
                          id: 'price',
                          label: 'Price per share',
                          value:
                            quote.all_in_price_per_share !== null
                              ? `$${quote.all_in_price_per_share.toFixed(2)}`
                              : 'N/A',
                          title: 'All-in execution price per share',
                          subtitle: `Order size $${quote.amount_usd.toFixed(2)} USD / ${quote.shares?.toFixed(6) ?? 'N/A'} shares`,
                          detail: `Computed as $${quote.amount_usd.toFixed(2)} USD divided by ${quote.shares?.toFixed(6) ?? '0'} share-adjusted units ($${quote.all_in_price_per_share?.toFixed(2) ?? 'N/A'}/sh), compared against the $${quote.reference_price_per_share?.toFixed(2) ?? 'N/A'}/sh stock reference price.`,
                        },
                        {
                          id: 'spread',
                          label: 'Versus market price',
                          value:
                            quote.spread_pct !== null
                              ? `${quote.spread_pct > 0 ? '+' : ''}${quote.spread_pct.toFixed(2)}%`
                              : 'N/A',
                          title: 'Spread versus stock reference price',
                          subtitle: 'Guard threshold: <= +1.00% (100 bps)',
                          detail: `All-in share price ($${quote.all_in_price_per_share?.toFixed(2) ?? 'N/A'}) vs underlying stock reference ($${quote.reference_price_per_share?.toFixed(2) ?? 'N/A'}). Bine refuses any quote where the spread exceeds +1.00%.`,
                        },
                        {
                          id: 'impact',
                          label: 'Price impact',
                          value:
                            selectedRow?.slippage_pct !== null && selectedRow?.slippage_pct !== undefined
                              ? `${selectedRow.slippage_pct.toFixed(2)}%`
                              : '0.00%',
                          title: 'DEX aggregator price impact',
                          subtitle: `Route: ${selectedRow?.route || 'BNB Chain DEX aggregator'}`,
                          detail: `Estimated pool price impact reported by the BNB Chain aggregator for a $${quote.amount_usd.toFixed(2)} USDT swap into ${quote.token?.symbol ?? quote.ticker}.`,
                        },
                        {
                          id: 'depth',
                          label: 'Pool depth',
                          value: formatCompactUsd(selectedRow?.depth_usd),
                          title: 'On-chain liquidity depth',
                          subtitle: 'Guard threshold: >= $10K AMM depth or >= $1M 24h volume',
                          detail: `Measured liquidity for ${quote.token?.symbol ?? quote.ticker} on BNB Smart Chain: ${formatCompactUsd(selectedRow?.depth_usd)} (${humanizeStatus(selectedRow?.depth_source || 'amm_pools')}).`,
                        },
                      ]
                      const activeMetric = metricItems.find(m => m.id === openMetricId) ?? null
                      const activeMetricTriggerRef = {
                        get current() {
                          return openMetricId ? metricTriggerRefs.current[openMetricId] ?? null : null
                        },
                      }

                      return (
                        <div className="space-y-2">
                          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
                            {metricItems.map((m, idx) => {
                              const isOpen = openMetricId === m.id
                              return (
                                <button
                                  key={m.id}
                                  ref={el => {
                                    metricTriggerRefs.current[m.id] = el
                                  }}
                                  type="button"
                                  aria-expanded={isOpen}
                                  aria-controls={`guard-metric-glass-${m.id}`}
                                  onClick={() =>
                                    runGlassViewTransition(() => {
                                      setOpenMetricId(prev => (prev === m.id ? null : m.id))
                                    }, reducedMotion)
                                  }
                                  className={`p-3.5 rounded-2xl space-y-1 text-left cursor-pointer min-h-[44px] bine-glass-trigger ${
                                    idx === 4 ? 'col-span-2 sm:col-span-1' : ''
                                  } ${isOpen ? 'bine-glass-trigger-active' : ''}`}
                                  style={{ backgroundColor: 'var(--surface-subtle)' }}
                                >
                                  <div className="text-xs flex items-center justify-between gap-1" style={{ color: 'var(--text-secondary)' }}>
                                    <span>{m.label}</span>
                                    <span aria-hidden="true" className="font-mono text-[11px]">
                                      {isOpen ? '−' : '+'}
                                    </span>
                                  </div>
                                  <div className="font-mono font-semibold text-sm" style={{ color: 'var(--text)' }}>
                                    {m.value}
                                  </div>
                                </button>
                              )
                            })}
                          </div>

                          {activeMetric && (
                            <GlassDetailPanel
                              id={`guard-metric-glass-${activeMetric.id}`}
                              isOpen={true}
                              onClose={() =>
                                runGlassViewTransition(() => {
                                  setOpenMetricId(null)
                                }, reducedMotion)
                              }
                              title={activeMetric.title}
                              subtitle={activeMetric.subtitle}
                              triggerRef={activeMetricTriggerRef}
                            >
                              <p className="m-0">{activeMetric.detail}</p>
                            </GlassDetailPanel>
                          )}
                        </div>
                      )
                    })()}

                    {/* Primary Actions: Preview trade (dry-run) + Copy as curl */}
                    <div className="flex flex-wrap items-center gap-3">
                      <button
                        type="button"
                        onClick={() => dryRunMutation.mutate()}
                        disabled={dryRunMutation.isPending}
                        className="bine-pill-primary min-h-[48px] px-6 disabled:opacity-60"
                      >
                        {dryRunMutation.isPending
                          ? 'Simulating with Transaction API...'
                          : liveModeOn
                            ? 'Preview & prepare swap'
                            : 'Preview trade (dry-run)'}
                      </button>

                      <button
                        type="button"
                        onClick={handleCopyCurl}
                        className="bine-pill-secondary min-h-[48px] px-5"
                      >
                        {copiedCurl ? 'Copied' : 'Copy as curl'}
                      </button>

                      <span className="sr-only" aria-live="polite">
                        {copiedCurl ? 'Copied curl command to clipboard' : ''}
                      </span>
                    </div>

                    {/* Dry-Run Simulation Card */}
                    {dryRunReceipt && (
                      <div
                        className="p-5 rounded-2xl space-y-3"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--hairline)',
                        }}
                      >
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <span
                            className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold"
                            style={{
                              backgroundColor: dryRunReceipt.simulation.passed
                                ? 'var(--chip-good-bg)'
                                : 'var(--chip-bad-bg)',
                              color: dryRunReceipt.simulation.passed ? 'var(--good)' : 'var(--bad)',
                            }}
                          >
                            {dryRunReceipt.simulation.passed
                              ? 'Dry-run passed. Simulated with the Transaction API'
                              : 'Dry-run failed'}
                          </span>
                          <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                            Decision #{dryRunReceipt.decision_id}
                          </span>
                        </div>

                        <p className="text-sm m-0" style={{ color: 'var(--text)' }}>
                          {dryRunReceipt.simulation.summary}
                        </p>

                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs pt-1">
                          <div>
                            <div style={{ color: 'var(--text-secondary)' }}>Simulation status</div>
                            <div className="font-mono font-semibold mt-0.5" style={{ color: 'var(--text)' }}>
                              {(() => {
                                const sim = formatSimulationStatus(dryRunReceipt.simulation.status)
                                return sim.tooltip ? (
                                  <span
                                    title={sim.tooltip}
                                    className="underline decoration-dotted cursor-help"
                                  >
                                    {sim.label}
                                  </span>
                                ) : (
                                  <span>{sim.label}</span>
                                )
                              })()}
                            </div>
                          </div>
                          <div>
                            <div style={{ color: 'var(--text-secondary)' }}>Estimated gas limit</div>
                            <div className="font-mono font-semibold mt-0.5" style={{ color: 'var(--text)' }}>
                              {dryRunReceipt.simulation.swap_tx_gas_limit || 'Standard BSC swap'}
                            </div>
                          </div>
                          <div>
                            <div style={{ color: 'var(--text-secondary)' }}>Calldata size</div>
                            <div className="font-mono font-semibold mt-0.5" style={{ color: 'var(--text)' }}>
                              {dryRunReceipt.simulation.swap_tx_calldata_bytes} bytes
                            </div>
                          </div>
                        </div>

                        <p className="text-xs m-0" style={{ color: 'var(--text-secondary)' }}>
                          {SIM_ROUTER_TOOLTIP}
                        </p>

                        <LiveExecutionControl quote={quote} dryRunResult={dryRunReceipt} />
                      </div>
                    )}

                    {/* Guard Checks List (Pass/Fail per rule, clickable to open GlassDetailPanel) */}
                    <div className="space-y-2.5 pt-1">
                      <div className="flex items-baseline justify-between gap-2 flex-wrap">
                        <h3 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                          Guard checks ({guardChecks.filter(c => c.passed).length}/{guardChecks.length} passed)
                        </h3>
                        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                          Click any check to inspect rule threshold
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {guardChecks.map(chk => {
                          const isOpen = openCheckCode === chk.code
                          return (
                            <button
                              key={chk.code}
                              ref={el => {
                                checkTriggerRefs.current[chk.code] = el
                              }}
                              type="button"
                              aria-expanded={isOpen}
                              aria-controls={`guard-check-glass-${chk.code}`}
                              onClick={() =>
                                runGlassViewTransition(() => {
                                  setOpenCheckCode(prev => (prev === chk.code ? null : chk.code))
                                }, reducedMotion)
                              }
                              className={`flex items-start gap-2.5 p-3 rounded-xl text-xs text-left cursor-pointer min-h-[44px] bine-glass-trigger ${
                                isOpen ? 'bine-glass-trigger-active' : ''
                              }`}
                              style={{ backgroundColor: 'var(--surface-subtle)' }}
                            >
                              <span
                                className="inline-flex items-center justify-center w-5 h-5 rounded-full shrink-0 font-bold mt-0.5"
                                style={{
                                  backgroundColor: chk.passed
                                    ? 'var(--chip-good-bg)'
                                    : 'var(--chip-bad-bg)',
                                  color: chk.passed ? 'var(--good)' : 'var(--bad)',
                                }}
                                aria-hidden="true"
                              >
                                {chk.passed ? '✓' : '✕'}
                              </span>
                              <div className="min-w-0 flex-1">
                                <div className="font-semibold" style={{ color: 'var(--text)' }}>
                                  {chk.name}
                                </div>
                                <div
                                  className="truncate"
                                  title={chk.detail}
                                  style={{ color: 'var(--text-secondary)' }}
                                >
                                  {chk.detail}
                                </div>
                              </div>
                            </button>
                          )
                        })}
                      </div>

                      {openCheckCode && GUARD_RULE_DEFINITIONS[openCheckCode] && (
                        <GlassDetailPanel
                          id={`guard-check-glass-${openCheckCode}`}
                          isOpen={true}
                          onClose={() =>
                            runGlassViewTransition(() => {
                              setOpenCheckCode(null)
                            }, reducedMotion)
                          }
                          title={GUARD_RULE_DEFINITIONS[openCheckCode].name}
                          subtitle={`Rule threshold: ${GUARD_RULE_DEFINITIONS[openCheckCode].threshold}`}
                          triggerRef={{
                            get current() {
                              return openCheckCode ? checkTriggerRefs.current[openCheckCode] ?? null : null
                            },
                          }}
                        >
                          <p className="m-0">{GUARD_RULE_DEFINITIONS[openCheckCode].explanation}</p>
                          <p className="m-0 text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                            Current quote evaluation:{' '}
                            {guardChecks.find(c => c.code === openCheckCode)?.detail}
                          </p>
                        </GlassDetailPanel>
                      )}
                    </div>

                    {/* Technical Route Details Disclosure */}
                    {selectedRow && (
                      <details
                        className="rounded-2xl overflow-hidden"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--hairline)',
                        }}
                      >
                        <summary
                          className="px-4 py-3 min-h-[44px] text-xs font-semibold cursor-pointer flex items-center justify-between select-none"
                          style={{ color: 'var(--text)' }}
                        >
                          <span>Route details</span>
                          <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                            {selectedRow.symbol} · {shortAddress(selectedRow.address)}
                          </span>
                        </summary>
                        <div
                          className="px-4 pb-4 pt-3 text-xs space-y-2 font-mono"
                          style={{
                            borderTop: '1px solid var(--hairline)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          <div>
                            Contract:{' '}
                            <a
                              href={selectedRow.bsctrace_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="underline"
                              style={{ color: 'var(--text)' }}
                            >
                              {selectedRow.address}
                            </a>
                          </div>
                          <div>Route: {selectedRow.route || 'DEX aggregator'}</div>
                          {selectedRow.token_to_share_ratio !== null && (
                            <div>
                              Share ratio: {selectedRow.token_to_share_ratio.toFixed(6)}x · Tokens:{' '}
                              {selectedRow.tokens_received?.toFixed(6) ?? 'N/A'}
                            </div>
                          )}
                          {selectedRow.execution_note && <div>Note: {selectedRow.execution_note}</div>}
                        </div>
                      </details>
                    )}

                    {/* Compare Issuers Table Disclosure */}
                    {issuerRows.length > 0 && (
                      <details
                        className="rounded-2xl overflow-hidden"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--hairline)',
                        }}
                      >
                        <summary
                          className="px-4 py-3 min-h-[44px] text-xs font-semibold cursor-pointer flex items-center justify-between select-none"
                          style={{ color: 'var(--text)' }}
                        >
                          <span>Compare issuers ({issuerRows.length})</span>
                          <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                            {issuerRows.map(r => r.symbol).join(' vs ')}
                          </span>
                        </summary>
                        <div
                          className="px-4 pb-4 pt-3 overflow-x-auto"
                          style={{ borderTop: '1px solid var(--hairline)' }}
                        >
                          <table className="w-full text-left border-collapse text-xs">
                            <thead>
                              <tr
                                style={{
                                  borderBottom: '1px solid var(--hairline)',
                                  color: 'var(--text-secondary)',
                                }}
                              >
                                <th className="py-2 pr-2 font-medium">Token</th>
                                <th className="py-2 px-2 font-medium">Shares</th>
                                <th className="py-2 px-2 font-medium">Price / sh</th>
                                <th className="py-2 px-2 font-medium">Vs market</th>
                                <th className="py-2 px-2 font-medium">Depth</th>
                                <th className="py-2 pl-2 font-medium">Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {issuerRows.map(row => (
                                <tr
                                  key={`${row.issuer}-${row.symbol}`}
                                  style={{ borderBottom: '1px solid var(--hairline)' }}
                                >
                                  <td className="py-2.5 pr-2 font-mono font-semibold">
                                    <a
                                      href={row.bsctrace_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="underline"
                                      style={{ color: 'var(--text)' }}
                                    >
                                      {row.symbol}
                                    </a>
                                    <div
                                      className="font-sans font-normal"
                                      style={{ color: 'var(--text-secondary)' }}
                                    >
                                      {row.issuer_label}
                                    </div>
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {row.shares !== null ? row.shares.toFixed(4) : 'N/A'}
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {row.all_in_price_per_share !== null
                                      ? `$${row.all_in_price_per_share.toFixed(2)}`
                                      : 'N/A'}
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {row.spread_pct !== null
                                      ? `${row.spread_pct > 0 ? '+' : ''}${row.spread_pct.toFixed(2)}%`
                                      : 'N/A'}
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {formatCompactUsd(row.depth_usd)}
                                  </td>
                                  <td className="py-2.5 pl-2">
                                    {row.eligible ? (
                                      <span style={{ color: 'var(--good)' }}>Eligible</span>
                                    ) : (
                                      <span style={{ color: 'var(--bad)' }}>
                                        {humanizeCode(row.refusal_code)}: {row.refusal_message}
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </details>
                    )}
                  </motion.div>
                )}

                {/* STATE 5: REFUSE */}
                {!isLoadingView && !errorInfo && quote && quote.verdict === 'REFUSE' && (
                  <motion.div
                    key={`refuse-${quote.ticker}-${quote.amount_usd}`}
                    initial={reducedMotion ? false : { opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.22 }}
                    className="space-y-6"
                  >
                    {/* Calm Tinted Refusal Header */}
                    <div
                      className="p-5 sm:p-6 rounded-2xl space-y-3"
                      style={{
                        backgroundColor: 'var(--chip-bad-bg)',
                      }}
                    >
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span
                          className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wide"
                          style={{
                            backgroundColor: 'var(--bg-card)',
                            color: 'var(--bad)',
                          }}
                        >
                          REFUSE
                        </span>
                        {quote.refusal?.code && (
                          <span
                            className="inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-semibold"
                            style={{
                              backgroundColor: 'var(--bg-card)',
                              color: 'var(--text)',
                            }}
                          >
                            {humanizeCode(quote.refusal.code)}
                          </span>
                        )}
                      </div>

                      <h3
                        className="text-lg font-semibold m-0"
                        style={{ color: 'var(--text)' }}
                      >
                        Bine would not buy this
                      </h3>

                      <p
                        className="font-medium leading-relaxed m-0"
                        style={{
                          fontSize: 'clamp(17px, 2vw, 21px)',
                          color: 'var(--text)',
                        }}
                      >
                        {quote.refusal?.message}
                      </p>

                      {quote.refusal?.code && GUARD_RULE_DEFINITIONS[quote.refusal.code] && (
                        <p className="text-xs m-0 pt-1" style={{ color: 'var(--text-secondary)' }}>
                          <strong>{GUARD_RULE_DEFINITIONS[quote.refusal.code].name}:</strong>{' '}
                          {GUARD_RULE_DEFINITIONS[quote.refusal.code].explanation}
                        </p>
                      )}
                    </div>

                    {/* What to try instead */}
                    <div className="flex flex-wrap items-center gap-3">
                      {suggestedTryAmount !== null && (
                        <button
                          type="button"
                          onClick={() => submitTradeCheck(quote.ticker, suggestedTryAmount)}
                          className="bine-pill-primary min-h-[48px] px-5"
                        >
                          Try {quote.ticker} at ${suggestedTryAmount.toFixed(2)} instead
                        </button>
                      )}

                      <button
                        type="button"
                        onClick={() => submitTradeCheck('NVDA', 5.5)}
                        className="bine-pill-secondary min-h-[48px] px-5"
                      >
                        Try NVDA at $5.50
                      </button>

                      <button
                        type="button"
                        onClick={handleCopyCurl}
                        className="bine-pill-secondary min-h-[48px] px-5"
                      >
                        {copiedCurl ? 'Copied' : 'Copy as curl'}
                      </button>

                      <span className="sr-only" aria-live="polite">
                        {copiedCurl ? 'Copied curl command to clipboard' : ''}
                      </span>
                    </div>

                    {/* Guard Checks List on Refusal (clickable to open GlassDetailPanel) */}
                    <div className="space-y-2.5">
                      <div className="flex items-baseline justify-between gap-2 flex-wrap">
                        <h3 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
                          Guard checks ({guardChecks.filter(c => c.passed).length}/{guardChecks.length} passed)
                        </h3>
                        <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                          Click any check to inspect rule threshold
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {guardChecks.map(chk => {
                          const isOpen = openCheckCode === chk.code
                          return (
                            <button
                              key={chk.code}
                              ref={el => {
                                checkTriggerRefs.current[chk.code] = el
                              }}
                              type="button"
                              aria-expanded={isOpen}
                              aria-controls={`guard-refuse-check-glass-${chk.code}`}
                              onClick={() =>
                                runGlassViewTransition(() => {
                                  setOpenCheckCode(prev => (prev === chk.code ? null : chk.code))
                                }, reducedMotion)
                              }
                              className={`flex items-start gap-2.5 p-3 rounded-xl text-xs text-left cursor-pointer min-h-[44px] bine-glass-trigger ${
                                isOpen ? 'bine-glass-trigger-active' : ''
                              }`}
                              style={{ backgroundColor: 'var(--surface-subtle)' }}
                            >
                              <span
                                className="inline-flex items-center justify-center w-5 h-5 rounded-full shrink-0 font-bold mt-0.5"
                                style={{
                                  backgroundColor: chk.passed
                                    ? 'var(--chip-good-bg)'
                                    : 'var(--chip-bad-bg)',
                                  color: chk.passed ? 'var(--good)' : 'var(--bad)',
                                }}
                                aria-hidden="true"
                              >
                                {chk.passed ? '✓' : '✕'}
                              </span>
                              <div className="min-w-0 flex-1">
                                <div className="font-semibold" style={{ color: 'var(--text)' }}>
                                  {chk.name}
                                </div>
                                <div
                                  className="truncate"
                                  title={chk.detail}
                                  style={{ color: 'var(--text-secondary)' }}
                                >
                                  {chk.detail}
                                </div>
                              </div>
                            </button>
                          )
                        })}
                      </div>

                      {openCheckCode && GUARD_RULE_DEFINITIONS[openCheckCode] && (
                        <GlassDetailPanel
                          id={`guard-refuse-check-glass-${openCheckCode}`}
                          isOpen={true}
                          onClose={() =>
                            runGlassViewTransition(() => {
                              setOpenCheckCode(null)
                            }, reducedMotion)
                          }
                          title={GUARD_RULE_DEFINITIONS[openCheckCode].name}
                          subtitle={`Rule threshold: ${GUARD_RULE_DEFINITIONS[openCheckCode].threshold}`}
                          triggerRef={{
                            get current() {
                              return openCheckCode ? checkTriggerRefs.current[openCheckCode] ?? null : null
                            },
                          }}
                        >
                          <p className="m-0">{GUARD_RULE_DEFINITIONS[openCheckCode].explanation}</p>
                          <p className="m-0 text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                            Current quote evaluation:{' '}
                            {guardChecks.find(c => c.code === openCheckCode)?.detail}
                          </p>
                        </GlassDetailPanel>
                      )}
                    </div>

                    {/* Compare Issuers Disclosure */}
                    {issuerRows.length > 0 && (
                      <details
                        className="rounded-2xl overflow-hidden"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--hairline)',
                        }}
                      >
                        <summary
                          className="px-4 py-3 min-h-[44px] text-xs font-semibold cursor-pointer flex items-center justify-between select-none"
                          style={{ color: 'var(--text)' }}
                        >
                          <span>Compare issuers ({issuerRows.length})</span>
                          <span className="font-mono" style={{ color: 'var(--text-secondary)' }}>
                            {issuerRows.map(r => r.symbol).join(' vs ')}
                          </span>
                        </summary>
                        <div
                          className="px-4 pb-4 pt-3 overflow-x-auto"
                          style={{ borderTop: '1px solid var(--hairline)' }}
                        >
                          <table className="w-full text-left border-collapse text-xs">
                            <thead>
                              <tr
                                style={{
                                  borderBottom: '1px solid var(--hairline)',
                                  color: 'var(--text-secondary)',
                                }}
                              >
                                <th className="py-2 pr-2 font-medium">Token</th>
                                <th className="py-2 px-2 font-medium">Shares</th>
                                <th className="py-2 px-2 font-medium">Price / sh</th>
                                <th className="py-2 px-2 font-medium">Vs market</th>
                                <th className="py-2 px-2 font-medium">Depth</th>
                                <th className="py-2 pl-2 font-medium">Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {issuerRows.map(row => (
                                <tr
                                  key={`${row.issuer}-${row.symbol}`}
                                  style={{ borderBottom: '1px solid var(--hairline)' }}
                                >
                                  <td className="py-2.5 pr-2 font-mono font-semibold">
                                    {row.symbol}
                                    <div
                                      className="font-sans font-normal"
                                      style={{ color: 'var(--text-secondary)' }}
                                    >
                                      {row.issuer_label}
                                    </div>
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {row.shares !== null ? row.shares.toFixed(4) : 'N/A'}
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {row.all_in_price_per_share !== null
                                      ? `$${row.all_in_price_per_share.toFixed(2)}`
                                      : 'N/A'}
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {row.spread_pct !== null
                                      ? `${row.spread_pct > 0 ? '+' : ''}${row.spread_pct.toFixed(2)}%`
                                      : 'N/A'}
                                  </td>
                                  <td className="py-2.5 px-2 font-mono">
                                    {formatCompactUsd(row.depth_usd)}
                                  </td>
                                  <td className="py-2.5 pl-2">
                                    <span style={{ color: 'var(--bad)' }}>
                                      {humanizeCode(row.refusal_code)}: {row.refusal_message}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </details>
                    )}
                  </motion.div>
                )}
              </section>
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  )
}
