import { useMutation, useQuery } from '@tanstack/react-query'
import { FlaskConical, Loader2 } from 'lucide-react'
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom'
import ErrorAlert from '../components/ErrorAlert'
import LoadingScreen from '../components/LoadingScreen'
import Money from '../components/Money'
import { parseApiError } from '../lib/apiErrors'
import { paymentMethodLabel } from '../lib/paymentMethods'
import { confirmMockPayment, getPayment } from '../services/membershipService'

const PURPOSE_LABEL = { MEMBERSHIP: 'Membresía VIP', REMITTANCE: 'Remesa', RECHARGE: 'Recarga' } as const

/**
 * Stand-in for a payment gateway's hosted page. Nothing is charged: it exists to
 * exercise the real flow (pay -> signed webhook -> membership activated).
 */
export default function MockCheckoutPage() {
  const { reference = '' } = useParams()
  const navigate = useNavigate()

  const { data: payment, isPending, isError, error } = useQuery({
    queryKey: ['payment', reference],
    queryFn: () => getPayment(reference),
  })

  const settle = useMutation({
    mutationFn: (outcome: 'succeeded' | 'failed') => confirmMockPayment(reference, outcome),
    onSuccess: () => navigate(`/membership/result?payment=${reference}`, { replace: true }),
  })

  if (isPending) return <LoadingScreen />

  if (isError) {
    return (
      <main className="mx-auto mt-16 max-w-md px-4">
        <ErrorAlert message={`No pudimos encontrar ese pago. ${parseApiError(error).message}`} />
        <Link to="/membership" className="font-semibold text-blue-700 hover:underline">Volver a la membresía</Link>
      </main>
    )
  }

  // Already settled (for instance the user pressed "back"): show the outcome instead.
  if (payment.status !== 'PENDING') {
    return <Navigate to={`/membership/result?payment=${reference}`} replace />
  }

  const apiError = settle.error ? parseApiError(settle.error) : null

  return (
    <main className="flex min-h-dvh items-center justify-center bg-slate-100 px-4 py-10">
      <section aria-labelledby="checkout-title" className="w-full max-w-md overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-center gap-2 bg-amber-100 px-6 py-3 text-sm font-semibold text-amber-900">
          <FlaskConical className="size-4" aria-hidden />
          Pasarela de pago simulada · no se cobra nada
        </div>
        <div className="space-y-5 p-6">
          <div>
            <h1 id="checkout-title" className="text-lg font-semibold text-slate-900">
              {PURPOSE_LABEL[payment.purpose]}
            </h1>
            <p className="text-sm text-slate-500">Medio elegido: {paymentMethodLabel(payment.method)}</p>
          </div>
          <p className="text-center">
            <Money amount={payment.amount} currency={payment.currency} className="text-4xl font-bold text-slate-900" />
          </p>

          {apiError && <ErrorAlert message={apiError.message} />}

          <div className="space-y-3">
            <button
              type="button"
              disabled={settle.isPending}
              onClick={() => settle.mutate('succeeded')}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-emerald-600 px-4 py-3 font-semibold text-white hover:bg-emerald-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-70"
            >
              {settle.isPending && <Loader2 className="size-5 animate-spin" aria-hidden />}
              Pagar
            </button>
            <button
              type="button"
              disabled={settle.isPending}
              onClick={() => settle.mutate('failed')}
              className="w-full rounded-lg border border-red-200 bg-white px-4 py-2.5 font-medium text-red-700 hover:bg-red-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 disabled:opacity-70"
            >
              Simular un pago fallido
            </button>
            <Link to="/membership" className="block text-center text-sm font-medium text-slate-600 hover:underline">
              Cancelar y volver
            </Link>
          </div>
        </div>
      </section>
    </main>
  )
}
