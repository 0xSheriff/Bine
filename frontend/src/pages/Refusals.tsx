import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchQuote, fetchTickers } from '../api'
import { Footer, TopHeader, formatSecondsAgo, navigateApp } from '../components/shared'
import recordedRefusals from '../data/recorded-refusals.json'
import type { QuoteVerdictResponse } from '../types'
import { GUARD_RULE_DEFINITIONS } from './Guard'

export default function Refusals() {
  const [runningId, setRunningId] = useState<string | null>(null)
  const [liveResults, setLiveResults] = useState<Record<string, QuoteVerdictResponse>>({})
  const [liveErrors, setLiveErrors] = useState<Record<string, string>>({})

  const { data: catalog } = useQuery({
    queryKey: ['tickers'],
    queryFn: fetchTickers,
    staleTime: 60_000,
  })

  // Lightweight single quote to show current live session banner without firing 5 calls in parallel
  const { data: sessionSample } = useQuery({
    queryKey: ['quote-session-banner'],
    queryFn: () => fetchQuote('NVDA', 5.5, false),
    staleTime: 60_000,
  })

  const handleRunLive = async (id: string, ticker: string, amountUsd: number) => {
    if (runningId) return
    setRunningId(id)
    setLiveErrors(prev => {
      const next = { ...prev }
      delete next[id]
      return next
    })
    try {
      const res = await fetchQuote(ticker, amountUsd, false)
      setLiveResults(prev => ({ ...prev, [id]: res }))
    } catch (err) {
      setLiveErrors(prev => ({
        ...prev,
        [id]: err instanceof Error ? err.message : 'Could not fetch live quote.',
      }))
    } finally {
      setRunningId(null)
    }
  }

  const sessionStatus = sessionSample?.market?.status || 'regular / offhours'
  const sessionOpen = sessionSample?.market?.open ?? true

  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--bg-page)', color: 'var(--text)' }}
    >
      <TopHeader />
      <main className="flex-1 w-full py-8 sm:py-12">
        <div className="bine-container">
          <div className="w-full max-w-[1120px] mx-auto space-y-10">
            {/* Page Heading + Live Session Banner */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div className="max-w-2xl space-y-2">
                <h1 tabIndex={-1} className="bine-section-heading m-0 outline-none">
                  Why Bine says no
                </h1>
                <p className="bine-body m-0" style={{ color: 'var(--text-secondary)' }}>
                  Every trade runs through 8 deterministic pre-trade checks. Below is the rule legend and recorded refusal evidence from BNB Chain, with one-at-a-time live verification.
                </p>
              </div>

              <div
                className="bine-card px-4 py-3 flex items-center gap-3 self-start md:self-auto shrink-0"
                role="status"
                aria-live="polite"
              >
                <span
                  className="w-2.5 h-2.5 rounded-full shrink-0"
                  style={{
                    backgroundColor: sessionOpen ? 'var(--good)' : 'var(--warn)',
                  }}
                />
                <div className="text-xs font-mono">
                  <div className="font-semibold" style={{ color: 'var(--text)' }}>
                    Live BSC session: {sessionStatus} ({sessionOpen ? 'open' : 'paused'})
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    {catalog?.count ?? 448} catalog tickers loaded
                    {sessionSample?.quoted_at ? ` · checked ${formatSecondsAgo(sessionSample.quoted_at)}` : ''}
                  </div>
                </div>
              </div>
            </div>

            {/* 1. 8-Rule Legend */}
            <section aria-labelledby="rule-legend-heading" className="space-y-4">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <h2 id="rule-legend-heading" className="text-lg font-semibold m-0">
                  The 8 pre-trade guard rules
                </h2>
                <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                  Evaluated in order on every GET /api/quote request
                </span>
              </div>

              <div className="bine-card overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-sm">
                    <thead>
                      <tr
                        style={{
                          borderBottom: '1px solid var(--hairline)',
                          backgroundColor: 'var(--surface-subtle)',
                          color: 'var(--text-secondary)',
                        }}
                      >
                        <th className="py-3 px-4 font-medium">Rule</th>
                        <th className="py-3 px-4 font-medium">Code</th>
                        <th className="py-3 px-4 font-medium">What it protects</th>
                        <th className="py-3 px-4 font-medium">Threshold</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(GUARD_RULE_DEFINITIONS).map(([code, rule]) => (
                        <tr
                          key={code}
                          style={{ borderBottom: '1px solid var(--hairline)' }}
                        >
                          <td className="py-3 px-4 font-medium whitespace-nowrap">{rule.name}</td>
                          <td className="py-3 px-4 font-mono text-xs whitespace-nowrap" style={{ color: 'var(--text-secondary)' }}>
                            {code}
                          </td>
                          <td className="py-3 px-4" style={{ color: 'var(--text-secondary)' }}>
                            {rule.explanation}
                          </td>
                          <td className="py-3 px-4 font-mono text-xs whitespace-nowrap">
                            {rule.threshold}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            {/* 2. Recorded Evidence Cards + One-at-a-Time Live Verification */}
            <section aria-labelledby="recorded-evidence-heading" className="space-y-4">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <h2 id="recorded-evidence-heading" className="text-lg font-semibold m-0">
                  Recorded refusal evidence
                </h2>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Click &ldquo;Run live now&rdquo; on any card to query GET /api/quote one request at a time.
                </span>
              </div>

              <div className="space-y-4">
                {recordedRefusals.map(item => {
                  const live = liveResults[item.id]
                  const liveErr = liveErrors[item.id]
                  const isRunningThis = runningId === item.id
                  const liveCode = live?.refusal?.code || (live?.verdict === 'BUY' ? 'BUY' : null)

                  return (
                    <article
                      key={item.id}
                      className="bine-card p-5 sm:p-6 space-y-4"
                    >
                      <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                        <div className="space-y-2.5 min-w-0 flex-1">
                          <div className="flex items-center gap-2.5 flex-wrap">
                            <span
                              className="inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-semibold"
                              style={{
                                backgroundColor: 'var(--chip-bad-bg)',
                                color: 'var(--bad)',
                              }}
                            >
                              {item.refusal_code}
                            </span>
                            <span className="text-sm font-semibold">
                              {item.ticker} ({item.symbol}) · ${item.amount_usd.toFixed(2)}
                            </span>
                            <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                              {item.recorded_label}
                            </span>
                          </div>

                          <p className="text-sm sm:text-base font-medium m-0 leading-relaxed">
                            {item.message}
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleRunLive(item.id, item.ticker, item.amount_usd)}
                            disabled={Boolean(runningId)}
                            className="bine-pill-secondary cursor-pointer disabled:opacity-50 min-h-[44px]"
                            style={{
                              height: '44px',
                              padding: '0 18px',
                              fontSize: '13px',
                            }}
                          >
                            {isRunningThis ? 'Running live...' : 'Run live now'}
                          </button>

                          <a
                            href={item.guard_href}
                            onClick={e => navigateApp(item.guard_href, e)}
                            className="bine-pill-secondary min-h-[44px]"
                            style={{
                              height: '44px',
                              padding: '0 18px',
                              fontSize: '13px',
                            }}
                          >
                            Open in Guard &rarr;
                          </a>
                        </div>
                      </div>

                      {/* Live comparison box when user clicks "Run live now" */}
                      {(live || liveErr) && (
                        <div
                          className="rounded-xl p-4 space-y-2"
                          style={{
                            backgroundColor: 'var(--surface-subtle)',
                            border: '1px solid var(--border)',
                          }}
                          aria-live="polite"
                        >
                          {liveErr ? (
                            <div className="text-xs font-mono" style={{ color: 'var(--bad)' }}>
                              Live check error: {liveErr}
                            </div>
                          ) : live ? (
                            <>
                              <div className="flex items-center justify-between gap-2 flex-wrap">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
                                    Live result right now:
                                  </span>
                                  <span
                                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-mono font-semibold"
                                    style={{
                                      backgroundColor:
                                        live.verdict === 'BUY' ? 'var(--chip-good-bg)' : 'var(--chip-bad-bg)',
                                      color: live.verdict === 'BUY' ? 'var(--good)' : 'var(--bad)',
                                    }}
                                  >
                                    {liveCode}
                                  </span>
                                </div>
                                <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                                  market {live.market.status} · {formatSecondsAgo(live.quoted_at)}
                                </span>
                              </div>
                              <p className="text-sm m-0 leading-relaxed">
                                {live.verdict === 'BUY'
                                  ? `BUY ${live.shares?.toFixed(4) ?? '0.0000'} ${live.ticker} (${live.token?.symbol}) at $${live.all_in_price_per_share?.toFixed(2) ?? 'N/A'}/sh (${live.spread_pct?.toFixed(2) ?? '0.00'}% vs reference).`
                                  : live.refusal?.message || 'Refused by guard.'}
                              </p>
                            </>
                          ) : null}
                        </div>
                      )}
                    </article>
                  )
                })}
              </div>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
