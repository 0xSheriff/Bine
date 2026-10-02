import axios from 'axios'
import type {
  DecisionListResponse,
  ExecuteTradeResponse,
  HealthResponse,
  QuoteVerdictResponse,
  TickerListResponse,
} from './types'

const api = axios.create({ baseURL: '/api' })

export const fetchHealth = (): Promise<HealthResponse> =>
  api.get('/health').then(r => r.data)

export const fetchTickers = (): Promise<TickerListResponse> =>
  api.get('/tickers').then(r => r.data)

export const fetchQuote = (
  ticker: string,
  amount_usd: number,
  details = true,
): Promise<QuoteVerdictResponse> =>
  api.get('/quote', { params: { ticker, amount_usd, details } }).then(r => r.data)

export const executeTrade = (
  ticker: string,
  amount_usd: number,
  execute_live: boolean,
  admin_token?: string,
): Promise<ExecuteTradeResponse> =>
  api
    .post(
      '/execute',
      { ticker, amount_usd, execute_live, admin_token },
      admin_token ? { headers: { 'X-Bine-Admin-Token': admin_token } } : undefined,
    )
    .then(r => r.data)

export const fetchDecisions = (limit = 5): Promise<DecisionListResponse> =>
  api.get('/decisions', { params: { limit } }).then(r => r.data)
