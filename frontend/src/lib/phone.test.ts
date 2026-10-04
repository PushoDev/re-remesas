import { describe, expect, it } from 'vitest'
import { normalizeCubanMobile } from './phone'

describe('normalizeCubanMobile (mirrors the backend rule)', () => {
  it.each([
    '+53 5123 4567', '+5351234567', '5351234567', '53-51234567', '(+53) 51234567', '51234567', '  5123 4567  ',
    '5123-4567', '+53.5123.4567',
  ])('accepts %j', (raw) => {
    expect(normalizeCubanMobile(raw)).toBe('+5351234567')
  })

  it.each([
    '', '   ', '5123456', '512345678', '41234567', '71234567', '+54 51234567', '+1 5123 4567', '5311111111',
    'abcdefgh', '5123 45a7', '+53',
  ])('rejects %j', (raw) => {
    expect(normalizeCubanMobile(raw)).toBeNull()
  })

  it('is stable when applied twice', () => {
    const once = normalizeCubanMobile('5123 4567') as string
    expect(normalizeCubanMobile(once)).toBe(once)
  })
})
