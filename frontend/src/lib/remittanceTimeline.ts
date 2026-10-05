import type { TimelineItem } from '../components/Timeline'
import type { CustomerStatusEntry, RemittanceStatus } from '../types/remittances'

const TONE: Record<RemittanceStatus, NonNullable<TimelineItem['tone']>> = {
  PENDING_PAYMENT: 'warning',
  PAID: 'default',
  COMPLETED: 'success',
  CANCELLED: 'danger',
}

/** The customer's timeline: what happened and when, in plain words. */
export function customerTimeline(entries: CustomerStatusEntry[]): TimelineItem[] {
  return entries.map((entry, index) => {
    if (!entry.event) {
      return { key: index, title: 'Enviaste tu comprobante de pago', at: entry.changed_at, event: false }
    }
    return {
      key: index,
      title: entry.from_status === '' ? 'Solicitud creada' : entry.to_status_display,
      at: entry.changed_at,
      event: true,
      tone: TONE[entry.to_status],
    }
  })
}

/** What to tell the customer next, from the real state. */
export function nextStepText(status: RemittanceStatus, manualPayment: boolean): string {
  switch (status) {
    case 'PENDING_PAYMENT':
      return manualPayment
        ? 'Haz el pago y envía tu comprobante; un administrador lo verificará.'
        : 'Falta completar el pago para que podamos procesar tu envío.'
    case 'PAID':
      return 'Recibimos tu pago. Ahora entregamos el dinero en Cuba.'
    case 'COMPLETED':
      return 'El dinero ya fue entregado al destinatario.'
    case 'CANCELLED':
      return 'Esta solicitud se canceló. Si ya habías pagado, nos pondremos en contacto contigo para el reembolso.'
  }
}

/** The message to flash when the status changed while the page was open; null when nothing changed. */
export function statusChangeMessage(previous: string | undefined, next: string | undefined, label: string | undefined): string | null {
  if (!previous || !next || previous === next) return null
  return `Tu remesa cambió de estado: ahora está «${label ?? next}».`
}
