import { useQuery } from '@tanstack/react-query'
import { fetchDecisions } from '../api'
import { Footer, TopHeader, formatSecondsAgo, shortAddress } from '../components/shared'

export default function Receipts() {
  const { data, isLoading } = useQuery({
    queryKey: ['decisions-live'],
    queryFn: () => fetchDecisions(50, true),
    refetchInterval: 15_000,
  })

  const liveRows = (data?.decisions ?? []).filter(d => Boolean(d.tx_hash))

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: 'var(--bg)', color: 'var(--text)' }}>
      <TopHeader />
      <main className="flex-1 w-full py-10 sm:py-14">
        <div className="bine-container space-y-8">
          <div className="max-w-3xl space-y-2">
            <h1 className="bine-section-heading m-0">Executed Trade Receipts</h1>
            <p className="bine-body m-0" style={{ color: 'var(--text-secondary)' }}>
              On-chain BSC trades executed with a verified <code className="font-mono text-xs">tx_hash</code>. Dry-run simulations are excluded.
            </p>
          </div>

          <section className="bine-card p-6 sm:p-8">
            {isLoading ? (
              <div className="space-y-3 py-2">
                <div className="bine-skeleton h-10 w-full" />
                <div className="bine-skeleton h-10 w-full" />
              </div>
            ) : liveRows.length === 0 ? (
              <p className="text-sm font-medium m-0" style={{ color: 'var(--text-secondary)' }}>
                No live trades yet.
              </p>
            ) : (
              <div>
                {liveRows.map((row, idx) => {
                  const traceUrl = row.bsctrace_url || `https://bsctrace.com/tx/${row.tx_hash}`
                  return (
                    <div
                      key={row.id}
                      className="py-4 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                      style={{
                        borderBottom: idx < liveRows.length - 1 ? '1px solid var(--hairline)' : 'none',
                      }}
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2.5 text-sm font-medium">
                          <span className="font-semibold">{row.ticker}</span>
                          <span>${row.amount_usd.toFixed(2)}</span>
                          {row.recommended_symbol && (
                            <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
                              ({row.recommended_symbol})
                            </span>
                          )}
                        </div>
                        <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                          Decision #{row.id} · {formatSecondsAgo(row.created_at)}
                        </div>
                      </div>

                      <a
                        href={traceUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bine-pill-secondary gap-1.5 shrink-0 self-start sm:self-center"
                        style={{
                          height: '36px',
                          padding: '0 14px',
                          fontSize: '12px',
                        }}
                      >
                        <span>BscTrace:</span>
                        <span className="font-mono">{shortAddress(row.tx_hash)}</span>
                        <span>↗</span>
                      </a>
                    </div>
                  )
                })}
              </div>
            )}
          </section>
        </div>
      </main>
      <Footer />
    </div>
  )
}

