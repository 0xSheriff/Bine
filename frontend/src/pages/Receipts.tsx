import { useQuery } from '@tanstack/react-query'
import { fetchDecisions } from '../api'
import { TopHeader, formatSecondsAgo, shortAddress } from '../components/shared'

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
      <main className="flex-1 w-full max-w-3xl mx-auto px-4 sm:px-6 py-8 sm:py-10 space-y-5">
        <div>
          <h1 className="text-xl sm:text-2xl font-semibold tracking-tight">Executed Trade Receipts</h1>
          <p className="text-sm mt-1" style={{ color: 'var(--muted)' }}>
            On-chain BSC trades executed with a verified <code>tx_hash</code>. Dry-run simulations are excluded.
          </p>
        </div>

        <section
          className="rounded-lg p-5 sm:p-6"
          style={{ backgroundColor: 'var(--surface)', border: '1px solid var(--border)' }}
        >
          {isLoading ? (
            <p className="text-sm m-0" style={{ color: 'var(--muted)' }}>
              Loading executed trades…
            </p>
          ) : liveRows.length === 0 ? (
            <p className="text-sm font-medium m-0" style={{ color: 'var(--muted)' }}>
              No live trades yet.
            </p>
          ) : (
            <div className="divide-y" style={{ borderColor: 'var(--border)' }}>
              {liveRows.map(row => {
                const traceUrl = row.bsctrace_url || `https://bsctrace.com/tx/${row.tx_hash}`
                return (
                  <div
                    key={row.id}
                    className="py-3 first:pt-0 last:pb-0 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                  >
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2 text-sm font-medium">
                        <span className="font-mono font-semibold">{row.ticker}</span>
                        <span>${row.amount_usd.toFixed(2)}</span>
                        {row.recommended_symbol && (
                          <span className="text-xs font-mono" style={{ color: 'var(--muted)' }}>
                            ({row.recommended_symbol})
                          </span>
                        )}
                      </div>
                      <div className="text-xs" style={{ color: 'var(--muted)' }}>
                        Decision #{row.id} · {formatSecondsAgo(row.created_at)}
                      </div>
                    </div>

                    <a
                      href={traceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-mono underline shrink-0"
                      style={{ color: 'var(--accent)' }}
                    >
                      BscTrace: {shortAddress(row.tx_hash)} ↗
                    </a>
                  </div>
                )
              })}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
