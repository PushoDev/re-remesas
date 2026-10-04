import { useQuery } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { parseApiError } from '../../lib/apiErrors'
import { formatDecimal } from '../../lib/decimal'
import { getExchangeRateHistory } from '../../services/exchangeRateService'

const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'medium', timeStyle: 'short' })

export default function ExchangeRateHistory({ rateId }: { rateId: number }) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['admin', 'exchange-rates', rateId, 'history'],
    queryFn: () => getExchangeRateHistory(rateId),
  })

  if (isPending) {
    return (
      <p role="status" className="flex items-center gap-2 text-slate-600">
        <Loader2 className="size-4 animate-spin" aria-hidden /> Cargando historial…
      </p>
    )
  }
  if (isError) return <p role="alert" className="text-red-600">{parseApiError(error).message}</p>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Historial de cambios, del más reciente al más antiguo</caption>
        <thead className="text-xs uppercase text-slate-500">
          <tr>
            <th scope="col" className="py-2 pr-4">Fecha</th>
            <th scope="col" className="py-2 pr-4 text-right">Tasa base</th>
            <th scope="col" className="py-2 pr-4 text-right">Estándar</th>
            <th scope="col" className="py-2 pr-4 text-right">VIP</th>
            <th scope="col" className="py-2 pr-4">Estado</th>
            <th scope="col" className="py-2">Por</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {data.map((entry) => (
            <tr key={entry.id}>
              <td className="py-2 pr-4 whitespace-nowrap">{dateTime.format(new Date(entry.changed_at))}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{formatDecimal(entry.base_rate)}</td>
              <td className="py-2 pr-4 text-right tabular-nums">{formatDecimal(entry.standard_spread_percent)} %</td>
              <td className="py-2 pr-4 text-right tabular-nums">{formatDecimal(entry.vip_spread_percent)} %</td>
              <td className="py-2 pr-4">{entry.is_active ? 'Activa' : 'Inactiva'}</td>
              <td className="py-2 text-slate-600">{entry.changed_by_email ?? '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
