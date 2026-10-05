import { describe, expect, it } from 'vitest'
import { paymentOutcome } from './paymentOutcome'

describe('paymentOutcome', () => {
  it.each([
    ['SUCCEEDED', false, 'paid'],
    ['SUCCEEDED', true, 'paid'],
    ['FAILED', false, 'failed'],
    ['PENDING', true, 'in-review'],
    ['PENDING', false, 'awaiting-payment'],
  ] as const)('%s (manual=%s) -> %s', (status, manual, expected) => {
    expect(paymentOutcome({ status, requires_manual_confirmation: manual })).toBe(expected)
  })
})
