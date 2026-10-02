import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'

import { api, setUnauthorizedHandler, tokenStore } from '../lib/api'
import type { TokenResponse, User } from '../lib/types'
import { AuthContext, type AuthStatus } from './context'

const ME_KEY = ['auth', 'me'] as const

/**
 * Holds the session. The token lives in storage; the signed-in user is read
 * from /auth/me through React Query, and the session status is derived from
 * that query instead of being stored separately.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setToken] = useState(() => tokenStore.get())

  const me = useQuery({
    queryKey: ME_KEY,
    queryFn: () => api<User>('/auth/me'),
    enabled: token !== null,
    staleTime: Infinity,
    retry: false,
  })

  const signOut = useCallback(() => {
    tokenStore.clear()
    setToken(null)
    queryClient.clear()
  }, [queryClient])

  // Any 401 on an authenticated call means the session is over.
  useEffect(() => {
    setUnauthorizedHandler(signOut)
    return () => setUnauthorizedHandler(null)
  }, [signOut])

  const signIn = useCallback(
    async (email: string, password: string) => {
      const result = await api<TokenResponse>('/auth/login', {
        form: { username: email, password },
      })
      tokenStore.set(result.access_token)
      queryClient.setQueryData(ME_KEY, result.user)
      setToken(result.access_token)
      return result.user
    },
    [queryClient],
  )

  const refreshUser = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ME_KEY })
  }, [queryClient])

  let status: AuthStatus = 'signed-out'
  if (token !== null && me.data) status = 'signed-in'
  else if (token !== null && me.isPending) status = 'loading'

  const user = status === 'signed-in' ? (me.data ?? null) : null
  const value = useMemo(
    () => ({ status, user, signIn, signOut, refreshUser }),
    [status, user, signIn, signOut, refreshUser],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
