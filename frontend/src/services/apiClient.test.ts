import { describe, expect, it, vi } from 'vitest'
import { loadFreshApi, type FakeCall } from '../test/fakeApi'

const refreshCalls = (calls: FakeCall[]) => calls.filter((call) => call.url === '/auth/refresh/')

describe('apiClient: access token', () => {
  it('sends the Bearer token when there is one', async () => {
    const api = await loadFreshApi(() => ({ status: 200, data: {} }))
    api.tokenStorage.set('tok-1')

    await api.apiClient.get('/users/me/')

    expect(api.calls[0].authorization).toBe('Bearer tok-1')
  })

  it('sends no Authorization header without a token', async () => {
    const api = await loadFreshApi(() => ({ status: 200, data: {} }))

    await api.apiClient.get('/health/')

    expect(api.calls[0].authorization).toBeNull()
  })
})

describe('apiClient: automatic session renewal', () => {
  it('on a 401 it refreshes once and retries with the new token', async () => {
    const api = await loadFreshApi((call) => {
      if (call.url === '/auth/refresh/') return { status: 200, data: { access: 'tok-new' } }
      return call.authorization === 'Bearer tok-new'
        ? { status: 200, data: { ok: true } }
        : { status: 401, data: { detail: 'expired' } }
    })
    api.tokenStorage.set('tok-old')

    const response = await api.apiClient.get('/users/me/')

    expect(response.data).toEqual({ ok: true })
    expect(refreshCalls(api.calls)).toHaveLength(1)
    expect(api.tokenStorage.get()).toBe('tok-new')
    expect(api.calls.filter((call) => call.url === '/users/me/')).toHaveLength(2)
  })

  it('several parallel 401s share a single refresh', async () => {
    const api = await loadFreshApi((call) => {
      if (call.url === '/auth/refresh/') return { status: 200, data: { access: 'tok-new' } }
      return call.authorization === 'Bearer tok-new' ? { status: 200, data: {} } : { status: 401 }
    })
    api.tokenStorage.set('tok-old')

    await Promise.all([api.apiClient.get('/a/'), api.apiClient.get('/b/'), api.apiClient.get('/c/')])

    expect(refreshCalls(api.calls)).toHaveLength(1)
  })

  it('if the refresh is rejected, it clears the token and notifies once', async () => {
    const api = await loadFreshApi((call) =>
      call.url === '/auth/refresh/' ? { status: 401, data: { detail: 'no session' } } : { status: 401 },
    )
    const expired = vi.fn()
    api.setSessionExpiredHandler(expired)
    api.tokenStorage.set('tok-old')

    await expect(api.apiClient.get('/users/me/')).rejects.toMatchObject({ response: { status: 401 } })

    expect(api.tokenStorage.get()).toBeNull()
    expect(expired).toHaveBeenCalledTimes(1)
  })

  it('a network failure during refresh does NOT end the session', async () => {
    const api = await loadFreshApi((call) => (call.url === '/auth/refresh/' ? 'network-error' : { status: 401 }))
    const expired = vi.fn()
    api.setSessionExpiredHandler(expired)
    api.tokenStorage.set('tok-old')

    await expect(api.apiClient.get('/users/me/')).rejects.toBeDefined()

    expect(api.tokenStorage.get()).toBe('tok-old')
    expect(expired).not.toHaveBeenCalled()
  })

  it('a request that still gets 401 after the retry fails without looping', async () => {
    const api = await loadFreshApi((call) =>
      call.url === '/auth/refresh/' ? { status: 200, data: { access: 'tok-new' } } : { status: 401 },
    )

    await expect(api.apiClient.get('/users/me/')).rejects.toMatchObject({ response: { status: 401 } })

    expect(refreshCalls(api.calls)).toHaveLength(1)
    expect(api.calls.filter((call) => call.url === '/users/me/')).toHaveLength(2)
  })

  it('a 401 from /auth/login/ (bad credentials) never triggers a refresh', async () => {
    const api = await loadFreshApi(() => ({ status: 401, data: { detail: 'No active account found' } }))

    await expect(api.apiClient.post('/auth/login/', {})).rejects.toMatchObject({ response: { status: 401 } })

    expect(refreshCalls(api.calls)).toHaveLength(0)
  })

  it('other errors (400, 500) pass through untouched', async () => {
    const api = await loadFreshApi(() => ({ status: 400, data: { email: ['x'] } }))

    await expect(api.apiClient.post('/auth/register/', {})).rejects.toMatchObject({ response: { status: 400 } })

    expect(refreshCalls(api.calls)).toHaveLength(0)
  })
})
