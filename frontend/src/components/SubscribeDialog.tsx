import { useMutation } from '@tanstack/react-query'
import { Info, Loader2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { parseApiError } from '../lib/apiErrors'
import { primaryButtonClass } from '../lib/formStyles'
import { isManualMethod } from '../lib/paymentMethods'
import { subscribe } from '../services/membershipService'
import type { MembershipPlan, PaymentMethodCode, SubscribeResult } from '../types/memberships'
import ErrorAlert from './ErrorAlert'
import Modal from './Modal'
import Money from './Money'
import PaymentMethodPicker from './PaymentMethodPicker'

interface Props {
  plan: MembershipPlan | null
  onClose: () => void
}

export default function SubscribeDialog({ plan, onClose }: Props) {
  const navigate = useNavigate()
  const [method, setMethod] = useState<PaymentMethodCode>('STRIPE')
  const [manualResult, setManualResult] = useState<SubscribeResult | null>(null)

  const mutation = useMutation({
    mutationFn: subscribe,
    onSuccess: (result) => {
      if (result.payment.checkout_url) {
        navigate(result.payment.checkout_url) // simulated gateway page
      } else {
        setManualResult(result) // manual method: show what to do next
      }
    },
  })

  const apiError = mutation.error ? parseApiError(mutation.error) : null
  const manual = isManualMethod(method)

  return (
    <Modal open={plan !== null} onClose={onClose} title={manualResult ? 'Solicitud registrada' : `Suscribirte a ${plan?.name ?? ''}`}>
      {plan && manualResult && (
        <div className="space-y-4">
          <p className="rounded-xl bg-amber-50 p-4 text-sm text-amber-900">{manualResult.payment.instructions}</p>
          <p className="text-sm text-slate-600">
            Referencia: <code className="rounded bg-slate-100 px-1.5 py-0.5">{manualResult.payment.reference}</code>
          </p>
          <button
            type="button"
            onClick={() => navigate(`/membership/result?payment=${manualResult.payment.reference}`)}
            className={primaryButtonClass}
          >
            Entendido
          </button>
        </div>
      )}

      {plan && !manualResult && (
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-xl bg-slate-50 p-4">
            <div>
              <p className="font-semibold text-slate-900">{plan.name}</p>
              <p className="text-sm text-slate-600">{plan.duration_days} días de membresía</p>
            </div>
            <Money amount={plan.price} currency={plan.currency} className="text-xl font-bold text-slate-900" />
          </div>

          {apiError && <ErrorAlert message={apiError.message} />}

          <PaymentMethodPicker value={method} onChange={setMethod} />

          <p className="flex items-start gap-2 text-xs text-slate-500">
            <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
            Tu membresía se activa solo cuando el pago se confirma, no al volver a esta página.
          </p>

          <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
            >
              Cancelar
            </button>
            <button
              type="button"
              disabled={mutation.isPending}
              onClick={() => mutation.mutate({ plan_code: plan.code, payment_method: method })}
              className={`${primaryButtonClass} sm:w-auto`}
            >
              {mutation.isPending && <Loader2 className="size-5 animate-spin" aria-hidden />}
              {manual ? 'Solicitar suscripción' : 'Continuar al pago'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  )
}
