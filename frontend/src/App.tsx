import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { usePrefersReducedMotion } from './components/BineLogo'
import { focusPageHeading } from './components/shared'
import Home from './pages/Home'

const Guard = lazy(() => import('./pages/Guard'))
const Integrate = lazy(() => import('./pages/Integrate'))
const Receipts = lazy(() => import('./pages/Receipts'))
const Refusals = lazy(() => import('./pages/Refusals'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15_000,
    },
  },
})

function resolveInitialPath(): string {
  if (typeof window === 'undefined') return '/'
  if (window.location.pathname === '/' && window.location.hash === '#guard') {
    const nextUrl = `/guard${window.location.search}`
    window.history.replaceState({}, '', nextUrl)
    return '/guard'
  }
  return window.location.pathname
}

export default function App() {
  const [path, setPath] = useState<string>(resolveInitialPath)
  const reducedMotion = usePrefersReducedMotion()
  const isFirstRender = useRef(true)

  useEffect(() => {
    if (typeof window === 'undefined') return
    const syncLocation = () => {
      if (window.location.pathname === '/' && window.location.hash === '#guard') {
        const nextUrl = `/guard${window.location.search}`
        window.history.replaceState({}, '', nextUrl)
        setPath('/guard')
        return
      }
      setPath(window.location.pathname)
    }
    window.addEventListener('popstate', syncLocation)
    window.addEventListener('hashchange', syncLocation)
    return () => {
      window.removeEventListener('popstate', syncLocation)
      window.removeEventListener('hashchange', syncLocation)
    }
  }, [])

  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false
      return
    }
    focusPageHeading()
  }, [path])

  let Page: React.ComponentType = Home
  if (path === '/guard') Page = Guard
  else if (path === '/integrate') Page = Integrate
  else if (path === '/refusals') Page = Refusals
  else if (path === '/receipts') Page = Receipts

  return (
    <QueryClientProvider client={queryClient}>
      <AnimatePresence mode="wait" initial={false}>
        <motion.div
          key={path}
          initial={reducedMotion ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={reducedMotion ? undefined : { opacity: 0, y: -8 }}
          transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        >
          <Suspense
            fallback={
              <div
                className="min-h-screen"
                style={{ backgroundColor: 'var(--bg-page)', color: 'var(--text)' }}
              />
            }
          >
            <Page />
          </Suspense>
        </motion.div>
      </AnimatePresence>
    </QueryClientProvider>
  )
}
