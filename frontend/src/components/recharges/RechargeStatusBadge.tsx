import type { RechargeStatus } from '../../types/recharges'

const STYLES: Record<RechargeStatus, string> = {
  PENDING_PAYMENT: 'bg-amber-100 text-amber-800',
  PROCESSING: 'bg-blue-100 text-blue-800',
  SUCCESS: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-red-100 text-red-800',
}

export default function RechargeStatusBadge({ status, label }: { status: RechargeStatus; label: string }) {
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[status]}`}>{label}</span>
}
