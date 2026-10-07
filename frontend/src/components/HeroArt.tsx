import { useEffect, useId, useRef } from 'react'
import { motion } from 'motion/react'
import bineMarkPng from '../assets/bine-mark.png'
import { usePrefersReducedMotion } from './BineLogo'

const B_GLYPH_PATH =
  'M96 92C96 72.1177 112.118 56 132 56H284C359.111 56 412 100.889 412 166C412 206.42 389.64 239.41 353.8 253.2C396.42 267.35 424 303.65 424 350C424 419.588 368.588 456 290 456H132C112.118 456 96 439.882 96 420V92ZM178 130C171.373 130 166 135.373 166 142V212C166 218.627 171.373 224 178 224H272C306.242 224 328 204.242 328 177C328 149.758 306.242 130 272 130H178ZM178 286C171.373 286 166 291.373 166 298V370C166 376.627 171.373 382 178 382H280C316.451 382 340 361.851 340 334C340 306.149 316.451 286 280 286H178Z'

export function HeroArt() {
  const rawId = useId().replace(/:/g, '')
  const idPrefix = `bine-art-${rawId}`
  const scrollWrapRef = useRef<HTMLDivElement | null>(null)
  const ringParallaxRef = useRef<SVGGElement | null>(null)
  const coinParallaxRef = useRef<SVGGElement | null>(null)
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (reducedMotion || typeof window === 'undefined') return

    const isTouch = window.matchMedia && window.matchMedia('(pointer: coarse)').matches
    let targetX = 0
    let targetY = 0
    let currentX = 0
    let currentY = 0
    let rafId = 0

    const onPointerMove = (e: PointerEvent) => {
      if (isTouch) return
      const nx = (e.clientX / window.innerWidth - 0.5) * 2
      const ny = (e.clientY / window.innerHeight - 0.5) * 2
      targetX = Math.max(-1, Math.min(1, nx))
      targetY = Math.max(-1, Math.min(1, ny))
    }

    const onScroll = () => {
      const wrap = scrollWrapRef.current
      if (!wrap) return
      const y = window.scrollY || 0
      const heroH = Math.max(520, window.innerHeight - 80)
      const progress = Math.min(1, Math.max(0, y / heroH))
      const translateY = y * 0.15
      const opacity = 1 - progress
      wrap.style.transform = `translate3d(0, ${translateY.toFixed(2)}px, 0)`
      wrap.style.opacity = opacity.toFixed(3)
    }

    const tick = () => {
      currentX += (targetX - currentX) * 0.08
      currentY += (targetY - currentY) * 0.08

      if (ringParallaxRef.current) {
        const rx = currentX * 14
        const ry = currentY * 14
        ringParallaxRef.current.style.transform = `translate3d(${rx.toFixed(2)}px, ${ry.toFixed(2)}px, 0)`
      }
      if (coinParallaxRef.current) {
        const cx = -currentX * 26
        const cy = -currentY * 26
        coinParallaxRef.current.style.transform = `translate3d(${cx.toFixed(2)}px, ${cy.toFixed(2)}px, 0)`
      }

      rafId = window.requestAnimationFrame(tick)
    }

    if (!isTouch) {
      window.addEventListener('pointermove', onPointerMove, { passive: true })
      rafId = window.requestAnimationFrame(tick)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()

    return () => {
      window.removeEventListener('pointermove', onPointerMove)
      window.removeEventListener('scroll', onScroll)
      if (rafId) window.cancelAnimationFrame(rafId)
    }
  }, [reducedMotion])

  return (
    <motion.div
      initial={reducedMotion ? false : { opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
      className="w-full h-full flex items-center justify-end pointer-events-none select-none"
      aria-hidden="true"
    >
      <div
        ref={scrollWrapRef}
        className="w-full h-full flex items-center justify-end will-change-transform"
      >
        <svg
          viewBox="-20 -30 900 680"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-[104%] max-w-[780px] h-auto overflow-visible"
        >
          <defs>
            {/* Ring lavender surface gradient (#D6D5E6 to #B9B8CF) */}
            <linearGradient id={`${idPrefix}-ring-fill`} x1="80" y1="140" x2="860" y2="480" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="var(--ring-lavender-start)" />
              <stop offset="52%" stopColor="#CBCADE" />
              <stop offset="100%" stopColor="var(--ring-lavender-end)" />
            </linearGradient>

            {/* Ring inner wall thickness shading */}
            <linearGradient id={`${idPrefix}-ring-wall`} x1="120" y1="220" x2="780" y2="520" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#DFDFEC" />
              <stop offset="45%" stopColor="#B4B3CA" />
              <stop offset="100%" stopColor="#9E9DB7" />
            </linearGradient>

            {/* 2px light inner/outer edge highlight */}
            <linearGradient id={`${idPrefix}-ring-highlight`} x1="85" y1="260" x2="760" y2="490" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.95" />
              <stop offset="45%" stopColor="#F5F5FA" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#E2E1F0" stopOpacity="0.45" />
            </linearGradient>

            {/* Soft lavender drop shadow (blur 40px, ~12% opacity) */}
            <filter id={`${idPrefix}-ring-shadow`} x="-20%" y="-20%" width="150%" height="160%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="28" />
            </filter>

            {/* Contact shadow under the coin */}
            <filter id={`${idPrefix}-coin-contact-shadow`} x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur in="SourceGraphic" stdDeviation="12" />
            </filter>

            {/* Coin radial gold fill (#F7F1D0 to #E3CF8A) */}
            <radialGradient
              id={`${idPrefix}-coin-face`}
              cx="0"
              cy="0"
              r="1"
              gradientUnits="userSpaceOnUse"
              gradientTransform="translate(-18 -22) rotate(52) scale(135 122)"
            >
              <stop offset="0%" stopColor="#FFFDF0" />
              <stop offset="28%" stopColor="var(--coin-gold-start)" />
              <stop offset="74%" stopColor="var(--coin-gold-end)" />
              <stop offset="100%" stopColor="#CCAFA0" stopOpacity="0" />
            </radialGradient>

            <linearGradient id={`${idPrefix}-coin-face-base`} x1="-70" y1="-80" x2="70" y2="80" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="var(--coin-gold-start)" />
              <stop offset="68%" stopColor="var(--coin-gold-end)" />
              <stop offset="100%" stopColor="#D1B768" />
            </linearGradient>

            {/* Darker metallic gold rim for 3D coin thickness */}
            <linearGradient id={`${idPrefix}-coin-rim`} x1="-55" y1="-84" x2="85" y2="84" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#8F7532" />
              <stop offset="22%" stopColor="#F6EAB9" />
              <stop offset="44%" stopColor="#725A1E" />
              <stop offset="68%" stopColor="#E6D28C" />
              <stop offset="88%" stopColor="#5D4714" />
              <stop offset="100%" stopColor="#B89B4C" />
            </linearGradient>

            {/* Embossed BINE gold mark fill */}
            <linearGradient id={`${idPrefix}-coin-emboss`} x1="-45" y1="-25" x2="45" y2="25" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#C9AE5E" />
              <stop offset="50%" stopColor="#DFC97F" />
              <stop offset="100%" stopColor="#9E8134" />
            </linearGradient>
          </defs>

          {/* Parallax Group 1: Tilted Elliptical Lavender Ring */}
          <g ref={ringParallaxRef} className="will-change-transform">
            {/* Soft diffused ambient shadow cast onto the floor below the ring */}
            <g filter={`url(#${idPrefix}-ring-shadow)`} opacity="0.13">
              <path
                fill="#5E5C86"
                fillRule="evenodd"
                clipRule="evenodd"
                d="M 92 382 C 74 240, 340 105, 760 68 C 1020 45, 1210 110, 1230 235 C 1250 360, 995 505, 620 532 C 265 556, 110 495, 92 382 Z M 238 372 C 226 286, 430 185, 765 154 C 980 134, 1125 182, 1138 272 C 1152 362, 955 468, 635 492 C 350 513, 250 458, 238 372 Z"
              />
            </g>

            {/* Lower 3D thickness wall of the ring */}
            <path
              fill={`url(#${idPrefix}-ring-wall)`}
              fillRule="evenodd"
              clipRule="evenodd"
              d="M 84 328 C 65 188, 345 48, 780 8 C 1050 -16, 1240 52, 1258 182 C 1276 312, 1012 465, 622 494 C 258 520, 102 446, 84 328 Z M 234 326 C 222 238, 430 135, 772 102 C 992 80, 1140 130, 1154 222 C 1168 314, 966 424, 636 450 C 344 472, 246 414, 234 326 Z"
              transform="translate(0, 8)"
            />

            {/* Main tilted elliptical lavender ribbon (outer & inner ellipse) */}
            <path
              fill={`url(#${idPrefix}-ring-fill)`}
              fillRule="evenodd"
              clipRule="evenodd"
              d="M 84 328 C 65 188, 345 48, 780 8 C 1050 -16, 1240 52, 1258 182 C 1276 312, 1012 465, 622 494 C 258 520, 102 446, 84 328 Z M 234 326 C 222 238, 430 135, 772 102 C 992 80, 1140 130, 1154 222 C 1168 314, 966 424, 636 450 C 344 472, 246 414, 234 326 Z"
            />

            {/* 2px light inner and outer bevel highlight */}
            <path
              d="M 84 328 C 102 446, 258 520, 622 494 C 1012 465, 1276 312, 1258 182"
              stroke={`url(#${idPrefix}-ring-highlight)`}
              strokeWidth="2.2"
              strokeLinecap="round"
            />
            <path
              d="M 234 326 C 222 238, 430 135, 772 102 C 992 80, 1140 130, 1154 222"
              stroke={`url(#${idPrefix}-ring-highlight)`}
              strokeWidth="2"
              strokeLinecap="round"
            />
          </g>

          {/* Parallax Group 2: 3D Gold Coin resting on the lower edge of the ring */}
          <g ref={coinParallaxRef} className="will-change-transform">
            <g className="bine-coin-motion">
              {/* Coordinates centered around (0,0) because offset-path positions the group */}
              <g transform="translate(0, -68) rotate(-20)">
                {/* Soft contact shadow on the ring track directly under the coin */}
                <ellipse
                  cx="6"
                  cy="82"
                  rx="54"
                  ry="13"
                  fill="#4A486A"
                  opacity="0.22"
                  filter={`url(#${idPrefix}-coin-contact-shadow)`}
                  transform="rotate(20 6 82)"
                />

                {/* Darker offset duplicate for 3D coin rim thickness */}
                <ellipse
                  cx="13"
                  cy="4"
                  rx="73"
                  ry="84"
                  fill={`url(#${idPrefix}-coin-rim)`}
                  stroke="#7A6020"
                  strokeWidth="1"
                />
                {/* Metallic specular ridge bands on the coin edge */}
                <path
                  d="M 52 -58 L 65 -54 C 76 -40, 82 -22, 85 -4 L 72 -8 C 69 -26, 63 -44, 52 -58 Z"
                  fill="#FFF7CC"
                  opacity="0.7"
                />
                <path
                  d="M 44 58 L 57 62 C 69 48, 78 30, 82 10 L 69 6 C 65 26, 56 44, 44 58 Z"
                  fill="#523E10"
                  opacity="0.55"
                />

                {/* Main coin face */}
                <ellipse
                  cx="0"
                  cy="0"
                  rx="73"
                  ry="84"
                  fill={`url(#${idPrefix}-coin-face-base)`}
                  stroke="#FFFBEA"
                  strokeWidth="1.5"
                />
                <ellipse cx="0" cy="0" rx="73" ry="84" fill={`url(#${idPrefix}-coin-face)`} />

                {/* Inner recessed coin rim bevel (1px dark gold + 1px white highlight) */}
                <ellipse
                  cx="-1"
                  cy="0"
                  rx="64"
                  ry="74"
                  fill="none"
                  stroke="#C4A856"
                  strokeWidth="1.4"
                />
                <ellipse
                  cx="0.5"
                  cy="1"
                  rx="64"
                  ry="74"
                  fill="none"
                  stroke="#FFFDF2"
                  strokeWidth="1"
                  opacity="0.85"
                />

                {/* Embossed BINE mark + tile on the coin face (rotated vertically like IPO [FX] in reference) */}
                <g transform="rotate(90)">
                  {/* 1px white highlight offset */}
                  <g transform="translate(1, 1)" opacity="0.9">
                    <text
                      x="-22"
                      y="7"
                      textAnchor="middle"
                      fill="#FFFDF4"
                      style={{
                        fontFamily: "'Inter Variable', 'Inter', sans-serif",
                        fontWeight: 700,
                        fontSize: '21px',
                        letterSpacing: '-0.03em',
                      }}
                    >
                      BINE
                    </text>
                    <rect
                      x="10"
                      y="-17"
                      width="34"
                      height="34"
                      rx="7"
                      fill="none"
                      stroke="#FFFDF4"
                      strokeWidth="1.5"
                    />
                  </g>

                  {/* Slightly darker embossed gold letters */}
                  <text
                    x="-22"
                    y="7"
                    textAnchor="middle"
                    fill={`url(#${idPrefix}-coin-emboss)`}
                    stroke="#A68939"
                    strokeWidth="0.5"
                    style={{
                      fontFamily: "'Inter Variable', 'Inter', sans-serif",
                      fontWeight: 700,
                      fontSize: '21px',
                      letterSpacing: '-0.03em',
                    }}
                  >
                    BINE
                  </text>

                  {/* Embossed BINE rounded-square tile on the coin face */}
                  <rect
                    x="10"
                    y="-17"
                    width="34"
                    height="34"
                    rx="7"
                    fill="#DFC980"
                    stroke="#A48838"
                    strokeWidth="1.3"
                  />
                  {/* Static BINE glyph inside the coin tile with 1px white highlight + embossed gold fill */}
                  <g transform="translate(13.5, -13.5) scale(0.053)">
                    <path
                      d={B_GLYPH_PATH}
                      fill="#FFFDF5"
                      fillRule="evenodd"
                      clipRule="evenodd"
                      transform="translate(18, 18)"
                    />
                    <path
                      d={B_GLYPH_PATH}
                      fill={`url(#${idPrefix}-coin-emboss)`}
                      stroke="#9A7D2E"
                      strokeWidth="10"
                      fillRule="evenodd"
                      clipRule="evenodd"
                    />
                  </g>
                  {/* Hidden reference to static PNG asset so bundler keeps coin & nav mark synced */}
                  <image href={bineMarkPng} width="0" height="0" opacity="0" />
                </g>
              </g>
            </g>
          </g>
        </svg>
      </div>
    </motion.div>
  )
}
