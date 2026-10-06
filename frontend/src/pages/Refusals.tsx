import { useQueries, useQuery } from '@tanstack/react-query'
import { fetchQuote, fetchTickers } from '../api'
import { Footer, TopHeader, navigateApp } from '../components/shared'

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
      label: 'AAPL at $2.00, Ondo $5 minimum order',
      ticker: 'AAPL',
      amount: 2,
    },
    {
      key: 'slip',
      label: 'SPYon at $250.00, Thin PMM/DEX pool cliff',
      ticker: 'SPYon',
      amount: 250,
    },
    {
      key: 'enlv',
      label: 'ENLV at $5.50, Quarantined sub-$1 outlier',
      ticker: 'ENLV',
      amount: 5.5,
    },
    {
      key: 'ratio',
      label: ratioEx
        ? `${ratioEx.ticker} (${ratioEx.symbol}) at $5.50, Share ratio ${ratioEx.token_to_share_ratio}x (ratios outside 0.25-5.00x are not supported by this tool)`
        : 'Share ratio outside 0.25-5.00x (not supported by this tool)',
      ticker: ratioEx?.ticker || 'KLAC',
      amount: 5.5,
    },
    {
      key: 'closed',
      label: closedEx
        ? `${closedEx.ticker} (${closedEx.symbol}) at $5.50, Session ${closedEx.reason_code} (${closedEx.market_status})`
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
      <main className="flex-1 w-full py-10 sm:py-14">
        <div className="bine-container space-y-8">
          <div className="max-w-3xl space-y-2">
            <h1 className="bine-section-heading m-0">Live Refusals</h1>
            <p className="bine-body m-0" style={{ color: 'var(--text-secondary)' }}>
              Every card below is fetched live from <code className="font-mono text-xs">GET /api/quote</code> and the BSC RWA catalog.
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
                  className="bine-card p-5 sm:p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
                >
                  <div className="space-y-2 min-w-0">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <span
                        className="inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-semibold"
                        style={{
                          backgroundColor: 'var(--chip-bad-bg)',
                          color: 'var(--bad)',
                        }}
                      >
                        {code}
                      </span>
                      <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                        {item.label}
                      </span>
                    </div>
                    <p className="text-sm sm:text-base font-medium m-0 leading-relaxed">{msg}</p>
                  </div>

                  <a
                    href={runHref}
                    onClick={e => navigateApp(runHref, e)}
                    className="bine-pill-secondary shrink-0 self-start sm:self-center"
                    style={{
                      height: '38px',
                      padding: '0 16px',
                      fontSize: '13px',
                    }}
                  >
                    Run it →
                  </a>
                </section>
              )
            })}
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}

