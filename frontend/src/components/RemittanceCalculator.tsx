import { ArrowRight, BadgeCheck, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import { useRemittanceQuote } from '../hooks/useRemittanceQuote'
import { parseAmountInput } from '../lib/amount'
import { parseApiError } from '../lib/apiErrors'
import { formatDecimal } from '../lib/decimal'
import { inputClass } from '../lib/formStyles'
import type { CurrencyCode } from '../types/remittances'
import Money from './Money'

export interface CalculatorValues {
  amount: string
  currency: CurrencyCode
}

interface Props {
  initialAmount?: string
  initialCurrency?: CurrencyCode
  /** The button under the result. Enabled only while there is a valid quote. */
  cta: { label: string; onClick: (values: CalculatorValues) => void; hint?: string; disabled?: boolean }
}

/**
 * The remittance calculator. It never computes money itself: every figure comes from the
 * quote endpoint, which applies the member rate automatically. It refreshes while open,
 * so a rate changed by the administrator shows up without reloading.
 */
export default function RemittanceCalculator({ initialAmount = '100', initialCurrency = 'USD', cta }: Props) {
  const { user } = useAuth()
  const [amountText, setAmountText] = useState(initialAmount)
  const [currency, setCurrency] = useState<CurrencyCode>(initialCurrency)

  const debouncedAmount = useDebouncedValue(amountText, 400)
  const parsed = parseAmountInput(debouncedAmount)
  const typing = amountText !== debouncedAmount
  const typed = parseAmountInput(amountText)

  const { data: quote, error, isError, isFetching, isPlaceholderData, refetch } = useRemittanceQuote(
    parsed.normalized,
    currency,
    parsed.valid,
  )

  const apiError = isError ? parseApiError(error) : null
  const amountError = !typed.valid && typed.reason ? typed.reason : (apiError?.fieldErrors.amount?.[0] ?? null)
  const otherError = apiError && !apiError.fieldErrors.amount ? (apiError.fieldErrors.currency?.[0] ?? apiError.message) : null
  const stale = typing || isPlaceholderData
  const showQuote = quote && parsed.valid && !amountError
  const canContinue = Boolean(showQuote) && !typing && !isPlaceholderData && !isFetching && !cta.disabled

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
        <div>
          <label htmlFor="calc-amount" className="text-sm font-medium text-slate-700">
            Tú envías
          </label>
          <input
            id="calc-amount"
            inputMode="decimal"
            autoComplete="off"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
            aria-invalid={amountError ? 'true' : 'false'}
            aria-describedby={amountError ? 'calc-amount-error' : undefined}
            className={`${inputClass} text-lg font-semibold tabular-nums`}
          />
        </div>
        <div>
          <label htmlFor="calc-currency" className="text-sm font-medium text-slate-700">
            Moneda
          </label>
          <select
            id="calc-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value as CurrencyCode)}
            className={`${inputClass} text-lg font-semibold sm:w-32`}
          >
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
        </div>
      </div>
      {amountError && (
        <p id="calc-amount-error" role="alert" className="-mt-3 text-sm text-red-600">
          {amountError}
        </p>
      )}

      {otherError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <span>{otherError}</span>
          <button
            type="button"
            onClick={() => void refetch()}
            className="inline-flex items-center gap-1.5 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100"
          >
            <RefreshCw className="size-4" aria-hidden /> Reintentar
          </button>
        </div>
      )}

      <section
        aria-live="polite"
        aria-label="Resultado del cálculo"
        className={`rounded-2xl border p-5 transition-opacity ${
          quote?.is_vip_rate ? 'border-amber-200 bg-amber-50' : 'border-blue-100 bg-blue-50'
        } ${stale ? 'opacity-60' : ''}`}
      >
        {!showQuote && !otherError && !amountError && (
          <p className="flex items-center gap-2 text-slate-600">
            {parsed.valid ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden /> Calculando…
              </>
            ) : (
              'Escribe un monto para ver cuánto recibe tu familiar.'
            )}
          </p>
        )}

        {showQuote && (
          <>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm text-slate-600">El destinatario recibe</p>
                <p className="mt-1">
                  <Money amount={quote.amount_cup} currency="CUP" className="text-3xl font-bold text-slate-900" />
                </p>
              </div>
              {quote.is_vip_rate && (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-3 py-1 text-sm font-semibold text-white">
                  <BadgeCheck className="size-4" aria-hidden /> Tarifa VIP
                </span>
              )}
            </div>

            <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-slate-600">Tu envío</dt>
              <dd className="text-right font-medium text-slate-900">
                <Money amount={quote.amount} currency={quote.currency} />
              </dd>
              <dt className="text-slate-600">Tasa de cambio</dt>
              <dd className="text-right tabular-nums text-slate-900">
                1 {quote.currency} = {formatDecimal(quote.base_rate)} CUP
              </dd>
              <dt className="text-slate-600">Margen del servicio</dt>
              <dd className="text-right tabular-nums text-slate-900">{formatDecimal(quote.spread_percent)} %</dd>
              <dt className="font-medium text-slate-700">Tasa que se aplica</dt>
              <dd className="text-right font-semibold tabular-nums text-slate-900">
                1 {quote.currency} = {formatDecimal(quote.effective_rate)} CUP
              </dd>
            </dl>

            {quote.is_vip_rate && quote.saving_cup && quote.standard_effective_rate && (
              <p className="mt-4 flex items-start gap-2 rounded-xl bg-white/70 p-3 text-sm text-amber-900">
                <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span>
                  Con tu membresía recibes <strong><Money amount={quote.saving_cup} currency="CUP" /></strong> más que con la
                  tarifa estándar (1 {quote.currency} = {formatDecimal(quote.standard_effective_rate)} CUP).
                </span>
              </p>
            )}
            {!quote.is_vip_rate && user && (
              <p className="mt-4 text-sm text-slate-600">
                ¿Quieres una mejor tasa? Los miembros VIP reciben más CUP por cada envío.{' '}
                <Link to="/membership" className="font-semibold text-blue-700 hover:underline">
                  Ver la membresía
                </Link>
              </p>
            )}
          </>
        )}
      </section>

      <div>
        <button
          type="button"
          disabled={!canContinue}
          onClick={() => parsed.valid && cta.onClick({ amount: parsed.normalized, currency })}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-4 py-3 font-semibold text-white shadow-sm transition hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {cta.label}
          <ArrowRight className="size-5" aria-hidden />
        </button>
        {cta.hint && <p className="mt-2 text-center text-xs text-slate-500">{cta.hint}</p>}
      </div>
    </div>
  )
}
