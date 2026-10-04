import type { Profile } from '../types/auth'

const DAY_MS = 24 * 60 * 60 * 1000

export type MembershipView =
  | { kind: 'vip'; expiresAt: Date | null; daysLeft: number | null }
  | { kind: 'expired'; expiredAt: Date }
  | { kind: 'free' }

/**
 * What to show about the membership. The backend decides who is VIP
 * (`membership_status`); this only derives the wording around it.
 */
export function describeMembership(profile: Profile, now: Date = new Date()): MembershipView {
  const expiresAt = profile.membership_expires_at ? new Date(profile.membership_expires_at) : null

  if (profile.membership_status === 'VIP') {
    const daysLeft = expiresAt ? Math.max(0, Math.ceil((expiresAt.getTime() - now.getTime()) / DAY_MS)) : null
    return { kind: 'vip', expiresAt, daysLeft }
  }
  // It was VIP and lapsed: the flag is still on but the date is in the past.
  if (profile.is_membership_active && expiresAt) return { kind: 'expired', expiredAt: expiresAt }
  return { kind: 'free' }
}

export function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('es', { dateStyle: 'long' }).format(date)
}

export function formatDaysLeft(days: number): string {
  if (days <= 0) return 'vence hoy'
  return days === 1 ? 'queda 1 día' : `quedan ${days} días`
}
