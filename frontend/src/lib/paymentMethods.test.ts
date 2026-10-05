import { describe, expect, it } from 'vitest'
import { PAYMENT_METHODS, isManualMethod, paymentMethodLabel } from './paymentMethods'

describe('payment methods', () => {
  it('offers the seven methods the backend accepts, each once', () => {
    expect(PAYMENT_METHODS.map((method) => method.code).sort()).toEqual(
      ['CASH', 'ENZONA', 'MERCADO_PAGO', 'PAYPAL', 'STRIPE', 'WISE', 'ZELLE'],
    )
  })

  it('Wise, Zelle and cash are manual; the gateways are not (as the backend decides)', () => {
    expect(['WISE', 'ZELLE', 'CASH'].every((code) => isManualMethod(code as never))).toBe(true)
    expect(['STRIPE', 'PAYPAL', 'MERCADO_PAGO', 'ENZONA'].some((code) => isManualMethod(code as never))).toBe(false)
  })

  it('has a readable label', () => {
    expect(paymentMethodLabel('STRIPE')).toBe('Tarjeta (Stripe)')
  })
})
