import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import LoadingScreen from './LoadingScreen'

/** Wraps the routes that need a session; remembers where the user wanted to go. */
export default function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <LoadingScreen />
  if (status === 'anonymous') return <Navigate to="/login" replace state={{ from: location }} />
  return <Outlet />
}
