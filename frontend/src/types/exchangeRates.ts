export type CurrencyCode = 'USD' | 'EUR'

/** Admin view of a rate. Decimals are strings: they are never floats. */
export interface AdminExchangeRate {
  id: number
  currency: CurrencyCode
  target_currency: string
  base_rate: string
  standard_spread_percent: string
  vip_spread_percent: string
  is_active: boolean
  effective_rate_standard: string
  effective_rate_vip: string
  created_at: string
  updated_at: string
  updated_by_email: string | null
}

export interface ExchangeRateHistoryEntry {
  id: number
  base_rate: string
  standard_spread_percent: string
  vip_spread_percent: string
  is_active: boolean
  changed_by_email: string | null
  changed_at: string
}

export interface ExchangeRatePayload {
  currency: CurrencyCode
  base_rate: string
  standard_spread_percent: string
  vip_spread_percent: string
  is_active: boolean
}
