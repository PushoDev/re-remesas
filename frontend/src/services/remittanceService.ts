import type {
  CreateRemittanceRequest,
  CreateRemittanceResult,
  Page,
  Remittance,
  RemittanceDetail,
  RemittanceListParams,
  RemittanceQuote,
  RemittanceQuoteRequest,
} from '../types/remittances'
import { apiClient } from './apiClient'

/** Works signed out; a signed-in member gets the preferential rate automatically. */
export async function quoteRemittance(payload: RemittanceQuoteRequest): Promise<RemittanceQuote> {
  const { data } = await apiClient.post<RemittanceQuote>('/remittances/quote/', payload)
  return data
}

/** Creates the request. The server recomputes every figure; none of the quote's numbers are sent. */
export async function createRemittance(payload: CreateRemittanceRequest): Promise<CreateRemittanceResult> {
  const { data } = await apiClient.post<CreateRemittanceResult>('/remittances/', payload)
  return data
}

export async function listRemittances(params: RemittanceListParams): Promise<Page<Remittance>> {
  const { data } = await apiClient.get<Page<Remittance>>('/remittances/', { params })
  return data
}

export async function getRemittance(trackingId: string): Promise<RemittanceDetail> {
  const { data } = await apiClient.get<RemittanceDetail>(`/remittances/${encodeURIComponent(trackingId)}/`)
  return data
}
