import type { RemittanceStatus } from '../../types/remittances'

const STYLES: Record<RemittanceStatus, string> = {
  PENDING_PAYMENT: 'bg-amber-100 text-amber-800',
  PAID: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-emerald-100 text-emerald-800',
  CANCELLED: 'bg-slate-200 text-slate-700',
}

export default function StatusBadge({ status, label }: { status: RemittanceStatus; label: string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[status]}`}>{label}</span>
}
