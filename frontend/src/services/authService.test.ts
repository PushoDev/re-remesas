import { describe, expect, it } from 'vitest'
import { loadFreshApi, USER } from '../test/fakeApi'

describe('authService', () => {
  it('login stores the access token and returns the user from /users/me/', async () => {
    const api = await loadFreshApi((call) => {
      if (call.url === '/auth/login/') return { status: 200, data: { access: 'tok-login' } }
      if (call.url === '/users/me/') return { status: 200, data: USER }
      return { status: 404 }
    })

    const user = await api.auth.login({ email: 'ana@example.com', password: 'x' })

    expect(user.email).toBe('ana@example.com')
    expect(api.tokenStorage.get()).toBe('tok-login')
    expect(api.calls.find((call) => call.url === '/users/me/')?.authorization).toBe('Bearer tok-login')
  })

  it('a failed login leaves no token behind', async () => {
    const api = await loadFreshApi(() => ({ status: 401, data: { detail: 'No active account found' } }))

    await expect(api.auth.login({ email: 'a@a.com', password: 'mala' })).rejects.toBeDefined()

    expect(api.tokenStorage.get()).toBeNull()
  })

  it('register stores the access token and returns the new user', async () => {
    const api = await loadFreshApi(() => ({ status: 201, data: { user: USER, access: 'tok-reg' } }))

    const user = await api.auth.register({ email: 'ana@example.com', password: 'Tr3sPatos88x' })

    expect(user.profile.membership_status).toBe('FREE')
    expect(api.tokenStorage.get()).toBe('tok-reg')
  })

  it('logout clears the token even if the server fails', async () => {
    const api = await loadFreshApi(() => 'network-error')
    api.tokenStorage.set('tok')

    await expect(api.auth.logout()).rejects.toBeDefined()

    expect(api.tokenStorage.get()).toBeNull()
  })

  it('restoreSession returns the user when the refresh cookie is valid', async () => {
    const api = await loadFreshApi((call) => {
      if (call.url === '/auth/refresh/') return { status: 200, data: { access: 'tok-restored' } }
      return { status: 200, data: USER }
    })

    const user = await api.auth.restoreSession()

    expect(user?.email).toBe('ana@example.com')
    expect(api.tokenStorage.get()).toBe('tok-restored')
  })

  it('restoreSession returns null when there is no session', async () => {
    const api = await loadFreshApi(() => ({ status: 401, data: { detail: 'No hay una sesión activa.' } }))

    expect(await api.auth.restoreSession()).toBeNull()
    expect(api.tokenStorage.get()).toBeNull()
  })
})
