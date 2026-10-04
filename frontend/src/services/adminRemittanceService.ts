import type {
  AdminOverview,
  AdminRemittanceDetail,
  AdminRemittanceParams,
  AdminRemittanceRow,
  StatusChangeRequest,
} from '../types/adminRemittances'
import type { Page } from '../types/remittances'
import { apiClient } from './apiClient'

export async function getAdminOverview(): Promise<AdminOverview> {
  const { data } = await apiClient.get<AdminOverview>('/admin/overview/')
  return data
}

export async function listAdminRemittances(params: AdminRemittanceParams): Promise<Page<AdminRemittanceRow>> {
  const { data } = await apiClient.get<Page<AdminRemittanceRow>>('/admin/remittances/', { params })
  return data
}

export async function getAdminRemittance(trackingId: string): Promise<AdminRemittanceDetail> {
  const { data } = await apiClient.get<AdminRemittanceDetail>(`/admin/remittances/${encodeURIComponent(trackingId)}/`)
  return data
}

/** PAID confirms a manual payment, COMPLETED records the delivery, CANCELLED needs a reason. */
export async function changeRemittanceStatus(trackingId: string, body: StatusChangeRequest): Promise<AdminRemittanceDetail> {
  const { data } = await apiClient.patch<AdminRemittanceDetail>(`/admin/remittances/${encodeURIComponent(trackingId)}/status/`, body)
  return data
}

/** The proof file. It has no public URL: it is fetched with the administrator's token as a blob. */
export async function fetchProof(trackingId: string): Promise<Blob> {
  const { data } = await apiClient.get<Blob>(`/admin/remittances/${encodeURIComponent(trackingId)}/proof/`, {
    responseType: 'blob',
  })
  return data
}
