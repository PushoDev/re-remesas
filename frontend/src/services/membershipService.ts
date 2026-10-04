import type { MembershipPlan, Payment, SubscribeRequest, SubscribeResult } from '../types/memberships'
import { apiClient } from './apiClient'

export async function listPlans(): Promise<MembershipPlan[]> {
  const { data } = await apiClient.get<MembershipPlan[]>('/memberships/plans/')
  return data
}

/** Starts a purchase. It never activates the membership: only a confirmed payment does. */
export async function subscribe(payload: SubscribeRequest): Promise<SubscribeResult> {
  const { data } = await apiClient.post<SubscribeResult>('/memberships/subscribe/', payload)
  return data
}

export async function getPayment(reference: string): Promise<Payment> {
  const { data } = await apiClient.get<Payment>(`/payments/${reference}/`)
  return data
}

/** The "pay" button of the simulated checkout (development only; the API refuses it otherwise). */
export async function confirmMockPayment(reference: string, outcome: 'succeeded' | 'failed'): Promise<Payment> {
  const { data } = await apiClient.post<Payment>(`/payments/mock/${reference}/confirm/`, { outcome })
  return data
}
