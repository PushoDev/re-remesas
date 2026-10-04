import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { setSessionExpiredHandler } from '../services/apiClient'
import * as authService from '../services/authService'
import type { LoginRequest, RegisterRequest, User } from '../types/auth'
import { AuthContext, type AuthContextValue, type AuthStatus } from './authContext'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [status, setStatus] = useState<AuthStatus>('loading')

  const startSession = useCallback((nextUser: User) => {
    setUser(nextUser)
    setStatus('authenticated')
    return nextUser
  }, [])

  const endSession = useCallback(() => {
    setUser(null)
    setStatus('anonymous')
  }, [])

  // On app start: recover the session from the httpOnly refresh cookie.
  useEffect(() => {
    let cancelled = false
    setSessionExpiredHandler(endSession)
    authService.restoreSession().then((restored) => {
      if (cancelled) return
      if (restored) startSession(restored)
      else endSession()
    })
    return () => {
      cancelled = true
      setSessionExpiredHandler(null)
    }
  }, [startSession, endSession])

  const login = useCallback(
    async (payload: LoginRequest) => startSession(await authService.login(payload)),
    [startSession],
  )

  const register = useCallback(
    async (payload: RegisterRequest) => startSession(await authService.register(payload)),
    [startSession],
  )

  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } finally {
      endSession()
    }
  }, [endSession])

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, login, register, logout }),
    [user, status, login, register, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
