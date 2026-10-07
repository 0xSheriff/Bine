import { useRef, useState } from 'react'
import { fetchQuote } from '../api'
import { Footer, TopHeader } from '../components/shared'
import { humanizeField } from '../lib/humanize'
import type { QuoteVerdictResponse } from '../types'

const DEFAULT_API_URL = 'http://localhost:8000'

interface IntegrationTab {
  id: 'http' | 'cli' | 'mcp' | 'skill'
  label: string
  title: string
  description: string
  code: string
}

const INTEGRATION_TABS: IntegrationTab[] = [
  {
    id: 'http',
    label: 'HTTP',
    title: 'GET /api/quote (frozen schema version 1)',
    description:
      'Call /api/quote before any tokenized stock purchase. Check the verdict ("BUY" or "REFUSE") and token contract address before building swap calldata.',
    code: `curl -s "${DEFAULT_API_URL}/api/quote?ticker=NVDA&amount_usd=5.50" | jq .`,
  },
  {
    id: 'cli',
    label: 'CLI',
    title: 'bine CLI (human & shell script entry point)',
    description:
      'Install the backend package in editable mode and run bine check for a pre-trade verdict or bine buy to run the Transaction API dry-run pipeline.',
    code: `pip install -e backend\nbine check NVDA 5.50\nbine check SPYon 250 --json\nbine buy NVDA 2.00`,
  },
  {
    id: 'mcp',
    label: 'MCP',
    title: 'Model Context Protocol server (stdio)',
    description:
      'Expose the Bine check and buy tools to Claude Desktop, Cursor, or any Model Context Protocol host.',
    code: JSON.stringify(
      {
        mcpServers: {
          'bine-pre-trade-guard': {
            command: 'bine-mcp',
            env: {
              BINE_API_URL: DEFAULT_API_URL,
            },
          },
        },
      },
      null,
      2,
    ),
  },
  {
    id: 'skill',
    label: 'Agent skill',
    title: 'Binance Agentic Wallet skill (SKILL.md)',
    description:
      'Install the skill file so autonomous agents using @binance/agentic-wallet (baw) always run bine check and verify the token address before baw market-order swap.',
    code: `mkdir -p ~/.claude/skills/bine-pre-trade-guard && cp skills/bine-pre-trade-guard/SKILL.md ~/.claude/skills/bine-pre-trade-guard/SKILL.md`,
  },
]

