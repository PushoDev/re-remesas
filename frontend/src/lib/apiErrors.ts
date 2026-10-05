import { isAxiosError } from 'axios'

export interface ApiErrorInfo {
  /** Message ready to show to the user. */
  message: string
  /** Backend validation errors by field, e.g. { email: ['...'] }. */
  fieldErrors: Record<string, string[]>
}

const GENERIC = 'Ocurrió un error inesperado. Inténtalo de nuevo.'
const NETWORK = 'No se pudo conectar con el servidor. Revisa tu conexión.'
const SERVER = 'El servidor tuvo un problema. Inténtalo de nuevo en unos minutos.'
const BAD_CREDENTIALS = 'Correo o contraseña incorrectos.'

function toStrings(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === 'string')
  return []
}

/** Turns anything thrown by the API client into a message plus field errors. */
export function parseApiError(error: unknown): ApiErrorInfo {
  if (!isAxiosError(error)) return { message: GENERIC, fieldErrors: {} }

  const response = error.response
  if (!response) return { message: NETWORK, fieldErrors: {} }
  if (response.status >= 500) return { message: SERVER, fieldErrors: {} }

  const data: unknown = response.data
  if (typeof data !== 'object' || data === null) return { message: GENERIC, fieldErrors: {} }

  const record = data as Record<string, unknown>
  const detail = toStrings(record.detail)[0]
  if (response.status === 401 && detail?.startsWith('No active account')) {
    return { message: BAD_CREDENTIALS, fieldErrors: {} }
  }

  const fieldErrors: Record<string, string[]> = {}
  for (const [field, value] of Object.entries(record)) {
    if (field === 'detail') continue
    const messages = toStrings(value)
    if (messages.length > 0) fieldErrors[field] = messages
  }

  const message = detail ?? fieldErrors.non_field_errors?.[0] ?? Object.values(fieldErrors)[0]?.[0] ?? GENERIC
  return { message, fieldErrors }
}
