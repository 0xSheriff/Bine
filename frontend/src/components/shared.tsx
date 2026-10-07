/** Shared formatting helpers, TopHeader, Footer, LiveModeChip, and inlined Simple Icons for Bine. */

import { useEffect, useId, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { executeTrade, fetchDecisions, fetchHealth } from '../api'
import type { ExecuteTradeResponse, QuoteVerdictResponse } from '../types'
import { BineWordmarkLockup } from './BineLogo'

export function parseUtcDate(iso: string): Date {
  const normalized = /[Z+-]\d*:*\d*$/.test(iso) ? iso : `${iso}Z`
  return new Date(normalized)
}

export function getSecondsElapsed(iso: string | null | undefined, nowMs = Date.now()): number {
  if (!iso) return 0
  const parsed = parseUtcDate(iso).getTime()
  if (Number.isNaN(parsed)) return 0
  return Math.max(0, Math.round((nowMs - parsed) / 1000))
}

export function formatSecondsAgo(iso: string | null | undefined, nowMs = Date.now()): string {
  if (!iso) return 'just now'
  const sec = getSecondsElapsed(iso, nowMs)
  if (sec < 60) return `${sec}s ago`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}m ago`
  const hours = Math.floor(min / 60)
  if (hours < 24) return hours === 1 ? '1 hour ago' : `${hours} hours ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? '1 day ago' : `${days} days ago`
}

export function formatAbsoluteAndRelative(iso: string | null | undefined, nowMs = Date.now()): string {
  if (!iso) return 'N/A'
  const date = parseUtcDate(iso)
  if (Number.isNaN(date.getTime())) return iso
  // Format in Africa/Lagos (WAT, UTC+1) to match user local timezone consistently
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'Africa/Lagos',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const month = parts.find(p => p.type === 'month')?.value ?? ''
  const day = parts.find(p => p.type === 'day')?.value ?? ''
  const hour = parts.find(p => p.type === 'hour')?.value ?? '00'
  const minute = parts.find(p => p.type === 'minute')?.value ?? '00'
  const rel = formatSecondsAgo(iso, nowMs)
  return `${month} ${day}, ${hour}:${minute} WAT, ${rel}`
}

export function formatCompactUsd(val: number | null | undefined): string {
  if (val === null || val === undefined) return 'N/A'
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(2)}B`
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`
  return `$${val.toFixed(2)}`
}