export const RESPONSE_FIELDS = [
  {
    key: 'schema_version',
    label: humanizeField('schema_version'),
    type: '"1"',
    meaning: 'Frozen contract version string. Always "1".',
    sample: '"1"',
  },
  {
    key: 'ticker',
    label: humanizeField('ticker'),
    type: 'string',
    meaning: 'Normalized underlying equity ticker (for example "NVDA" or "SPY").',
    sample: '"NVDA"',
  },
  {
    key: 'amount_usd',
    label: humanizeField('amount_usd'),
    type: 'number',
    meaning: 'Requested order size in USD (USDT equivalent on BNB Chain).',
    sample: '5.5',
  },
  {
    key: 'quoted_at',
    label: humanizeField('quoted_at'),
    type: 'string (ISO-8601 UTC)',
    meaning: 'UTC timestamp when the live quote was evaluated.',
    sample: '"2026-10-05T15:04:08Z"',
  },
  {
    key: 'verdict',
    label: humanizeField('verdict'),
    type: '"BUY" | "REFUSE"',
    meaning: 'Deterministic guard decision. Only proceed when verdict is "BUY".',
    sample: '"BUY"',
  },
  {
    key: 'token',
    label: humanizeField('token'),
    type: '{ symbol, address, issuer } | null',
    meaning: 'Winning BSC token contract to buy, or null when verdict is "REFUSE".',
    sample: '{"symbol":"NVDAB","address":"0xA923...2246","issuer":"bstock"}',
  },
  {
    key: 'shares',
    label: humanizeField('shares'),
    type: 'number | null',
    meaning: 'Expected share-adjusted equity units received after applying the token-to-share ratio.',
    sample: '0.030956',
  },
  {
    key: 'all_in_price_per_share',
    label: humanizeField('all_in_price_per_share'),
    type: 'number | null',
    meaning: 'All-in effective execution price per share in USD including fees and gas.',
    sample: '177.67',
  },
  {
    key: 'reference_price_per_share',
    label: humanizeField('reference_price_per_share'),
    type: 'number | null',
    meaning: 'Catalog per-share reference price in USD.',
    sample: '177.82',
  },
  {
    key: 'spread_pct',
    label: humanizeField('spread_pct'),
    type: 'number | null',
    meaning: 'All-in percentage spread versus the per-share reference price.',
    sample: '-0.08',
  },
  {
    key: 'refusal',
    label: humanizeField('refusal'),
    type: '{ code, message } | null',
    meaning: 'Refusal rule and one-sentence explanation when verdict is "REFUSE".',
    sample: 'null',
  },
  {
    key: 'alternative',
    label: humanizeField('alternative'),
    type: '{ symbol, issuer, eligible, note } | null',
    meaning: 'Comparison note for the second issuer (including 5 bps tiebreak status).',
    sample: '{"symbol":"NVDAon","issuer":"ondo","eligible":true,"note":"NVDAB selected via 5 bps tiebreak"}',
  },
  {
    key: 'market',
    label: humanizeField('market'),
    type: '{ status, open }',
    meaning: 'Current RWA session state ("regular", "premarket", "postmarket", "overnight", "offhours", or "paused").',
    sample: '{"status":"regular","open":true}',
  },
]

const ERROR_ROWS = [
  {
    status: '401 / 403',
    meaning: 'Missing or invalid X-Bine-Admin-Token header on POST /api/execute when live execution is requested.',
    action: 'Keep live execution disabled for dry-run simulations, or pass the configured X-Bine-Admin-Token header on your own local instance.',
  },
  {
    status: '429',
    meaning: 'Per-IP sliding-window rate limit exceeded (60 req/min on /api/quote, 20 req/min on /api/execute).',
    action: 'Wait for the window to reset and reuse quotes within the 15-second freshness window.',
  },
  {
    status: '503',
    meaning: 'Binance API keys missing or rejected, or upstream web3.binance.com is unreachable.',
    action: 'Configure your Binance API credentials in .env (and enable the local DNS fallback flag if DNS times out) and restart uvicorn.',
  },
]

