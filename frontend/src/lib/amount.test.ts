import { describe, expect, it } from 'vitest'
import { parseAmountInput } from './amount'

describe('parseAmountInput', () => {
  it.each([
    ['100', '100'],
    ['100.5', '100.5'],
    ['100,50', '100.50'],
    ['  37.45 ', '37.45'],
    ['007', '7'],
    ['0.5', '0.5'],
    ['100.', '100'],
  ])('%j -> %j', (raw, normalized) => {
    expect(parseAmountInput(raw)).toEqual({ valid: true, normalized })
  })

  it('an empty box is not an error yet', () => {
    expect(parseAmountInput('')).toEqual({ valid: false, normalized: '', reason: null })
    expect(parseAmountInput('   ')).toEqual({ valid: false, normalized: '', reason: null })
  })

  it.each(['abc', '1e3', '-5', '+5', '1.2.3', '10 000', '$100'])('rejects %j with a reason', (raw) => {
    const result = parseAmountInput(raw)
    expect(result.valid).toBe(false)
    expect(result.valid === false && result.reason).toMatch(/números/)
  })

  it('rejects more than 2 decimals', () => {
    const result = parseAmountInput('10.123')
    expect(result.valid === false && result.reason).toMatch(/2 decimales/)
  })

  it('rejects zero in any spelling', () => {
    for (const raw of ['0', '0.00', '000', '0,0']) {
      const result = parseAmountInput(raw)
      expect(result.valid === false && result.reason).toMatch(/mayor que 0/)
    }
  })
})
