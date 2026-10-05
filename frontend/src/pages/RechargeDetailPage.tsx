import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, CheckCircle2, Clock, CreditCard, Info, Loader2, Sparkles, XCircle } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import CopyButton from '../components/CopyButton'
import Money from '../components/Money'
import RechargeStatusBadge from '../components/recharges/RechargeStatusBadge'
import { parseApiError } from '../lib/apiErrors'
import { trimDecimal } from '../lib/decimal'
import { FINAL_STATUSES, discountAmount, outcomeMessage } from '../lib/recharges'
import { getRecharge } from '../services/rechargeService'
import type { RechargeOrderDetail } from '../types/recharges'

const dateTime = new Intl.DateTimeFormat('es', { dateStyle: 'long', timeStyle: 'short' })
const REFRESH_MS = 8_000

const TONE = {
  info: 'bg-blue-50 text-blue-900',
  ok: 'bg-emerald-50 text-emerald-900',
  bad: 'bg-red-50 text-red-800',
} as const

function PaymentBlock({ order }: { order: RechargeOrderDetail }) {
  const { payment } = order
  const here = `/recharges/${order.reference}`

  return (
    <section aria-labelledby="payment-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <h2 id="payment-title" className="mb-3 flex items-center gap-2 text-base font-semibold text-slate-900">
        <CreditCard className="size-5" aria-hidden /> Pago
      </h2>
      <p className="text-sm text-slate-600">
        <Money amount={payment.amount} currency={payment.currency} className="font-semibold text-slate-900" />
      </p>
      {payment.status === 'SUCCEEDED' && (
        <p className="mt-3 flex items-center gap-2 text-sm font-medium text-emerald-700"><CheckCircle2 className="size-5" aria-hidden /> Pago recibido</p>
      )}
      {payment.status === 'FAILED' && (
        <p className="mt-3 flex items-start gap-2 text-sm text-red-700">
          <XCircle className="mt-0.5 size-5 shrink-0" aria-hidden /> El pago no se completó. No se hizo ningún cobro; puedes hacer una nueva recarga.
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
      {payment.status === 'PENDING' && !payment.checkout_url && payment.instructions && (
        <p className="mt-3 rounded-xl bg-amber-50 p-3 text-sm text-amber-900">{payment.instructions}</p>
      )}
    </section>
  )
}

export default function RechargeDetailPage() {
  const { reference = '' } = useParams()
  const [params] = useSearchParams()
  const justCreated = params.get('created') === '1'

  const { data: order, isPending, isError, error } = useQuery({
    queryKey: ['recharge', reference],
    queryFn: () => getRecharge(reference),
    retry: false,
    // Follow the order while it can still change (payment confirmation, the provider finishing).
    refetchInterval: (query) => (query.state.data && FINAL_STATUSES.includes(query.state.data.status) ? false : REFRESH_MS),
  })

  const previous = useRef<string | undefined>(undefined)
  useEffect(() => {
    if (order && previous.current && previous.current !== order.status) {
      toast.info(`Tu recarga ahora está: ${order.status_display}.`, { duration: 8000 })
    }
    previous.current = order?.status
  }, [order])

  if (isPending) {
    return (
      <p role="status" className="flex items-center gap-2 text-slate-600">
        <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando la recarga…
      </p>
    )
  }
  if (isError || !order) {
    return (
      <div role="alert" className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">No encontramos esa recarga</h1>
        <p className="mt-2 text-slate-600">Búscala en tu lista de recargas. {isError ? parseApiError(error).message : ''}</p>
        <Link to="/recharges" className="mt-4 inline-block font-semibold text-blue-700 hover:underline">Ver mis recargas</Link>
      </div>
    )
  }

  const outcome = outcomeMessage(order.status, order.payment.status)
  const discount = order.discount_percent_applied !== '0.00'
  const saved = discount ? discountAmount(order.price_base, order.amount_total) : null

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      {justCreated && (
        <div role="status" className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
          <p className="flex items-center gap-2 font-semibold text-emerald-900"><CheckCircle2 className="size-5" aria-hidden /> ¡Tu solicitud quedó registrada!</p>
          <p className="mt-1 text-sm text-emerald-900">Aquí puedes seguir el estado de la recarga.</p>
        </div>
      )}

      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm text-slate-600">Recarga para</p>
          <p className="mt-1 text-2xl font-bold tracking-wide text-slate-900 tabular-nums">{order.phone_number.replace(/^\+53/, '+53 ')}</p>
        </div>
        <RechargeStatusBadge status={order.status} label={order.status_display} />
      </header>
      <p className="text-sm text-slate-500">Creada el {dateTime.format(new Date(order.created_at))}</p>

      <p className={`flex items-start gap-2 rounded-xl p-3 text-sm ${TONE[outcome.tone]}`}>
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
        <span>{outcome.text}</span>
      </p>

      <PaymentBlock order={order} />

      <section aria-labelledby="order-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 id="order-title" className="mb-3 text-base font-semibold text-slate-900">La recarga</h2>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
          <dt className="text-slate-600">Paquete</dt>
          <dd className="text-right font-medium text-slate-900">{order.package.name}</dd>
          <dt className="text-slate-600">Precio</dt>
          <dd className="text-right"><Money amount={order.price_base} currency={order.currency} /></dd>
          {discount && saved && (
            <>
              <dt className="flex items-center gap-1.5 text-amber-800"><BadgeCheck className="size-4" aria-hidden /> Descuento VIP ({trimDecimal(order.discount_percent_applied)} %)</dt>
              <dd className="text-right text-amber-800">−<Money amount={saved} currency={order.currency} /></dd>
            </>
          )}
          <dt className="border-t border-slate-100 pt-2 font-medium text-slate-700">Total</dt>
          <dd className="border-t border-slate-100 pt-2 text-right text-lg font-bold text-slate-900"><Money amount={order.amount_total} currency={order.currency} /></dd>
        </dl>
        {order.promotion && (
          <p className="mt-3 flex items-start gap-2 text-sm text-amber-900">
            <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
            <span><strong>{order.promotion.title}.</strong> {order.promotion.description}</span>
          </p>
        )}
        <p className="mt-3 text-xs text-slate-500">Estas cifras quedaron fijadas al crear la solicitud.</p>
      </section>

      {order.provider_reference && (
        <section aria-labelledby="ref-title" className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 id="ref-title" className="mb-2 text-base font-semibold text-slate-900">Referencia del operador</h2>
          <p className="flex flex-wrap items-center gap-3">
            <span className="font-mono text-lg font-bold text-slate-900">{order.provider_reference}</span>
            <CopyButton text={order.provider_reference} />
          </p>
          {order.provider_message && <p className="mt-2 text-sm text-slate-600">{order.provider_message}</p>}
        </section>
      )}

      <Link to="/recharges" className="inline-block text-sm font-semibold text-blue-700 hover:underline">← Volver a mis recargas</Link>
    </div>
  )
}
