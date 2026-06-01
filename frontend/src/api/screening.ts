import { ApiClient } from './request'

export interface ScreeningOrderBy { field: string; direction: 'asc' | 'desc' }
export interface ScreeningRunReq {
  market?: 'CN'
  date?: string | null
  adj?: 'qfq' | 'hfq' | 'none'
  conditions: any
  order_by?: ScreeningOrderBy[]
  limit?: number
  offset?: number
}

export interface ScreeningRunItem {
  code: string
  close?: number
  pct_chg?: number
  amount?: number
  ma20?: number
  rsi14?: number
  kdj_k?: number
  kdj_d?: number
  kdj_j?: number
  dif?: number
  dea?: number
  macd_hist?: number
}

export interface ScreeningRunResp { total: number; items: ScreeningRunItem[] }

export interface SmartScreeningEvidence {
  evidence_type: string
  source: string
  field?: string
  value?: any
  condition?: string
  title?: string
  event_date?: string
  summary?: string
}

export interface SmartScreeningCandidate {
  symbol: string
  name?: string
  market?: string
  industry?: string
  score: number
  matched_conditions: string[]
  reasons: string[]
  evidence: SmartScreeningEvidence[]
  data: Record<string, any>
}

export interface SmartScreeningRunResp {
  total: number
  items: SmartScreeningCandidate[]
  dsl?: Record<string, any>
  plan: Record<string, any>
  audit: Record<string, any>
  data_gaps: string[]
  deep_analysis_tasks: any[]
  synthesis?: {
    summary: string
    top_symbols: string[]
    key_reasons: string[]
    risks: string[]
  }
}

export interface SmartScreeningNaturalLanguageReq {
  query: string
  as_of?: string | null
  use_database?: boolean
  include_deep_analysis_tasks?: boolean
  deep_analysis_top_n?: number
}

// 筛选字段配置
export interface FieldInfo {
  name: string
  display_name: string
  field_type: string
  data_type: string
  description: string
  supported_operators: string[]
}

export interface FieldConfigResponse {
  fields: Record<string, FieldInfo>
  categories: Record<string, string[]>
}

// 行业列表响应
export interface IndustryOption {
  value: string
  label: string
  count: number
}

export interface IndustriesResponse {
  industries: IndustryOption[]
  total: number
}

export const screeningApi = {
  run: (payload: ScreeningRunReq, options?: { timeout?: number }) =>
    ApiClient.post<ScreeningRunResp>('/api/screening/run', payload, { timeout: options?.timeout ?? 120000 }),
  runSmartNaturalLanguage: (payload: SmartScreeningNaturalLanguageReq, options?: { timeout?: number }) =>
    ApiClient.post<SmartScreeningRunResp>('/api/screening/smart/run-natural-language', payload, { timeout: options?.timeout ?? 120000 }),
  getFields: () => ApiClient.get<FieldConfigResponse>('/api/screening/fields'),
  getIndustries: () => ApiClient.get<IndustriesResponse>('/api/screening/industries')
}
