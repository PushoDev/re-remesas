import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Loader2, Plus, RefreshCw, Search } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Money from '../components/Money'
import StatusBadge from '../components/remittances/StatusBadge'
import { parseApiError } from '../lib/apiErrors'
import { inputClass } from '../lib/formStyles'
import { listRemittances } from '../services/remittanceService'
import type { RemittanceStatus } from '../types/remittances'

const FILTERS: { value: RemittanceStatus | ''; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'PENDING_PAYMENT', label: 'Pendientes de pago' },
  { value: 'PAID', label: 'Pagadas' },
  { value: 'COMPLETED', label: 'Completadas' },
  { value: 'CANCELLED', label: 'Canceladas' },
]
const PAGE_SIZE = 10
const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'short' })

export default function RemittanceListPage() {
  const [params, setParams] = useSearchParams()
  const status = (params.get('status') ?? '') as RemittanceStatus | ''
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
    queryKey: ['remittances', status, search, page],
    queryFn: () => listRemittances({ status: status || undefined, search: search || undefined, page }),
    placeholderData: keepPreviousData,
  })

  const onSearch = (event: FormEvent) => {
    event.preventDefault()
    update({ search: searchText.trim(), page: '' })
  }
  const pages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Mis remesas</h1>
          <p className="text-slate-600">Sigue el estado de tus envíos con su ID de seguimiento.</p>
        </div>
        <Link to="/remittances/new" className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2">
          <Plus className="size-5" aria-hidden /> Nueva remesa
        </Link>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
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
        <form onSubmit={onSearch} role="search" className="flex gap-2">
          <label htmlFor="remittance-search" className="sr-only">Buscar por ID de seguimiento</label>
          <input id="remittance-search" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Buscar por ID" className={`${inputClass} mt-0 w-44`} />
          <button type="submit" className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">
            <Search className="size-4" aria-hidden /> Buscar
          </button>
        </form>
      </div>

      {isPending && (
        <p role="status" className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
          <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando tus remesas…
        </p>
      )}

      {isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <span>No se pudieron cargar tus remesas. {parseApiError(error).message}</span>
          <button type="button" onClick={() => void refetch()} disabled={isFetching} className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60">
            <RefreshCw className="size-4" aria-hidden /> Reintentar
          </button>
        </div>
      )}

      {data && data.count === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="font-medium text-slate-900">
            {status || search ? 'No hay remesas con ese filtro' : 'Todavía no has enviado ninguna remesa'}
          </p>
          <p className="mt-1 text-sm text-slate-600">
            {status || search ? 'Prueba con otro estado o borra la búsqueda.' : 'Calcula cuánto recibirá tu familiar y envía tu primera remesa.'}
          </p>
          {!(status || search) && (
            <Link to="/remittances/new" className="mt-4 inline-block font-semibold text-blue-700 hover:underline">Enviar mi primera remesa</Link>
          )}
        </div>
      )}

      {data && data.count > 0 && (
        <div className={`overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`}>
          <table className="w-full min-w-[44rem] text-left text-sm">
            <caption className="sr-only">Tus remesas, de la más reciente a la más antigua</caption>
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">ID de seguimiento</th>
                <th scope="col" className="px-4 py-3">Fecha</th>
                <th scope="col" className="px-4 py-3">Destinatario</th>
                <th scope="col" className="px-4 py-3 text-right">Enviado</th>
                <th scope="col" className="px-4 py-3 text-right">Recibe</th>
                <th scope="col" className="px-4 py-3">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.results.map((remittance) => (
                <tr key={remittance.tracking_id} className="hover:bg-slate-50">
                  <th scope="row" className="px-4 py-3 font-mono font-semibold">
                    <Link to={`/remittances/${remittance.tracking_id}`} className="text-blue-700 hover:underline">{remittance.tracking_id}</Link>
                  </th>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">{dateTime.format(new Date(remittance.created_at))}</td>
                  <td className="px-4 py-3 text-slate-900">{remittance.recipient_name}</td>
                  <td className="px-4 py-3 text-right"><Money amount={remittance.amount_sent} currency={remittance.currency} /></td>
                  <td className="px-4 py-3 text-right font-medium"><Money amount={remittance.amount_cup} currency="CUP" /></td>
                  <td className="px-4 py-3"><StatusBadge status={remittance.status} label={remittance.status_display} /></td>
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
