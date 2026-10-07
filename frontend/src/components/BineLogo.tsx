import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import bineMarkPng from '../assets/bine-mark.png'

const LazyLiquidMetal = lazy(() =>
  import('@paper-design/shaders-react').then(m => ({ default: m.LiquidMetal })),
)

let cachedWebGlAvailable: boolean | null = null

function checkWebGlAvailable(): boolean {
  if (typeof window === 'undefined') return false
  if (cachedWebGlAvailable !== null) return cachedWebGlAvailable
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl')
    cachedWebGlAvailable = Boolean(gl)
  } catch {
    cachedWebGlAvailable = false
  }
  return cachedWebGlAvailable
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return false
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches
  })

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)')
    const onChange = (e: MediaQueryListEvent) => setReduced(e.matches)
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [])

  return reduced
}

interface BineLogoTileProps {
  size?: number
  staticOnly?: boolean
}

export function BineLogoTile({ size = 36, staticOnly = false }: BineLogoTileProps) {
  const tileRef = useRef<HTMLDivElement | null>(null)
  const reducedMotion = usePrefersReducedMotion()
  const [webGlReady, setWebGlReady] = useState<boolean>(false)
  const [inView, setInView] = useState<boolean>(true)

  useEffect(() => {
    setWebGlReady(checkWebGlAvailable())
  }, [])

  useEffect(() => {
    const el = tileRef.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const observer = new IntersectionObserver(
      entries => {
        const entry = entries[0]
        if (entry) {
          setInView(entry.isIntersecting)
        }
      },
      { threshold: 0.05 },
    )
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const radius = Math.round(size * 0.24)
  const useShader = webGlReady && !reducedMotion && !staticOnly
  const shaderSpeed = useShader && inView ? 0.51 : 0

  return (
    <div
      ref={tileRef}
      aria-hidden="true"
      className="relative inline-flex items-center justify-center overflow-hidden shrink-0 select-none"
      style={{
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: `${radius}px`,
        backgroundColor: '#000000',
        boxShadow: 'inset 0 0 0 1px rgba(255, 255, 255, 0.12)',
      }}
    >
      {/* Static masked chrome fallback (always present underneath while shader initializes or when static/reduced-motion) */}
      <div
        className="w-[78%] h-[78%] pointer-events-none"
        style={{
          backgroundImage:
            'linear-gradient(135deg, #F7F8FB 0%, #CFD4E2 38%, #FF8424 51%, #2E6BFF 63%, #8A90A4 100%)',
          WebkitMaskImage: `url(${bineMarkPng})`,
          maskImage: `url(${bineMarkPng})`,
          WebkitMaskSize: 'contain',
          maskSize: 'contain',
          WebkitMaskRepeat: 'no-repeat',
          maskRepeat: 'no-repeat',
          WebkitMaskPosition: 'center',
          maskPosition: 'center',
        }}
      />

      {useShader && (
        <div className="absolute inset-0">
          <Suspense fallback={null}>
            <LazyLiquidMetal
              image={bineMarkPng}
              colorBack="#000000"
              colorTint="#ffffff"
              repetition={1.75}
              softness={0.12}
              shiftRed={0.44}
              shiftBlue={0.44}
              distortion={0.14}
              contour={0.58}
              angle={64}
              scale={0.78}
              fit="contain"
              speed={shaderSpeed}
              minPixelRatio={2}
              style={{ width: '100%', height: '100%', display: 'block' }}
            />
          </Suspense>
        </div>
      )}
    </div>
  )
}

interface BineWordmarkLockupProps {
  tileSize?: number
  staticTile?: boolean
}

export function BineWordmarkLockup({ tileSize = 36, staticTile = false }: BineWordmarkLockupProps) {
  return (
    <span className="inline-flex items-center gap-2.5 select-none">
      <BineLogoTile size={tileSize} staticOnly={staticTile} />
      <span
        style={{
          fontWeight: 700,
          letterSpacing: '-0.02em',
          textTransform: 'uppercase',
          fontSize: tileSize >= 36 ? '19px' : '17px',
          lineHeight: 1,
          color: 'var(--text)',
        }}
      >
        BINE
      </span>
    </span>
  )
}
