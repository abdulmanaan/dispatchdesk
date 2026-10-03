import { Navigate, Outlet, useLocation } from 'react-router'

import { FullPageSpinner } from '../components/Spinner'
import type { Role } from '../lib/types'
import { homePath, useAuth } from './useAuth'

/** Renders child routes only for signed-in users; otherwise sends them to login. */
export function RequireAuth() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') return <FullPageSpinner />
  if (status === 'signed-out') {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }
  return <Outlet />
}

/** Renders child routes only for the given role; other roles go to their own home. */
export function RequireRole({ role }: { role: Role }) {
  const { user } = useAuth()
  if (!user) return null
  if (user.role !== role) return <Navigate to={homePath[user.role]} replace />
  return <Outlet />
}
