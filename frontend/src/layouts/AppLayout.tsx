import { LogOut, User as UserIcon } from 'lucide-react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 ${
    isActive ? 'bg-blue-50 text-blue-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

/** Shell for the screens that need a session: top bar + page content. */
export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true, state: null })
  }

  return (
    <div className="min-h-dvh bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-3">
          <div className="flex items-center gap-6">
            <Link to="/" className="whitespace-nowrap text-lg font-bold tracking-tight text-blue-800">
              Re &amp; Re
            </Link>
            <nav aria-label="Principal" className="flex items-center gap-1">
              <NavLink to="/" end className={navLinkClass}>
                Inicio
              </NavLink>
              <NavLink to="/remittances/new" className={navLinkClass}>
                Enviar
              </NavLink>
              <NavLink to="/remittances" end className={navLinkClass}>
                Mis remesas
              </NavLink>
              <NavLink to="/recharges" className={navLinkClass}>
                Recargas
              </NavLink>
              <NavLink to="/profile" className={navLinkClass}>
                Perfil
              </NavLink>
              <NavLink to="/membership" className={navLinkClass}>
                Membresía
              </NavLink>
              {user?.is_staff && (
                <NavLink to="/admin" className={navLinkClass}>
                  Administración
                </NavLink>
              )}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 text-sm text-slate-600 sm:flex">
              <UserIcon className="size-4" aria-hidden />
              {user?.email}
            </span>
            <button
              type="button"
              onClick={() => void handleLogout()}
              className="inline-flex items-center gap-2 whitespace-nowrap rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600"
            >
              <LogOut className="size-4" aria-hidden />
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
