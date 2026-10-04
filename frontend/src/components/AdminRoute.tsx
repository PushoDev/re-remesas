import { ShieldAlert } from 'lucide-react'
import { Link, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

/** Inside ProtectedRoute: lets only administrators (is_staff) through. The API enforces it too. */
export default function AdminRoute() {
  const { user } = useAuth()
  if (user?.is_staff) return <Outlet />

  return (
    <div role="alert" className="mx-auto mt-10 max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
      <ShieldAlert className="mx-auto size-10 text-amber-500" aria-hidden />
      <h1 className="mt-4 text-xl font-semibold text-slate-900">Acceso restringido</h1>
      <p className="mt-2 text-slate-600">Esta sección es solo para administradores.</p>
      <Link to="/" className="mt-6 inline-block font-semibold text-blue-700 hover:underline">
        Volver al inicio
      </Link>
    </div>
  )
}
