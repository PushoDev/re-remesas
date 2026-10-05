import type { Payment, PaymentMethodCode } from './memberships'
import type { CurrencyCode, DeliveryMethod, RemittanceStatus } from './remittances'

export interface AdminOverview {
  remittances: {
    total: number
    pending_payment: number
    paid: number
    completed: number
    cancelled: number
    /** Manual payments (Zelle, Wise, cash) already carrying a reference or file: waiting for an administrator. */
    needs_review: number
  }
  recharge_orders: { total: number }
  memberships: { active_vip: number }
  generated_at: string
}

export interface AdminRemittanceRow {
  tracking_id: string
  status: RemittanceStatus
  status_display: string
  amount_sent: string
  currency: CurrencyCode
  amount_cup: string
  is_vip_rate: boolean
  sender_email: string
  recipient_name: string
  delivery_method_display: string
  payment_method: PaymentMethodCode
  payment_method_display: string
  payment_provider: 'MOCK' | 'MANUAL' | string
  payment_status: Payment['status']
  has_proof: boolean
  created_at: string
  updated_at: string
}

export interface AdminStatusLogEntry {
  from_status: RemittanceStatus | ''
  from_status_display: string
  to_status: RemittanceStatus
  to_status_display: string
  source: 'CUSTOMER' | 'PAYMENT' | 'ADMIN'
  source_display: string
  changed_by_email: string | null
  note: string
  changed_at: string
}

export interface AdminRemittanceDetail {
  tracking_id: string
  status: RemittanceStatus
  status_display: string
  amount_sent: string
  currency: CurrencyCode
  target_currency: 'CUP'
  base_rate_used: string
  spread_percent_used: string
  effective_rate_used: string
  amount_cup: string
  is_vip_rate: boolean
  recipient_name: string
  recipient_phone: string
  recipient_address: string
  recipient_account: string
  delivery_method: DeliveryMethod
  delivery_method_display: string
  payment_method: PaymentMethodCode
  payment_method_display: string
  created_at: string
  updated_at: string
  sender: { email: string; first_name: string; last_name: string; membership_status: 'FREE' | 'VIP' }
  payment: {
    reference: string
    method: PaymentMethodCode
    provider: string
    status: Payment['status']
    amount: string
    currency: string
    instructions: string
    external_reference: string
    confirmed_at: string | null
    confirmed_by_email: string | null
  }
  payment_reference: string
  has_proof_file: boolean
  status_log: AdminStatusLogEntry[]
  allowed_actions: string[]
}

export type AdminOrdering = 'created_at' | '-created_at' | 'amount_sent' | '-amount_sent' | 'amount_cup' | '-amount_cup' | 'status'

export interface AdminRemittanceParams {
  status?: RemittanceStatus
  search?: string
  ordering?: AdminOrdering
  page?: number
}

export interface StatusChangeRequest {
  status: 'PAID' | 'COMPLETED' | 'CANCELLED'
  note?: string
}
