import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, CalendarClock, Check, Loader2, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import Money from '../components/Money'
import SubscribeDialog from '../components/SubscribeDialog'
import { useAuth } from '../hooks/useAuth'
import { parseApiError } from '../lib/apiErrors'
import { describeMembership, formatDate, formatDaysLeft } from '../lib/membership'
import { listPlans } from '../services/membershipService'
import type { MembershipPlan } from '../types/memberships'

const PERIOD_LABEL = { MONTHLY: 'Mensual', ANNUAL: 'Anual' } as const

export default function MembershipPage() {
  const { user } = useAuth()
  const [selected, setSelected] = useState<MembershipPlan | null>(null)

  const { data: plans, isPending, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['membership-plans'],
    queryFn: listPlans,
  })

  const view = user ? describeMembership(user.profile) : { kind: 'free' as const }
  const isVip = view.kind === 'vip'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Membresía VIP</h1>
        <p className="mt-1 text-slate-600">
          Mejores tasas de cambio en tus remesas y descuentos en tus recargas telefónicas.
        </p>
      </div>

      <section
        aria-label="Tu membresía"
        className={`flex flex-wrap items-center gap-3 rounded-2xl border p-4 ${
          isVip ? 'border-amber-200 bg-amber-50' : 'border-slate-200 bg-white'
        }`}
      >
        {isVip ? (
          <>
            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-3 py-1 text-sm font-semibold text-white">
              <BadgeCheck className="size-4" aria-hidden /> VIP
            </span>
            {view.expiresAt && view.daysLeft !== null ? (
              <span className="flex items-center gap-2 text-sm text-slate-700">
                <CalendarClock className="size-4" aria-hidden />
                Vence el {formatDate(view.expiresAt)} · {formatDaysLeft(view.daysLeft)}. Si compras otro plan, se suma al
                tiempo que te queda.
              </span>
            ) : (
              <span className="text-sm text-slate-700">Tu membresía no tiene fecha de vencimiento.</span>
            )}
          </>
        ) : (
          <>
            <span className="inline-flex rounded-full bg-slate-200 px-3 py-1 text-sm font-semibold text-slate-700">Gratuita</span>
            <span className="text-sm text-slate-600">
              {view.kind === 'expired'
                ? `Tu membresía VIP venció el ${formatDate(view.expiredAt)}. Puedes renovarla cuando quieras.`
                : 'Hazte VIP para obtener mejores tasas y descuentos.'}
            </span>
          </>
        )}
      </section>

      {isPending && (
        <p role="status" className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white p-6 text-slate-600">
          <Loader2 className="size-5 animate-spin" aria-hidden /> Cargando planes…
        </p>
      )}

      {isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
          <span>No se pudieron cargar los planes. {parseApiError(error).message}</span>
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="inline-flex items-center gap-2 rounded-lg border border-red-300 bg-white px-3 py-1.5 font-medium hover:bg-red-100 disabled:opacity-60"
          >
            <RefreshCw className="size-4" aria-hidden /> Reintentar
          </button>
        </div>
      )}

      {plans && plans.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-slate-600">
          Por ahora no hay planes disponibles. Vuelve a intentarlo más tarde.
        </p>
      )}

      {plans && plans.length > 0 && (
        <div className="grid gap-6 md:grid-cols-2">
          {plans.map((plan) => (
            <article key={plan.code} className="flex flex-col rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-slate-900">{plan.name}</h2>
                <span className="rounded-full bg-blue-50 px-2.5 py-0.5 text-xs font-semibold text-blue-700">
                  {PERIOD_LABEL[plan.period]}
                </span>
              </div>
              <p className="mt-4">
                <Money amount={plan.price} currency={plan.currency} className="text-3xl font-bold text-slate-900" />
                <span className="ml-2 text-sm text-slate-500">por {plan.duration_days} días</span>
              </p>
              <ul className="mt-5 flex-1 space-y-2 text-sm text-slate-700">
                {plan.benefits.map((benefit) => (
                  <li key={benefit} className="flex items-start gap-2">
                    <Check className="mt-0.5 size-4 shrink-0 text-emerald-600" aria-hidden />
                    {benefit}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                onClick={() => setSelected(plan)}
                className="mt-6 w-full rounded-lg bg-blue-700 px-4 py-2.5 font-semibold text-white shadow-sm transition hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
              >
                {isVip ? 'Extender con este plan' : 'Suscribirse'}
              </button>
            </article>
          ))}
        </div>
      )}

      <SubscribeDialog plan={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
