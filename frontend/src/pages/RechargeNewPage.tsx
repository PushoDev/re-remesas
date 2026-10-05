import { useMutation, useQuery } from '@tanstack/react-query'
import { BadgeCheck, Loader2, RefreshCw, Sparkles } from 'lucide-react'
import { useId, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import ErrorAlert from '../components/ErrorAlert'
import Money from '../components/Money'
import PaymentMethodPicker from '../components/PaymentMethodPicker'
import { parseApiError } from '../lib/apiErrors'
import { trimDecimal } from '../lib/decimal'
import { inputClass, primaryButtonClass } from '../lib/formStyles'
import { contactToInput, groupByKind, phoneFromInput } from '../lib/recharges'
import { createRecharge, listPackages, listRecentContacts, quoteRecharge } from '../services/rechargeService'
import type { PaymentMethodCode } from '../types/memberships'
import type { CatalogPackage } from '../types/recharges'

const day = new Intl.DateTimeFormat('es', { dateStyle: 'medium' })

function PromotionBadge({ title, endsAt }: { title: string; endsAt: string }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
      <Sparkles className="size-3.5" aria-hidden />
      {title}
      <span className="font-normal text-amber-800">· hasta el {day.format(new Date(endsAt))}</span>
    </span>
  )
}

function PackageOption({ pkg, selected, onSelect }: { pkg: CatalogPackage; selected: boolean; onSelect: () => void }) {
  return (
    <label
      className={`flex cursor-pointer flex-col gap-1.5 rounded-xl border p-4 transition has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-blue-600 ${
        selected ? 'border-blue-600 bg-blue-50' : 'border-slate-200 bg-white hover:border-slate-300'
      }`}
    >
      <input type="radio" name="package" value={pkg.code} checked={selected} onChange={onSelect} className="sr-only" />
      <span className="flex items-start justify-between gap-3">
        <span className="font-semibold text-slate-900">{pkg.name}</span>
        <Money amount={pkg.price} currency={pkg.currency} className="shrink-0 font-bold text-slate-900" />
      </span>
      {pkg.description && <span className="text-sm text-slate-600">{pkg.description}</span>}
      {pkg.active_promotion && (
        <span className="space-y-1">
          <PromotionBadge title={pkg.active_promotion.title} endsAt={pkg.active_promotion.ends_at} />
          {pkg.active_promotion.description && <span className="block text-xs text-slate-600">{pkg.active_promotion.description}</span>}
        </span>
      )}
    </label>
  )
}

