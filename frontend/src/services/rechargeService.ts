import type {
  CatalogPackage,
  CreateRechargeRequest,
  CreateRechargeResult,
  RechargeListParams,
  RechargeOrder,
  RechargeOrderDetail,
  RechargeQuote,
  RechargeQuoteRequest,
  RecentContact,
} from '../types/recharges'
import type { Page } from '../types/remittances'
import { apiClient } from './apiClient'

/** The catalog, each package with the promotion the server says is current. */
export async function listPackages(): Promise<CatalogPackage[]> {
  const { data } = await apiClient.get<CatalogPackage[]>('/recharges/packages/')
  return data
}

export async function listRecentContacts(): Promise<RecentContact[]> {
  const { data } = await apiClient.get<RecentContact[]>('/recharges/recent-contacts/')
  return data
}

/** What the customer would pay. The server computes it; creating the order repeats the calculation. */
export async function quoteRecharge(payload: RechargeQuoteRequest): Promise<RechargeQuote> {
  const { data } = await apiClient.post<RechargeQuote>('/recharges/quote/', payload)
  return data
}

/** Creates the order and its pending payment. Only phone, package and method are sent: never a price. */
export async function createRecharge(payload: CreateRechargeRequest): Promise<CreateRechargeResult> {
  const { data } = await apiClient.post<CreateRechargeResult>('/recharges/', payload)
  return data
}

export async function listRecharges(params: RechargeListParams): Promise<Page<RechargeOrder>> {
  const { data } = await apiClient.get<Page<RechargeOrder>>('/recharges/', { params })
  return data
}

export async function getRecharge(reference: string): Promise<RechargeOrderDetail> {
  const { data } = await apiClient.get<RechargeOrderDetail>(`/recharges/${encodeURIComponent(reference)}/`)
  return data
}
