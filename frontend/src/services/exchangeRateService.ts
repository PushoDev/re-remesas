import type { AdminExchangeRate, ExchangeRateHistoryEntry, ExchangeRatePayload } from '../types/exchangeRates'
import { apiClient } from './apiClient'

const BASE = '/admin/exchange-rates/'

export async function listExchangeRates(): Promise<AdminExchangeRate[]> {
  const { data } = await apiClient.get<AdminExchangeRate[]>(BASE)
  return data
}

export async function createExchangeRate(payload: ExchangeRatePayload): Promise<AdminExchangeRate> {
  const { data } = await apiClient.post<AdminExchangeRate>(BASE, payload)
  return data
}

/** PATCH: the currency of an existing rate cannot change, so it is not sent. */
export async function updateExchangeRate(
  id: number,
  payload: Omit<ExchangeRatePayload, 'currency'>,
): Promise<AdminExchangeRate> {
  const { data } = await apiClient.patch<AdminExchangeRate>(`${BASE}${id}/`, payload)
  return data
}

/** The API deactivates the rate; its history is kept. */
export async function deactivateExchangeRate(id: number): Promise<void> {
  await apiClient.delete(`${BASE}${id}/`)
}

export async function getExchangeRateHistory(id: number): Promise<ExchangeRateHistoryEntry[]> {
  const { data } = await apiClient.get<ExchangeRateHistoryEntry[]>(`${BASE}${id}/history/`)
  return data
}