export default function Integrate() {
  const [activeIndex, setActiveIndex] = useState<number>(0)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [tryLoading, setTryLoading] = useState<boolean>(false)
  const [tryResult, setTryResult] = useState<QuoteVerdictResponse | null>(null)
  const [tryError, setTryError] = useState<string | null>(null)

  const tabRefs = useRef<Array<HTMLButtonElement | null>>([])

  const activeTab = INTEGRATION_TABS[activeIndex]

  const handleCopy = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(id)
      window.setTimeout(() => setCopiedId(prev => (prev === id ? null : prev)), 1500)
    } catch {
      // ignore clipboard errors
    }
  }

  const handleTabKeyDown = (e: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    let nextIdx: number | null = null
    if (e.key === 'ArrowRight') {
      nextIdx = (index + 1) % INTEGRATION_TABS.length
    } else if (e.key === 'ArrowLeft') {
      nextIdx = (index - 1 + INTEGRATION_TABS.length) % INTEGRATION_TABS.length
    } else if (e.key === 'Home') {
      nextIdx = 0
    } else if (e.key === 'End') {
      nextIdx = INTEGRATION_TABS.length - 1
    }

    if (nextIdx !== null) {
      e.preventDefault()
      setActiveIndex(nextIdx)
      tabRefs.current[nextIdx]?.focus()
    }
  }

  const handleTryHttp = async () => {
    setTryLoading(true)
    setTryError(null)
    try {
      const res = await fetchQuote('NVDA', 5.5, false)
      setTryResult(res)
    } catch (err) {
      setTryError(err instanceof Error ? err.message : 'Request failed.')
    } finally {
      setTryLoading(false)
    }
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
            {/* Two-sentence intro */}
            <div className="max-w-3xl space-y-2">
              <h1 tabIndex={-1} className="bine-section-heading m-0 outline-none">
                Use Bine from your agent
              </h1>
              <p className="bine-body m-0" style={{ color: 'var(--text-secondary)' }}>
                Bine exposes one frozen pre-trade decision contract across HTTP, CLI, MCP, and the Binance Agentic Wallet skill. Query the guard before every tokenized stock order and only execute when the verdict is BUY.
              </p>
            </div>

            {/* Live region for copy announcement */}
            <div className="sr-only" aria-live="polite">
              {copiedId ? `Copied ${copiedId} snippet to clipboard` : ''}
            </div>

            {/* 1. WAI-ARIA APG Tabs */}
            <section aria-label="Integration methods" className="space-y-4">
              <div
                role="tablist"
                aria-label="Integration surface tabs"
                className="flex flex-wrap items-center gap-2"
              >
                {INTEGRATION_TABS.map((tab, idx) => {
                  const isSelected = idx === activeIndex
                  return (
                    <button
                      key={tab.id}
                      ref={el => {
                        tabRefs.current[idx] = el
                      }}
                      id={`tab-${tab.id}`}
                      role="tab"
                      type="button"
                      aria-selected={isSelected}
                      aria-controls={`panel-${tab.id}`}
                      tabIndex={isSelected ? 0 : -1}
                      onClick={() => setActiveIndex(idx)}
                      onKeyDown={e => handleTabKeyDown(e, idx)}
                      className="px-4 py-2.5 rounded-full text-sm font-medium cursor-pointer transition-colors min-h-[44px]"
                      style={{
                        backgroundColor: isSelected ? 'var(--accent)' : 'var(--surface)',
                        color: isSelected ? 'var(--accent-fg)' : 'var(--text)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      {tab.label}
                    </button>
                  )
                })}
              </div>

              <div
                id={`panel-${activeTab.id}`}
                role="tabpanel"
                aria-labelledby={`tab-${activeTab.id}`}
                tabIndex={0}
                className="bine-card p-6 sm:p-7 space-y-4 outline-none"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="space-y-1">
                    <h2 className="text-base font-semibold m-0">{activeTab.title}</h2>
                    <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
                      {activeTab.description}
                    </p>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    {activeTab.id === 'http' && (
                      <button
                        type="button"
                        onClick={handleTryHttp}
                        disabled={tryLoading}
                        className="bine-pill-primary cursor-pointer disabled:opacity-60 min-h-[44px]"
                        style={{
                          height: '44px',
                          padding: '0 20px',
                          fontSize: '13px',
                        }}
                      >
                        {tryLoading ? 'Running...' : 'Try it'}
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => handleCopy(activeTab.id, activeTab.code)}
                      className="bine-pill-secondary cursor-pointer min-h-[44px]"
                      style={{
                        height: '44px',
                        padding: '0 18px',
                        fontSize: '13px',
                        color: copiedId === activeTab.id ? 'var(--good)' : 'var(--text)',
                      }}
                    >
                      {copiedId === activeTab.id ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                </div>

                <pre
                  data-raw-code
                  className="p-4 rounded-xl text-xs font-mono overflow-x-auto m-0"
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    border: '1px solid var(--border)',
                    color: 'var(--text)',
                  }}
                >
                  <code>{activeTab.code}</code>
                </pre>

                {activeTab.id === 'http' && (tryResult || tryError) && (
                  <div className="space-y-2 pt-2" aria-live="polite">
                    <div className="flex items-center justify-between text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                      <span>Live response for NVDA ($5.50 USD)</span>
                      {tryResult && <span>verdict: {tryResult.verdict}</span>}
                    </div>
                    <pre
                      data-raw-code
                      className="p-4 rounded-xl text-xs font-mono overflow-x-auto m-0 max-h-[340px]"
                      style={{
                        backgroundColor: 'var(--surface-subtle)',
                        border: '1px solid var(--border)',
                        color: tryError ? 'var(--bad)' : 'var(--text)',
                      }}
                    >
                      <code>
                        {tryError ? tryError : JSON.stringify(tryResult, null, 2)}
                      </code>
                    </pre>
                  </div>
                )}
              </div>
            </section>

            {/* 2. Frozen Response Fields Table */}
            <section aria-labelledby="response-fields-heading" className="space-y-4">
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <h2 id="response-fields-heading" className="text-lg font-semibold m-0">
                  Response fields (GET /api/quote)
                </h2>
                <span className="text-xs font-mono" style={{ color: 'var(--text-secondary)' }}>
                  13 top-level frozen fields
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
                        <th className="py-3 px-4 font-medium">Field</th>
                        <th className="py-3 px-4 font-medium">Type</th>
                        <th className="py-3 px-4 font-medium">Meaning</th>
                      </tr>
                    </thead>
                    <tbody>
                      {RESPONSE_FIELDS.map(row => (
                        <tr key={row.key} style={{ borderBottom: '1px solid var(--hairline)' }}>
                          <td className="py-3 px-4 text-xs font-semibold whitespace-nowrap">
                            {row.label}
                          </td>
                          <td className="py-3 px-4 font-mono text-xs whitespace-nowrap" style={{ color: 'var(--text-secondary)' }}>
                            {row.type}
                          </td>
                          <td className="py-3 px-4" style={{ color: 'var(--text-secondary)' }}>
                            {row.meaning}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            {/* 3. HTTP Errors Table */}
            <section aria-labelledby="http-errors-heading" className="space-y-4">
              <h2 id="http-errors-heading" className="text-lg font-semibold m-0">
                Errors
              </h2>

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
                        <th className="py-3 px-4 font-medium">HTTP status</th>
                        <th className="py-3 px-4 font-medium">Meaning</th>
                        <th className="py-3 px-4 font-medium">What to do</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ERROR_ROWS.map(row => (
                        <tr key={row.status} style={{ borderBottom: '1px solid var(--hairline)' }}>
                          <td className="py-3 px-4 font-mono text-xs font-semibold whitespace-nowrap">
                            {row.status}
                          </td>
                          <td className="py-3 px-4" style={{ color: 'var(--text-secondary)' }}>
                            {row.meaning}
                          </td>
                          <td className="py-3 px-4" style={{ color: 'var(--text-secondary)' }}>
                            {row.action}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </section>

            {/* 4. Contract & Safety Notes */}
            <section aria-labelledby="contract-notes-heading" className="bine-card p-6 space-y-3">
              <h2 id="contract-notes-heading" className="text-base font-semibold m-0">
                Contract &amp; safety notes
              </h2>
              <ul className="m-0 pl-5 space-y-1.5 text-sm" style={{ color: 'var(--text-secondary)' }}>
                <li>
                  <strong style={{ color: 'var(--text)' }}>Frozen schema:</strong>{' '}
                  Schema version 1 is frozen. Field names and refusal codes do not change across releases.
                </li>
                <li>
                  <strong style={{ color: 'var(--text)' }}>Scope:</strong> Spot tokenized stocks on BNB Smart Chain (<code className="font-mono text-xs">chainId = 56</code>) across Ondo Global Markets and bStocks.
                </li>
                <li>
                  <strong style={{ color: 'var(--text)' }}>Hard execution caps:</strong> Dry-run via the Binance Transaction API runs before any swap; live swaps require live mode enabled on your local server and stay capped at <code className="font-mono text-xs">$6.00</code> per trade and <code className="font-mono text-xs">$10.00</code> per day.
                </li>
              </ul>
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
