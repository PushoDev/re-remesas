import { LogOut, Menu, User as UserIcon, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const focusRing = 'focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600'

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium transition ${focusRing} ${
    isActive ? 'bg-blue-50 text-blue-800' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2.5 text-base font-medium transition ${focusRing} ${
    isActive ? 'bg-blue-50 text-blue-800' : 'text-slate-700 hover:bg-slate-100'
  }`

interface NavItem {
  to: string
  label: string
  end?: boolean
}

const BASE_LINKS: NavItem[] = [
  { to: '/', label: 'Inicio', end: true },
  { to: '/remittances/new', label: 'Enviar' },
  { to: '/remittances', label: 'Mis remesas', end: true },
  { to: '/recharges', label: 'Recargas' },
  { to: '/profile', label: 'Perfil' },
  { to: '/membership', label: 'Membresía' },
]

/**
 * Shell for the screens that need a session: top bar + page content.
 * From 1024 px the links sit in the bar; below that they fold into a menu opened by a button.
 */
export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)

  const links = user?.is_staff ? [...BASE_LINKS, { to: '/admin', label: 'Administración' }] : BASE_LINKS

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true, state: null })
  }

  // Escape closes the open menu.
  useEffect(() => {
    if (!menuOpen) return undefined
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  return (
    <div className="min-h-dvh bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3">
          <div className="flex items-center gap-6">
            <Link to="/" className="whitespace-nowrap text-lg font-bold tracking-tight text-blue-800">
              Re &amp; Re
            </Link>
            <nav aria-label="Principal" className="hidden items-center gap-1 lg:flex">
              {links.map((link) => (
                <NavLink key={link.to} to={link.to} end={link.end} className={navLinkClass}>
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <span className="hidden items-center gap-1.5 text-sm text-slate-600 xl:flex">
              <UserIcon className="size-4" aria-hidden />
              {user?.email}
            </span>
            <button
              type="button"
              onClick={() => void handleLogout()}
              aria-label="Cerrar sesión"
              className={`inline-flex items-center gap-2 whitespace-nowrap rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 ${focusRing}`}
            >
              <LogOut className="size-4" aria-hidden />
              <span className="hidden sm:inline">Cerrar sesión</span>
            </button>
            <button
              type="button"
              onClick={() => setMenuOpen((open) => !open)}
              aria-expanded={menuOpen}
              aria-controls="mobile-menu"
              aria-label={menuOpen ? 'Cerrar el menú' : 'Abrir el menú'}
              className={`inline-flex items-center rounded-lg border border-slate-300 bg-white p-2 text-slate-700 hover:bg-slate-100 lg:hidden ${focusRing}`}
            >
              {menuOpen ? <X className="size-5" aria-hidden /> : <Menu className="size-5" aria-hidden />}
            </button>
          </div>
        </div>

        {menuOpen && (
          <nav id="mobile-menu" aria-label="Principal" className="border-t border-slate-200 lg:hidden">
            <div className="mx-auto max-w-5xl px-4 py-3">
              {user?.email && (
                <p className="mb-2 flex items-center gap-1.5 break-all px-3 text-sm text-slate-500">
                  <UserIcon className="size-4 shrink-0" aria-hidden />
                  {user.email}
                </p>
              )}
              <ul className="space-y-1">
                {links.map((link) => (
                  <li key={link.to}>
                    <NavLink to={link.to} end={link.end} className={mobileLinkClass} onClick={() => setMenuOpen(false)}>
                      {link.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          </nav>
        )}
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  )
}
