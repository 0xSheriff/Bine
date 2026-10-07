import {
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  useEffect,
  useId,
  useRef,
} from 'react'
import { usePrefersReducedMotion } from './BineLogo'

export function BineGlassFilterDef() {
  return (
    <svg
      width="0"
      height="0"
      aria-hidden="true"
      focusable="false"
      style={{ position: 'absolute', width: 0, height: 0, overflow: 'hidden', pointerEvents: 'none' }}
    >
      <defs>
        <filter id="bine-glass" x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.012"
            numOctaves="2"
            seed="7"
            result="noise"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="noise"
            scale="4"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>
    </svg>
  )
}

export function runGlassViewTransition(update: () => void, reducedMotion: boolean) {
  if (
    !reducedMotion &&
    typeof document !== 'undefined' &&
    'startViewTransition' in document &&
    typeof (document as Document & { startViewTransition?: (cb: () => void) => unknown })
      .startViewTransition === 'function'
  ) {
    try {
      ;(
        document as Document & { startViewTransition: (cb: () => void) => unknown }
      ).startViewTransition(() => {
        update()
      })
      return
    } catch {
      // Fall back to direct update + WAAPI FLIP
    }
  }
  update()
}

interface GlassDetailPanelProps {
  id: string
  isOpen: boolean
  onClose: () => void
  title: string
  subtitle?: string
  badge?: ReactNode
  triggerRef?: React.RefObject<HTMLElement | null>
  children: ReactNode
}

export function GlassDetailPanel({
  id,
  isOpen,
  onClose,
  title,
  subtitle,
  badge,
  triggerRef,
  children,
}: GlassDetailPanelProps) {
  const panelRef = useRef<HTMLDivElement | null>(null)
  const closeBtnRef = useRef<HTMLButtonElement | null>(null)
  const rafRef = useRef<number | null>(null)
  const reducedMotion = usePrefersReducedMotion()
  const headingId = useId()

  useEffect(() => {
    if (!isOpen) return
    const el = panelRef.current
    if (!el) return

    // WAAPI entrance animation (transform + opacity only, 60fps compositor)
    if (reducedMotion) {
      el.animate([{ opacity: 0 }, { opacity: 1 }], {
        duration: 80,
        easing: 'linear',
      })
    } else {
      const triggerRect = triggerRef?.current?.getBoundingClientRect()
      const panelRect = el.getBoundingClientRect()
      let dy = -8
      let sx = 0.985
      if (triggerRect && panelRect.width > 0 && panelRect.height > 0) {
        dy = Math.max(-24, Math.min(24, (triggerRect.top - panelRect.top) * 0.18))
        sx = Math.max(0.96, Math.min(1.02, triggerRect.width / panelRect.width))
      }
      el.animate(
        [
          {
            opacity: 0,
            transform: `translate3d(0, ${dy.toFixed(1)}px, 0) scale(${sx.toFixed(3)}, 0.97)`,
          },
          {
            opacity: 1,
            transform: 'translate3d(0, 0, 0) scale(1, 1)',
          },
        ],
        {
          duration: 320,
          easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
        },
      )
    }

    // Move focus into the panel close button for keyboard users without scrolling the viewport abruptly
    const timer = window.setTimeout(() => {
      closeBtnRef.current?.focus({ preventScroll: true })
    }, 30)

    return () => {
      window.clearTimeout(timer)
      if (rafRef.current !== null) {
        window.cancelAnimationFrame(rafRef.current)
      }
    }
  }, [isOpen, reducedMotion, triggerRef])

  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopPropagation()
        const triggerEl = triggerRef?.current
        onClose()
        window.setTimeout(() => triggerEl?.focus({ preventScroll: true }), 10)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen, onClose, triggerRef])

  if (!isOpen) return null

  const handlePointerMove = (e: ReactPointerEvent<HTMLDivElement>) => {
    if (reducedMotion) return
    const el = panelRef.current
    if (!el) return
    const clientX = e.clientX
    const clientY = e.clientY
    if (rafRef.current !== null) return
    rafRef.current = window.requestAnimationFrame(() => {
      rafRef.current = null
      const rect = el.getBoundingClientRect()
      const x = Math.round(clientX - rect.left)
      const y = Math.round(clientY - rect.top)
      el.style.setProperty('--mx', `${x}px`)
      el.style.setProperty('--my', `${y}px`)
    })
  }

  const handleCloseClick = () => {
    const triggerEl = triggerRef?.current
    onClose()
    window.setTimeout(() => triggerEl?.focus({ preventScroll: true }), 10)
  }

  return (
    <div
      ref={panelRef}
      id={id}
      role="region"
      aria-labelledby={headingId}
      data-glass-panel
      onPointerMove={handlePointerMove}
      className="bine-glass-panel mt-3 p-4 sm:p-5"
    >
      <BineGlassFilterDef />
      <div className="bine-glass-scrim space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2.5 flex-wrap">
              <h3 id={headingId} className="text-base font-semibold m-0" style={{ color: 'var(--text)' }}>
                {title}
              </h3>
              {badge}
            </div>
            {subtitle && (
              <p className="text-xs font-mono m-0" style={{ color: 'var(--text-secondary)' }}>
                {subtitle}
              </p>
            )}
          </div>

          <button
            ref={closeBtnRef}
            type="button"
            onClick={handleCloseClick}
            aria-label={`Close ${title} details`}
            className="bine-pill-secondary px-3.5 min-h-[44px] min-w-[44px] text-xs font-semibold shrink-0"
          >
            Close
          </button>
        </div>

        <div className="text-sm leading-relaxed space-y-3" style={{ color: 'var(--text)' }}>
          {children}
        </div>
      </div>
    </div>
  )
}