export function shortAddress(addr: string | null | undefined): string {
  if (!addr) return 'N/A'
  if (addr.length <= 12) return addr
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`
}

export const SIM_ROUTER_TOOLTIP =
  'The dry-run simulates against router 0xB444.... Live swaps through baw use router 0xb300.... See README.'

export function formatSimulationStatus(status: string | null | undefined): {
  label: string
  tooltip?: string
} {
  if (!status) return { label: 'N/A' }
  if (status === 'REQUIRES_APPROVAL') {
    return {
      label: 'Sim router needs allowance',
      tooltip: SIM_ROUTER_TOOLTIP,
    }
  }
  return { label: status }
}

/** Inlined from simple-icons/icons/github.svg */
export function GitHubIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      role="img"
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  )
}

/** Inlined from simple-icons/icons/x.svg */
export function XIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      role="img"
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z" />
    </svg>
  )
}

export function focusPageHeading() {
  if (typeof window === 'undefined') return
  window.setTimeout(() => {
    const h1 = document.querySelector('main h1, h1') as HTMLElement | null
    if (h1) {
      if (!h1.hasAttribute('tabindex')) {
        h1.setAttribute('tabindex', '-1')
      }
      h1.focus({ preventScroll: true })
    }
  }, 60)
}

export function navigateApp(href: string, e?: React.MouseEvent<HTMLAnchorElement>) {
  if (typeof window === 'undefined') return
  if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0)) return

  const url = new URL(href, window.location.origin)
  // Redirect /#guard to /guard
  if (url.pathname === '/' && url.hash === '#guard') {
    url.pathname = '/guard'
    url.hash = ''
  }

  const samePath = url.pathname === window.location.pathname && url.search === window.location.search

  if (e) e.preventDefault()

  if (!samePath) {
    window.history.pushState({}, '', `${url.pathname}${url.search}${url.hash}`)
    window.dispatchEvent(new PopStateEvent('popstate'))
    window.scrollTo({ top: 0, behavior: 'auto' })
    focusPageHeading()
  } else if (url.hash) {
    const id = url.hash.slice(1)
    window.setTimeout(() => {
      const target = document.getElementById(id)
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 0)
  }
}

export function TopHeader() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      try {
        const qTheme = new URLSearchParams(window.location.search).get('theme')
        if (qTheme === 'dark' || qTheme === 'light') return qTheme
        const stored = localStorage.getItem('bine-theme')
        if (stored === 'dark' || stored === 'light') return stored
      } catch {
        // ignore storage error
      }
      const current = document.documentElement.getAttribute('data-theme')
      if (current === 'dark' || current === 'light') return current
    }
    return 'light'
  })

  const [scrolled, setScrolled] = useState<boolean>(false)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.style.colorScheme = theme
    try {
      localStorage.setItem('bine-theme', theme)
    } catch {
      // ignore storage errors
    }
  }, [theme])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const onScroll = () => {
      setScrolled((window.scrollY || 0) > 8)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const pathname = typeof window !== 'undefined' ? window.location.pathname : '/'
  const navItems = [
    { href: '/guard', matchPath: '/guard', label: 'Guard' },
    { href: '/refusals', matchPath: '/refusals', label: 'Refusals' },
    { href: '/receipts', matchPath: '/receipts', label: 'Receipts' },
    { href: '/integrate', matchPath: '/integrate', label: 'Developers' },
  ]

  return (
    <header
      className="sticky top-0 z-40 min-h-[80px] flex items-center transition-colors duration-200"
      style={{
        backgroundColor: scrolled ? 'var(--nav-blur-bg)' : 'transparent',
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(12px)' : 'none',
        borderBottom: scrolled ? '1px solid var(--hairline)' : '1px solid transparent',
      }}
    >
      <div className="bine-container py-2 sm:py-0">
        <div className="w-full max-w-[1240px] mx-auto flex flex-wrap sm:flex-nowrap items-center justify-between gap-y-2 gap-x-4">
          <div className="flex items-center gap-4 md:gap-8 min-w-0">
            <a
              href="/"
              onClick={e => navigateApp('/', e)}
              className="no-underline shrink-0 inline-flex items-center min-h-[44px] px-1 rounded-lg"
              aria-label="Bine home"
            >
              <BineWordmarkLockup tileSize={36} />
            </a>

            <nav
              className="hidden sm:flex items-center gap-2 md:gap-5"
              aria-label="Main navigation"
            >
              {navItems.map(item => {
                const active = pathname === item.matchPath
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    onClick={e => navigateApp(item.href, e)}
                    aria-current={active ? 'page' : undefined}
                    className="no-underline inline-flex items-center min-h-[44px] px-2.5 rounded-lg shrink-0 transition-colors"
                    style={{
                      fontSize: '14px',
                      fontWeight: active ? 600 : 500,
                      color: active ? 'var(--text)' : 'var(--text-secondary)',
                    }}
                  >
                    {item.label}
                  </a>
                )
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
            <button
              type="button"
              onClick={() => setTheme(prev => (prev === 'light' ? 'dark' : 'light'))}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              className="w-11 h-11 min-w-[44px] min-h-[44px] inline-flex items-center justify-center rounded-full cursor-pointer shrink-0 transition-transform hover:-translate-y-0.5 active:scale-95"
              style={{
                backgroundColor: 'var(--pill-secondary-bg)',
                color: 'var(--text)',
                boxShadow: 'var(--pill-secondary-shadow)',
                border: 'none',
              }}
            >
              {theme === 'dark' ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>

            <a
              href="/guard"
              onClick={e => navigateApp('/guard', e)}
              className="bine-pill-primary"
              style={{
                minHeight: '44px',
                padding: '0 20px',
              }}
            >
              Check a trade
            </a>
          </div>

          {/* Mobile navigation row (<640px) with >= 44px tap targets */}
          <nav
            className="flex sm:hidden items-center justify-between w-full pt-1 border-t"
            style={{ borderColor: 'var(--hairline)' }}
            aria-label="Mobile navigation"
          >
            {navItems.map(item => {
              const active = pathname === item.matchPath
              return (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={e => navigateApp(item.href, e)}
                  aria-current={active ? 'page' : undefined}
                  className="no-underline inline-flex items-center justify-center min-h-[44px] px-2 rounded-md transition-colors"
                  style={{
                    fontSize: '14px',
                    fontWeight: active ? 600 : 500,
                    color: active ? 'var(--text)' : 'var(--text-secondary)',
                  }}
                >
                  {item.label}
                </a>
              )
            })}
          </nav>
        </div>
      </div>
    </header>
  )
}

export function LiveModeChip() {
  const [open, setOpen] = useState(false)
  const popoverId = useId()
  const wrapRef = useRef<HTMLDivElement | null>(null)

  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    staleTime: 30_000,
  })

  useEffect(() => {
    if (!open) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const onPointerDown = (e: MouseEvent) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('mousedown', onPointerDown)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('mousedown', onPointerDown)
    }
  }, [open])

  const liveMode = healthQuery.data?.live_mode ?? false
  const maxTrade = healthQuery.data?.max_trade_usd ?? 6
  const dailyCap = healthQuery.data?.daily_cap_usd ?? 10

  if (liveMode) {
    return (
      <div
        className="inline-flex items-center gap-2 px-3.5 py-2 rounded-full text-xs font-medium"
        style={{
          backgroundColor: 'var(--chip-warn-bg)',
          color: 'var(--warn)',
        }}
      >
        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: 'var(--warn)' }} />
        <span>
          Live mode on, caps ${maxTrade} / ${dailyCap}
        </span>
      </div>
    )
  }

  return (
    <div ref={wrapRef} className="relative inline-flex flex-wrap items-center gap-2">
      <div
        className="inline-flex items-center gap-2 px-3.5 py-2 rounded-2xl text-xs leading-relaxed"
        style={{
          backgroundColor: 'var(--surface-subtle)',
          color: 'var(--text-secondary)',
        }}
      >
        <span
          className="w-2 h-2 rounded-full shrink-0"
          style={{ backgroundColor: 'var(--good)' }}
          aria-hidden="true"
        />
        <span>
          Dry-run mode. Bine simulates every trade with the Transaction API and never signs one from this page.
        </span>
      </div>

      <button
        type="button"
        aria-expanded={open}
        aria-controls={popoverId}
        onClick={() => setOpen(prev => !prev)}
        className="inline-flex items-center justify-center min-h-[44px] px-3 rounded-full text-xs font-semibold cursor-pointer"
        style={{
          backgroundColor: 'var(--surface-subtle)',
          color: 'var(--text)',
          border: '1px solid var(--hairline)',
        }}
      >
        Why dry-run?
      </button>

      {open && (
        <div
          id={popoverId}
          role="region"
          aria-label="Live execution policy"
          className="w-full sm:max-w-[440px] mt-1 p-3.5 rounded-2xl text-xs leading-relaxed"
          style={{
            backgroundColor: 'var(--bg-card)',
            color: 'var(--text-secondary)',
            border: '1px solid var(--hairline)',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          Live swaps run from the CLI with your own Agentic Wallet, capped at ${maxTrade} per trade and $
          {dailyCap} per day, so a hosted copy of Bine can never spend anyone&apos;s funds.
        </div>
      )}
    </div>
  )
}

interface LiveExecutionControlProps {
  quote: QuoteVerdictResponse
  dryRunResult: ExecuteTradeResponse | null
  onTradeComplete?: (res: ExecuteTradeResponse) => void
}

export function LiveExecutionControl({
  quote,
  dryRunResult,
  onTradeComplete,
}: LiveExecutionControlProps) {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    staleTime: 30_000,
  })
  const [dialogOpen, setDialogOpen] = useState(false)
  const [adminToken, setAdminToken] = useState('')
  const [stage, setStage] = useState<'idle' | 'submitted' | 'polling' | 'filled' | 'failed'>('idle')
  const [liveResult, setLiveResult] = useState<ExecuteTradeResponse | null>(null)
  const [liveError, setLiveError] = useState<string | null>(null)

  const liveMode = healthQuery.data?.live_mode ?? false
  const maxTrade = healthQuery.data?.max_trade_usd ?? 6
  const dailyCap = healthQuery.data?.daily_cap_usd ?? 10

  if (!liveMode || quote.verdict !== 'BUY' || !dryRunResult?.simulation?.passed) {
    return null
  }

  const issuerLabel = quote.token?.issuer === 'bstock' ? 'bStocks' : 'Ondo Global Markets'

  const handleConfirmSwap = async () => {
    setStage('submitted')
    setLiveError(null)
    try {
      const pollTimer = window.setTimeout(() => setStage('polling'), 900)
      const res = await executeTrade(
        quote.ticker,
        quote.amount_usd,
        true,
        adminToken.trim() || undefined,
      )
      window.clearTimeout(pollTimer)
      setLiveResult(res)
      if (res.execution.status === 'LIVE_SUBMITTED' && res.execution.tx_hash) {
        setStage('filled')
      } else {
        setStage('failed')
        setLiveError(res.execution.detail || 'Live execution did not return a confirmed tx_hash.')
      }
      await fetchDecisions(5)
      onTradeComplete?.(res)
    } catch (err) {
      setStage('failed')
      setLiveError(err instanceof Error ? err.message : 'Live execution failed')
    }
  }

  return (
    <div className="mt-3 space-y-3">
      {!dialogOpen && stage === 'idle' && (
        <button
          type="button"
          onClick={() => setDialogOpen(true)}
          className="bine-pill-secondary px-5 min-h-[44px]"
        >
          Review live swap (${quote.amount_usd.toFixed(2)})
        </button>
      )}

      {dialogOpen && (
        <div
          role="dialog"
          aria-modal="false"
          aria-label="Confirm live swap"
          className="p-5 rounded-2xl space-y-4"
          style={{
            backgroundColor: 'var(--surface-subtle)',
            border: '1px solid var(--hairline)',
          }}
        >
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-sm font-semibold m-0" style={{ color: 'var(--text)' }}>
              Review live swap before signing
            </h3>
            <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
              Wallet 0x34dA...b730
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div>
              <div style={{ color: 'var(--text-secondary)' }}>Amount</div>
              <div className="font-mono font-semibold mt-0.5" style={{ color: 'var(--text)' }}>
                ${quote.amount_usd.toFixed(2)} USDT
              </div>
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)' }}>Token</div>
              <div className="font-mono font-semibold mt-0.5" style={{ color: 'var(--text)' }}>
                {quote.token?.symbol} ({issuerLabel})
              </div>
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)' }}>Route</div>
              <div className="font-mono font-semibold mt-0.5" style={{ color: 'var(--text)' }}>
                baw (0xb300...028d)
              </div>
            </div>
            <div>
              <div style={{ color: 'var(--text-secondary)' }}>Safety caps</div>
              <div className="font-mono font-semibold mt-0.5" style={{ color: 'var(--text)' }}>
                ${maxTrade} trade / ${dailyCap} day
              </div>
            </div>
          </div>

          <div>
            <label
              htmlFor="live-admin-token"
              className="block text-xs font-medium mb-1"
              style={{ color: 'var(--text-secondary)' }}
            >
              Local admin token (optional if not configured)
            </label>
            <input
              id="live-admin-token"
              type="password"
              value={adminToken}
              onChange={e => setAdminToken(e.target.value)}
              placeholder="X-Bine-Admin-Token"
              className="w-full h-11 px-3 rounded-xl text-xs font-mono border-0"
              style={{
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text)',
              }}
            />
          </div>

          {stage !== 'idle' && (
            <div
              role="status"
              aria-live="polite"
              className="p-3 rounded-xl text-xs space-y-1"
              style={{
                backgroundColor: 'var(--bg-card)',
                color: stage === 'failed' ? 'var(--bad)' : 'var(--text)',
              }}
            >
              <div className="font-semibold">
                {stage === 'submitted' && '1/3 Submitted to Binance Agentic Wallet...'}
                {stage === 'polling' && '2/3 Polling BSC mainnet receipt...'}
                {stage === 'filled' && '3/3 Swap filled and verified on BNB Chain.'}
                {stage === 'failed' && 'Swap stopped before fill.'}
              </div>
              {liveResult?.execution?.tx_hash && (
                <div className="font-mono">
                  tx: {shortAddress(liveResult.execution.tx_hash)}{' '}
                  {liveResult.execution.bsctrace_url && (
                    <a
                      href={liveResult.execution.bsctrace_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline ml-2"
                      style={{ color: 'var(--text)' }}
                    >
                      Open BscTrace
                    </a>
                  )}
                </div>
              )}
              {liveError && <div>{liveError}</div>}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={stage === 'submitted' || stage === 'polling'}
              onClick={handleConfirmSwap}
              className="bine-pill-primary px-5 min-h-[44px] disabled:opacity-50"
            >
              Confirm swap
            </button>
            <button
              type="button"
              onClick={() => {
                setDialogOpen(false)
                setStage('idle')
              }}
              className="bine-pill-secondary px-4 min-h-[44px]"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export function Footer() {
  return (
    <footer
      className="mt-20 py-12"
      style={{
        borderTop: '1px solid var(--hairline)',
      }}
    >
      <div className="bine-container">
        <div className="w-full max-w-[1240px] mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-8">
          <div className="space-y-3">
            <BineWordmarkLockup tileSize={36} staticTile />
            <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
              Built for BNB Hack: Tokenized Stocks Edition on BNB Chain.
            </p>
          </div>

          <div className="space-y-3">
            <h2
              className="text-xs font-semibold uppercase tracking-wider m-0"
              style={{ color: 'var(--text-secondary)' }}
            >
              Connect
            </h2>
            <div className="flex flex-wrap items-center gap-4 sm:gap-6">
              <a
                href="https://github.com/0xSheriff"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub profile"
                className="group inline-flex items-center gap-3 no-underline rounded-full pr-3 min-h-[44px] py-0.5 transition-transform"
                style={{ color: 'var(--text)' }}
              >
                <span
                  className="w-11 h-11 rounded-full inline-flex items-center justify-center shrink-0 transition-transform group-hover:-translate-y-0.5"
                  style={{
                    backgroundColor: 'var(--pill-secondary-bg)',
                    color: 'var(--text)',
                    boxShadow: 'var(--pill-secondary-shadow)',
                  }}
                >
                  <GitHubIcon size={22} />
                </span>
                <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                  github.com/0xSheriff
                </span>
              </a>

              <a
                href="https://x.com/0xearthh"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="X profile"
                className="group inline-flex items-center gap-3 no-underline rounded-full pr-3 min-h-[44px] py-0.5 transition-transform"
                style={{ color: 'var(--text)' }}
              >
                <span
                  className="w-11 h-11 rounded-full inline-flex items-center justify-center shrink-0 transition-transform group-hover:-translate-y-0.5"
                  style={{
                    backgroundColor: 'var(--pill-secondary-bg)',
                    color: 'var(--text)',
                    boxShadow: 'var(--pill-secondary-shadow)',
                  }}
                >
                  <XIcon size={22} />
                </span>
                <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                  @0xearthh
                </span>
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
