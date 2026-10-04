import { useMutation } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { toast } from 'sonner'
import PaymentMethodPicker from '../components/PaymentMethodPicker'
import RecipientForm from '../components/remittances/RecipientForm'
import RemittanceSummary from '../components/remittances/RemittanceSummary'
import RemittanceCalculator, { type CalculatorValues } from '../components/RemittanceCalculator'
import StepIndicator from '../components/StepIndicator'
import { parseAmountInput } from '../lib/amount'
import { parseApiError } from '../lib/apiErrors'
import { normalizeCubanMobile } from '../lib/phone'
import type { RecipientForm as RecipientValues } from '../schemas/remittance'
import { createRemittance } from '../services/remittanceService'
import type { PaymentMethodCode } from '../types/memberships'
import type { CurrencyCode } from '../types/remittances'

const STEPS = ['Monto', 'Destinatario', 'Pago', 'Resumen']

export default function RemittanceNewPage() {
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const initial = parseAmountInput(params.get('amount') ?? '')

  const [step, setStep] = useState(1)
  const [money, setMoney] = useState<CalculatorValues | null>(null)
  const [recipient, setRecipient] = useState<RecipientValues | undefined>(undefined)
  const [method, setMethod] = useState<PaymentMethodCode>('STRIPE')

  useEffect(() => window.scrollTo(0, 0), [step])

  const create = useMutation({
    mutationFn: createRemittance,
    onSuccess: ({ remittance, payment }) => {
      toast.success('Solicitud registrada.')
      const detail = `/remittances/${remittance.tracking_id}?created=1`
      // Online methods go to the (simulated) gateway first and come back to the detail page.
      navigate(payment.checkout_url ? `${payment.checkout_url}?next=${encodeURIComponent(detail)}` : detail)
    },
  })

  const submitError = create.error
    ? (() => {
        const { message, fieldErrors } = parseApiError(create.error)
        const details = Object.values(fieldErrors).flat()
        return details.length > 0 ? details.join(' ') : message
      })()
    : null

  const confirm = () => {
    if (!money || !recipient) return
    create.mutate({
      amount: money.amount,
      currency: money.currency,
      recipient_name: recipient.recipient_name,
      recipient_phone: normalizeCubanMobile(recipient.recipient_phone) ?? recipient.recipient_phone,
      delivery_method: recipient.delivery_method,
      recipient_address: recipient.delivery_method === 'CASH_DELIVERY' ? recipient.recipient_address : '',
      recipient_account: recipient.delivery_method === 'LOCAL_TRANSFER' ? recipient.recipient_account : '',
      payment_method: method,
    })
  }

  const currency: CurrencyCode = params.get('currency') === 'EUR' ? 'EUR' : 'USD'

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold text-slate-900">Enviar dinero a Cuba</h1>
        <StepIndicator steps={STEPS} current={step} />
      </div>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {step === 1 && (
          <RemittanceCalculator
            initialAmount={money?.amount ?? (initial.valid ? initial.normalized : '100')}
            initialCurrency={money?.currency ?? currency}
            cta={{ label: 'Continuar', onClick: (values) => { setMoney(values); setStep(2) } }}
          />
        )}

        {step === 2 && (
          <RecipientForm
            defaultValues={recipient}
            onBack={() => setStep(1)}
            onSubmit={(values) => { setRecipient(values); setStep(3) }}
          />
        )}

        {step === 3 && (
          <div className="space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">¿Cómo vas a pagar?</h2>
              <p className="text-sm text-slate-600">Elige el medio de pago de tu envío.</p>
            </div>
            <PaymentMethodPicker value={method} onChange={setMethod} />
            <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
              <button type="button" onClick={() => setStep(2)} className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-100">Atrás</button>
              <button type="button" onClick={() => setStep(4)} className="rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white hover:bg-blue-800">Continuar</button>
            </div>
          </div>
        )}

        {step === 4 && money && recipient && (
          <RemittanceSummary
            amount={money.amount}
            currency={money.currency}
            recipient={recipient}
            paymentMethod={method}
            onEdit={(target) => setStep(target)}
            onBack={() => setStep(3)}
            onConfirm={confirm}
            submitting={create.isPending}
            submitError={submitError}
          />
        )}
      </section>
    </div>
  )
}
