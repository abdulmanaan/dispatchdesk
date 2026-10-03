import { ArrowRight } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { useNavigate } from 'react-router'

import { homePath, useAuth } from '../auth/useAuth'
import { ApiError } from '../lib/api'
import { roleName } from '../lib/format'
import { useDemoInfo } from '../lib/hooks'
import type { Role } from '../lib/types'
import { ErrorNote } from './Card'

/**
 * One-click sign-in buttons for the demo accounts. Renders ``fallback`` when the
 * backend has demo mode off (or cannot be reached).
 */
export function DemoAccounts({ fallback = null }: { fallback?: ReactNode }) {
  const demo = useDemoInfo()
  const { signInDemo } = useAuth()
  const navigate = useNavigate()
  const [pending, setPending] = useState<Role | null>(null)
  const [error, setError] = useState<string | null>(null)

  if (demo.isPending) {
    // Reserve the space so the page does not jump when the buttons arrive.
    return (
      <div aria-hidden="true" className="grid gap-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-[76px] animate-pulse rounded-card bg-card/70" />
        ))}
      </div>
    )
  }
  if (!demo.data?.enabled) return <>{fallback}</>

  async function open(role: Role) {
    setError(null)
    setPending(role)
    try {
      const user = await signInDemo(role)
      navigate(homePath[user.role])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
      setPending(null)
    }
  }

  return (
    <div className="grid gap-3">
      {error && <ErrorNote message={error} />}
      <ul className="grid gap-3">
        {demo.data.accounts.map((account) => (
          <li key={account.role}>
            <button
              type="button"
              disabled={pending !== null}
              onClick={() => open(account.role)}
              aria-label={`Open the ${account.role} demo as ${account.full_name}`}
              aria-describedby={`demo-${account.role}-text`}
              className="group grid w-full grid-cols-[1fr_auto] items-center gap-4 rounded-card bg-card px-6 py-4 text-left shadow-card transition-shadow hover:ring-2 hover:ring-accent/30 disabled:opacity-60"
            >
              <span className="grid gap-0.5">
                <span className="font-semibold">
                  {roleName(account.role)}
                  <span className="font-normal text-muted"> · {account.full_name}</span>
                </span>
                <span id={`demo-${account.role}-text`} className="text-sm text-muted">
                  {account.description}
                </span>
              </span>
              <span className="inline-flex items-center gap-1.5 text-sm font-semibold whitespace-nowrap text-accent">
                {pending === account.role ? (
                  'Opening…'
                ) : (
                  <>
                    Open
                    <ArrowRight
                      aria-hidden="true"
                      className="size-4 transition-transform group-hover:translate-x-0.5"
                    />
                  </>
                )}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
