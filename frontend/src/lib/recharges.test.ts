import { describe, expect, it } from 'vitest'
import type { CatalogPackage } from '../types/recharges'
import { contactToInput, discountAmount, formatPhone, groupByKind, outcomeMessage, phoneFromInput } from './recharges'

const pkg = (code: string, kind: CatalogPackage['kind']): CatalogPackage => ({
  code, name: code, kind, kind_display: kind, price: '5.00', currency: 'USD', description: '', active_promotion: null,
})

describe('groupByKind', () => {
  it('splits by type in a fixed order and drops empty groups', () => {
    const groups = groupByKind([pkg('c', 'COMBO'), pkg('s1', 'BALANCE'), pkg('d', 'DATA'), pkg('s2', 'BALANCE')])
    expect(groups.map((group) => group.kind)).toEqual(['BALANCE', 'DATA', 'COMBO'])
  })

  it('keeps the order the server gave inside each group', () => {
    const groups = groupByKind([pkg('s2', 'BALANCE'), pkg('s1', 'BALANCE')])
    expect(groups[0].packages.map((item) => item.code)).toEqual(['s2', 's1'])
  })

  it('is empty for an empty catalog', () => {
    expect(groupByKind([])).toEqual([])
  })
})

describe('phoneFromInput', () => {
  it.each([
    ['5123 4567', '+5351234567'],
    ['51234567', '+5351234567'],
    ['+53 5123 4567', '+5351234567'],
    ['53 5123 4567', '+5351234567'],
    ['5123-4567', '+5351234567'],
  ])('accepts %s', (raw, expected) => {
    expect(phoneFromInput(raw)).toBe(expected)
  })

  it.each(['', '   ', '2123 4567', '5123 456', '5123 45678', 'hola', '+34 612345678'])('rejects %j', (raw) => {
    expect(phoneFromInput(raw)).toBeNull()
  })
})

describe('contactToInput', () => {
  it('shows the 8 digits after the fixed prefix, in two groups', () => {
    expect(contactToInput('+5351234567')).toBe('5123 4567')
  })

  it('round-trips with phoneFromInput', () => {
    expect(phoneFromInput(contactToInput('+5351234567'))).toBe('+5351234567')
  })
})

describe('outcomeMessage', () => {
  it('celebrates a delivered top-up', () => {
    expect(outcomeMessage('SUCCESS', 'SUCCEEDED').tone).toBe('ok')
  })

  it('says it is in progress while processing', () => {
    expect(outcomeMessage('PROCESSING', 'SUCCEEDED')).toMatchObject({ tone: 'info' })
  })

  it('asks for the payment while pending', () => {
    expect(outcomeMessage('PENDING_PAYMENT', 'PENDING').text).toMatch(/pago/)
  })

  it('promises a refund review when the money was taken but the top-up failed', () => {
    expect(outcomeMessage('FAILED', 'SUCCEEDED').text).toMatch(/reembolso/)
  })

  it('says nothing was charged when the payment itself failed', () => {
    expect(outcomeMessage('FAILED', 'FAILED').text).toMatch(/ningún cobro/)
  })

  it('never reveals how the provider is implemented', () => {
    const statuses = ['PENDING_PAYMENT', 'PROCESSING', 'SUCCESS', 'FAILED'] as const
    const payments = ['PENDING', 'SUCCEEDED', 'FAILED'] as const
    for (const status of statuses) {
      for (const payment of payments) {
        expect(outcomeMessage(status, payment).text.toLowerCase()).not.toMatch(/mock|simul|demo|prueba/)
      }
    }
  })
})

describe('discountAmount', () => {
  it.each([
    ['10.00', '9.50', '0.50'],
    ['10.00', '10.00', '0.00'],
    ['9.99', '9.49', '0.50'],
    ['0.10', '0.07', '0.03'],
  ])('%s - %s = %s exactly', (base, total, expected) => {
    expect(discountAmount(base, total)).toBe(expected)
  })

  it('has no floating point error where a float would', () => {
    expect(discountAmount('0.30', '0.10')).toBe('0.20')
  })

  it('is null for something that cannot be a discount', () => {
    expect(discountAmount('5.00', '6.00')).toBeNull()
    expect(discountAmount('abc', '1.00')).toBeNull()
  })
})

describe('formatPhone', () => {
  it('groups a normalized number in 4 + 4', () => {
    expect(formatPhone('+5351234567')).toBe('+53 5123 4567')
  })

  it('leaves anything else as it came', () => {
    expect(formatPhone('+34612345678')).toBe('+34612345678')
    expect(formatPhone('')).toBe('')
  })
})
