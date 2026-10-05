import type { AdminRechargeOrder, RechargeListParams } from '../types/recharges'
import type { Page } from '../types/remittances'
import { apiClient } from './apiClient'

export async function listAdminRecharges(params: RechargeListParams): Promise<Page<AdminRechargeOrder>> {
  const { data } = await apiClient.get<Page<AdminRechargeOrder>>('/admin/recharges/', { params })
  return data
}
