import { ArrowLeft, BadgeCheck, Info, Loader2, Pencil } from 'lucide-react'
import type { ReactNode } from 'react'
import { useRemittanceQuote } from '../../hooks/useRemittanceQuote'
import { parseApiError } from '../../lib/apiErrors'
import { formatDecimal } from '../../lib/decimal'
import { paymentMethodLabel } from '../../lib/paymentMethods'
import { primaryButtonClass } from '../../lib/formStyles'
import type { RecipientForm } from '../../schemas/remittance'
import type { PaymentMethodCode } from '../../types/memberships'
import type { CurrencyCode } from '../../types/remittances'
import ErrorAlert from '../ErrorAlert'
import Money from '../Money'

interface Props {
  amount: string
  currency: CurrencyCode
  recipient: RecipientForm
  paymentMethod: PaymentMethodCode
  onEdit: (step: 1 | 2 | 3) => void
  onBack: () => void
  onConfirm: () => void
  submitting: boolean
  submitError: string | null
}

function Block({ title, step, onEdit, children }: { title: string; step: 1 | 2 | 3; onEdit: (step: 1 | 2 | 3) => void; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-200 p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <button type="button" onClick={() => onEdit(step)} className="inline-flex items-center gap-1 text-sm font-medium text-blue-700 hover:underline">
          <Pencil className="size-3.5" aria-hidden /> Editar
        </button>
      </div>
      {children}
    </section>
  )
}

export default function RemittanceSummary({ amount, currency, recipient, paymentMethod, onEdit, onBack, onConfirm, submitting, submitError }: Props) {
  const { data: quote, error, isError, isPlaceholderData, isFetching } = useRemittanceQuote(amount, currency, true)
  const apiError = isError ? parseApiError(error).fieldErrors.currency?.[0] ?? parseApiError(error).message : null
  const ready = Boolean(quote) && !isPlaceholderData && !isFetching && !apiError

  return (
    <div className="space-y-4">
      {apiError && <ErrorAlert message={apiError} />}
      {submitError && <ErrorAlert message={submitError} />}

      <Block title="Monto" step={1} onEdit={onEdit}>
        {quote ? (
          <div className="space-y-1 text-sm">
            <p className="flex items-center justify-between">
              <span className="text-slate-600">Tú envías</span>
              <Money amount={quote.amount} currency={quote.currency} className="font-semibold text-slate-900" />
            </p>
            <p className="flex items-center justify-between">
              <span className="text-slate-600">Tasa que se aplica {quote.is_vip_rate && <BadgeCheck className="inline size-4 text-amber-500" aria-label="Tarifa VIP" />}</span>
              <span className="tabular-nums text-slate-900">1 {quote.currency} = {formatDecimal(quote.effective_rate)} CUP</span>
            </p>
            <p className="flex items-center justify-between border-t border-slate-100 pt-2">
              <span className="font-medium text-slate-700">El destinatario recibe</span>
              <Money amount={quote.amount_cup} currency="CUP" className="text-lg font-bold text-slate-900" />
            </p>
            {quote.saving_cup && (
              <p className="text-xs text-amber-800">Con tu tarifa VIP recibe <Money amount={quote.saving_cup} currency="CUP" /> más que con la estándar.</p>
            )}
          </div>
        ) : (
          <p className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="size-4 animate-spin" aria-hidden /> Calculando…</p>
        )}
      </Block>

      <Block title="Destinatario y entrega" step={2} onEdit={onEdit}>
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-slate-600">Nombre</dt><dd className="text-slate-900">{recipient.recipient_name}</dd>
          <dt className="text-slate-600">Teléfono</dt><dd className="text-slate-900">{recipient.recipient_phone}</dd>
          <dt className="text-slate-600">Entrega</dt>
          <dd className="text-slate-900">{recipient.delivery_method === 'CASH_DELIVERY' ? 'Efectivo en Cuba' : 'Transferencia local'}</dd>
          <dt className="text-slate-600">{recipient.delivery_method === 'CASH_DELIVERY' ? 'Dirección' : 'Cuenta'}</dt>
          <dd className="break-words text-slate-900">
            {recipient.delivery_method === 'CASH_DELIVERY' ? recipient.recipient_address : recipient.recipient_account}
          </dd>
        </dl>
      </Block>

      <Block title="Medio de pago" step={3} onEdit={onEdit}>
        <p className="text-sm text-slate-900">{paymentMethodLabel(paymentMethod)}</p>
      </Block>

      <p className="flex items-start gap-2 text-xs text-slate-500">
        <Info className="mt-0.5 size-4 shrink-0" aria-hidden />
        Las cifras definitivas se fijan al crear la solicitud, con la tasa vigente en ese momento; las verás en el detalle.
      </p>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
        <button type="button" onClick={onBack} disabled={submitting} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 disabled:opacity-60">
          <ArrowLeft className="size-5" aria-hidden /> Atrás
        </button>
        <button type="button" onClick={onConfirm} disabled={!ready || submitting} className={`${primaryButtonClass} sm:w-auto`}>
          {submitting && <Loader2 className="size-5 animate-spin" aria-hidden />}
          Confirmar y continuar al pago
        </button>
      </div>
    </div>
  )
}
