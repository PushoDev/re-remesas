import type { Payment, PaymentMethodCode } from './memberships'

export type CurrencyCode = 'USD' | 'EUR'

export interface RemittanceQuoteRequest {
  amount: string
  currency: CurrencyCode
}

/** What the backend says the recipient gets. Decimals are strings: never floats. */
export interface RemittanceQuote {
  currency: CurrencyCode
  target_currency: 'CUP'
  amount: string
  base_rate: string
  spread_percent: string
  effective_rate: string
  amount_cup: string
  is_vip_rate: boolean
  /** Only for members: the rate a standard customer would get, and how much they save. */
  standard_effective_rate: string | null
  saving_cup: string | null
}

export type DeliveryMethod = 'CASH_DELIVERY' | 'LOCAL_TRANSFER'
export type RemittanceStatus = 'PENDING_PAYMENT' | 'PAID' | 'COMPLETED' | 'CANCELLED'

export interface CreateRemittanceRequest {
  amount: string
  currency: CurrencyCode
  recipient_name: string
  recipient_phone: string
  delivery_method: DeliveryMethod
  recipient_address: string
  recipient_account: string
  payment_method: PaymentMethodCode
}

/** A remittance as its owner sees it. The money is a snapshot taken when it was created. */
export interface Remittance {
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
}

/** One step of the timeline the customer sees: states and when, never internal notes or who acted. */
export interface CustomerStatusEntry {
  from_status: RemittanceStatus | ''
  to_status: RemittanceStatus
  to_status_display: string
  changed_at: string
  /** false = an annotation (e.g. the customer sent a proof), not a change of state. */
  event: boolean
}

export interface RemittanceDetail extends Remittance {
  payment: Payment
  payment_reference: string
  has_proof_file: boolean
  status_log: CustomerStatusEntry[]
}

export interface CreateRemittanceResult {
  remittance: Remittance
  payment: Payment
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface RemittanceListParams {
  status?: RemittanceStatus
  search?: string
  page?: number
}
