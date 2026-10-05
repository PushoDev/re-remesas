import { describe, expect, it } from 'vitest'
import { safeInternalPath } from './redirect'

const FALLBACK = '/membership/result'

describe('safeInternalPath', () => {
  it.each(['/remittances/RR-20261004-ABCDE?created=1', '/profile', '/membership/result?payment=abc', '/'])(
    'keeps the internal path %j', (path) => {
      expect(safeInternalPath(path, FALLBACK)).toBe(path)
    },
  )

  it.each([
    'https://evil.example/phish', 'http://evil.example', '//evil.example', '///evil.example', '\\\\evil.example',
    '/\\evil.example', 'javascript:alert(1)', 'evil.example', 'remittances/x', '/ok\nhttp://evil', '',
  ])('refuses %j and uses the fallback', (path) => {
    expect(safeInternalPath(path, FALLBACK)).toBe(FALLBACK)
  })

  it('falls back when there is nothing', () => {
    expect(safeInternalPath(null, FALLBACK)).toBe(FALLBACK)
    expect(safeInternalPath(undefined, FALLBACK)).toBe(FALLBACK)
  })
})
