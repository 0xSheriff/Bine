import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'motion/react'
import { fetchDecisions, fetchTickers } from '../api'
import { usePrefersReducedMotion } from '../components/BineLogo'
import { GlassStack, type GlassStackItem } from '../components/GlassStack'
import { HeroArt } from '../components/HeroArt'
import {
  Footer,
  TopHeader,
  formatAbsoluteAndRelative,
  navigateApp,
  shortAddress,
} from '../components/shared'
import onchainReceipts from '../data/onchain-receipts.json'
import recordedRefusals from '../data/recorded-refusals.json'
import { GUARD_RULE_DEFINITIONS, humanizeCode, humanizeStatus } from '../lib/humanize'

const FEATURED_REFUSAL =
  recordedRefusals.find(item => item.id === 'spyon-slippage-250') ?? recordedRefusals[0]
const LATEST_RECEIPT = onchainReceipts[0]

export default function Home() {
  const reducedMotion = usePrefersReducedMotion()

  // Redirect legacy /#guard or /?ticker=... links directly to /guard
  useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    if (window.location.hash === '#guard' || params.has('ticker') || params.has('amount')) {
      const qs = params.toString()
      navigateApp(qs ? `/guard?${qs}` : '/guard')
    }
  }, [])

  const { data: tickerCatalog } = useQuery({
    queryKey: ['tickers'],
    queryFn: fetchTickers,
    staleTime: 300_000,
  })

  const { data: liveDecisions } = useQuery({
    queryKey: ['decisions-live'],
    queryFn: () => fetchDecisions(50, true),
    staleTime: 60_000,
  })

  const tokensWatchedCount = tickerCatalog?.count ?? 448
  const verifiedSwapsCount =
    liveDecisions?.decisions?.filter(d => Boolean(d.tx_hash)).length || onchainReceipts.length

  const issuerBreakdown = useMemo(() => {
    const items = tickerCatalog?.tickers ?? []
    let ondoTokens = 0
    let bstockTokens = 0
    let dualIssuerTickers = 0
    for (const t of items) {
      if (t.issuers.includes('ondo')) ondoTokens += 1
      if (t.issuers.includes('bstock')) bstockTokens += 1
      if (t.dual) dualIssuerTickers += 1
    }
    return {
      ondoTokens: ondoTokens || 425,
      bstockTokens: bstockTokens || 55,
      dualIssuerTickers: dualIssuerTickers || 32,
    }
  }, [tickerCatalog])

  const proofItems: GlassStackItem[] = [
    {
      id: 'tokens',
      title: `${tokensWatchedCount} tokenized stock tickers watched on BNB Chain`,
      subtitle: `${issuerBreakdown.ondoTokens} Ondo Global Markets contracts · ${issuerBreakdown.bstockTokens} bStocks contracts · ${issuerBreakdown.dualIssuerTickers} dual-issuer tickers`,
      summary: (
        <div>
          <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
            Tokens watched on BSC
          </div>
          <div className="text-2xl sm:text-3xl font-semibold font-mono mt-1" style={{ color: 'var(--text)' }}>
            {tokensWatchedCount}
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            Ondo Global Markets &amp; bStocks
          </div>
        </div>
      ),
      detail: (
        <div className="space-y-3">
          <p className="m-0">
            Bine indexes every tokenized equity and ETF returned by the Binance Web3 RWA catalog on BNB Smart Chain (chain ID 56) across both supported issuers:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono">
            <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
              <div style={{ color: 'var(--text-secondary)' }}>Ondo Global Markets</div>
              <div className="text-base font-semibold mt-0.5">{issuerBreakdown.ondoTokens} tokens</div>
              <div style={{ color: 'var(--text-secondary)' }}>Minimum order $5.00 USD</div>
            </div>
            <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
              <div style={{ color: 'var(--text-secondary)' }}>bStocks (Backed)</div>
              <div className="text-base font-semibold mt-0.5">{issuerBreakdown.bstockTokens} tokens</div>
              <div style={{ color: 'var(--text-secondary)' }}>Verified live at $2.00 USD</div>
            </div>
            <div className="p-3 rounded-xl" style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}>
              <div style={{ color: 'var(--text-secondary)' }}>Dual-issuer overlap</div>
              <div className="text-base font-semibold mt-0.5">{issuerBreakdown.dualIssuerTickers} tickers</div>
              <div style={{ color: 'var(--text-secondary)' }}>5 bps tie-break rule</div>
            </div>
          </div>
          <div className="pt-1">
            <a
              href="/guard"
              onClick={e => navigateApp('/guard', e)}
              className="bine-pill-primary min-h-[44px] px-5 text-xs"
            >
              Open Guard &rarr;
            </a>
          </div>
        </div>
      ),
    },
    {
      id: 'rules',
      title: '8 deterministic pre-trade guard rules',
      subtitle: 'Evaluated sequentially on every GET /api/quote request',
      summary: (
        <div>
          <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
            Guard rules active
          </div>
          <div className="text-2xl sm:text-3xl font-semibold font-mono mt-1" style={{ color: 'var(--text)' }}>
            8
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            Deterministic pre-trade checks
          </div>
        </div>
      ),
      detail: (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
            {Object.entries(GUARD_RULE_DEFINITIONS).map(([code, rule]) => (
              <div
                key={code}
                className="p-3 rounded-xl flex items-start justify-between gap-2"
                style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <div>
                  <div className="font-semibold" style={{ color: 'var(--text)' }}>
                    {rule.name}
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>{rule.explanation}</div>
                </div>
                <span className="font-mono shrink-0" style={{ color: 'var(--text)' }}>
                  {rule.threshold}
                </span>
              </div>
            ))}
          </div>
          <div className="pt-1">
            <a
              href="/refusals"
              onClick={e => navigateApp('/refusals', e)}
              className="bine-pill-secondary min-h-[44px] px-5 text-xs"
            >
              See all 6 recorded refusals &rarr;
            </a>
          </div>
        </div>
      ),
    },
    {
      id: 'swaps',
      title: `${verifiedSwapsCount} verified mainnet swaps on BNB Chain`,
      subtitle: 'Executed via Binance Agentic Wallet after passing Transaction API dry-run',
      summary: (
        <div>
          <div className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-secondary)' }}>
            On-chain swaps verified
          </div>
          <div className="text-2xl sm:text-3xl font-semibold font-mono mt-1" style={{ color: 'var(--text)' }}>
            {verifiedSwapsCount}
          </div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-secondary)' }}>
            Real USDT to NVDAB fills on BSC
          </div>
        </div>
      ),
      detail: (
        <div className="space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
            {onchainReceipts.map(r => (
              <div
                key={r.decision_id}
                className="p-3.5 rounded-xl space-y-1.5"
                style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <div className="flex items-center justify-between gap-2 font-mono font-semibold">
                  <span>Decision #{r.decision_id} · ${r.amount_usd.toFixed(2)} USDT &rarr; {r.symbol}</span>
                  <span>Block #{r.block_number}</span>
                </div>
                <div style={{ color: 'var(--text-secondary)' }}>
                  Filled {r.filled_shares.toFixed(6)} vs {r.quoted_shares.toFixed(6)} quoted ({r.fill_diff_bps} bps) · Gas {r.gas_bnb.toFixed(8)} BNB
                </div>
                <div className="font-mono">
                  <a
                    href={r.bsctrace_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline"
                    style={{ color: 'var(--text)' }}
                  >
                    BscTrace {shortAddress(r.tx_hash)} &#8599;
                  </a>
                </div>
              </div>
            ))}
          </div>
          <div className="pt-1">
            <a
              href="/receipts"
              onClick={e => navigateApp('/receipts', e)}
              className="bine-pill-secondary min-h-[44px] px-5 text-xs"
            >
              Inspect full receipts &rarr;
            </a>
          </div>
        </div>
      ),
    },
  ]

  const howItWorksItems: GlassStackItem[] = [
    {
      id: 'step-check',
      title: '1. Check: Multi-issuer BNB Chain quote normalization',
      subtitle: 'Ondo Global Markets + bStocks catalog and DEX aggregator quote',
      summary: (
        <div className="space-y-2.5">
          <div className="flex items-center gap-2.5">
            <span
              className="w-8 h-8 rounded-lg inline-flex items-center justify-center"
              style={{ backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)' }}
              aria-hidden="true"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-3.5-3.5" strokeLinecap="round" />
              </svg>
            </span>
            <h3 className="text-base font-semibold m-0">1. Check</h3>
          </div>
          <p className="text-sm m-0 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Fetch live quotes across Ondo Global Markets and bStocks on BNB Chain and compute share-adjusted all-in price per share.
          </p>
        </div>
      ),
      detail: (
        <div className="space-y-2">
          <p className="m-0">
            For any ticker such as NVDA or SPY, Bine queries both Ondo Global Markets and bStocks contracts on BNB Smart Chain, divides raw token output by the catalog share ratio, and computes the true all-in USD price per underlying share.
          </p>
          <p className="m-0 text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
            Tie-break rule: when both issuers pass all 8 checks and their all-in share prices are within 5 bps (0.05%), Bine selects the issuer with the lower minimum order floor.
          </p>
        </div>
      ),
    },
    {
      id: 'step-guard',
      title: '2. Guard: 8 deterministic pre-trade safety gates',
      subtitle: 'Zero silent fallbacks on thin liquidity, closed sessions, or share-ratio traps',
      summary: (
        <div className="space-y-2.5">
          <div className="flex items-center gap-2.5">
            <span
              className="w-8 h-8 rounded-lg inline-flex items-center justify-center"
              style={{ backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)' }}
              aria-hidden="true"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 3l7 4v5c0 4.5-3 8.5-7 9.5-4-1-7-5-7-9.5V7l7-4z" strokeLinejoin="round" />
              </svg>
            </span>
            <h3 className="text-base font-semibold m-0">2. Guard</h3>
          </div>
          <p className="text-sm m-0 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Enforce 8 pre-trade safety rules covering session status, share-ratio traps, minimum order sizes, pool depth, and spread caps.
          </p>
        </div>
      ),
      detail: (
        <div className="space-y-2">
          <p className="m-0">
            Every quote is checked against the 1.00% maximum spread above stock reference, the 0.50x to 1.50x supported share-ratio window, the $10K AMM pool depth / $1M 24h volume floor, and active market session status. If any rule fails, Bine returns a structured refusal with the exact reason.
          </p>
        </div>
      ),
    },
    {
      id: 'step-receipt',
      title: '3. Receipt: Transaction API dry-run and SQLite audit log',
      subtitle: 'Every decision and live fill is recorded with block, gas, and fill delta',
      summary: (
        <div className="space-y-2.5">
          <div className="flex items-center gap-2.5">
            <span
              className="w-8 h-8 rounded-lg inline-flex items-center justify-center"
              style={{ backgroundColor: 'var(--surface-subtle)', border: '1px solid var(--border)' }}
              aria-hidden="true"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M9 12l2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
                <rect x="4" y="4" width="16" height="16" rx="3" />
              </svg>
            </span>
            <h3 className="text-base font-semibold m-0">3. Receipt</h3>
          </div>
          <p className="text-sm m-0 leading-relaxed" style={{ color: 'var(--text-secondary)' }}>
            Simulate the unsigned transaction via the Binance Transaction API before any live Agentic Wallet swap and log the on-chain receipt.
          </p>
        </div>
      ),
      detail: (
        <div className="space-y-2">
          <p className="m-0">
            Before any swap can execute, Bine simulates the unsigned swap calldata against the Binance Transaction API and logs a dry-run decision row in SQLite. Live swaps through Binance Agentic Wallet remain capped at $6.00 per trade and $10.00 per day.
          </p>
        </div>
      ),
    },
  ]

  const sectionReveal = reducedMotion
    ? {}
    : {
        initial: { opacity: 0, y: 12 },
        whileInView: { opacity: 1, y: 0 },
        viewport: { once: true, amount: 0.2 },
        transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] as const },
      }

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
        {/* 1. HERO SECTION (min(88vh, 760px)) */}
        <section className="relative overflow-hidden md:min-h-[min(88vh,760px)] flex items-center py-10 sm:py-14 md:py-16">
          {/* Desktop / Tablet Right-Side Ring Art (never touches nav, headline, or bottom edge) */}
          <div className="hidden md:flex absolute top-8 bottom-8 right-0 w-[49%] lg:w-[47%] translate-x-6 items-center justify-end pointer-events-none z-0 pr-2">
            <HeroArt />
          </div>

          <div className="bine-container relative z-10 w-full">
            <div className="w-full max-w-[1240px] mx-auto">
              <div className="max-w-[680px]">
                <h1 tabIndex={-1} className="bine-hero-headline m-0 outline-none">
                  <motion.span
                    className="block"
                    initial={reducedMotion ? false : { opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0, ease: [0.22, 1, 0.36, 1] }}
                  >
                    Your Pre-Trade Guard
                  </motion.span>
                  <motion.span
                    className="block"
                    initial={reducedMotion ? false : { opacity: 0, y: 18 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, delay: 0.07, ease: [0.22, 1, 0.36, 1] }}
                  >
                    for Tokenized Stocks
                  </motion.span>
                </h1>

                <motion.div
                  className="mt-7 flex flex-wrap items-center gap-3.5"
                  initial={reducedMotion ? false : { opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.14, ease: [0.22, 1, 0.36, 1] }}
                >
                  <a
                    href="/guard"
                    onClick={e => navigateApp('/guard', e)}
                    className="bine-pill-primary"
                    style={{
                      height: '52px',
                      padding: '0 36px',
                    }}
                  >
                    Check a trade
                  </a>

                  <a
                    href="/refusals"
                    onClick={e => navigateApp('/refusals', e)}
                    className="bine-pill-secondary"
                    style={{
                      height: '52px',
                      padding: '0 30px',
                    }}
                  >
                    See live refusals
                  </a>
                </motion.div>

                <motion.p
                  className="bine-body-copy mt-6 mb-0 max-w-[520px]"
                  initial={reducedMotion ? false : { opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.21, ease: [0.22, 1, 0.36, 1] }}
                >
                  Bine compares Ondo Global Markets and bStocks on BNB Chain, checks pool depth, spread, and market session, and returns BUY or REFUSE with one clear reason.
                </motion.p>
              </div>

              {/* Mobile Stacked Art */}
              <div className="md:hidden relative mt-8 -mr-6 opacity-75 pointer-events-none">
                <HeroArt />
              </div>
            </div>
          </div>
        </section>

        {/* 2. PROOF STRIP (GlassStack on click) */}
        <motion.section {...sectionReveal} className="py-6 sm:py-8">
          <div className="bine-container">
            <div className="w-full max-w-[1240px] mx-auto">
              <GlassStack items={proofItems} columns={3} ariaLabel="Bine live proof metrics" />
            </div>
          </div>
        </motion.section>

        {/* 3. HOW BINE WORKS (GlassStack on click) */}
        <motion.section {...sectionReveal} className="py-10 sm:py-12">
          <div className="bine-container">
            <div className="w-full max-w-[1240px] mx-auto space-y-5">
              <div className="flex items-baseline justify-between gap-4 flex-wrap">
                <h2 className="bine-section-heading m-0">How Bine works</h2>
                <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                  Click any step to inspect the underlying guard logic.
                </p>
              </div>

              <GlassStack items={howItWorksItems} columns={3} ariaLabel="How Bine works steps" />
            </div>
          </div>
        </motion.section>

        {/* 4. WHAT BINE REFUSES + 5. VERIFIED ON BNB CHAIN */}
        <motion.section {...sectionReveal} className="py-8 sm:py-10">
          <div className="bine-container">
            <div className="w-full max-w-[1240px] mx-auto grid grid-cols-1 lg:grid-cols-2 gap-5">
              {/* What Bine refuses */}
              <div className="bine-card p-6 sm:p-7 flex flex-col justify-between gap-5">
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <h2 className="text-lg font-semibold m-0">What Bine refuses</h2>
                    <span
                      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-semibold"
                      style={{ backgroundColor: 'var(--chip-bad-bg)', color: 'var(--bad)' }}
                    >
                      {humanizeCode(FEATURED_REFUSAL.refusal_code)}
                    </span>
                  </div>

                  <div className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {FEATURED_REFUSAL.token_symbol} · ${FEATURED_REFUSAL.amount_usd.toFixed(2)} order ·{' '}
                    {formatAbsoluteAndRelative(FEATURED_REFUSAL.recorded_at)}
                  </div>

                  <p className="text-sm sm:text-base font-medium m-0 leading-relaxed" style={{ color: 'var(--text)' }}>
                    {FEATURED_REFUSAL.message}
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <a
                    href={`/guard?ticker=${encodeURIComponent(FEATURED_REFUSAL.ticker)}&amount=${FEATURED_REFUSAL.amount_usd}`}
                    onClick={e =>
                      navigateApp(
                        `/guard?ticker=${encodeURIComponent(FEATURED_REFUSAL.ticker)}&amount=${FEATURED_REFUSAL.amount_usd}`,
                        e,
                      )
                    }
                    className="bine-pill-secondary"
                    style={{ height: '44px', padding: '0 20px', fontSize: '13px' }}
                  >
                    Test in Guard
                  </a>
                  <a
                    href="/refusals"
                    onClick={e => navigateApp('/refusals', e)}
                    className="inline-flex items-center min-h-[44px] px-2 text-sm font-medium underline"
                    style={{ color: 'var(--text)' }}
                  >
                    All 6 recorded refusals &rarr;
                  </a>
                </div>
              </div>

              {/* Verified on BNB Chain */}
              <div className="bine-card p-6 sm:p-7 flex flex-col justify-between gap-5">
                <div className="space-y-3">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <h2 className="text-lg font-semibold m-0">Verified on BNB Chain</h2>
                    <span
                      className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-mono font-semibold"
                      style={{ backgroundColor: 'var(--chip-good-bg)', color: 'var(--good)' }}
                    >
                      Decision #{LATEST_RECEIPT.decision_id} · {humanizeStatus('LIVE_SUBMITTED')}
                    </span>
                  </div>

                  <div className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                    {LATEST_RECEIPT.symbol} ({LATEST_RECEIPT.issuer}) · {formatAbsoluteAndRelative(LATEST_RECEIPT.created_at)}
                  </div>

                  <p className="text-sm sm:text-base font-medium m-0 leading-relaxed" style={{ color: 'var(--text)' }}>
                    Swapped ${LATEST_RECEIPT.amount_usd.toFixed(2)} USDT for {LATEST_RECEIPT.filled_shares.toFixed(6)}{' '}
                    {LATEST_RECEIPT.symbol} shares (quoted {LATEST_RECEIPT.quoted_shares.toFixed(6)} shares,{' '}
                    {LATEST_RECEIPT.fill_diff_bps} bps difference) at ${LATEST_RECEIPT.all_in_price_per_share_usd.toFixed(2)}/sh.{' '}
                    {LATEST_RECEIPT.execution_source}.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-3 pt-1">
                  <a
                    href={LATEST_RECEIPT.bsctrace_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bine-pill-secondary font-mono"
                    style={{ height: '44px', padding: '0 20px', fontSize: '13px' }}
                  >
                    BscTrace {shortAddress(LATEST_RECEIPT.tx_hash)} &#8599;
                  </a>
                  <a
                    href="/receipts"
                    onClick={e => navigateApp('/receipts', e)}
                    className="inline-flex items-center min-h-[44px] px-2 text-sm font-medium underline"
                    style={{ color: 'var(--text)' }}
                  >
                    View all receipts &rarr;
                  </a>
                </div>
              </div>
            </div>
          </div>
        </motion.section>

        {/* 6. CLOSING BAND */}
        <motion.section {...sectionReveal} className="py-10 sm:py-14">
          <div className="bine-container">
            <div className="w-full max-w-[1240px] mx-auto bine-card p-7 sm:p-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
              <div className="space-y-1.5 max-w-xl">
                <h2 className="text-xl sm:text-2xl font-semibold m-0">
                  Ready to check a tokenized stock trade?
                </h2>
                <p className="text-sm sm:text-base m-0" style={{ color: 'var(--text-secondary)' }}>
                  Run a live quote in the browser or plug Bine into your agent over HTTP, CLI, or MCP.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3.5 shrink-0">
                <a
                  href="/guard"
                  onClick={e => navigateApp('/guard', e)}
                  className="bine-pill-primary"
                  style={{ height: '48px', padding: '0 30px' }}
                >
                  Check a trade
                </a>
                <a
                  href="/integrate"
                  onClick={e => navigateApp('/integrate', e)}
                  className="bine-pill-secondary"
                  style={{ height: '48px', padding: '0 26px' }}
                >
                  Read the developer docs
                </a>
              </div>
            </div>
          </div>
        </motion.section>
      </main>

      <Footer />
    </div>
  )
}
