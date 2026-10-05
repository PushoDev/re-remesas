import { useQuery, useQueryClient } from '@tanstack/react-query'
import { BadgeCheck, CircleX, Clock, Hourglass, Loader2 } from 'lucide-react'
import { useEffect } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import Money from '../components/Money'
import { useAuth } from '../hooks/useAuth'
import { parseApiError } from '../lib/apiErrors'
import { describeMembership, formatDate } from '../lib/membership'
import { paymentOutcome } from '../lib/paymentOutcome'
import { getPayment } from '../services/membershipService'

const linkButton =
  'inline-flex items-center justify-center rounded-lg px-4 py-2.5 font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2'

/**
 * Where the user lands after paying. It never trusts the URL: the reference only
 * says which payment to look up, and what is shown comes from the API.
 */
export default function MembershipResultPage() {
  const [params] = useSearchParams()
  const reference = params.get('payment')
  const { user, refreshUser } = useAuth()
  const queryClient = useQueryClient()

  const { data: payment, isPending, isError, error } = useQuery({
    queryKey: ['payment', reference],
    queryFn: () => getPayment(reference as string),
    enabled: Boolean(reference),
    // While an online payment is still pending, keep checking: the gateway's webhook may be on its way.
    refetchInterval: (query) => {
      const data = query.state.data
      return data && data.status === 'PENDING' && !data.requires_manual_confirmation ? 3000 : false
    },
  })

  const paid = payment?.status === 'SUCCEEDED'
  useEffect(() => {
    if (!paid) return
    void refreshUser() // the badge and expiry everywhere must reflect the new membership
    void queryClient.invalidateQueries({ queryKey: ['me'] })
  }, [paid, refreshUser, queryClient])

  if (!reference) return <Navigate to="/membership" replace />

  if (isPending) {
    return (
      <p role="status" className="flex items-center gap-2 text-slate-600">
        <Loader2 className="size-5 animate-spin" aria-hidden /> Comprobando tu pago…
      </p>
    )
  }
  if (isError) {
    return (
      <div role="alert" className="mx-auto max-w-md rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-red-700">
        <p>No pudimos consultar ese pago. {parseApiError(error).message}</p>
        <Link to="/membership" className="mt-3 inline-block font-semibold underline">Volver a la membresía</Link>
      </div>
    )
  }

  const outcome = paymentOutcome(payment)
  const view = user ? describeMembership(user.profile) : null

  const content = {
    paid: {
      icon: <BadgeCheck className="mx-auto size-12 text-emerald-600" aria-hidden />,
      title: '¡Listo! Ya eres VIP',
      text:
        view?.kind === 'vip' && view.expiresAt
          ? `Tu membresía está activa hasta el ${formatDate(view.expiresAt)}.`
          : 'Tu membresía está activa.',
    },
    failed: {
      icon: <CircleX className="mx-auto size-12 text-red-600" aria-hidden />,
      title: 'No se completó el pago',
      text: 'No se hizo ningún cobro y tu membresía no cambió. Puedes intentarlo de nuevo.',
    },
    'in-review': {
      icon: <Clock className="mx-auto size-12 text-amber-500" aria-hidden />,
      title: 'Pago en revisión',
      text: 'Un administrador verificará tu comprobante y lo confirmará. Verás tu membresía activa en cuanto lo haga.',
    },
    'awaiting-payment': {
      icon: <Hourglass className="mx-auto size-12 text-blue-600" aria-hidden />,
      title: 'Esperando la confirmación del pago',
      text: 'Todavía no recibimos la confirmación. Esta página se actualiza sola.',
    },
  }[outcome]

  return (
    <section aria-live="polite" className="mx-auto max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
      {content.icon}
      <h1 className="mt-4 text-xl font-semibold text-slate-900">{content.title}</h1>
      <p className="mt-2 text-slate-600">{content.text}</p>
      <p className="mt-4 text-sm text-slate-500">
        Pago de <Money amount={payment.amount} currency={payment.currency} className="font-semibold text-slate-700" />
      </p>
      {payment.instructions && outcome === 'in-review' && (
        <p className="mt-4 rounded-xl bg-amber-50 p-3 text-left text-sm text-amber-900">{payment.instructions}</p>
      )}
      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-center">
        {outcome === 'awaiting-payment' && payment.checkout_url && (
          <Link to={payment.checkout_url} className={`${linkButton} bg-blue-700 text-white hover:bg-blue-800`}>Ir a pagar</Link>
        )}
        {outcome === 'failed' && (
          <Link to="/membership" className={`${linkButton} bg-blue-700 text-white hover:bg-blue-800`}>Intentar de nuevo</Link>
        )}
        <Link to="/profile" className={`${linkButton} border border-slate-300 bg-white text-slate-800 hover:bg-slate-100`}>
          Ver mi perfil
        </Link>
      </div>
    </section>
  )
}
