import axios, { isAxiosError, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { tokenStorage } from '../lib/tokenStorage'
import type { AccessTokenResponse } from '../types/auth'

const baseURL = import.meta.env.VITE_API_BASE_URL

export const apiClient = axios.create({ baseURL, withCredentials: true })

// Bare client for the refresh call: it must not go through the interceptors
// below, otherwise a failed refresh would try to refresh itself forever.
const refreshClient = axios.create({ baseURL, withCredentials: true })

type RetriableRequest = InternalAxiosRequestConfig & { _retried?: boolean }

let refreshInFlight: Promise<string> | null = null
let onSessionExpired: (() => void) | null = null

/** The auth layer registers here to learn when the session can't be renewed. */
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler
}

/**
 * Asks the backend for a new access token using the httpOnly refresh cookie.
 * Concurrent callers share one request: the refresh token rotates, so a second
 * parallel call would be rejected.
 */
export function refreshAccessToken(): Promise<string> {
  refreshInFlight ??= refreshClient
    .post<AccessTokenResponse>('/auth/refresh/')
    .then((response) => {
      tokenStorage.set(response.data.access)
      return response.data.access
    })
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

function isAuthEndpoint(url: string | undefined): boolean {
  return url?.startsWith('/auth/') ?? false
}

function isRejectedSession(error: unknown): boolean {
  return isAxiosError(error) && (error.response?.status === 401 || error.response?.status === 403)
}

apiClient.interceptors.request.use((config) => {
  const token = tokenStorage.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetriableRequest | undefined

    // Only an expired access token on a normal request is worth a refresh. A 401
    // from /auth/* (wrong password, no cookie) is a real answer, and a request
    // that was already retried once must not loop.
    if (!request || error.response?.status !== 401 || request._retried || isAuthEndpoint(request.url)) {
      throw error
    }

    request._retried = true
    try {
      await refreshAccessToken()
    } catch (refreshError) {
      // Only a rejected refresh ends the session; a network blip does not.
      if (isRejectedSession(refreshError)) {
        tokenStorage.clear()
        onSessionExpired?.()
      }
      throw error
    }
    return apiClient(request) // the request interceptor attaches the new token
  },
)
