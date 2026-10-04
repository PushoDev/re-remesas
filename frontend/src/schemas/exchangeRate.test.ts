import { describe, expect, it } from 'vitest'
import { exchangeRateSchema } from './exchangeRate'

const valid = { currency: 'USD', base_rate: '700', standard_spread_percent: '5', vip_spread_percent: '2', is_active: true }

function messages(overrides: Record<string, unknown>): Record<string, string> {
  const result = exchangeRateSchema.safeParse({ ...valid, ...overrides })
  if (result.success) return {}
  return Object.fromEntries(result.error.issues.map((issue) => [String(issue.path[0]), issue.message]))
}

describe('exchangeRateSchema', () => {
  it('accepts valid values, including decimal commas', () => {
    expect(exchangeRateSchema.safeParse(valid).success).toBe(true)
    expect(exchangeRateSchema.safeParse({ ...valid, base_rate: '700,5' }).success).toBe(true)
  })

  it.each([
    ['', 'Ingresa la tasa base.'],
    ['0', 'mayor que 0'],
    ['abc', 'número válido'],
    ['-5', 'número válido'],
    ['1.1234567', 'máximo 6 decimales'],
  ])('base rate %j', (value, expected) => {
    expect(messages({ base_rate: value }).base_rate).toContain(expected)
  })

  it.each([
    ['100', 'menor que 100'],
    ['5.123', 'máximo 2 decimales'],
    ['x', 'número válido'],
    ['', 'Ingresa el margen estándar.'],
  ])('standard spread %j', (value, expected) => {
    expect(messages({ standard_spread_percent: value }).standard_spread_percent).toContain(expected)
  })

  it('the VIP spread cannot be above the standard one', () => {
    expect(messages({ standard_spread_percent: '5', vip_spread_percent: '6' }).vip_spread_percent).toContain(
      'VIP no puede ser mayor',
    )
  })

  it('equal VIP and standard spreads are allowed', () => {
    expect(exchangeRateSchema.safeParse({ ...valid, standard_spread_percent: '4', vip_spread_percent: '4' }).success).toBe(true)
  })

  it('only USD and EUR are valid currencies', () => {
    expect(exchangeRateSchema.safeParse({ ...valid, currency: 'MXN' }).success).toBe(false)
  })
})
