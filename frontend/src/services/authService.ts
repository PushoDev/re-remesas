import { tokenStorage } from '../lib/tokenStorage'
import type { LoginRequest, RegisterRequest, RegisterResponse, AccessTokenResponse, User } from '../types/auth'
import { apiClient, refreshAccessToken } from './apiClient'

export async function getMe(): Promise<User> {
  const { data } = await apiClient.get<User>('/users/me/')
  return data
}

export async function register(payload: RegisterRequest): Promise<User> {
  const { data } = await apiClient.post<RegisterResponse>('/auth/register/', payload)
  tokenStorage.set(data.access)
  return data.user
}

export async function login(payload: LoginRequest): Promise<User> {
  const { data } = await apiClient.post<AccessTokenResponse>('/auth/login/', payload)
  tokenStorage.set(data.access)
  return getMe()
}

/** Always drops the local token, even if the server could not be reached. */
export async function logout(): Promise<void> {
  try {
    await apiClient.post('/auth/logout/')
  } finally {
    tokenStorage.clear()
  }
}

/**
 * On app start: tries to recover the session from the refresh cookie.
 * Returns the user, or null when there is no valid session.
 */
export async function restoreSession(): Promise<User | null> {
  try {
    await refreshAccessToken()
    return await getMe()
  } catch {
    tokenStorage.clear()
    return null
  }
}
