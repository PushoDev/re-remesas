import type { AdminOrdering } from '../types/adminRemittances'

export type AdminAction = 'confirm_payment' | 'complete' | 'cancel'

/** The order the buttons appear in: the positive step first, the destructive one last. */
const ORDER: AdminAction[] = ['confirm_payment', 'complete', 'cancel']

export const ACTION_LABEL: Record<AdminAction, string> = {
  confirm_payment: 'Confirmar pago',
  complete: 'Marcar como entregada',
  cancel: 'Cancelar remesa',
}

/** The actions the API says are possible right now, in display order. Unknown ones are ignored. */
export function visibleActions(allowed: readonly string[]): AdminAction[] {
  return ORDER.filter((action) => allowed.includes(action))
}

export const ORDERING_OPTIONS: { value: AdminOrdering; label: string }[] = [
  { value: '-created_at', label: 'Más recientes' },
  { value: 'created_at', label: 'Más antiguas' },
  { value: '-amount_sent', label: 'Mayor monto' },
  { value: 'amount_sent', label: 'Menor monto' },
]

export const MIN_REASON_LENGTH = 5

/** A cancellation must say why. Returns the problem, or null when the reason is fine. */
export function validateCancelReason(raw: string): string | null {
  const reason = raw.trim()
  if (reason.length === 0) return 'Indica el motivo de la cancelación.'
  if (reason.length < MIN_REASON_LENGTH) return `Escribe al menos ${MIN_REASON_LENGTH} caracteres.`
  if (reason.length > 500) return 'El motivo admite máximo 500 caracteres.'
  return null
}

export function isOrdering(value: string | null): value is AdminOrdering {
  return ORDERING_OPTIONS.some((option) => option.value === value)
}
