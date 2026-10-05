export type PaymentMethodCode = 'STRIPE' | 'PAYPAL' | 'MERCADO_PAGO' | 'ENZONA' | 'WISE' | 'ZELLE' | 'CASH'
export type PaymentStatus = 'PENDING' | 'SUCCEEDED' | 'FAILED'

export interface MembershipPlan {
  code: string
  name: string
  period: 'MONTHLY' | 'ANNUAL'
  price: string
  currency: string
  duration_days: number
  recharge_discount_percent: string
  benefits: string[]
}

export interface Payment {
  reference: string
  purpose: 'MEMBERSHIP' | 'REMITTANCE' | 'RECHARGE'
  method: PaymentMethodCode
  provider: string
  status: PaymentStatus
  amount: string
  currency: string
  instructions: string
  /** Where to pay while pending (simulated gateway); null otherwise. */
  checkout_url: string | null
  requires_manual_confirmation: boolean
  created_at: string
  confirmed_at: string | null
}

export interface SubscribeRequest {
  plan_code: string
  payment_method: PaymentMethodCode
}

export interface SubscribeResult {
  subscription: { id: number; status: string; plan: MembershipPlan }
  payment: Payment
}
