/**
 * Cuban mobile numbers: +53 followed by 8 digits that start with 5. Same rule as the backend
 * (apps/common/phone.py); this copy only gives instant feedback, the server decides.
 * Returns "+53XXXXXXXX", or null when the text is not a valid number.
 */
export function normalizeCubanMobile(raw: string): string | null {
  const text = raw.trim()
  if (/[^\d\s+()\-.]/.test(text)) return null

  let digits = text.replace(/\D/g, '')
  if (text.startsWith('+') || (digits.startsWith('53') && digits.length === 10)) {
    if (!digits.startsWith('53')) return null
    digits = digits.slice(2)
  }
  return /^5\d{7}$/.test(digits) ? `+53${digits}` : null
}