export interface GlassStackItem {
  id: string
  title: string
  subtitle?: string
  summary: ReactNode
  badge?: ReactNode
  detail: ReactNode
}

interface GlassStackProps {
  items: GlassStackItem[]
  columns?: 1 | 2 | 3
  defaultOpenId?: string | null
  ariaLabel?: string
}

export function GlassStack({
  items,
  columns = 3,
  defaultOpenId = null,
  ariaLabel,
}: GlassStackProps) {
  const [openId, setOpenId] = useIdState(defaultOpenId)
  const reducedMotion = usePrefersReducedMotion()
  const triggerRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const groupUid = useId()

  const activeItem = items.find(i => i.id === openId) ?? null
  const activeTriggerRef = {
    get current() {
      return openId ? triggerRefs.current[openId] ?? null : null
    },
  }

  const toggleItem = (id: string) => {
    runGlassViewTransition(() => {
      setOpenId(prev => (prev === id ? null : id))
    }, reducedMotion)
  }

  const handleKeyDown = (e: ReactKeyboardEvent<HTMLButtonElement>, id: string) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      toggleItem(id)
    }
  }

  const gridCols =
    columns === 1
      ? 'grid-cols-1'
      : columns === 2
        ? 'grid-cols-1 lg:grid-cols-2'
        : 'grid-cols-1 sm:grid-cols-3'

  return (
    <div aria-label={ariaLabel} className="space-y-3">
      <div className={`grid ${gridCols} gap-4`}>
        {items.map(item => {
          const isOpen = openId === item.id
          const panelId = `${groupUid}-panel-${item.id}`
          return (
            <button
              key={item.id}
              ref={el => {
                triggerRefs.current[item.id] = el
              }}
              type="button"
              aria-expanded={isOpen}
              aria-controls={panelId}
              onClick={() => toggleItem(item.id)}
              onKeyDown={e => handleKeyDown(e, item.id)}
              className={`bine-card bine-glass-trigger text-left p-6 sm:p-7 w-full min-h-[44px] cursor-pointer transition-transform hover:-translate-y-0.5 flex flex-col justify-between gap-3 ${
                isOpen ? 'bine-glass-trigger-active' : ''
              }`}
            >
              <div className="w-full space-y-2">{item.summary}</div>
              <div className="flex items-center justify-between w-full pt-1 text-xs font-medium">
                <span style={{ color: 'var(--text-secondary)' }}>
                  {isOpen ? 'Hide glass breakdown' : 'Inspect details'}
                </span>
                <span
                  aria-hidden="true"
                  className="inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-mono"
                  style={{
                    backgroundColor: 'var(--surface-subtle)',
                    color: 'var(--text)',
                  }}
                >
                  {isOpen ? '−' : '+'}
                </span>
              </div>
            </button>
          )
        })}
      </div>

      {activeItem && (
        <GlassDetailPanel
          id={`${groupUid}-panel-${activeItem.id}`}
          isOpen={true}
          onClose={() =>
            runGlassViewTransition(() => {
              setOpenId(null)
            }, reducedMotion)
          }
          title={activeItem.title}
          subtitle={activeItem.subtitle}
          badge={activeItem.badge}
          triggerRef={activeTriggerRef}
        >
          {activeItem.detail}
        </GlassDetailPanel>
      )}
    </div>
  )
}

import { useState } from 'react'
function useIdState(initial: string | null) {
  return useState<string | null>(initial)
}
