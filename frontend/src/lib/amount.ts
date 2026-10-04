import { toScaled } from './decimal'

export type AmountParse =
  | { valid: true; normalized: string }
  /** `reason` is null while the field is empty (nothing to complain about yet). */
  | { valid: false; normalized: ''; reason: string | null }

const invalid = (reason: string | null): AmountParse => ({ valid: false, normalized: '', reason })

/**
 * What the user typed in the amount box -> the plain text the API expects ("100.5").
 * Accepts a decimal comma. Limits (minimum/maximum) are the server's call.
 */
export function parseAmountInput(raw: string): AmountParse {
  const text = raw.trim()
  if (text === '') return invalid(null)

  const dotted = text.replace(',', '.')
  if (!/^\d+(\.\d*)?$/.test(dotted)) return invalid('Escribe solo números, por ejemplo 100 o 100,50.')

  const [whole, fraction = ''] = dotted.split('.')
  if (fraction.length > 2) return invalid('El monto admite máximo 2 decimales.')

  const normalized = `${whole.replace(/^0+(?=\d)/, '')}${fraction ? `.${fraction}` : ''}`
  if (toScaled(normalized, 2) === 0n) return invalid('El monto debe ser mayor que 0.')
  return { valid: true, normalized }
}
