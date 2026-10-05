import { describe, expect, it } from 'vitest'
import { formatMoney } from './money'

describe('formatMoney', () => {
  it('formats the string amount with a decimal comma and the currency', () => {
    expect(formatMoney('9.99', 'USD')).toBe('9,99 USD')
    expect(formatMoney('99.00', 'USD')).toBe('99,00 USD')
    expect(formatMoney('1234.5', 'EUR')).toBe('1.234,50 EUR')
  })
})
