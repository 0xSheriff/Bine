import { useState } from 'react'
import { TopHeader } from '../components/shared'

const HOSTED_URL = 'https://bine-guard.fly.dev'

const SNIPPETS = [
  {
    id: 'curl',
    title: '1. Hosted HTTP API (curl — no keys needed)',
    code: `curl -s "${HOSTED_URL}/api/quote?ticker=NVDA&amount_usd=5.50" | jq .`,
  },
  {
    id: 'cli',
    title: '2. CLI (bine check — defaults to hosted API when no keys are set)',
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
              BINE_API_URL: HOSTED_URL,
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
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10 space-y-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Integrate Bine</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            Copy-paste integration for HTTP clients, shell scripts, MCP agents, and Binance Agentic Wallet skills.
          </p>
        </div>

        <div className="space-y-4">
          {SNIPPETS.map(item => (
            <section
              key={item.id}
              className="rounded-lg p-4 sm:p-5 space-y-2.5"
              style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
            >
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold">{item.title}</h2>
                <button
                  type="button"
                  onClick={() => handleCopy(item.id, item.code)}
                  className="px-2.5 py-1 rounded border text-xs font-medium cursor-pointer shrink-0"
                  style={{
                    backgroundColor: 'var(--bg)',
                    borderColor: 'var(--border)',
                    color: copiedId === item.id ? 'var(--good)' : 'var(--text)',
                  }}
                >
                  {copiedId === item.id ? 'Copied' : 'Copy'}
                </button>
              </div>
              <pre
                className="p-3 rounded text-xs font-mono overflow-x-auto m-0"
                style={{ backgroundColor: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)' }}
              >
                <code>{item.code}</code>
              </pre>
            </section>
          ))}
        </div>
      </main>
    </div>
  )
}
