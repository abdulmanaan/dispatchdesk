import { useContext } from 'react'

import type { Role } from '../lib/types'
import { AuthContext, type AuthContextValue } from './context'

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>')
  return value
}

/** Where each role lands after signing in. */
export const homePath: Record<Role, string> = {
  admin: '/admin',
  business: '/business',
  driver: '/driver',
}
