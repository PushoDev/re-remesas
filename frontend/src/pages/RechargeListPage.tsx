import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2, Plus, RefreshCw } from 'lucide-react'
import { Link, useSearchParams } from 'react-router-dom'
import Money from '../components/Money'
import RechargeStatusBadge from '../components/recharges/RechargeStatusBadge'
import { parseApiError } from '../lib/apiErrors'
import { formatPhone } from '../lib/recharges'
import { listRecharges } from '../services/rechargeService'
import type { RechargeStatus } from '../types/recharges'

const FILTERS: { value: RechargeStatus | ''; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'PENDING_PAYMENT', label: 'Pendientes de pago' },
  { value: 'PROCESSING', label: 'Procesando' },
  { value: 'SUCCESS', label: 'Exitosas' },
  { value: 'FAILED', label: 'Fallidas' },
]
const PAGE_SIZE = 10
const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'short' })

export default function RechargeListPage() {
  const [params, setParams] = useSearchParams()
  const statusParam = params.get('status')
  const status: RechargeStatus | '' = FILTERS.some((filter) => filter.value === statusParam) ? (statusParam as RechargeStatus | '') : ''
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next, { replace: true })
  }

  const { data, isPending, isError, error, refetch, isFetching, isPlaceholderData } = useQuery({
    queryKey: ['recharges', status, page],
    queryFn: () => listRecharges({ status: status || undefined, page }),
    placeholderData: keepPreviousData,
    refetchInterval: 15_000, // an order moves on its own once its payment is confirmed
  })
  const pages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Mis recargas</h1>
          <p className="text-slate-600">Sigue el estado de tus recargas y su referencia.</p>
        </div>
        <Link to="/recharges/new" className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2">
          <Plus className="size-5" aria-hidden /> Nueva recarga
        </Link>
      </div>

      <div role="group" aria-label="Filtrar por estado" className="flex flex-wrap gap-2">
        {FILTERS.map((filter) => (
          <button
            key={filter.value}
            type="button"
            aria-pressed={status === filter.value}
            onClick={() => update({ status: filter.value, page: '' })}
            className={`rounded-full border px-3 py-1.5 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
              status === filter.value ? 'border-blue-700 bg-blue-700 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
            }`}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {isPending && (
        <p role="status" className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
          <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando tus recargas…
        </p>
      )}

      {isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <span>No se pudieron cargar tus recargas. {parseApiError(error).message}</span>
          <button type="button" onClick={() => void refetch()} disabled={isFetching} className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60">
            <RefreshCw className="size-4" aria-hidden /> Reintentar
          </button>
        </div>
      )}

      {data && data.count === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="font-medium text-slate-900">{status ? 'No hay recargas con ese filtro' : 'Todavía no has hecho ninguna recarga'}</p>
          <p className="mt-1 text-sm text-slate-600">{status ? 'Prueba con otro estado.' : 'Recarga el móvil de tu familia en Cuba en un momento.'}</p>
          {!status && <Link to="/recharges/new" className="mt-4 inline-block font-semibold text-blue-700 hover:underline">Hacer mi primera recarga</Link>}
        </div>
      )}

      {data && data.count > 0 && (
        <div className={`overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`}>
          <table className="w-full min-w-[46rem] text-left text-sm">
            <caption className="sr-only">Tus recargas, de la más reciente a la más antigua</caption>
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">Número</th>
                <th scope="col" className="px-4 py-3">Fecha</th>
                <th scope="col" className="px-4 py-3">Paquete</th>
                <th scope="col" className="px-4 py-3 text-right">Total</th>
                <th scope="col" className="px-4 py-3">Estado</th>
                <th scope="col" className="px-4 py-3">Referencia</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.results.map((order) => (
                <tr key={order.reference} className="hover:bg-slate-50">
                  <th scope="row" className="px-4 py-3 font-semibold tabular-nums">
                    <Link to={`/recharges/${order.reference}`} className="text-blue-700 hover:underline">{formatPhone(order.phone_number)}</Link>
                  </th>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">{dateTime.format(new Date(order.created_at))}</td>
                  <td className="px-4 py-3 text-slate-900">{order.package.name}</td>
                  <td className="px-4 py-3 text-right font-medium"><Money amount={order.amount_total} currency={order.currency} /></td>
                  <td className="px-4 py-3"><RechargeStatusBadge status={order.status} label={order.status_display} /></td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{order.provider_reference || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && pages > 1 && (
        <nav aria-label="Paginación" className="flex items-center justify-between">
          <button type="button" disabled={!data.previous} onClick={() => update({ page: String(page - 1) })} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50">
            <ChevronLeft className="size-4" aria-hidden /> Anterior
          </button>
          <span className="text-sm text-slate-600">Página {page} de {pages}</span>
          <button type="button" disabled={!data.next} onClick={() => update({ page: String(page + 1) })} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50">
            Siguiente <ChevronRight className="size-4" aria-hidden />
          </button>
        </nav>
      )}
    </div>
  )
}
