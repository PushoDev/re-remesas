export type MembershipStatus = 'FREE' | 'VIP'

export interface Profile {
  is_membership_active: boolean
  membership_expires_at: string | null
  membership_status: MembershipStatus
}

export interface User {
  id: number
  email: string
  first_name: string
  last_name: string
  is_staff: boolean
  profile: Profile
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest {
  email: string
  password: string
  first_name?: string
  last_name?: string
}

/** The refresh token is never in a body: it lives in an httpOnly cookie. */
export interface AccessTokenResponse {
  access: string
}

export interface RegisterResponse extends AccessTokenResponse {
  user: User
}
