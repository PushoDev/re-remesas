/**
 * Exact decimal helpers for money-like strings. The API sends decimals as
 * strings ("700.000000"); they are never turned into JS floats. Parsing uses
 * BigInt scaled integers so a preview matches the backend's Decimal math.
 */
const DECIMAL = /^\d+(\.\d+)?$/

/** "700.5" -> 700500000n (scale 6). null if invalid or with more decimals than `scale`. */
export function toScaled(value: string, scale: number): bigint | null {
  const text = value.trim().replace(',', '.')
  if (!DECIMAL.test(text)) return null
  const [whole, fraction = ''] = text.split('.')
  if (fraction.length > scale) return null
  return BigInt(whole + fraction.padEnd(scale, '0'))
}

export function fromScaled(value: bigint, scale: number): string {
  const digits = value.toString().padStart(scale + 1, '0')
  return scale === 0 ? digits : `${digits.slice(0, -scale)}.${digits.slice(-scale)}`
}

/**
 * Same rule as the backend: base * (100 - spread) / 100, 4 decimals, half up.
 * Only for a live preview in forms; the server is always the authority.
 */
export function previewEffectiveRate(base: string, spread: string): string | null {
  const baseScaled = toScaled(base, 6)
  const spreadScaled = toScaled(spread, 2)
  if (baseScaled === null || spreadScaled === null || spreadScaled >= 10000n) return null
  return fromScaled((baseScaled * (10000n - spreadScaled) + 500000n) / 1000000n, 4)
}

/** "700.000000" -> "700"; "665.1200" -> "665.12". */
export function trimDecimal(value: string): string {
  if (!value.includes('.')) return value
  return value.replace(/0+$/, '').replace(/\.$/, '')
}

/** "1234567.5" -> "1.234.567,50" (es). Pure string work, no floats. */
export function formatDecimal(value: string, minDecimals = 2): string {
  const [whole, fraction = ''] = value.split('.')
  const trimmed = fraction.replace(/0+$/, '')
  const decimals = trimmed.length >= minDecimals ? trimmed : trimmed.padEnd(minDecimals, '0')
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return decimals ? `${grouped},${decimals}` : grouped
}
