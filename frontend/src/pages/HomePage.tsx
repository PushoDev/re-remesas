import { LogIn, LogOut, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import RemittanceCalculator, { type CalculatorValues } from '../components/RemittanceCalculator'
import { useAuth } from '../hooks/useAuth'
import { apiClient } from '../services/apiClient'

type HealthStatus = 'checking' | 'ok' | 'error'

const buttonClass =
  'inline-flex items-center gap-2 rounded-lg px-4 py-2.5 font-semibold shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2'

export default function HomePage() {
  const [health, setHealth] = useState<HealthStatus>('checking')
  const { user, status: authStatus, logout } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    apiClient
      .get('/health/')
      .then(() => setHealth('ok'))
      .catch(() => setHealth('error'))
  }, [])

  const authenticated = authStatus === 'authenticated' && user
  const goToSend = ({ amount, currency }: CalculatorValues) => {
    const target = `/remittances/new?amount=${amount}&currency=${currency}`
    if (authenticated) navigate(target)
    else navigate('/login', { state: { from: { pathname: '/remittances/new', search: `?amount=${amount}&currency=${currency}` } } })
  }

  return (
    <div className="min-h-dvh bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <p className="text-lg font-bold tracking-tight text-blue-800">Re &amp; Re</p>
          <div className="flex items-center gap-2">
            {authenticated ? (
              <>
                <span className="hidden text-sm text-slate-600 sm:inline">
                  {user.email} · <strong>{user.profile.membership_status === 'VIP' ? 'VIP' : 'Gratuita'}</strong>
                </span>
                <Link to="/profile" className={`${buttonClass} bg-blue-700 text-white hover:bg-blue-800`}>
                  <UserRound className="size-5" aria-hidden />
                  Mi perfil
                </Link>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className={`${buttonClass} border border-slate-300 bg-white text-slate-800 hover:bg-slate-100`}
                >
                  <LogOut className="size-5" aria-hidden />
                  <span className="hidden sm:inline">Cerrar sesión</span>
                </button>
              </>
            ) : (
              authStatus === 'anonymous' && (
                <Link to="/login" className={`${buttonClass} bg-blue-700 text-white hover:bg-blue-800`}>
                  <LogIn className="size-5" aria-hidden />
                  Iniciar sesión
                </Link>
              )
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-5xl gap-10 px-4 py-10 lg:grid-cols-[1fr_28rem] lg:items-start">
        <section>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            Envía dinero y recargas a Cuba, sin complicaciones
          </h1>
          <p className="mt-4 text-lg text-slate-600">
            Mira al instante cuánto recibirá tu familiar. Los miembros VIP obtienen una mejor tasa de cambio.
          </p>
          <p
            className="mt-6 inline-block rounded-full px-3 py-1 text-xs font-medium data-[status=ok]:bg-emerald-100 data-[status=ok]:text-emerald-700 data-[status=error]:bg-red-100 data-[status=error]:text-red-700 data-[status=checking]:bg-slate-200 data-[status=checking]:text-slate-700"
            data-status={health}
          >
            Servicio: {health === 'ok' ? 'disponible' : health === 'error' ? 'no disponible' : 'comprobando…'}
          </p>
        </section>

        <section aria-labelledby="calc-title" className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 id="calc-title" className="mb-4 text-lg font-semibold text-slate-900">
            Calcula tu envío
          </h2>
          <RemittanceCalculator
            cta={{
              label: authenticated ? 'Continuar' : 'Inicia sesión para enviar',
              onClick: goToSend,
              hint: authenticated ? undefined : 'Puedes calcular sin cuenta; para enviar necesitas iniciar sesión.',
            }}
          />
        </section>
      </main>
    </div>
  )
}
