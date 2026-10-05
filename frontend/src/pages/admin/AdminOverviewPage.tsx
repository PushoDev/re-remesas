import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, Loader2, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { parseApiError } from '../../lib/apiErrors'
import { getAdminOverview } from '../../services/adminRemittanceService'

const REFRESH_MS = 20_000

function Card({ label, value, to, tone = 'default', hint }: { label: string; value: number; to?: string; tone?: 'default' | 'alert'; hint?: ReactNode }) {
  const body = (
    <>
      <p className="text-sm text-slate-600">{label}</p>
      <p className={`mt-1 text-3xl font-bold tabular-nums ${tone === 'alert' && value > 0 ? 'text-amber-700' : 'text-slate-900'}`}>{value}</p>
      {hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
    </>
  )
  const base = `rounded-2xl border p-5 shadow-sm ${tone === 'alert' && value > 0 ? 'border-amber-300 bg-amber-50' : 'border-slate-200 bg-white'}`
  return to ? (
    <Link to={to} className={`${base} block transition hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600`}>{body}</Link>
  ) : (
    <div className={base}>{body}</div>
  )
}

export default function AdminOverviewPage() {
  const { data, isPending, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['admin', 'overview'],
    queryFn: getAdminOverview,
    refetchInterval: REFRESH_MS,
  })

  if (isPending) {
    return <p role="status" className="flex items-center gap-2 text-slate-600"><Loader2 className="size-5 animate-spin" aria-hidden /> Cargando el resumen…</p>
  }
  if (isError) {
    return (
      <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
        <span>No se pudo cargar el resumen. {parseApiError(error).message}</span>
        <button type="button" onClick={() => void refetch()} disabled={isFetching} className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60">
          <RefreshCw className="size-4" aria-hidden /> Reintentar
        </button>
      </div>
    )
  }

  const { remittances: r } = data
  return (
    <div className="space-y-6">
      <section aria-labelledby="remittances-title" className="space-y-3">
        <h2 id="remittances-title" className="text-lg font-semibold text-slate-900">Remesas</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card label="Por revisar" value={r.needs_review} tone="alert" to="/admin/remittances?status=PENDING_PAYMENT"
            hint="Pagos manuales con comprobante, esperando que los verifiques." />
          <Card label="Total de remesas" value={r.total} to="/admin/remittances" />
          <Card label="Pendientes de pago" value={r.pending_payment} to="/admin/remittances?status=PENDING_PAYMENT" />
          <Card label="Pagadas" value={r.paid} to="/admin/remittances?status=PAID" hint="Listas para entregar en Cuba." />
          <Card label="Completadas" value={r.completed} to="/admin/remittances?status=COMPLETED" />
          <Card label="Canceladas" value={r.cancelled} to="/admin/remittances?status=CANCELLED" />
        </div>
      </section>

      <section aria-labelledby="others-title" className="space-y-3">
        <h2 id="others-title" className="text-lg font-semibold text-slate-900">Otros</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Card label="Órdenes de recarga" value={data.recharge_orders.total} to="/admin/recharges" />
          <Card label="Membresías VIP activas" value={data.memberships.active_vip}
            hint={<span className="inline-flex items-center gap-1"><BadgeCheck className="size-3.5" aria-hidden /> Vigentes, sin vencer.</span>} />
        </div>
      </section>
      <p className="text-xs text-slate-500">Se actualiza solo cada 20 segundos.</p>
    </div>
  )
}
