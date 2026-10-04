import type { PaymentMethodCode } from '../types/memberships'

export interface PaymentMethodOption {
  code: PaymentMethodCode
  label: string
  /** online: handled by a (simulated) gateway · manual: settled outside the app, confirmed by an administrator */
  kind: 'online' | 'manual'
}

export const PAYMENT_METHODS: PaymentMethodOption[] = [
  { code: 'STRIPE', label: 'Tarjeta (Stripe)', kind: 'online' },
  { code: 'PAYPAL', label: 'PayPal', kind: 'online' },
  { code: 'MERCADO_PAGO', label: 'Mercado Pago', kind: 'online' },
  { code: 'ENZONA', label: 'EnZona', kind: 'online' },
  { code: 'WISE', label: 'Wise', kind: 'manual' },
  { code: 'ZELLE', label: 'Zelle', kind: 'manual' },
  { code: 'CASH', label: 'Efectivo', kind: 'manual' },
]

export function paymentMethodLabel(code: PaymentMethodCode): string {
  return PAYMENT_METHODS.find((method) => method.code === code)?.label ?? code
}

export function isManualMethod(code: PaymentMethodCode): boolean {
  return PAYMENT_METHODS.find((method) => method.code === code)?.kind === 'manual'
}
