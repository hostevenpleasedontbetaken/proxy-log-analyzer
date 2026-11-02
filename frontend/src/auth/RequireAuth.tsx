import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '@/auth/auth-context'
import { PageLoading } from '@/components/PageLoading'

/** Route guard: renders the child routes only for a signed-in user. */
export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) return <PageLoading />
  if (!user) {
    // Remember where the user was going so login can send them back there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
