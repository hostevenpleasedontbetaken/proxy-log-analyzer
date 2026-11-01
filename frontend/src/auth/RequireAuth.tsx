import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '@/auth/auth-context'

/** Route guard: renders the child routes only for a signed-in user. */
export function RequireAuth() {
  const { user, loading } = useAuth()
  const location = useLocation()

  if (loading) {
    return <div className="grid min-h-svh place-items-center text-muted-foreground">Loading…</div>
  }
  if (!user) {
    // Remember where the user was going so login can send them back there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}
