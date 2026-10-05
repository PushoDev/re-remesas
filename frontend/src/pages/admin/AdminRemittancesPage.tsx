import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, FileCheck2, Loader2, RefreshCw, Search } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Money from '../../components/Money'
import StatusBadge from '../../components/remittances/StatusBadge'
import { ORDERING_OPTIONS, isOrdering } from '../../lib/adminRemittances'
import { parseApiError } from '../../lib/apiErrors'
import { inputClass } from '../../lib/formStyles'
import { listAdminRemittances } from '../../services/adminRemittanceService'
import type { AdminOrdering } from '../../types/adminRemittances'
import type { RemittanceStatus } from '../../types/remittances'

const TABS: { value: RemittanceStatus | ''; label: string }[] = [
  { value: '', label: 'Todas' },
  { value: 'PENDING_PAYMENT', label: 'Pendientes de pago' },
  { value: 'PAID', label: 'Pagadas' },
  { value: 'COMPLETED', label: 'Completadas' },
  { value: 'CANCELLED', label: 'Canceladas' },
]
const PAGE_SIZE = 10
const REFRESH_MS = 20_000
const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'short' })

export default function AdminRemittancesPage() {
  const [params, setParams] = useSearchParams()
  const statusParam = params.get('status')
  const status: RemittanceStatus | '' = TABS.some((tab) => tab.value === statusParam) ? (statusParam as RemittanceStatus | '') : ''
  const search = params.get('search') ?? ''
  const orderingParam = params.get('ordering')
  const ordering: AdminOrdering = isOrdering(orderingParam) ? orderingParam : '-created_at'
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
    queryKey: ['admin', 'remittances', status, search, ordering, page],
    queryFn: () => listAdminRemittances({ status: status || undefined, search: search || undefined, ordering, page }),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })

  const pages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1
  const onSearch = (event: FormEvent) => {
    event.preventDefault()
    update({ search: searchText.trim(), page: '' })
  }

  return (
    <section aria-labelledby="inbox-title" className="space-y-4">
      <div>
        <h2 id="inbox-title" className="text-lg font-semibold text-slate-900">Bandeja de remesas</h2>
        <p className="text-sm text-slate-600">Revisa los pagos, confirma los manuales y marca las entregas.</p>
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

      <div className="flex flex-wrap items-end justify-between gap-3">
        <form onSubmit={onSearch} role="search" className="flex gap-2">
          <div>
            <label htmlFor="admin-search" className="sr-only">Buscar por ID, correo, nombre o teléfono</label>
            <input id="admin-search" value={searchText} onChange={(event) => setSearchText(event.target.value)}
              placeholder="ID, correo, nombre o teléfono" className={`${inputClass} mt-0 w-72`} />
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
        <div>
          <label htmlFor="admin-ordering" className="sr-only">Ordenar por</label>
          <select id="admin-ordering" value={ordering} onChange={(event) => update({ ordering: event.target.value === '-created_at' ? '' : event.target.value, page: '' })} className={`${inputClass} mt-0`}>
            {ORDERING_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>
      </div>

      {isPending && (
        <p role="status" className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
          <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando remesas…
        </p>
      )}
      {isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <span>No se pudo cargar la bandeja. {parseApiError(error).message}</span>
          <button type="button" onClick={() => void refetch()} disabled={isFetching} className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60">
            <RefreshCw className="size-4" aria-hidden /> Reintentar
          </button>
        </div>
      )}

      {data && data.count === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="font-medium text-slate-900">{status || search ? 'No hay remesas con ese filtro' : 'Todavía no hay remesas'}</p>
          <p className="mt-1 text-sm text-slate-600">{status || search ? 'Prueba con otro estado o quita la búsqueda.' : 'Aparecerán aquí cuando los clientes las soliciten.'}</p>
        </div>
      )}

      {data && data.count > 0 && (
        <div className={`overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm transition-opacity ${isPlaceholderData ? 'opacity-60' : ''}`}>
          <table className="w-full min-w-[60rem] text-left text-sm">
            <caption className="sr-only">Remesas de todos los clientes</caption>
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">ID</th>
                <th scope="col" className="px-4 py-3">Fecha</th>
                <th scope="col" className="px-4 py-3">Remitente</th>
                <th scope="col" className="px-4 py-3">Destinatario</th>
                <th scope="col" className="px-4 py-3 text-right">Enviado</th>
                <th scope="col" className="px-4 py-3 text-right">Recibe</th>
                <th scope="col" className="px-4 py-3">Pago</th>
                <th scope="col" className="px-4 py-3">Estado</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.results.map((row) => (
                <tr key={row.tracking_id} className="hover:bg-slate-50">
                  <th scope="row" className="px-4 py-3 font-mono font-semibold">
                    <Link to={`/admin/remittances/${row.tracking_id}`} className="text-blue-700 hover:underline">{row.tracking_id}</Link>
                  </th>
                  <td className="px-4 py-3 whitespace-nowrap text-slate-600">{dateTime.format(new Date(row.created_at))}</td>
                  <td className="px-4 py-3 text-slate-900">{row.sender_email}{row.is_vip_rate && <span className="ml-1.5 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-bold text-amber-800">VIP</span>}</td>
                  <td className="px-4 py-3 text-slate-900">{row.recipient_name}</td>
                  <td className="px-4 py-3 text-right"><Money amount={row.amount_sent} currency={row.currency} /></td>
                  <td className="px-4 py-3 text-right font-medium"><Money amount={row.amount_cup} currency="CUP" /></td>
                  <td className="px-4 py-3">
                    <span className="block text-slate-900">{row.payment_method_display}</span>
                    <span className="flex items-center gap-1 text-xs text-slate-500">
                      {row.payment_provider === 'MANUAL' ? 'Manual' : 'En línea'}
                      {row.has_proof && <FileCheck2 className="size-3.5 text-emerald-600" aria-label="Con comprobante" />}
                    </span>
                  </td>
                  <td className="px-4 py-3"><StatusBadge status={row.status} label={row.status_display} /></td>
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
          <span className="text-sm text-slate-600">Página {page} de {pages} · {data.count} remesas</span>
          <button type="button" disabled={!data.next} onClick={() => update({ page: String(page + 1) })} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium disabled:opacity-50">
            Siguiente <ChevronRight className="size-4" aria-hidden />
          </button>
        </nav>
      )}
    </section>
  )
}
