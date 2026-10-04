import { LogIn, LogOut, UserRound } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { apiClient } from '../services/apiClient'

type HealthStatus = 'checking' | 'ok' | 'error'

const buttonClass =
  'inline-flex items-center gap-2 rounded-lg px-4 py-2.5 font-semibold shadow-sm transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2'

export default function HomePage() {
  const [status, setStatus] = useState<HealthStatus>('checking')
  const { user, status: authStatus, logout } = useAuth()

  useEffect(() => {
    apiClient
      .get('/health/')
      .then(() => setStatus('ok'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-50 px-4 text-center">
      <h1 className="text-3xl font-semibold text-slate-900">Re & Re</h1>
      <p className="text-slate-600">Remesas & Recargas</p>
      <p className="rounded-full px-4 py-1 text-sm font-medium data-[status=ok]:bg-emerald-100 data-[status=ok]:text-emerald-700 data-[status=error]:bg-red-100 data-[status=error]:text-red-700 data-[status=checking]:bg-slate-200 data-[status=checking]:text-slate-700" data-status={status}>
        Backend: {status}
      </p>

      {authStatus === 'authenticated' && user ? (
        <div className="mt-2 flex flex-col items-center gap-3">
          <p className="text-slate-700">
            Sesión: <strong>{user.email}</strong> ·{' '}
            <span className="font-medium">{user.profile.membership_status === 'VIP' ? 'VIP' : 'Gratuita'}</span>
            {user.is_staff && ' · Administrador'}
          </p>
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
            Cerrar sesión
          </button>
        </div>
      ) : (
        authStatus === 'anonymous' && (
          <Link to="/login" className={`${buttonClass} mt-2 bg-blue-700 text-white hover:bg-blue-800`}>
            <LogIn className="size-5" aria-hidden />
            Iniciar sesión
          </Link>
        )
      )}
    </main>
  )
}
