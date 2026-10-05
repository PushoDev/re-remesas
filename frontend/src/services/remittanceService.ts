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

/** Sends the reference and/or the file of a manual payment (multipart). The server validates the file's real content. */
export async function submitPaymentProof(trackingId: string, proof: { reference: string; file: File | null }): Promise<RemittanceDetail> {
  const body = new FormData()
  if (proof.reference.trim()) body.append('reference', proof.reference.trim())
  if (proof.file) body.append('file', proof.file)
  const { data } = await apiClient.post<RemittanceDetail>(`/remittances/${encodeURIComponent(trackingId)}/payment-proof/`, body)
  return data
}
