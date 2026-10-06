/** Shared formatting helpers, TopHeader, Footer, and inlined Simple Icons for Bine. */

import { useEffect, useState } from 'react'
import { BineWordmarkLockup } from './BineLogo'

export function parseUtcDate(iso: string): Date {
  const normalized = /[Z+-]\d*:*\d*$/.test(iso) ? iso : `${iso}Z`
  return new Date(normalized)
}

export function formatSecondsAgo(iso: string | null | undefined): string {
  if (!iso) return 'just now'
  const sec = Math.max(0, Math.round((Date.now() - parseUtcDate(iso).getTime()) / 1000))
  if (sec < 60) return `${sec}s ago`
  const min = Math.round(sec / 60)
  return `${min}m ago`
}

export function formatCompactUsd(val: number | null | undefined): string {
  if (val === null || val === undefined) return 'N/A'
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(2)}B`
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`
  return `$${val.toFixed(2)}`
}

export function shortAddress(addr: string | null | undefined): string {
  if (!addr) return 'N/A'
  if (addr.length <= 12) return addr
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`
}

/** Inlined from simple-icons/icons/github.svg */
export function GitHubIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      role="img"
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  )
}

/** Inlined from simple-icons/icons/x.svg */
export function XIcon({ size = 22 }: { size?: number }) {
  return (
    <svg
      role="img"
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d="M14.234 10.162 22.977 0h-2.072l-7.591 8.824L7.251 0H.258l9.168 13.343L.258 24H2.33l8.016-9.318L16.749 24h6.993zm-2.837 3.299-.929-1.329L3.076 1.56h3.182l5.965 8.532.929 1.329 7.754 11.09h-3.182z" />
    </svg>
  )
}

export function navigateApp(href: string, e?: React.MouseEvent<HTMLAnchorElement>) {
  if (typeof window === 'undefined') return
  if (e && (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0)) return

  const url = new URL(href, window.location.origin)
  const samePath = url.pathname === window.location.pathname && url.search === window.location.search

  if (e) e.preventDefault()

  if (!samePath) {
    window.history.pushState({}, '', `${url.pathname}${url.search}${url.hash}`)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }

  if (url.hash) {
    const id = url.hash.slice(1)
    window.setTimeout(() => {
      const target = document.getElementById(id)
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, samePath ? 0 : 60)
  } else if (!samePath) {
    window.scrollTo({ top: 0, behavior: 'auto' })
  }
}

export function TopHeader() {
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    if (typeof window !== 'undefined') {
      const qTheme = new URLSearchParams(window.location.search).get('theme')
      if (qTheme === 'dark' || qTheme === 'light') return qTheme
      const current = document.documentElement.getAttribute('data-theme')
      if (current === 'dark' || current === 'light') return current
    }
    return 'light'
  })

  const [scrolled, setScrolled] = useState<boolean>(false)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.style.colorScheme = theme
    try {
      localStorage.setItem('bine-theme', theme)
    } catch {
      // ignore storage errors
    }
  }, [theme])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const onScroll = () => {
      setScrolled((window.scrollY || 0) > 8)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const pathname = typeof window !== 'undefined' ? window.location.pathname : '/'
  const navItems = [
    { href: '/#guard', matchPath: '/', label: 'Guard' },
    { href: '/integrate', matchPath: '/integrate', label: 'Integrate' },
    { href: '/refusals', matchPath: '/refusals', label: 'Refusals' },
    { href: '/receipts', matchPath: '/receipts', label: 'Receipts' },
  ]

  return (
    <header
      className="sticky top-0 z-40 min-h-[80px] flex items-center transition-colors duration-200"
      style={{
        backgroundColor: scrolled ? 'var(--nav-blur-bg)' : 'transparent',
        backdropFilter: scrolled ? 'blur(12px)' : 'none',
        WebkitBackdropFilter: scrolled ? 'blur(12px)' : 'none',
        borderBottom: scrolled ? '1px solid var(--hairline)' : '1px solid transparent',
      }}
    >
      <div className="bine-container py-2.5 sm:py-0">
        <div className="w-full max-w-[1240px] mx-auto flex flex-wrap sm:flex-nowrap items-center justify-between gap-y-2 gap-x-4">
          <div className="flex items-center gap-4 md:gap-9 min-w-0">
            <a
              href="/"
              onClick={e => navigateApp('/', e)}
              className="no-underline shrink-0 inline-flex items-center rounded-lg"
              aria-label="Bine home"
            >
              <BineWordmarkLockup tileSize={36} />
            </a>

            <nav
              className="hidden sm:flex items-center gap-4 md:gap-7"
              aria-label="Main navigation"
            >
              {navItems.map(item => {
                const active = pathname === item.matchPath
                return (
                  <a
                    key={item.href}
                    href={item.href}
                    onClick={e => navigateApp(item.href, e)}
                    aria-current={active ? 'page' : undefined}
                    className="no-underline py-1 rounded-md shrink-0 transition-colors"
                    style={{
                      fontSize: '14px',
                      fontWeight: active ? 600 : 500,
                      color: active ? 'var(--text)' : 'var(--text-secondary)',
                    }}
                  >
                    {item.label}
                  </a>
                )
              })}
            </nav>
          </div>

          <div className="flex items-center gap-2.5 sm:gap-3 shrink-0">
            <button
              type="button"
              onClick={() => setTheme(prev => (prev === 'light' ? 'dark' : 'light'))}
              aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              className="w-10 h-10 inline-flex items-center justify-center rounded-full cursor-pointer shrink-0 transition-transform hover:-translate-y-0.5 active:scale-95"
              style={{
                backgroundColor: 'var(--pill-secondary-bg)',
                color: 'var(--text)',
                boxShadow: 'var(--pill-secondary-shadow)',
                border: 'none',
              }}
            >
              {theme === 'dark' ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
              )}
            </button>

            <a
              href="/#guard"
              onClick={e => navigateApp('/#guard', e)}
              className="bine-pill-primary"
              style={{
                height: '40px',
                padding: '0 20px',
              }}
            >
              Check a trade
            </a>
          </div>

          {/* Mobile navigation row (<640px) so all 4 routes and "Check a trade" fit without horizontal scroll */}
          <nav
            className="flex sm:hidden items-center justify-between w-full pt-1 border-t"
            style={{ borderColor: 'var(--hairline)' }}
            aria-label="Mobile navigation"
          >
            {navItems.map(item => {
              const active = pathname === item.matchPath
              return (
                <a
                  key={item.href}
                  href={item.href}
                  onClick={e => navigateApp(item.href, e)}
                  aria-current={active ? 'page' : undefined}
                  className="no-underline py-1 px-1 rounded-md transition-colors"
                  style={{
                    fontSize: '14px',
                    fontWeight: active ? 600 : 500,
                    color: active ? 'var(--text)' : 'var(--text-secondary)',
                  }}
                >
                  {item.label}
                </a>
              )
            })}
          </nav>
        </div>
      </div>
    </header>
  )
}

export function Footer() {
  return (
    <footer
      className="mt-20 py-12"
      style={{
        borderTop: '1px solid var(--hairline)',
      }}
    >
      <div className="bine-container">
        <div className="w-full max-w-[1240px] mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-8">
          <div className="space-y-3">
            <BineWordmarkLockup tileSize={36} staticTile />
            <p className="text-sm m-0" style={{ color: 'var(--text-secondary)' }}>
              Built for BNB Hack: Tokenized Stocks Edition on BNB Chain.
            </p>
          </div>

          <div className="space-y-3">
            <h2
              className="text-xs font-semibold uppercase tracking-wider m-0"
              style={{ color: 'var(--text-secondary)' }}
            >
              Connect
            </h2>
            <div className="flex flex-wrap items-center gap-4 sm:gap-6">
              <a
                href="https://github.com/0xSheriff"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub profile"
                className="group inline-flex items-center gap-3 no-underline rounded-full pr-3 py-0.5 transition-transform"
                style={{ color: 'var(--text)' }}
              >
                <span
                  className="w-11 h-11 rounded-full inline-flex items-center justify-center shrink-0 transition-transform group-hover:-translate-y-0.5"
                  style={{
                    backgroundColor: 'var(--pill-secondary-bg)',
                    color: 'var(--text)',
                    boxShadow: 'var(--pill-secondary-shadow)',
                  }}
                >
                  <GitHubIcon size={22} />
                </span>
                <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                  github.com/0xSheriff
                </span>
              </a>

              <a
                href="https://x.com/0xearthh"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="X profile"
                className="group inline-flex items-center gap-3 no-underline rounded-full pr-3 py-0.5 transition-transform"
                style={{ color: 'var(--text)' }}
              >
                <span
                  className="w-11 h-11 rounded-full inline-flex items-center justify-center shrink-0 transition-transform group-hover:-translate-y-0.5"
                  style={{
                    backgroundColor: 'var(--pill-secondary-bg)',
                    color: 'var(--text)',
                    boxShadow: 'var(--pill-secondary-shadow)',
                  }}
                >
                  <XIcon size={22} />
                </span>
                <span className="text-sm font-medium" style={{ color: 'var(--text)' }}>
                  @0xearthh
                </span>
              </a>
            </div>
          </div>
        </div>
      </div>
    </footer>
  )
}
