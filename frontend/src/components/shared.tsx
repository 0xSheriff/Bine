/** Shared formatting helpers and minimal Header component for the one-screen Bine UI. */

import { useEffect, useState } from 'react'

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
  if (val === null || val === undefined) return '—'
  if (val >= 1_000_000_000) return `$${(val / 1_000_000_000).toFixed(2)}B`
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`
  return `$${val.toFixed(2)}`
}

export function shortAddress(addr: string | null | undefined): string {
  if (!addr) return '—'
  if (addr.length <= 12) return addr
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`
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

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    document.documentElement.style.colorScheme = theme
    try {
      localStorage.setItem('bine-theme', theme)
    } catch {
      // ignore storage errors
    }
  }, [theme])

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'))
  }

  return (
    <header
      style={{
        backgroundColor: 'var(--surface)',
        borderBottom: '1px solid var(--border)',
      }}
    >
      <div className="max-w-3xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
        <a
          href="/"
          className="text-base font-semibold tracking-tight no-underline"
          style={{ color: 'var(--text)' }}
        >
          Bine
        </a>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            className="w-8 h-8 inline-flex items-center justify-center rounded border cursor-pointer transition-colors"
            style={{
              backgroundColor: 'var(--bg)',
              borderColor: 'var(--border)',
              color: 'var(--text)',
            }}
          >
            {theme === 'dark' ? (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="5" />
                <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
              </svg>
            ) : (
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            )}
          </button>

          <a
            href="/docs"
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium no-underline px-2.5 py-1 rounded border"
            style={{
              color: 'var(--text)',
              borderColor: 'var(--border)',
              backgroundColor: 'var(--bg)',
            }}
          >
            API
          </a>
        </div>
      </div>
    </header>
  )
}
