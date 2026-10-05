import { AxiosError } from 'axios'
import { describe, expect, it } from 'vitest'
import { parseApiError } from './apiErrors'

function apiError(status: number, data?: unknown) {
  const config = { headers: {} } as never
  return new AxiosError('fail', 'ERR_BAD_REQUEST', config, null, {
    status,
    data,
    statusText: '',
    headers: {},
    config,
  })
}

describe('parseApiError', () => {
  it('collects validation errors by field', () => {
    const info = parseApiError(apiError(400, { email: ['Ya existe una cuenta.'], password: ['Muy corta.', 'Sin número.'] }))

    expect(info.fieldErrors).toEqual({ email: ['Ya existe una cuenta.'], password: ['Muy corta.', 'Sin número.'] })
    expect(info.message).toBe('Ya existe una cuenta.')
  })

  it('uses `detail` as the message', () => {
    const info = parseApiError(apiError(401, { detail: 'La sesión expiró.' }))

    expect(info.message).toBe('La sesión expiró.')
    expect(info.fieldErrors).toEqual({})
  })

  it('translates the bad-credentials answer of the login', () => {
    const info = parseApiError(apiError(401, { detail: 'No active account found with the given credentials' }))

    expect(info.message).toBe('Correo o contraseña incorrectos.')
  })

  it('reports a connection problem when there is no response', () => {
    const error = new AxiosError('Network Error', 'ERR_NETWORK')

    expect(parseApiError(error).message).toMatch(/conectar/)
  })

  it('hides server errors behind a generic message', () => {
    const info = parseApiError(apiError(500, '<html>Traceback...</html>'))

    expect(info.message).toMatch(/servidor/)
    expect(info.message).not.toMatch(/Traceback/)
  })

  it('handles non-axios errors and unexpected bodies', () => {
    expect(parseApiError(new Error('boom')).message).toMatch(/inesperado/)
    expect(parseApiError(apiError(400, null)).message).toMatch(/inesperado/)
  })
})
