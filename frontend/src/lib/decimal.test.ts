import { describe, expect, it } from 'vitest'
import { formatDecimal, fromScaled, previewEffectiveRate, toScaled, trimDecimal } from './decimal'

describe('toScaled / fromScaled', () => {
  it('parses exact decimals without floats', () => {
    expect(toScaled('700.5', 6)).toBe(700500000n)
    expect(toScaled('0.1', 6)).toBe(100000n)
    expect(fromScaled(700500000n, 6)).toBe('700.500000')
    expect(fromScaled(5n, 4)).toBe('0.0005')
  })

  it('accepts a decimal comma', () => {
    expect(toScaled('700,5', 6)).toBe(700500000n)
  })

  it.each(['', 'abc', '-1', '1.2.3', '1e5', '.5', '5.'])('rejects %j', (value) => {
    expect(toScaled(value, 6)).toBeNull()
  })

  it('rejects more decimals than allowed', () => {
    expect(toScaled('1.1234567', 6)).toBeNull()
    expect(toScaled('5.123', 2)).toBeNull()
  })
})

describe('previewEffectiveRate (matches the backend Decimal math)', () => {
  it.each([
    ['700', '5', '665.0000'],
    ['700', '2', '686.0000'],
    ['700.123456', '3.33', '676.8093'],
    ['1.000050', '0', '1.0001'], // half up, not banker's rounding
    ['665.5555', '0', '665.5555'],
    ['0.000001', '99.99', '0.0000'],
    ['1234567.1', '12.5', '1080246.2125'],
  ])('base %s with spread %s -> %s', (base, spread, expected) => {
    expect(previewEffectiveRate(base, spread)).toBe(expected)
  })

  it('returns null for invalid input or a spread of 100 or more', () => {
    expect(previewEffectiveRate('', '5')).toBeNull()
    expect(previewEffectiveRate('700', 'x')).toBeNull()
    expect(previewEffectiveRate('700', '100')).toBeNull()
  })
})

describe('formatting', () => {
  it('trimDecimal removes trailing zeros', () => {
    expect(trimDecimal('700.000000')).toBe('700')
    expect(trimDecimal('665.1200')).toBe('665.12')
    expect(trimDecimal('700')).toBe('700')
  })

  it('formatDecimal groups thousands and uses a decimal comma', () => {
    expect(formatDecimal('700.000000')).toBe('700,00')
    expect(formatDecimal('665.1235')).toBe('665,1235')
    expect(formatDecimal('1234567.5')).toBe('1.234.567,50')
    expect(formatDecimal('1000', 0)).toBe('1.000')
  })
})
