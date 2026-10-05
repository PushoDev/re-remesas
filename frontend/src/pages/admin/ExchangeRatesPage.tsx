import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { History, Loader2, Pencil, Plus, PowerOff, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import ExchangeRateForm from '../../components/admin/ExchangeRateForm'
import ExchangeRateHistory from '../../components/admin/ExchangeRateHistory'
import Modal from '../../components/Modal'
import { parseApiError } from '../../lib/apiErrors'
import { formatDecimal } from '../../lib/decimal'
import { deactivateExchangeRate, listExchangeRates } from '../../services/exchangeRateService'
import type { AdminExchangeRate } from '../../types/exchangeRates'

const QUERY_KEY = ['admin', 'exchange-rates'] as const
const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'short' })

type Dialog =
  | { kind: 'create' }
  | { kind: 'edit'; rate: AdminExchangeRate }
  | { kind: 'history'; rate: AdminExchangeRate }
  | { kind: 'deactivate'; rate: AdminExchangeRate }
  | null

const actionClass =
  'inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600'

export default function ExchangeRatesPage() {
  const queryClient = useQueryClient()
  const [dialog, setDialog] = useState<Dialog>(null)
  const close = () => setDialog(null)

  const { data: rates, isPending, isError, error, refetch, isFetching } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: listExchangeRates,
  })

  const refresh = () => queryClient.invalidateQueries({ queryKey: QUERY_KEY })

  const deactivate = useMutation({
    mutationFn: (rate: AdminExchangeRate) => deactivateExchangeRate(rate.id),
    onSuccess: async () => {
      toast.success('Tasa desactivada. Su historial se conserva.')
      close()
      await refresh()
    },
    onError: (err) => toast.error(parseApiError(err).message),
  })

  return (
    <section aria-labelledby="rates-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="rates-title" className="text-lg font-semibold text-slate-900">
            Tasas de cambio y márgenes
          </h2>
          <p className="text-sm text-slate-600">
            Los cambios se aplican de inmediato en las cotizaciones de los clientes.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setDialog({ kind: 'create' })}
          className="inline-flex items-center gap-2 rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
        >
          <Plus className="size-5" aria-hidden />
          Nueva tasa
        </button>
      </div>

      {isPending && (
        <p role="status" className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
          <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando tasas…
        </p>
      )}

      {isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <span>No se pudieron cargar las tasas. {parseApiError(error).message}</span>
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60"
          >
            <RefreshCw className="size-4" aria-hidden /> Reintentar
          </button>
        </div>
      )}

      {rates && rates.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center">
          <p className="font-medium text-slate-900">Todavía no hay tasas configuradas</p>
          <p className="mt-1 text-sm text-slate-600">Sin una tasa activa los clientes no pueden cotizar remesas.</p>
          <button
            type="button"
            onClick={() => setDialog({ kind: 'create' })}
            className="mt-4 font-semibold text-blue-700 hover:underline"
          >
            Crear la primera tasa
          </button>
        </div>
      )}

      {rates && rates.length > 0 && (
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <caption className="sr-only">Tasas de cambio configuradas</caption>
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th scope="col" className="px-4 py-3">Moneda</th>
                <th scope="col" className="px-4 py-3 text-right">Tasa base</th>
                <th scope="col" className="px-4 py-3 text-right">Margen estándar</th>
                <th scope="col" className="px-4 py-3 text-right">Margen VIP</th>
                <th scope="col" className="px-4 py-3 text-right">Efectiva estándar</th>
                <th scope="col" className="px-4 py-3 text-right">Efectiva VIP</th>
                <th scope="col" className="px-4 py-3">Estado</th>
                <th scope="col" className="px-4 py-3">Actualizada</th>
                <th scope="col" className="px-4 py-3"><span className="sr-only">Acciones</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rates.map((rate) => (
                <tr key={rate.id} className={rate.is_active ? '' : 'bg-slate-50/60 text-slate-500'}>
                  <th scope="row" className="px-4 py-3 font-semibold text-slate-900">
                    {rate.currency} <span className="font-normal text-slate-500">→ {rate.target_currency}</span>
                  </th>
                  <td className="px-4 py-3 text-right tabular-nums">{formatDecimal(rate.base_rate)}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatDecimal(rate.standard_spread_percent)} %</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatDecimal(rate.vip_spread_percent)} %</td>
                  <td className="px-4 py-3 text-right tabular-nums">{formatDecimal(rate.effective_rate_standard)}</td>
                  <td className="px-4 py-3 text-right font-medium tabular-nums text-amber-700">{formatDecimal(rate.effective_rate_vip)}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        rate.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'
                      }`}
                    >
                      {rate.is_active ? 'Activa' : 'Inactiva'}
                    </span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {dateTime.format(new Date(rate.updated_at))}
                    <span className="block text-xs text-slate-500">{rate.updated_by_email ?? '—'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex justify-end gap-1">
                      <button type="button" className={actionClass} onClick={() => setDialog({ kind: 'edit', rate })}>
                        <Pencil className="size-4" aria-hidden /> Editar
                      </button>
                      <button type="button" className={actionClass} onClick={() => setDialog({ kind: 'history', rate })}>
                        <History className="size-4" aria-hidden /> Historial
                      </button>
                      {rate.is_active && (
                        <button
                          type="button"
                          className={`${actionClass} text-red-700 hover:bg-red-50`}
                          onClick={() => setDialog({ kind: 'deactivate', rate })}
                        >
                          <PowerOff className="size-4" aria-hidden /> Desactivar
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <Modal open={dialog?.kind === 'create'} onClose={close} title="Nueva tasa de cambio">
        <ExchangeRateForm
          onCancel={close}
          onSaved={() => {
            close()
            void refresh()
          }}
        />
      </Modal>

      <Modal open={dialog?.kind === 'edit'} onClose={close} title={dialog?.kind === 'edit' ? `Editar tasa ${dialog.rate.currency}` : ''}>
        {dialog?.kind === 'edit' && (
          <ExchangeRateForm
            rate={dialog.rate}
            onCancel={close}
            onSaved={() => {
              close()
              void refresh()
            }}
          />
        )}
      </Modal>

      <Modal
        open={dialog?.kind === 'history'}
        onClose={close}
        widthClass="max-w-3xl"
        title={dialog?.kind === 'history' ? `Historial de la tasa ${dialog.rate.currency}` : ''}
      >
        {dialog?.kind === 'history' && <ExchangeRateHistory rateId={dialog.rate.id} />}
      </Modal>

      <Modal
        open={dialog?.kind === 'deactivate'}
        onClose={close}
        title={dialog?.kind === 'deactivate' ? `¿Desactivar la tasa ${dialog.rate.currency}?` : ''}
      >
        {dialog?.kind === 'deactivate' && (
          <div className="space-y-4">
            <p className="text-slate-700">
              Mientras no haya otra tasa activa para {dialog.rate.currency}, los clientes no podrán cotizar ni solicitar
              remesas en esa moneda. El historial se conserva y podrás crear una tasa nueva.
            </p>
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={close}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-100"
              >
                Cancelar
              </button>
              <button
                type="button"
                disabled={deactivate.isPending}
                onClick={() => deactivate.mutate(dialog.rate)}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-4 py-2.5 font-semibold text-white hover:bg-red-700 disabled:opacity-70"
              >
                {deactivate.isPending && <Loader2 className="size-5 animate-spin" aria-hidden />}
                Sí, desactivar
              </button>
            </div>
          </div>
        )}
      </Modal>
    </section>
  )
}
