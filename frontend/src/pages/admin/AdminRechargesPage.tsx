import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2, RefreshCw, Search, TriangleAlert } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import Money from '../../components/Money'
import RechargeStatusBadge from '../../components/recharges/RechargeStatusBadge'
import { parseApiError } from '../../lib/apiErrors'
import { inputClass } from '../../lib/formStyles'
import { paymentMethodLabel } from '../../lib/paymentMethods'
import { formatPhone } from '../../lib/recharges'
import { listAdminRecharges } from '../../services/adminRechargeService'
import type { RechargeStatus } from '../../types/recharges'

const TABS: { value: RechargeStatus | ''; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'PENDING_PAYMENT', label: 'Pendientes de pago' },
  { value: 'PROCESSING', label: 'Procesando' },
  { value: 'SUCCESS', label: 'Exitosas' },
  { value: 'FAILED', label: 'Fallidas' },
]
const PAGE_SIZE = 10
const REFRESH_MS = 20_000
const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'short' })

export default function AdminRechargesPage() {
  const [params, setParams] = useSearchParams()
  const statusParam = params.get('status')
  const status: RechargeStatus | '' = TABS.some((tab) => tab.value === statusParam) ? (statusParam as RechargeStatus | '') : ''
  const search = params.get('search') ?? ''
  const page = Math.max(1, Number(params.get('page') ?? 1) || 1)
  const [searchText, setSearchText] = useState(search)

  const update = (changes: Record<string, string>) => {
    const next = new URLSearchParams(params)
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value)
      else next.delete(key)
    }
    setParams(next, { replace: true })
  }

  const { data, isPending, isError, error, refetch, isFetching, isPlaceholderData } = useQuery({
    queryKey: ['admin', 'recharges', status, search, page],
    queryFn: () => listAdminRecharges({ status: status || undefined, search: search || undefined, page }),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })
  const pages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1
  const onSearch = (event: FormEvent) => {
    event.preventDefault()
    update({ search: searchText.trim(), page: '' })
  }

  return (
    <section aria-labelledby="recharges-title" className="space-y-4">
      <div>
        <h2 id="recharges-title" className="text-lg font-semibold text-slate-900">Órdenes de recarga</h2>
        <p className="text-sm text-slate-600">Estado de cada recarga y lo que respondió el operador. Las marcadas «Reembolsar» se cobraron pero no se entregaron.</p>
      </div>

      <div role="group" aria-label="Filtrar por estado" className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button key={tab.value} type="button" aria-pressed={status === tab.value} onClick={() => update({ status: tab.value, page: '' })}
            className={`rounded-full border px-3 py-1.5 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
              status === tab.value ? 'border-blue-700 bg-blue-700 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
            }`}>
            {tab.label}
          </button>
        ))}
      </div>

      <form onSubmit={onSearch} role="search" className="flex flex-wrap gap-2">
        <div>
          <label htmlFor="admin-recharge-search" className="sr-only">Buscar por teléfono, correo o referencia</label>
          <input id="admin-recharge-search" value={searchText} onChange={(event) => setSearchText(event.target.value)}
            placeholder="Teléfono, correo o referencia" className={`${inputClass} mt-0 w-72`} />
        </div>
        <button type="submit" className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
          <Search className="size-4" aria-hidden /> Buscar
        </button>
        {search && (
          <button type="button" onClick={() => { setSearchText(''); update({ search: '', page: '' }) }} className="text-sm font-medium text-blue-700 hover:underline">
            Quitar búsqueda
          </button>
        )}
      </form>

      {isPending && (
        <p role="status" className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
          <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando recargas…
        </p>
      )}
      {isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <span>No se pudieron cargar las recargas. {parseApiError(error).message}</span>
          <button type="button" onClick={() => void refetch()} disabled={isFetching} className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60">
            <RefreshCw className="size-4" aria-hidden /> Reintentar
          </button>
        </div>
      )}

      {data && data.count === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="font-medium text-slate-900">{status || search ? 'No hay recargas con ese filtro' : 'Todavía no hay recargas'}</p>
          <p className="mt-1 text-sm text-slate-600">{status || search ? 'Prueba con otro estado o quita la búsqueda.' : 'Aparecerán aquí cuando los clientes las soliciten.'}</p>
        </div>
      )}

      {data && data.count > 0 && (
        <div className={`overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`}>
          <table className="w-full min-w-[62rem] text-left text-sm">
            <caption className="sr-only">Órdenes de recarga de todos los clientes</caption>
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">Fecha</th>
                <th scope="col" className="px-4 py-3">Cliente</th>
                <th scope="col" className="px-4 py-3">Teléfono</th>
                <th scope="col" className="px-4 py-3">Paquete</th>
                <th scope="col" className="px-4 py-3 text-right">Monto</th>
                <th scope="col" className="px-4 py-3">Pago</th>
                <th scope="col" className="px-4 py-3">Estado</th>
                <th scope="col" className="px-4 py-3">Referencia del operador</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.results.map((row) => (
                <tr key={row.reference} className="hover:bg-slate-50">
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">{dateTime.format(new Date(row.created_at))}</td>
                  <td className="px-4 py-3 text-slate-900">{row.user_email}</td>
                  <td className="px-4 py-3 font-semibold tabular-nums text-slate-900">{formatPhone(row.phone_number)}</td>
                  <td className="px-4 py-3 text-slate-900">{row.package.name}</td>
                  <td className="px-4 py-3 text-right font-medium"><Money amount={row.amount_total} currency={row.currency} /></td>
                  <td className="px-4 py-3">
                    <span className="block text-slate-900">{paymentMethodLabel(row.payment_method)}</span>
                    <span className="text-xs text-slate-500">{row.payment_status === 'SUCCEEDED' ? 'Pagado' : row.payment_status === 'FAILED' ? 'Fallido' : 'Pendiente'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <RechargeStatusBadge status={row.status} label={row.status_display} />
                    {row.needs_refund && (
                      <span className="mt-1 flex items-center gap-1 text-xs font-semibold text-red-700"><TriangleAlert className="size-3.5" aria-hidden /> Reembolsar</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="block font-mono text-xs text-slate-700">{row.provider_reference || '—'}</span>
                    {row.provider_message && <span className="block text-xs text-slate-500">{row.provider_message}</span>}
                  </td>
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
          <span className="text-sm text-slate-600">Página {page} de {pages} · {data.count} recargas</span>
          <button type="button" disabled={!data.next} onClick={() => update({ page: String(page + 1) })} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50">
            Siguiente <ChevronRight className="size-4" aria-hidden />
          </button>
        </nav>
      )}
    </section>
  )
}
