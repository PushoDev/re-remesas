import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowLeft, ArrowRight, Banknote, Landmark } from 'lucide-react'
import { useForm, useWatch } from 'react-hook-form'
import { inputClass, primaryButtonClass } from '../../lib/formStyles'
import { recipientSchema, type RecipientForm as RecipientValues } from '../../schemas/remittance'

const EMPTY_RECIPIENT: RecipientValues = {
  recipient_name: '',
  recipient_phone: '',
  delivery_method: 'CASH_DELIVERY',
  recipient_address: '',
  recipient_account: '',
}

interface Props {
  defaultValues?: RecipientValues
  onBack: () => void
  onSubmit: (values: RecipientValues) => void
}

function FieldError({ id, message }: { id: string; message?: string }) {
  return message ? (
    <p id={id} className="mt-1 text-sm text-red-600">
      {message}
    </p>
  ) : null
}

export default function RecipientForm({ defaultValues = EMPTY_RECIPIENT, onBack, onSubmit }: Props) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors },
  } = useForm<RecipientValues>({ resolver: zodResolver(recipientSchema), defaultValues })

  const method = useWatch({ control, name: 'delivery_method' })

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="recipient_name" className="text-sm font-medium text-slate-700">Nombre completo del destinatario</label>
          <input
            id="recipient_name"
            autoComplete="off"
            aria-invalid={errors.recipient_name ? 'true' : 'false'}
            aria-describedby={errors.recipient_name ? 'recipient_name-error' : undefined}
            className={inputClass}
            {...register('recipient_name')}
          />
          <FieldError id="recipient_name-error" message={errors.recipient_name?.message} />
        </div>
        <div>
          <label htmlFor="recipient_phone" className="text-sm font-medium text-slate-700">Teléfono móvil en Cuba</label>
          <input
            id="recipient_phone"
            inputMode="tel"
            autoComplete="off"
            placeholder="+53 5123 4567"
            aria-invalid={errors.recipient_phone ? 'true' : 'false'}
            aria-describedby={errors.recipient_phone ? 'recipient_phone-error' : undefined}
            className={inputClass}
            {...register('recipient_phone')}
          />
          <FieldError id="recipient_phone-error" message={errors.recipient_phone?.message} />
        </div>
      </div>

      <fieldset>
        <legend className="text-sm font-medium text-slate-700">¿Cómo lo recibe?</legend>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          {[
            { value: 'CASH_DELIVERY', label: 'Efectivo en Cuba', hint: 'Se lo llevamos a la dirección indicada.', icon: <Banknote className="size-5" aria-hidden /> },
            { value: 'LOCAL_TRANSFER', label: 'Transferencia local', hint: 'A una cuenta o tarjeta en Cuba.', icon: <Landmark className="size-5" aria-hidden /> },
          ].map((option) => (
            <label
              key={option.value}
              className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-200 p-3 has-[:checked]:border-blue-600 has-[:checked]:bg-blue-50 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-blue-600"
            >
              <input type="radio" value={option.value} className="mt-1 size-4 accent-blue-700" {...register('delivery_method')} />
              <span>
                <span className="flex items-center gap-2 font-medium text-slate-900">{option.icon}{option.label}</span>
                <span className="block text-xs text-slate-500">{option.hint}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {method === 'CASH_DELIVERY' ? (
        <div>
          <label htmlFor="recipient_address" className="text-sm font-medium text-slate-700">Dirección de entrega</label>
          <textarea
            id="recipient_address"
            rows={3}
            placeholder="Calle, número, entre calles, municipio y provincia"
            aria-invalid={errors.recipient_address ? 'true' : 'false'}
            aria-describedby={errors.recipient_address ? 'recipient_address-error' : undefined}
            className={inputClass}
            {...register('recipient_address')}
          />
          <FieldError id="recipient_address-error" message={errors.recipient_address?.message} />
        </div>
      ) : (
        <div>
          <label htmlFor="recipient_account" className="text-sm font-medium text-slate-700">Cuenta o tarjeta que recibe</label>
          <input
            id="recipient_account"
            inputMode="numeric"
            autoComplete="off"
            placeholder="9225 1234 5678 9012"
            aria-invalid={errors.recipient_account ? 'true' : 'false'}
            aria-describedby={errors.recipient_account ? 'recipient_account-error' : 'recipient_account-hint'}
            className={inputClass}
            {...register('recipient_account')}
          />
          <p id="recipient_account-hint" className="mt-1 text-xs text-slate-500">Entre 12 y 20 dígitos. Es la cuenta de quien recibe, no la tuya.</p>
          <FieldError id="recipient_account-error" message={errors.recipient_account?.message} />
        </div>
      )}

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
        <button type="button" onClick={onBack} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2.5 font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600">
          <ArrowLeft className="size-5" aria-hidden /> Atrás
        </button>
        <button type="submit" className={`${primaryButtonClass} sm:w-auto`}>
          Continuar <ArrowRight className="size-5" aria-hidden />
        </button>
      </div>
    </form>
  )
}
