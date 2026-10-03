import { useQueries, useQuery } from '@tanstack/react-query'
import { fetchQuote, fetchTickers } from '../api'
import { TopHeader } from '../components/shared'

export default function Refusals() {
  const { data: catalog } = useQuery({
    queryKey: ['tickers'],
    queryFn: fetchTickers,
    staleTime: 60_000,
  })

  const ratioEx = catalog?.catalog_examples?.share_ratio
  const closedEx = catalog?.catalog_examples?.session_closed

  const specs = [
    {
      key: 'min',
      label: 'AAPL at $2.00 — Ondo $5 minimum order',
      ticker: 'AAPL',
      amount: 2,
    },
    {
      key: 'slip',
      label: 'SPYon at $250.00 — Thin PMM/DEX pool cliff',
      ticker: 'SPYon',
      amount: 250,
    },
    {
      key: 'enlv',
      label: 'ENLV at $5.50 — Quarantined sub-$1 outlier',
      ticker: 'ENLV',
      amount: 5.5,
    },
    {
      key: 'ratio',
      label: ratioEx
        ? `${ratioEx.ticker} (${ratioEx.symbol}) at $5.50 — Catalog share-ratio trap (${ratioEx.token_to_share_ratio}x shares/token)`
        : 'Catalog share-ratio trap',
      ticker: ratioEx?.ticker || 'KLAC',
      amount: 5.5,
    },
    {
      key: 'closed',
      label: closedEx
        ? `${closedEx.ticker} (${closedEx.symbol}) at $5.50 — Session ${closedEx.reason_code} (${closedEx.market_status})`
        : 'Catalog session-unsupported token',
      ticker: closedEx?.ticker || 'ICHR',
      amount: 5.5,
    },
  ]

  const quoteResults = useQueries({
    queries: specs.map(s => ({
      queryKey: ['quote', s.ticker, s.amount, false],
      queryFn: () => fetchQuote(s.ticker, s.amount, false),
      enabled: Boolean(catalog),
      staleTime: 30_000,
    })),
  })

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--bg)', color: 'var(--text)' }}>
      <TopHeader />
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10 space-y-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Live Refusals</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            Every card below is fetched live from <code>GET /api/quote</code> and the BSC RWA catalog.
          </p>
        </div>

        <div className="space-y-3">
          {specs.map((item, idx) => {
            const q = quoteResults[idx]?.data
            const loading = !catalog || quoteResults[idx]?.isLoading
            const code = q?.refusal?.code || (q?.verdict === 'BUY' ? 'BUY' : 'loading')
            const msg = q?.refusal?.message || (loading ? 'Querying live API…' : 'No refusal returned.')
            const runHref = `/?ticker=${encodeURIComponent(item.ticker)}&amount=${encodeURIComponent(String(item.amount))}`

            return (
              <section
                key={item.key}
                className="rounded-lg p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
              >
                <div className="space-y-1.5 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="inline-block px-2 py-0.5 rounded text-xs font-mono font-semibold"
                      style={{
                        backgroundColor: 'var(--chip-bad-bg)',
                        color: 'var(--bad)',
                      }}
                    >
                      {code}
                    </span>
                    <span className="text-xs font-medium" style={{ color: 'var(--muted)' }}>
                      {item.label}
                    </span>
                  </div>
                  <p className="text-sm sm:text-base font-medium m-0">{msg}</p>
                </div>

                <a
                  href={runHref}
                  className="px-3 py-1.5 rounded border text-xs font-semibold no-underline shrink-0 self-start sm:self-center"
                  style={{
                    backgroundColor: 'var(--bg)',
                    borderColor: 'var(--border)',
                    color: 'var(--text)',
                  }}
                >
                  Run it →
                </a>
              </section>
            )
          })}
        </div>
      </main>
    </div>
  )
}
