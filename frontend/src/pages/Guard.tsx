import { Footer, LiveModeChip, TopHeader } from '../components/shared'

export default function Guard() {
  return (
    <div
      className="min-h-screen flex flex-col overflow-x-hidden"
      style={{
        backgroundColor: 'var(--bg-page)',
        color: 'var(--text)',
      }}
    >
      <TopHeader />
      <main className="flex-1 py-10 sm:py-14">
        <div className="bine-container">
          <div className="w-full max-w-[1120px] mx-auto space-y-6">
            <h1
              tabIndex={-1}
              className="m-0 font-semibold tracking-tight"
              style={{
                fontSize: 'clamp(28px, 3.2vw, 40px)',
                letterSpacing: '-0.03em',
                color: 'var(--text)',
              }}
            >
              Check a trade
            </h1>
            <LiveModeChip />
          </div>
        </div>
      </main>
      <Footer />
    </div>
  )
}
