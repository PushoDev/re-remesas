import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, CheckCircle2, Clock, CreditCard, Loader2, XCircle } from 'lucide-react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import CopyButton from '../components/CopyButton'
import Money from '../components/Money'
import StatusBadge from '../components/remittances/StatusBadge'
import { parseApiError } from '../lib/apiErrors'
import { formatDecimal } from '../lib/decimal'
import { getRemittance } from '../services/remittanceService'
import type { RemittanceDetail } from '../types/remittances'

const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'long', timeStyle: 'short' })
const REFRESH_MS = 10_000

function PaymentBlock({ remittance }: { remittance: RemittanceDetail }) {
  const { payment } = remittance
  const here = `/remittances/${remittance.tracking_id}`

  return (
    <section aria-labelledby="payment-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 id="payment-title" className="mb-3 flex items-center gap-2 text-base font-semibold text-slate-900">
        <CreditCard className="size-5" aria-hidden /> Pago
      </h2>
      <p className="text-sm text-slate-600">
        {remittance.payment_method_display} · <Money amount={payment.amount} currency={payment.currency} className="font-semibold text-slate-900" />
      </p>

      {payment.status === 'SUCCEEDED' && (
        <p className="mt-3 flex items-center gap-2 text-sm font-medium text-emerald-700"><CheckCircle2 className="size-5" aria-hidden /> Pago recibido</p>
      )}
      {payment.status === 'FAILED' && (
        <p className="mt-3 flex items-start gap-2 text-sm text-red-700">
          <XCircle className="mt-0.5 size-5 shrink-0" aria-hidden />
          El pago no se completó y la solicitud se canceló. No se hizo ningún cobro; puedes crear una nueva remesa.
        </p>
      )}
      {payment.status === 'PENDING' && payment.checkout_url && (
        <div className="mt-3 space-y-2">
          <p className="flex items-center gap-2 text-sm text-amber-800"><Clock className="size-5" aria-hidden /> Falta completar el pago.</p>
          <Link
            to={`${payment.checkout_url}?next=${encodeURIComponent(here)}`}
            className="inline-flex rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
          >
            Pagar ahora
          </Link>
        </div>
      )}
      {payment.status === 'PENDING' && payment.requires_manual_confirmation && (
        <div className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">Pago en revisión</p>
          <p className="mt-1">{payment.instructions}</p>
        </div>
      )}
    </section>
  )
}

export default function RemittanceDetailPage() {
  const { trackingId = '' } = useParams()
  const [params] = useSearchParams()
  const justCreated = params.get('created') === '1'

  const { data: remittance, isPending, isError, error } = useQuery({
    queryKey: ['remittance', trackingId],
    queryFn: () => getRemittance(trackingId),
    retry: false,
    // Follow the state while it can still change (payment confirmation, administrator completing it).
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'COMPLETED' || status === 'CANCELLED' ? false : REFRESH_MS
    },
  })

  if (isPending) {
    return (
      <p role="status" className="flex items-center gap-2 text-slate-600">
        <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando la remesa…
      </p>
    )
  }
  if (isError || !remittance) {
    return (
      <div role="alert" className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">No encontramos esa remesa</h1>
        <p className="mt-2 text-slate-600">Revisa el ID de seguimiento o búscala en tu lista. {isError ? parseApiError(error).message : ''}</p>
        <Link to="/remittances" className="mt-4 inline-block font-semibold text-blue-700 hover:underline">Ver mis remesas</Link>
      </div>
    )
  }

  const cash = remittance.delivery_method === 'CASH_DELIVERY'

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      {justCreated && (
        <div role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <p className="flex items-center gap-2 font-semibold text-emerald-900"><CheckCircle2 className="size-5" aria-hidden /> ¡Tu solicitud quedó registrada!</p>
          <p className="mt-1 text-sm text-emerald-900">Guarda este ID: con él tú y nuestro equipo pueden seguir tu envío.</p>
        </div>
      )}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-600">ID de seguimiento</p>
          <p className="mt-1 flex flex-wrap items-center gap-3">
            <span className="font-mono text-2xl font-bold tracking-wide text-slate-900">{remittance.tracking_id}</span>
            <CopyButton text={remittance.tracking_id} />
          </p>
        </div>
        <StatusBadge status={remittance.status} label={remittance.status_display} />
      </header>
      <p className="text-sm text-slate-500">Creada el {dateTime.format(new Date(remittance.created_at))}</p>

      <PaymentBlock remittance={remittance} />

      <section aria-labelledby="money-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="mb-3 flex items-center justify-between">
          <h2 id="money-title" className="text-base font-semibold text-slate-900">El envío</h2>
          {remittance.is_vip_rate && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-2.5 py-0.5 text-xs font-semibold text-white"><BadgeCheck className="size-3.5" aria-hidden /> Tarifa VIP</span>
          )}
        </div>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-600">Enviado</dt>
          <dd className="text-right font-medium text-slate-900"><Money amount={remittance.amount_sent} currency={remittance.currency} /></dd>
          <dt className="text-slate-600">Tasa de cambio</dt>
          <dd className="text-right tabular-nums text-slate-900">1 {remittance.currency} = {formatDecimal(remittance.base_rate_used)} CUP</dd>
          <dt className="text-slate-600">Margen del servicio</dt>
          <dd className="text-right tabular-nums text-slate-900">{formatDecimal(remittance.spread_percent_used)} %</dd>
          <dt className="text-slate-600">Tasa aplicada</dt>
          <dd className="text-right tabular-nums text-slate-900">1 {remittance.currency} = {formatDecimal(remittance.effective_rate_used)} CUP</dd>
          <dt className="border-t border-slate-100 pt-2 font-medium text-slate-700">El destinatario recibe</dt>
          <dd className="border-t border-slate-100 pt-2 text-right text-lg font-bold text-slate-900"><Money amount={remittance.amount_cup} currency="CUP" /></dd>
        </dl>
        <p className="mt-3 text-xs text-slate-500">Estas cifras quedaron fijadas al crear la solicitud y no cambian aunque cambie la tasa.</p>
      </section>

      <section aria-labelledby="recipient-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 id="recipient-title" className="mb-3 text-base font-semibold text-slate-900">Destinatario</h2>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-600">Nombre</dt><dd className="text-slate-900">{remittance.recipient_name}</dd>
          <dt className="text-slate-600">Teléfono</dt><dd className="text-slate-900">{remittance.recipient_phone}</dd>
          <dt className="text-slate-600">Entrega</dt><dd className="text-slate-900">{remittance.delivery_method_display}</dd>
          <dt className="text-slate-600">{cash ? 'Dirección' : 'Cuenta'}</dt>
          <dd className="break-words text-slate-900">{cash ? remittance.recipient_address : remittance.recipient_account}</dd>
        </dl>
      </section>

      <Link to="/remittances" className="inline-block text-sm font-semibold text-blue-700 hover:underline">← Volver a mis remesas</Link>
    </div>
  )
}