export default function RechargeNewPage() {
  const navigate = useNavigate()
  const phoneId = useId()
  const phoneHelpId = useId()
  const [phoneText, setPhoneText] = useState('')
  const [touched, setTouched] = useState(false)
  const [packageCode, setPackageCode] = useState<string | null>(null)
  const [method, setMethod] = useState<PaymentMethodCode>('STRIPE')

  const phone = phoneFromInput(phoneText)
  const phoneError = !touched
    ? null
    : !phoneText.trim()
      ? 'Ingresa el número que vas a recargar.'
      : phone
        ? null
        : 'Escribe un móvil cubano válido: 8 dígitos que empiezan por 5.'

  const contacts = useQuery({ queryKey: ['recharge-contacts'], queryFn: listRecentContacts })
  const catalog = useQuery({
    queryKey: ['recharge-packages'],
    queryFn: listPackages,
    refetchInterval: 60_000, // promotions start and end by the clock
  })
  const selected = catalog.data?.find((pkg) => pkg.code === packageCode) ?? null

  const quote = useQuery({
    queryKey: ['recharge-quote', phone, selected?.code],
    queryFn: () => quoteRecharge({ phone_number: phone ?? '', package_code: selected?.code ?? '' }),
    enabled: Boolean(phone && selected),
    retry: false,
  })

  const create = useMutation({
    mutationFn: createRecharge,
    onSuccess: ({ order, payment }) => {
      toast.success('Solicitud registrada.')
      const detail = `/recharges/${order.reference}?created=1`
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
    setTouched(true)
    if (!phone || !selected || !quote.data) return
    create.mutate({ phone_number: phone, package_code: selected.code, payment_method: method })
  }

  const groups = groupByKind(catalog.data ?? [])
  const discount = quote.data && quote.data.discount_percent !== '0.00' ? quote.data : null

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Recargar un móvil en Cuba</h1>
          <p className="text-slate-600">Saldo o paquetes de datos y voz para un número ETECSA.</p>
        </div>
        <Link to="/recharges" className="text-sm font-semibold text-blue-700 hover:underline">Mis recargas</Link>
      </div>

      <section aria-labelledby="phone-title" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="phone-title" className="text-lg font-semibold text-slate-900">1. ¿Qué número vas a recargar?</h2>
        <div className="mt-3">
          <label htmlFor={phoneId} className="block text-sm font-medium text-slate-800">Teléfono móvil en Cuba</label>
          <div className="mt-1 flex">
            <span className="inline-flex items-center rounded-l-lg border border-r-0 border-slate-300 bg-slate-100 px-3 font-medium text-slate-700" aria-hidden>+53</span>
            <input
              id={phoneId}
              type="tel"
              inputMode="tel"
              autoComplete="off"
              value={phoneText}
              onChange={(event) => setPhoneText(event.target.value)}
              onBlur={() => setTouched(true)}
              placeholder="5123 4567"
              aria-invalid={Boolean(phoneError)}
              aria-describedby={phoneHelpId}
              className={`${inputClass} !mt-0 !rounded-l-none`}
            />
          </div>
          <p id={phoneHelpId} role={phoneError ? 'alert' : undefined} className={`mt-1 text-sm ${phoneError ? 'text-red-600' : 'text-slate-500'}`}>
            {phoneError ?? 'Móvil cubano: 8 dígitos que empiezan por 5.'}
          </p>
        </div>

        {contacts.data && contacts.data.length > 0 && (
          <div className="mt-4">
            <p className="text-sm font-medium text-slate-800">Contactos recientes</p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {contacts.data.map((contact) => (
                <li key={contact.phone_number}>
                  <button
                    type="button"
                    onClick={() => { setPhoneText(contactToInput(contact.phone_number)); setTouched(true) }}
                    aria-pressed={phone === contact.phone_number}
                    className={`rounded-full border px-3 py-1.5 text-sm font-medium tabular-nums transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
                      phone === contact.phone_number ? 'border-blue-700 bg-blue-700 text-white' : 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                    }`}
                  >
                    {contact.phone_number.replace(/^\+53/, '+53 ')}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section aria-labelledby="package-title" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="package-title" className="text-lg font-semibold text-slate-900">2. Elige qué enviar</h2>

        {catalog.isPending && (
          <p role="status" className="mt-3 flex items-center gap-2 text-slate-600">
            <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando los paquetes…
          </p>
        )}
        {catalog.isError && (
          <div role="alert" className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-red-200 bg-red-50 p-3 text-red-700">
            <span>No se pudieron cargar los paquetes. {parseApiError(catalog.error).message}</span>
            <button type="button" onClick={() => void catalog.refetch()} disabled={catalog.isFetching} className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60">
              <RefreshCw className="size-4" aria-hidden /> Reintentar
            </button>
          </div>
        )}
        {catalog.data && groups.length === 0 && (
          <p className="mt-3 rounded-xl border border-dashed border-slate-300 p-6 text-center text-slate-600">No hay paquetes disponibles en este momento.</p>
        )}

        <div className="mt-3 space-y-5">
          {groups.map((group) => (
            <fieldset key={group.kind}>
              <legend className="mb-2 text-sm font-semibold text-slate-700">{group.title}</legend>
              <div className="grid gap-3 sm:grid-cols-2">
                {group.packages.map((pkg) => (
                  <PackageOption key={pkg.code} pkg={pkg} selected={packageCode === pkg.code} onSelect={() => setPackageCode(pkg.code)} />
                ))}
              </div>
            </fieldset>
          ))}
        </div>
      </section>

      <section aria-labelledby="pay-title" className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 id="pay-title" className="text-lg font-semibold text-slate-900">3. Revisa y paga</h2>

        {!selected || !phone ? (
          <p className="text-sm text-slate-600">
            {!phone ? 'Escribe un número válido' : 'Elige un paquete'} para ver el precio.
          </p>
        ) : quote.isPending ? (
          <p role="status" className="flex items-center gap-2 text-slate-600">
            <Loader2 className="size-5 animate-spin" aria-hidden /> Calculando el precio…
          </p>
        ) : quote.isError ? (
          <ErrorAlert message={(() => {
            const { message, fieldErrors } = parseApiError(quote.error)
            return Object.values(fieldErrors).flat().join(' ') || message
          })()} />
        ) : (
          <div className="rounded-xl bg-slate-50 p-4">
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm">
              <dt className="text-slate-600">Paquete</dt>
              <dd className="text-right font-medium text-slate-900">{quote.data.package.name}</dd>
              <dt className="text-slate-600">Número</dt>
              <dd className="text-right tabular-nums text-slate-900">{quote.data.phone_number.replace(/^\+53/, '+53 ')}</dd>
              <dt className="text-slate-600">Precio</dt>
              <dd className="text-right"><Money amount={quote.data.price_base} currency={quote.data.currency} /></dd>
              {discount && (
                <>
                  <dt className="flex items-center gap-1.5 text-amber-800"><BadgeCheck className="size-4" aria-hidden /> Descuento VIP ({trimDecimal(discount.discount_percent)} %)</dt>
                  <dd className="text-right text-amber-800">−<Money amount={discount.discount_amount} currency={discount.currency} /></dd>
                </>
              )}
              <dt className="border-t border-slate-200 pt-2 font-medium text-slate-700">Total a pagar</dt>
              <dd className="border-t border-slate-200 pt-2 text-right text-lg font-bold text-slate-900"><Money amount={quote.data.amount_total} currency={quote.data.currency} /></dd>
            </dl>
            {quote.data.active_promotion && (
              <p className="mt-3 flex items-start gap-2 text-sm text-amber-900">
                <Sparkles className="mt-0.5 size-4 shrink-0" aria-hidden />
                <span><strong>{quote.data.active_promotion.title}.</strong> {quote.data.active_promotion.description}</span>
              </p>
            )}
            {!quote.data.is_vip && (
              <p className="mt-3 text-xs text-slate-600">
                ¿Recargas seguido? Los miembros VIP tienen descuento en recargas. <Link to="/membership" className="font-semibold text-blue-700 hover:underline">Ver la membresía</Link>
              </p>
            )}
          </div>
        )}

        <div>
          <p className="mb-2 text-sm font-medium text-slate-800">¿Cómo vas a pagar?</p>
          <PaymentMethodPicker value={method} onChange={setMethod} kinds={['online']} />
        </div>

        {submitError && <ErrorAlert message={submitError} />}

        <button type="button" onClick={confirm} disabled={create.isPending || !quote.data} className={primaryButtonClass}>
          {create.isPending && <Loader2 className="size-5 animate-spin" aria-hidden />}
          Confirmar y continuar al pago
        </button>
        <p className="text-xs text-slate-500">El importe definitivo lo fija el servidor al crear la solicitud. La recarga se envía cuando el pago se confirma.</p>
      </section>
    </div>
  )
}
