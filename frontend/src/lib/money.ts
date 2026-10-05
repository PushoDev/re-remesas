import { formatDecimal } from './decimal'

/** "9.99" + "USD" -> "9,99 USD". Pure string work: amounts are never floats. */
export function formatMoney(amount: string, currency: string): string {
  return `${formatDecimal(amount, 2)} ${currency}`
}
