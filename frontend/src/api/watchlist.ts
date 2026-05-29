import { ApiClient } from './request'

export type WatchMarket = 'CN' | 'US' | 'HK'

export interface WatchlistItem {
  id: string
  symbol: string
  stock_name?: string
  market: WatchMarket
  tags?: string[]
  notes?: string
  enabled: boolean
  created_at?: string
  updated_at?: string
}

export interface PositionItem extends WatchlistItem {
  quantity?: number
  cost_basis?: number
  target_price?: number
  stop_loss?: number
}

export interface WatchlistPayload {
  symbol: string
  stock_name?: string
  market: WatchMarket
  tags?: string[]
  notes?: string
  enabled?: boolean
}

export interface PositionPayload extends WatchlistPayload {
  quantity?: number
  cost_basis?: number
  target_price?: number
  stop_loss?: number
}

export interface MonitoringEvidence {
  type: string
  source?: string
  title?: string
  published_at?: string
  url?: string
  summary?: string
  confidence?: number
  status?: string
  reason?: string
  extracted_metrics?: Record<string, any>
}

export interface MonitoringReport {
  symbol: string
  stock_name?: string
  market: WatchMarket
  signal_type: string
  severity: string
  score: number
  summary?: string
  reasons?: string[]
  metrics?: Record<string, any>
  evidence?: MonitoringEvidence[]
  recommendation?: string
  has_position?: boolean
  data_gaps?: string[]
  created_at?: string
}

export interface MonitoringRunRequest {
  symbols?: string[]
  market?: WatchMarket
  include_disabled?: boolean
  max_deep_analysis?: number
  lookback_days?: number
  news_days?: number
  force_refresh?: boolean
}

export interface MonitoringScanItem {
  symbol: string
  stock_name?: string
  market: WatchMarket
  status: 'scanning' | 'triggered' | 'no_signal' | 'error'
  signal_type: string
  severity?: string
  score: number
  triggered: boolean
  reasons?: string[]
  metrics?: Record<string, any>
  current_price?: number
  change_percent?: number
  data_gaps?: string[]
  report_skipped_reason?: string
  error?: string
}

export interface MonitoringRunResult {
  run_id: string
  target_count: number
  scanned_count: number
  triggered_count: number
  report_count: number
  no_signal_count: number
  error_count: number
  scanned_items: MonitoringScanItem[]
  reports: MonitoringReport[]
  errors: Array<{ symbol: string; market: string; error: string }>
}

export interface MonitoringRunSummary {
  user_id: string
  status: string
  parameters?: Record<string, any>
  target_count?: number
  scanned_count?: number
  triggered_count?: number
  report_count?: number
  no_signal_count?: number
  error_count?: number
  errors?: Array<{ symbol: string; market: string; error: string }>
  scanned_items?: MonitoringScanItem[]
  created_at?: string
  completed_at?: string
}

export const watchlistApi = {
  listWatchlist(includeDisabled = false) {
    return ApiClient.get<{ items: WatchlistItem[]; total: number }>('/api/watchlists', {
      include_disabled: includeDisabled
    })
  },

  addWatchlistItem(payload: WatchlistPayload) {
    return ApiClient.post<WatchlistItem>('/api/watchlists', payload)
  },

  updateWatchlistItem(id: string, payload: Partial<WatchlistPayload>) {
    return ApiClient.put<WatchlistItem>(`/api/watchlists/${id}`, payload)
  },

  deleteWatchlistItem(id: string) {
    return ApiClient.delete(`/api/watchlists/${id}`)
  },

  listPositions(includeDisabled = false) {
    return ApiClient.get<{ items: PositionItem[]; total: number }>('/api/portfolio/positions', {
      include_disabled: includeDisabled
    })
  },

  addPosition(payload: PositionPayload) {
    return ApiClient.post<PositionItem>('/api/portfolio/positions', payload)
  },

  updatePosition(id: string, payload: Partial<PositionPayload>) {
    return ApiClient.put<PositionItem>(`/api/portfolio/positions/${id}`, payload)
  },

  deletePosition(id: string) {
    return ApiClient.delete(`/api/portfolio/positions/${id}`)
  },

  runMonitoring(payload: MonitoringRunRequest) {
    return ApiClient.post<MonitoringRunResult>('/api/monitoring/watchlist/run', payload, {
      timeout: 180000,
      showLoading: true,
      loadingText: '正在扫描 Watchlist'
    })
  },

  listReports(limit = 50, skip = 0) {
    return ApiClient.get<{ items: MonitoringReport[]; total: number }>('/api/monitoring/reports', {
      limit,
      skip
    })
  },

  listRuns(limit = 5, skip = 0) {
    return ApiClient.get<{ items: MonitoringRunSummary[]; total: number }>('/api/monitoring/runs', {
      limit,
      skip
    })
  }
}
