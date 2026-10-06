import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AnimatePresence, motion } from 'motion/react'
import { usePrefersReducedMotion } from './components/BineLogo'
import Home from './pages/Home'
import Integrate from './pages/Integrate'
import Receipts from './pages/Receipts'
import Refusals from './pages/Refusals'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15_000,
    },
  },
})

export default function App() {
  const [path, setPath] = useState<string>(() =>
    typeof window !== 'undefined' ? window.location.pathname : '/',
  )
  const reducedMotion = usePrefersReducedMotion()

  useEffect(() => {
    if (typeof window === 'undefined') return
    const onPopState = () => {
      setPath(window.location.pathname)
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [])

  let Page = Home
  if (path === '/integrate') Page = Integrate
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
          <Page />
        </motion.div>
      </AnimatePresence>
    </QueryClientProvider>
  )
}
