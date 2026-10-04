import { describe, expect, it } from 'vitest'
import type { Profile } from '../types/auth'
import { describeMembership, formatDaysLeft } from './membership'

const now = new Date('2026-10-04T12:00:00Z')
const profile = (overrides: Partial<Profile>): Profile => ({
  is_membership_active: false,
  membership_expires_at: null,
  membership_status: 'FREE',
  ...overrides,
})

describe('describeMembership', () => {
  it('VIP with an expiration counts the days left', () => {
    const view = describeMembership(
      profile({ is_membership_active: true, membership_status: 'VIP', membership_expires_at: '2026-11-03T12:00:00Z' }),
      now,
    )
    expect(view).toMatchObject({ kind: 'vip', daysLeft: 30 })
  })

  it('VIP without an expiration date has no countdown', () => {
    const view = describeMembership(profile({ is_membership_active: true, membership_status: 'VIP' }), now)
    expect(view).toEqual({ kind: 'vip', expiresAt: null, daysLeft: null })
  })

  it('free user', () => {
    expect(describeMembership(profile({}), now)).toEqual({ kind: 'free' })
  })

  it('a lapsed VIP (flag on, date in the past) is reported as expired', () => {
    const view = describeMembership(
      profile({ is_membership_active: true, membership_expires_at: '2026-10-03T12:00:00Z' }),
      now,
    )
    expect(view.kind).toBe('expired')
  })

  it('trusts the backend: flag off with a future date is just free', () => {
    const view = describeMembership(profile({ membership_expires_at: '2027-01-01T00:00:00Z' }), now)
    expect(view).toEqual({ kind: 'free' })
  })
})

describe('formatDaysLeft', () => {
  it('handles singular, plural and today', () => {
    expect(formatDaysLeft(0)).toBe('vence hoy')
    expect(formatDaysLeft(1)).toBe('queda 1 día')
    expect(formatDaysLeft(30)).toBe('quedan 30 días')
  })
})
