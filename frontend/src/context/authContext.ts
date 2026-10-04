import { createContext } from 'react'
import type { LoginRequest, RegisterRequest, User } from '../types/auth'

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous'

export interface AuthContextValue {
  user: User | null
  status: AuthStatus
  login: (payload: LoginRequest) => Promise<User>
  register: (payload: RegisterRequest) => Promise<User>
  logout: () => Promise<void>
  /** Re-reads the user from the API (e.g. after a payment changed the membership). */
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
