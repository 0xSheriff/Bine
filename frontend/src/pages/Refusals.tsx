import { useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchHealth, fetchQuote, fetchRecentChecks, fetchTickers } from '../api'
import { usePrefersReducedMotion } from '../components/BineLogo'
import { GlassDetailPanel, runGlassViewTransition } from '../components/GlassStack'
import {
  Footer,
  TopHeader,
  formatSecondsAgo,
  navigateApp,
} from '../components/shared'
import recordedRefusals from '../data/recorded-refusals.json'
import {
  GUARD_RULE_DEFINITIONS,
  GUARD_RULES_COUNT,
  deriveSessionFromUtc,
  formatUtcAndWat,
  getLiveMarketSession,
  humanizeCode,
  humanizeStatus,
} from '../lib/humanize'
import type { QuoteVerdictResponse } from '../types'

export default function Refusals() {
  const reducedMotion = usePrefersReducedMotion()
  const [runningId, setRunningId] = useState<string | null>(null)
  const [liveResults, setLiveResults] = useState<Record<string, QuoteVerdictResponse>>({})
  const [liveErrors, setLiveErrors] = useState<Record<string, string>>({})
  const [openRuleCode, setOpenRuleCode] = useState<string | null>(null)
  const [openCardId, setOpenCardId] = useState<string | null>(null)

  const ruleTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const cardTriggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    staleTime: 30_000,
  })

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

  const { data: recentChecksData } = useQuery({
    queryKey: ['recentChecks'],
    queryFn: () => fetchRecentChecks(24, 20),
    staleTime: 30_000,
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

  const liveSession = getLiveMarketSession()

  const activeRule = openRuleCode ? GUARD_RULE_DEFINITIONS[openRuleCode] : null
  const activeRuleTriggerRef = {
    get current() {
      return openRuleCode ? ruleTriggerRefs.current[openRuleCode] ?? null : null
    },
  }

  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden"
      style={{ backgroundColor: 'var(--bg-page)', color: 'var(--text)' }}
    >
      <TopHeader />
      <main className="flex-1 w-full py-8 sm:py-12">
        <div className="bine-container">
          <div className="w-full max-w-[1240px] mx-auto space-y-10">
            {/* Page Heading + Live Session Banner */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <div className="max-w-2xl space-y-2">
                <h1 tabIndex={-1} className="bine-section-heading m-0 outline-none">
                  Why Bine says no
                </h1>
                <p className="bine-body m-0" style={{ color: 'var(--text-secondary)' }}>
                  Every trade runs through {GUARD_RULES_COUNT} deterministic pre-trade checks. Click any rule row or any of the {recordedRefusals.length} recorded refusal cards to open its liquid-glass breakdown and run a live check.
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
                    backgroundColor: liveSession.isRegular ? 'var(--good)' : 'var(--warn)',
                  }}
                />
                <div className="text-xs font-mono">
                  <div className="font-semibold" style={{ color: 'var(--text)' }}>
                    Live session: {liveSession.label}
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    {catalog?.count ?? 448} tokens watched
                    {sessionSample?.quoted_at ? ` · quote ${formatSecondsAgo(sessionSample.quoted_at)}` : ''}
                    {health?.binance_credentials_present ? ' · Binance API ready' : ''}
                  </div>
                </div>
              </div>
            </div>

            {/* 1. Rule Legend (Code column removed per Phase A; clickable rows open GlassDetailPanel) */}
            <section aria-labelledby="rule-legend-heading" className="space-y-4">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <h2 id="rule-legend-heading" className="text-lg font-semibold m-0">
                  The {GUARD_RULES_COUNT} pre-trade guard rules
                </h2>
                <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                  Click any rule to inspect its threshold &amp; data source
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
                        <th className="py-3 px-4 font-medium">What it protects</th>
                        <th className="py-3 px-4 font-medium">Threshold</th>
                        <th className="py-3 px-4 font-medium text-right">Inspect</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(GUARD_RULE_DEFINITIONS).map(([code, rule]) => {
                        const isRuleOpen = openRuleCode === code
                        return (
                          <tr
                            key={code}
                            style={{
                              borderBottom: '1px solid var(--hairline)',
                              backgroundColor: isRuleOpen ? 'var(--surface-subtle)' : 'transparent',
                            }}
                          >
                            <td className="py-3 px-4 font-medium whitespace-nowrap">{rule.name}</td>
                            <td className="py-3 px-4" style={{ color: 'var(--text-secondary)' }}>
                              {rule.explanation}
                            </td>
                            <td className="py-3 px-4 font-mono text-xs whitespace-nowrap">
                              {rule.threshold}
                            </td>
                            <td className="py-2 px-4 text-right whitespace-nowrap">
                              <button
                                ref={el => {
                                  ruleTriggerRefs.current[code] = el
                                }}
                                type="button"
                                aria-expanded={isRuleOpen}
                                aria-controls={`rule-glass-${code}`}
                                onClick={() =>
                                  runGlassViewTransition(() => {
                                    setOpenRuleCode(prev => (prev === code ? null : code))
                                  }, reducedMotion)
                                }
                                className="bine-glass-trigger bine-pill-secondary px-3 min-h-[44px] text-xs font-medium cursor-pointer"
                              >
                                {isRuleOpen ? 'Hide' : 'Details'}
                              </button>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
              </div>

              {openRuleCode && activeRule && (
                <GlassDetailPanel
                  id={`rule-glass-${openRuleCode}`}
                  isOpen={true}
                  onClose={() =>
                    runGlassViewTransition(() => {
                      setOpenRuleCode(null)
                    }, reducedMotion)
                  }
                  title={activeRule.name}
                  subtitle={`Threshold: ${activeRule.threshold}`}
                  triggerRef={activeRuleTriggerRef}
                >
                  <p className="m-0">{activeRule.explanation}</p>
                  <div className="flex flex-wrap items-center gap-3 pt-1">
                    <a
                      href="/guard"
                      onClick={e => navigateApp('/guard', e)}
                      className="bine-pill-primary min-h-[44px] px-5 text-xs"
                    >
                      Test this rule in Guard &rarr;
                    </a>
                  </div>
                </GlassDetailPanel>
              )}
            </section>

            {/* Live now strip */}
            <div
              className="bine-card p-4 sm:p-5 flex flex-col md:flex-row md:items-center justify-between gap-4"
              style={{
                backgroundColor: 'var(--surface-subtle)',
                border: '1px solid var(--hairline)',
              }}
              role="region"
              aria-label="Live market status strip"
            >
              <div className="flex items-center gap-3">
                <span
                  className="w-3 h-3 rounded-full shrink-0"
                  style={{ backgroundColor: liveSession.isRegular ? 'var(--good)' : 'var(--warn)' }}
                />
                <div>
                  <div className="text-sm font-semibold" style={{ color: 'var(--text)' }}>
                    Live now: {liveSession.label}
                  </div>
                  <div className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {catalog?.count ?? 448} tokens watched
                    {sessionSample?.quoted_at ? ` · last live check ${formatSecondsAgo(sessionSample.quoted_at)}` : ''}
                    {' · '}
                    {health?.binance_credentials_present ? 'Binance API connected' : 'Demo mode'}
                    {' · '}
                    {health?.live_mode ? 'Live execution enabled' : 'Live execution disabled (dry-run only)'}
                  </div>
                </div>
              </div>
              <div className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                Recorded cards below are frozen snapshots.
              </div>
            </div>

            {/* 2. Recorded Evidence Cards + One-at-a-Time Live Verification */}
            <section aria-labelledby="recorded-evidence-heading" className="space-y-4">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <h2 id="recorded-evidence-heading" className="text-lg font-semibold m-0">
                  Recorded evidence (static snapshots) ({recordedRefusals.length})
                </h2>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Click &ldquo;Inspect details&rdquo; or &ldquo;Run live now&rdquo; on any card (one open at a time).
                </span>
              </div>

              <div className="space-y-4">
                {recordedRefusals.map(item => {
                  const live = liveResults[item.id]
                  const liveErr = liveErrors[item.id]
                  const isRunningThis = runningId === item.id
                  const isCardOpen = openCardId === item.id
                  const liveCode = live?.refusal?.code
                    ? humanizeCode(live.refusal.code)
                    : live?.verdict === 'BUY'
                      ? 'Buy'
                      : null
                  const guardHref = `/guard?ticker=${encodeURIComponent(item.ticker)}&amount=${item.amount_usd}`

                  const cardTriggerRef = {
                    get current() {
                      return cardTriggerRefs.current[item.id] ?? null
                    },
                  }

                  const derivedSession = deriveSessionFromUtc(item.recorded_at)

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
                              {humanizeCode(item.refusal_code)}
                            </span>
                            <span className="text-sm font-semibold">
                              {item.ticker} ({item.token_symbol}) · ${item.amount_usd.toFixed(2)}
                            </span>
                            <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                              <span>{formatUtcAndWat(item.recorded_at)}</span>
                              <span className="block sm:inline sm:ml-2 opacity-80">
                                {formatSecondsAgo(item.recorded_at)} · {humanizeStatus(derivedSession)}
                              </span>
                            </span>
                          </div>

                          <p className="text-sm sm:text-base font-medium m-0 leading-relaxed">
                            {item.message}
                          </p>
                        </div>

                        <div className="flex flex-wrap items-center gap-2.5 shrink-0">
                          <button
                            ref={el => {
                              cardTriggerRefs.current[item.id] = el
                            }}
                            type="button"
                            aria-expanded={isCardOpen}
                            aria-controls={`refusal-glass-${item.id}`}
                            onClick={() =>
                              runGlassViewTransition(() => {
                                setOpenCardId(prev => (prev === item.id ? null : item.id))
                              }, reducedMotion)
                            }
                            className="bine-glass-trigger bine-pill-secondary cursor-pointer min-h-[44px]"
                            style={{
                              height: '44px',
                              padding: '0 18px',
                              fontSize: '13px',
                            }}
                          >
                            {isCardOpen ? 'Hide details' : 'Inspect details'}
                          </button>

                          <button
                            type="button"
                            onClick={() => {
                              setOpenCardId(item.id)
                              handleRunLive(item.id, item.ticker, item.amount_usd)
                            }}
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
                            href={guardHref}
                            onClick={e => navigateApp(guardHref, e)}
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

                      <GlassDetailPanel
                        id={`refusal-glass-${item.id}`}
                        isOpen={isCardOpen}
                        onClose={() =>
                          runGlassViewTransition(() => {
                            setOpenCardId(null)
                          }, reducedMotion)
                        }
                        title={`${item.ticker} (${item.token_symbol}) · ${item.rule_label}`}
                        subtitle={`Recorded ${formatUtcAndWat(item.recorded_at)} · Issuer ${item.issuer}`}
                        triggerRef={cardTriggerRef}
                      >
                        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs font-mono">
                          <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
                            <div style={{ color: 'var(--text-secondary)' }}>Token price</div>
                            <div className="font-semibold text-sm mt-0.5">${item.token_price_usd.toFixed(2)}</div>
                          </div>
                          <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
                            <div style={{ color: 'var(--text-secondary)' }}>Reference / sh</div>
                            <div className="font-semibold text-sm mt-0.5">${item.reference_price_usd.toFixed(2)}</div>
                          </div>
                          <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
                            <div style={{ color: 'var(--text-secondary)' }}>Share ratio</div>
                            <div className="font-semibold text-sm mt-0.5">{item.share_ratio.toFixed(4)}x</div>
                          </div>
                          <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
                            <div style={{ color: 'var(--text-secondary)' }}>Spread / code</div>
                            <div className="font-semibold text-sm mt-0.5">
                              {item.spread_pct !== null
                                ? `${item.spread_pct.toFixed(2)}%`
                                : item.upstream_code
                                  ? `Code ${item.upstream_code}`
                                  : 'N/A'}
                            </div>
                          </div>
                        </div>

                        {item.alternative?.note && (
                          <p className="text-xs m-0" style={{ color: 'var(--text-secondary)' }}>
                            Alternative issuer note: {item.alternative.note}
                          </p>
                        )}

                        {/* Live comparison box when user clicks "Run live now" */}
                        {(live || liveErr) && (
                          <div
                            className="rounded-xl p-4 space-y-2"
                            style={{
                              backgroundColor: 'var(--surface)',
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
                                    {humanizeStatus(live.market.status)} · {formatSecondsAgo(live.quoted_at)}
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
                      </GlassDetailPanel>
                    </article>
                  )
                })}
              </div>
            </section>

            {/* 3. Last 24 hours (live checks) */}
            <section aria-labelledby="recent-checks-heading" className="space-y-4">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <h2 id="recent-checks-heading" className="text-lg font-semibold m-0">
                  Last 24 hours (live) ({recentChecksData?.checks.length ?? 0})
                </h2>
                <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                  Automated background probe checks recorded by the server.
                </span>
              </div>

              {!recentChecksData || recentChecksData.checks.length === 0 ? (
                <div
                  className="bine-card p-5 text-sm text-center"
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    border: '1px solid var(--hairline)',
                    color: 'var(--text-secondary)',
                  }}
                >
                  No automated probe checks recorded in the last 24 hours. The scheduled probe timer runs periodically on the VPS.
                </div>
              ) : (
                <div className="space-y-3">
                  {recentChecksData.checks.map(check => {
                    const isBuy = check.verdict === 'BUY'
                    const actionLabel = humanizeCode(check.action || 'scheduled')
                    const refusalLabel = check.refusal_code ? humanizeCode(check.refusal_code) : null

                    return (
                      <article
                        key={check.id}
                        className="bine-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono"
                        style={{
                          backgroundColor: 'var(--surface-subtle)',
                          border: '1px solid var(--hairline)',
                        }}
                      >
                        <div className="flex items-center gap-3">
                          <span
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold"
                            style={{
                              backgroundColor: isBuy ? 'var(--chip-good-bg)' : 'var(--chip-bad-bg)',
                              color: isBuy ? 'var(--good)' : 'var(--bad)',
                            }}
                          >
                            {isBuy ? 'BUY' : 'REFUSE'}
                          </span>
                          <div>
                            <span className="font-semibold text-sm" style={{ color: 'var(--text)' }}>
                              {check.ticker}
                              {check.recommended_symbol ? ` (${check.recommended_symbol})` : ''}
                            </span>
                            <span className="ml-2" style={{ color: 'var(--text-secondary)' }}>
                              ${check.amount_usd.toFixed(2)} · {actionLabel}
                            </span>
                          </div>
                        </div>

                        <div className="flex flex-col sm:items-end text-xs" style={{ color: 'var(--text-secondary)' }}>
                          <div>
                            {refusalLabel && <span className="font-semibold mr-2">{refusalLabel}</span>}
                            <span>{formatSecondsAgo(check.created_at)}</span>
                          </div>
                          <div className="opacity-80">
                            {formatUtcAndWat(check.created_at)}
                          </div>
                        </div>
                      </article>
                    )
                  })}
                </div>
              )}
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
