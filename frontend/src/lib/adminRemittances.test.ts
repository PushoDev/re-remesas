import { describe, expect, it } from 'vitest'
import { ACTION_LABEL, isOrdering, validateCancelReason, visibleActions } from './adminRemittances'

describe('visibleActions', () => {
  it('keeps the display order whatever order the API sends', () => {
    expect(visibleActions(['cancel', 'complete', 'confirm_payment'])).toEqual(['confirm_payment', 'complete', 'cancel'])
  })

  it.each([
    [['confirm_payment', 'cancel'], ['confirm_payment', 'cancel']],
    [['complete', 'cancel'], ['complete', 'cancel']],
    [['cancel'], ['cancel']],
    [[], []],
  ])('%j -> %j', (allowed, expected) => {
    expect(visibleActions(allowed)).toEqual(expected)
  })

  it('ignores actions it does not know (a newer backend must not break the screen)', () => {
    expect(visibleActions(['refund', 'complete', 'teleport'])).toEqual(['complete'])
  })

  it('every action has a label', () => {
    for (const action of visibleActions(['confirm_payment', 'complete', 'cancel'])) {
      expect(ACTION_LABEL[action]).toBeTruthy()
    }
  })
})

describe('validateCancelReason', () => {
  it.each(['', '   ', '\n'])('asks for a reason when it is %j', (reason) => {
    expect(validateCancelReason(reason)).toMatch(/motivo/)
  })

  it('rejects a reason that is too short', () => {
    expect(validateCancelReason('no')).toMatch(/al menos 5/)
  })

  it('rejects one that is too long, like the backend', () => {
    expect(validateCancelReason('x'.repeat(501))).toMatch(/500/)
  })

  it('accepts a real reason, ignoring surrounding spaces', () => {
    expect(validateCancelReason('  Datos del destinatario falsos  ')).toBeNull()
    expect(validateCancelReason('x'.repeat(500))).toBeNull()
  })
})

describe('isOrdering', () => {
  it('accepts only the offered orderings (the URL is untrusted)', () => {
    expect(isOrdering('-amount_sent')).toBe(true)
    expect(isOrdering('sender__password')).toBe(false)
    expect(isOrdering(null)).toBe(false)
  })
})
