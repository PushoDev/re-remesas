import { useQuery } from '@tanstack/react-query'
import { BadgeCheck, CalendarClock, ShieldCheck, Sparkles } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { parseApiError } from '../lib/apiErrors'
import { describeMembership, formatDate, formatDaysLeft } from '../lib/membership'
import { getMe } from '../services/authService'
import type { User } from '../types/auth'

function initialsOf(user: User): string {
  const source = `${user.first_name} ${user.last_name}`.trim() || user.email
  const parts = source.split(/[\s@._-]+/).filter(Boolean)
  return (parts[0]?.[0] ?? '?').concat(parts[1]?.[0] ?? '').toUpperCase()
}

function MembershipCard({ user }: { user: User }) {
  const view = describeMembership(user.profile)

  if (view.kind === 'vip') {
    return (
      <section aria-labelledby="membership-title" className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-3">
          <h2 id="membership-title" className="text-lg font-semibold text-slate-900">
            Membresía
          </h2>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-3 py-1 text-sm font-semibold text-white">
            <BadgeCheck className="size-4" aria-hidden />
            VIP
          </span>
        </div>
        <p className="mt-3 text-slate-700">Disfrutas de mejores tasas de cambio en tus remesas y descuentos en recargas.</p>
        {view.expiresAt && view.daysLeft !== null && (
          <p className="mt-4 flex items-center gap-2 text-sm text-slate-600">
            <CalendarClock className="size-4 shrink-0" aria-hidden />
            Vence el {formatDate(view.expiresAt)} · {formatDaysLeft(view.daysLeft)}
          </p>
        )}
      </section>
    )
  }

  return (
    <section aria-labelledby="membership-title" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 id="membership-title" className="text-lg font-semibold text-slate-900">
          Membresía
        </h2>
        <span className="inline-flex items-center rounded-full bg-slate-200 px-3 py-1 text-sm font-semibold text-slate-700">
          Gratuita
        </span>
      </div>
      {view.kind === 'expired' && (
        <p className="mt-3 flex items-center gap-2 text-sm text-amber-700">
          <CalendarClock className="size-4 shrink-0" aria-hidden />
          Tu membresía VIP venció el {formatDate(view.expiredAt)}.
        </p>
      )}
      <div className="mt-4 flex items-start gap-3 rounded-xl bg-blue-50 p-4 text-sm text-blue-900">
        <Sparkles className="mt-0.5 size-5 shrink-0" aria-hidden />
        <p>
          Con la membresía <strong>VIP</strong> obtienes mejores tasas de cambio en tus remesas y descuentos en las
          recargas telefónicas. Muy pronto podrás suscribirte desde aquí.
        </p>
      </div>
    </section>
  )
}

export default function ProfilePage() {
  const { user: sessionUser } = useAuth()

  // Show the session data right away, then refresh it: the membership may have
  // changed since login (for instance, a payment confirmed in the meantime).
  const { data: user, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['me'],
    queryFn: getMe,
    initialData: sessionUser ?? undefined,
    refetchOnMount: 'always',
  })

  if (!user) return null

  const fullName = `${user.first_name} ${user.last_name}`.trim()

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold text-slate-900">Mi perfil</h1>

      {isError && (
        <div role="alert" className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>No pudimos actualizar tus datos. {parseApiError(error).message}</span>
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 font-medium hover:bg-amber-100 disabled:opacity-60"
          >
            Reintentar
          </button>
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <section aria-labelledby="account-title" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 id="account-title" className="sr-only">
            Datos de la cuenta
          </h2>
          <div className="flex items-center gap-4">
            <div
              aria-hidden
              className="flex size-14 shrink-0 items-center justify-center rounded-full bg-blue-700 text-lg font-semibold text-white"
            >
              {initialsOf(user)}
            </div>
            <div className="min-w-0">
              <p className="truncate text-lg font-semibold text-slate-900">{fullName || 'Sin nombre registrado'}</p>
              <p className="truncate text-slate-600">{user.email}</p>
            </div>
          </div>
          <dl className="mt-6 space-y-3 text-sm">
            <div className="flex items-center justify-between gap-4 border-t border-slate-100 pt-3">
              <dt className="text-slate-500">Tipo de cuenta</dt>
              <dd className="inline-flex items-center gap-1.5 font-medium text-slate-900">
                {user.is_staff && <ShieldCheck className="size-4 text-blue-700" aria-hidden />}
                {user.is_staff ? 'Administrador' : 'Cliente'}
              </dd>
            </div>
          </dl>
        </section>

        <MembershipCard user={user} />
      </div>
    </div>
  )
}
