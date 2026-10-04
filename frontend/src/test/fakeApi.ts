import { vi } from 'vitest'

export interface FakeCall {
  method: string
  url: string
  authorization: string | null
}

export type FakeReply = { status: number; data?: unknown } | 'network-error'
export type FakeHandler = (call: FakeCall) => FakeReply

/**
 * Loads the API modules fresh (their state is module-level) on top of an axios
 * whose adapter is replaced by `handler`, so no real HTTP request is made.
 */
export async function loadFreshApi(handler: FakeHandler) {
  vi.resetModules()
  const { default: axios, AxiosError } = await import('axios')

  const calls: FakeCall[] = []
  axios.defaults.adapter = async (config) => {
    const call: FakeCall = {
      method: (config.method ?? 'get').toUpperCase(),
      url: config.url ?? '',
      authorization: String(config.headers.get('Authorization') ?? '') || null,
    }
    calls.push(call)

    const reply = handler(call)
    if (reply === 'network-error') throw new AxiosError('Network Error', 'ERR_NETWORK', config)

    const response = { data: reply.data, status: reply.status, statusText: '', headers: {}, config }
    if (reply.status >= 200 && reply.status < 300) return response
    throw new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, null, response)
  }

  const client = await import('../services/apiClient')
  const { tokenStorage } = await import('../lib/tokenStorage')
  const auth = await import('../services/authService')
  return { ...client, tokenStorage, auth, calls }
}

export const USER = {
  id: 1,
  email: 'ana@example.com',
  first_name: '',
  last_name: '',
  is_staff: false,
  profile: { is_membership_active: false, membership_expires_at: null, membership_status: 'FREE' },
} as const
