import { fromScaled, toScaled } from './decimal'
import { normalizeCubanMobile } from './phone'
import type { CatalogPackage, RechargeKind, RechargeStatus } from '../types/recharges'
import type { PaymentStatus } from '../types/memberships'

export const KIND_GROUPS: { kind: RechargeKind; title: string }[] = [
  { kind: 'BALANCE', title: 'Saldo' },
  { kind: 'DATA', title: 'Datos' },
  { kind: 'VOICE', title: 'Voz' },
  { kind: 'COMBO', title: 'Combos de datos y voz' },
]

/** The catalog split by type, in a fixed order, without empty groups. Keeps the server's order inside each. */
export function groupByKind(packages: CatalogPackage[]): { kind: RechargeKind; title: string; packages: CatalogPackage[] }[] {
  return KIND_GROUPS.map((group) => ({ ...group, packages: packages.filter((pkg) => pkg.kind === group.kind) }))
    .filter((group) => group.packages.length > 0)
}

/** What the customer typed (with or without +53, any usual separators) -> "+53XXXXXXXX", or null. */
export function phoneFromInput(raw: string): string | null {
  if (!raw.trim()) return null
  return normalizeCubanMobile(raw) ?? normalizeCubanMobile(`+53${raw}`)
}

/** "+5351234567" -> "5123 4567": the part the field shows after its fixed "+53" prefix. */
export function contactToInput(phone: string): string {
  const digits = phone.replace(/^\+53/, '')
  return digits.length === 8 ? `${digits.slice(0, 4)} ${digits.slice(4)}` : digits
}

export const FINAL_STATUSES: RechargeStatus[] = ['SUCCESS', 'FAILED']

/** What happened, in words for the customer. Never mentions how the provider is implemented. */
export function outcomeMessage(status: RechargeStatus, paymentStatus: PaymentStatus): { tone: 'info' | 'ok' | 'bad'; text: string } {
  if (status === 'SUCCESS') return { tone: 'ok', text: 'Recarga entregada. El destinatario ya la tiene.' }
  if (status === 'PROCESSING') return { tone: 'info', text: 'Tu recarga está en proceso. Esta página se actualiza sola cuando termine.' }
  if (status === 'PENDING_PAYMENT') return { tone: 'info', text: 'Falta completar el pago para enviar la recarga.' }
  if (paymentStatus === 'SUCCEEDED') {
    return { tone: 'bad', text: 'No pudimos completar la recarga. Nuestro equipo revisará el reembolso de tu pago.' }
  }
  return { tone: 'bad', text: 'El pago no se completó y la recarga no se envió. No se hizo ningún cobro.' }
}

/** price - total as an exact 2-decimal string ("10.00" - "9.50" = "0.50"). Never goes through a float. */
export function discountAmount(priceBase: string, amountTotal: string): string | null {
  const base = toScaled(priceBase, 2)
  const total = toScaled(amountTotal, 2)
  if (base === null || total === null || total > base) return null
  return fromScaled(base - total, 2)
}
