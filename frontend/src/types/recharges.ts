import type { Payment, PaymentMethodCode, PaymentStatus } from './memberships'
import type { Page } from './remittances'

export type RechargeKind = 'BALANCE' | 'DATA' | 'VOICE' | 'COMBO'
export type RechargeStatus = 'PENDING_PAYMENT' | 'PROCESSING' | 'SUCCESS' | 'FAILED'

/** A promotion the server says is current. The browser only draws it. */
export interface RechargePromotion {
  code: string
  title: string
  description: string
  ends_at: string
}

export interface RechargePackage {
  code: string
  name: string
  kind: RechargeKind
  kind_display: string
  price: string
  currency: string
  description: string
}

export interface CatalogPackage extends RechargePackage {
  active_promotion: RechargePromotion | null
}

export interface RechargeQuoteRequest {
  phone_number: string
  package_code: string
}

/** The price breakdown computed by the server. Decimals are strings: never floats. */
export interface RechargeQuote {
  package: RechargePackage
  phone_number: string
  price_base: string
  discount_percent: string
  discount_amount: string
  amount_total: string
  currency: string
  is_vip: boolean
  active_promotion: RechargePromotion | null
}

export interface CreateRechargeRequest extends RechargeQuoteRequest {
  payment_method: PaymentMethodCode
}

/** An order as its owner sees it. The money is a snapshot taken when it was created. */
export interface RechargeOrder {
  reference: string
  phone_number: string
  package: RechargePackage
  price_base: string
  discount_percent_applied: string
  amount_total: string
  currency: string
  promotion: { code: string; title: string; description: string; ends_at: string } | null
  status: RechargeStatus
  status_display: string
  provider_reference: string
  provider_message: string
  created_at: string
  updated_at: string
}

export interface RechargeOrderDetail extends RechargeOrder {
  payment: Payment
}

export interface CreateRechargeResult {
  order: RechargeOrder
  payment: Payment
}

export interface RecentContact {
  phone_number: string
  last_used_at: string
}

export interface AdminRechargeOrder extends RechargeOrder {
  user_email: string
  payment_method: PaymentMethodCode
  payment_status: PaymentStatus
  /** The money was taken but the top-up failed: someone must refund it by hand. */
  needs_refund: boolean
}

export interface RechargeListParams {
  status?: RechargeStatus
  search?: string
  page?: number
}

export type RechargePage<T> = Page<T>
