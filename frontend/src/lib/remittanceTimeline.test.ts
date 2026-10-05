import { describe, expect, it } from 'vitest'
import type { CustomerStatusEntry } from '../types/remittances'
import { customerTimeline, nextStepText, statusChangeMessage } from './remittanceTimeline'

const at = '2026-10-04T12:00:00Z'
const entry = (from: CustomerStatusEntry['from_status'], to: CustomerStatusEntry['to_status'], label: string, event = true): CustomerStatusEntry => ({
  from_status: from, to_status: to, to_status_display: label, changed_at: at, event,
})

describe('customerTimeline', () => {
  it('turns the history into plain steps, keeping the order', () => {
    const items = customerTimeline([
      entry('', 'PENDING_PAYMENT', 'Pendiente de pago'),
      entry('PENDING_PAYMENT', 'PENDING_PAYMENT', 'Pendiente de pago', false),
      entry('PENDING_PAYMENT', 'PAID', 'Pagado'),
      entry('PAID', 'COMPLETED', 'Completado'),
    ])

    expect(items.map((item) => item.title)).toEqual([
      'Solicitud creada', 'Enviaste tu comprobante de pago', 'Pagado', 'Completado'])
    expect(items.map((item) => item.event)).toEqual([true, false, true, true])
  })

  it('colours the final states', () => {
    const [paid, completed, cancelled] = customerTimeline([
      entry('PENDING_PAYMENT', 'PAID', 'Pagado'), entry('PAID', 'COMPLETED', 'Completado'),
      entry('PAID', 'CANCELLED', 'Cancelado'),
    ])

    expect([paid.tone, completed.tone, cancelled.tone]).toEqual(['default', 'success', 'danger'])
  })

  it('an empty history is an empty timeline', () => {
    expect(customerTimeline([])).toEqual([])
  })
})

describe('nextStepText', () => {
  it('differs for a manual and an online payment while it is pending', () => {
    expect(nextStepText('PENDING_PAYMENT', true)).toMatch(/comprobante/)
    expect(nextStepText('PENDING_PAYMENT', false)).toMatch(/completar el pago/)
  })

  it('says something sensible for every state', () => {
    for (const status of ['PENDING_PAYMENT', 'PAID', 'COMPLETED', 'CANCELLED'] as const) {
      expect(nextStepText(status, false).length).toBeGreaterThan(10)
    }
    expect(nextStepText('CANCELLED', false)).toMatch(/reembolso/)
  })
})

describe('statusChangeMessage', () => {
  it('announces a real change using the readable label', () => {
    expect(statusChangeMessage('PENDING_PAYMENT', 'PAID', 'Pagado')).toBe('Tu remesa cambió de estado: ahora está «Pagado».')
  })

  it.each([
    [undefined, 'PAID'], // first load: nothing to announce
    ['PAID', 'PAID'],    // unchanged
    ['PAID', undefined],
  ])('stays quiet for %j -> %j', (previous, next) => {
    expect(statusChangeMessage(previous, next, 'X')).toBeNull()
  })
})
