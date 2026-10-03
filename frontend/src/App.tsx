import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
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
  const path = typeof window !== 'undefined' ? window.location.pathname : '/'
  let Page = Home
  if (path === '/integrate') Page = Integrate
  else if (path === '/refusals') Page = Refusals
  else if (path === '/receipts') Page = Receipts

  return (
    <QueryClientProvider client={queryClient}>
      <Page />
    </QueryClientProvider>
  )
}
