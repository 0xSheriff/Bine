import { useState } from 'react'
import { Footer, TopHeader } from '../components/shared'

const DEFAULT_API_URL = 'http://localhost:8000'

const SNIPPETS = [
  {
    id: 'curl',
    title: '1. HTTP API (curl)',
    code: `curl -s "${DEFAULT_API_URL}/api/quote?ticker=NVDA&amount_usd=5.50" | jq .`,
  },
  {
    id: 'cli',
    title: '2. CLI (bine check, defaults to BINE_API_URL=http://localhost:8000)',
    code: `pip install -e backend\nbine check NVDA 5.50\nbine check SPYon 250 --json`,
  },
  {
    id: 'mcp',
    title: '3. MCP Client Configuration (Claude Desktop / Cursor / Windsurf)',
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
    title: '4. Agentic Wallet Skill Install',
    code: `mkdir -p ~/.claude/skills/bine-pre-trade-guard && cp skills/bine-pre-trade-guard/SKILL.md ~/.claude/skills/bine-pre-trade-guard/SKILL.md`,
  },
  {
    id: 'schema',
    title: '5. Frozen Response Schema (schema_version: "1")',
    code: JSON.stringify(
      {
        schema_version: '1',
        ticker: 'NVDA',
        amount_usd: 5.5,
        quoted_at: '2026-10-03T00:00:00Z',
        verdict: 'BUY | REFUSE',
        token: { symbol: 'NVDAB', address: '0x02fca66c1d1afb4e2a7884261eb00f63598a7436', issuer: 'bstock' },
        shares: 0.0235,
        all_in_price_per_share: 234.94,
        reference_price_per_share: 234.21,
        spread_pct: 0.31,
        refusal: { code: 'below_issuer_minimum | slippage_too_high | quality_unreliable | market_closed | ...', message: 'Plain-English explanation' },
        alternative: { symbol: 'NVDAon', issuer: 'ondo', eligible: true, note: 'Either works (within 5 bps).' },
        market: { status: 'postmarket', open: true },
      },
      null,
      2,
    ),
  },
]

export default function Integrate() {
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const handleCopy = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(id)
      window.setTimeout(() => setCopiedId(prev => (prev === id ? null : prev)), 1500)
    } catch {
      // ignore clipboard errors
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--bg)', color: 'var(--text)' }}>
      <TopHeader />
      <main className="flex-1 w-full py-10 sm:py-14">
        <div className="bine-container space-y-8">
          <div className="max-w-3xl space-y-2">
            <h1 className="bine-section-heading m-0">Integrate Bine</h1>
            <p className="bine-body m-0" style={{ color: 'var(--text-secondary)' }}>
              Copy-paste integration for HTTP clients, shell scripts, MCP agents, and Binance Agentic Wallet skills.
            </p>
          </div>

          <div className="space-y-4">
            {SNIPPETS.map(item => (
              <section
                key={item.id}
                className="bine-card p-5 sm:p-7 space-y-3.5"
              >
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-base font-semibold m-0">{item.title}</h2>
                  <button
                    type="button"
                    onClick={() => handleCopy(item.id, item.code)}
                    className="bine-pill-secondary cursor-pointer shrink-0"
                    style={{
                      height: '34px',
                      padding: '0 14px',
                      fontSize: '12px',
                      color: copiedId === item.id ? 'var(--good)' : 'var(--text)',
                    }}
                  >
                    {copiedId === item.id ? 'Copied' : 'Copy'}
                  </button>
                </div>
                <pre
                  className="p-4 rounded-2xl text-xs font-mono overflow-x-auto m-0"
                  style={{
                    backgroundColor: 'var(--bg-canvas)',
                    border: '1px solid var(--hairline)',
                    color: 'var(--text)',
                  }}
                >
                  <code>{item.code}</code>
                </pre>
              </section>
            ))}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}

