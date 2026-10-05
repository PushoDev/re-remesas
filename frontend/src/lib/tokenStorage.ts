/**
 * The access token lives only in memory: it disappears on reload and is never
 * readable from localStorage/sessionStorage. The refresh token is an httpOnly
 * cookie managed by the browser and the backend, invisible to JavaScript.
 */
let accessToken: string | null = null

export const tokenStorage = {
  get: (): string | null => accessToken,
  set: (token: string): void => {
    accessToken = token
  },
  clear: (): void => {
    accessToken = null
  },
}
