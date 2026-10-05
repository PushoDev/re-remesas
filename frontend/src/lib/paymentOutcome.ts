import type { Payment } from '../types/memberships'

export type PaymentOutcome = 'paid' | 'failed' | 'in-review' | 'awaiting-payment'

/** What the result screen should tell the user, from the real state of the payment. */
export function paymentOutcome(payment: Pick<Payment, 'status' | 'requires_manual_confirmation'>): PaymentOutcome {
  if (payment.status === 'SUCCEEDED') return 'paid'
  if (payment.status === 'FAILED') return 'failed'
  return payment.requires_manual_confirmation ? 'in-review' : 'awaiting-payment'
}
