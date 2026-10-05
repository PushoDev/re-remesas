import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation } from '@tanstack/react-query'
import { Loader2 } from 'lucide-react'
import { useForm, useWatch } from 'react-hook-form'
import { toast } from 'sonner'
import { parseApiError } from '../../lib/apiErrors'
import { formatDecimal, previewEffectiveRate, trimDecimal } from '../../lib/decimal'
import { inputClass, primaryButtonClass } from '../../lib/formStyles'
import { exchangeRateSchema, type ExchangeRateForm as FormValues } from '../../schemas/exchangeRate'
import { createExchangeRate, updateExchangeRate } from '../../services/exchangeRateService'
import type { AdminExchangeRate } from '../../types/exchangeRates'

const FIELDS = ['currency', 'base_rate', 'standard_spread_percent', 'vip_spread_percent', 'is_active'] as const

interface Props {
  /** Present when editing; absent when creating. */
  rate?: AdminExchangeRate
  onSaved: () => void
  onCancel: () => void
}

function Field({ id, label, hint, error, children }: { id: string; label: string; hint?: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-slate-500">{hint}</p>}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-sm text-red-600">
          {error}
        </p>
      )}
    </div>
  )
}

export default function ExchangeRateForm({ rate, onSaved, onCancel }: Props) {
  const editing = Boolean(rate)

  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(exchangeRateSchema),
    defaultValues: {
      currency: rate?.currency ?? 'USD',
      base_rate: rate ? trimDecimal(rate.base_rate) : '',
      standard_spread_percent: rate ? trimDecimal(rate.standard_spread_percent) : '5',
      vip_spread_percent: rate ? trimDecimal(rate.vip_spread_percent) : '2',
      is_active: rate?.is_active ?? true,
    },
  })

  const [currency, base, standard, vip] = useWatch({
    control,
    name: ['currency', 'base_rate', 'standard_spread_percent', 'vip_spread_percent'],
  })
  const previewStandard = previewEffectiveRate(base, standard)
  const previewVip = previewEffectiveRate(base, vip)

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const payload = {
        base_rate: values.base_rate.trim().replace(',', '.'),
        standard_spread_percent: values.standard_spread_percent.trim().replace(',', '.'),
        vip_spread_percent: values.vip_spread_percent.trim().replace(',', '.'),
        is_active: values.is_active,
      }
      return rate ? updateExchangeRate(rate.id, payload) : createExchangeRate({ currency: values.currency, ...payload })
    },
    onSuccess: () => {
      toast.success(editing ? 'Tasa actualizada. Se aplica ya en las cotizaciones.' : 'Tasa creada.')
      onSaved()
    },
    onError: (error) => {
      const { fieldErrors, message } = parseApiError(error)
      let placed = false
      for (const field of FIELDS) {
        if (fieldErrors[field]) {
          setError(field, { message: fieldErrors[field].join(' ') })
          placed = true
        }
      }
      if (!placed) toast.error(message)
    },
  })

  return (
    <form onSubmit={handleSubmit((values) => mutation.mutate(values))} noValidate className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field id="currency" label="Moneda de origen" error={errors.currency?.message}>
          <select id="currency" disabled={editing} className={inputClass} {...register('currency')}>
            <option value="USD">USD · Dólar estadounidense</option>
            <option value="EUR">EUR · Euro</option>
          </select>
        </Field>
        <Field id="base_rate" label={`Tasa base (CUP por 1 ${currency})`} error={errors.base_rate?.message}>
          <input
            id="base_rate"
            inputMode="decimal"
            autoComplete="off"
            placeholder="700"
            aria-invalid={errors.base_rate ? 'true' : 'false'}
            aria-describedby={errors.base_rate ? 'base_rate-error' : undefined}
            className={inputClass}
            {...register('base_rate')}
          />
        </Field>
        <Field
          id="standard_spread_percent"
          label="Margen estándar (%)"
          hint="Lo que se queda la plataforma con un cliente normal."
          error={errors.standard_spread_percent?.message}
        >
          <input
            id="standard_spread_percent"
            inputMode="decimal"
            autoComplete="off"
            aria-invalid={errors.standard_spread_percent ? 'true' : 'false'}
            aria-describedby={errors.standard_spread_percent ? 'standard_spread_percent-error' : undefined}
            className={inputClass}
            {...register('standard_spread_percent')}
          />
        </Field>
        <Field
          id="vip_spread_percent"
          label="Margen VIP (%)"
          hint="Menor o igual al estándar: es la ventaja de ser miembro."
          error={errors.vip_spread_percent?.message}
        >
          <input
            id="vip_spread_percent"
            inputMode="decimal"
            autoComplete="off"
            aria-invalid={errors.vip_spread_percent ? 'true' : 'false'}
            aria-describedby={errors.vip_spread_percent ? 'vip_spread_percent-error' : undefined}
            className={inputClass}
            {...register('vip_spread_percent')}
          />
        </Field>
      </div>

      <div>
        <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
          <input type="checkbox" className="size-4 rounded border-slate-300" {...register('is_active')} />
          Tasa activa (solo puede haber una activa por moneda)
        </label>
        {errors.is_active && <p className="mt-1 text-sm text-red-600">{errors.is_active.message}</p>}
      </div>

      <section aria-label="Vista previa" className="rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
        <p className="font-semibold">Vista previa · 1 {currency} equivale a:</p>
        <dl className="mt-2 grid grid-cols-2 gap-2">
          <div>
            <dt className="text-blue-700">Cliente estándar</dt>
            <dd className="text-base font-semibold">{previewStandard ? `${formatDecimal(previewStandard)} CUP` : '—'}</dd>
          </div>
          <div>
            <dt className="text-blue-700">Cliente VIP</dt>
            <dd className="text-base font-semibold">{previewVip ? `${formatDecimal(previewVip)} CUP` : '—'}</dd>
          </div>
        </dl>
        <p className="mt-2 text-xs text-blue-700">Orientativa: el cálculo oficial lo hace el servidor.</p>
      </section>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
        >
          Cancelar
        </button>
        <button type="submit" disabled={mutation.isPending} className={`${primaryButtonClass} sm:w-auto`}>
          {mutation.isPending && <Loader2 className="size-5 animate-spin" aria-hidden />}
          {editing ? 'Guardar cambios' : 'Crear tasa'}
        </button>
      </div>
    </form>
  )
}
