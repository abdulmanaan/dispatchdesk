import { createContext } from 'react'

import type { User } from '../lib/types'

export type AuthStatus = 'loading' | 'signed-in' | 'signed-out'

export interface AuthContextValue {
  status: AuthStatus
  user: User | null
  signIn: (email: string, password: string) => Promise<User>
  signOut: () => void
  /** Re-read the current user (e.g. after a driver changes status). */
  refreshUser: () => Promise<void>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
