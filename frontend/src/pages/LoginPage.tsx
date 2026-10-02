import { useQuery } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router'

import { homePath, useAuth } from '../auth/useAuth'
import { Button } from '../components/Button'
import { Card, ErrorNote } from '../components/Card'
import { Logo } from '../components/Logo'
import { TextField } from '../components/TextField'
import { api, ApiError } from '../lib/api'
import { roleName } from '../lib/format'
import type { DemoInfo, Role, User } from '../lib/types'

export function LoginPage() {
  const { status, user, signIn, signInDemo } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState<'form' | Role | null>(null)
  const demo = useQuery({
    queryKey: ['auth', 'demo'],
    queryFn: () => api<DemoInfo>('/auth/demo'),
    staleTime: Infinity,
    retry: false,
  })

  if (status === 'signed-in' && user) return <Navigate to={homePath[user.role]} replace />

  async function run(kind: 'form' | Role, attempt: () => Promise<User>) {
    setError(null)
    setSubmitting(kind)
    try {
      const signedIn = await attempt()
      // Return to the page that asked for login, if it belongs to this role.
      const from = (location.state as { from?: string } | null)?.from
      const home = homePath[signedIn.role]
      navigate(from?.startsWith(home) ? from : home, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    } finally {
      setSubmitting(null)
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    run('form', () => signIn(email.trim(), password))
  }

  return (
    <div className="grid min-h-dvh place-items-center px-5 py-12">
      <div className="grid w-full max-w-[420px] gap-8">
        <div className="grid justify-items-center gap-6 text-center">
          <Logo />
          <div className="grid gap-2">
            <h1 className="text-[28px] leading-tight font-semibold tracking-tight">Sign in</h1>
            <p className="text-muted">Dispatch, deliver and track local orders.</p>
          </div>
        </div>

        <Card className="p-7 sm:p-8">
          <form onSubmit={handleSubmit} className="grid gap-5" noValidate>
            {error && <ErrorNote message={error} />}
            <TextField
              id="email"
              label="Email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <TextField
              id="password"
              label="Password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Button type="submit" size="lg" loading={submitting === 'form'} className="mt-1 w-full">
              Sign in
            </Button>
          </form>
        </Card>

        {demo.data?.enabled && (
          <section aria-labelledby="demo-title" className="grid gap-4">
            <div className="grid gap-1 text-center">
              <h2 id="demo-title" className="text-lg font-semibold">
                Or try the demo
              </h2>
              <p className="text-sm text-muted">Sample data around Lahore. Sign in with one click.</p>
            </div>
            <ul className="grid gap-3">
              {demo.data.accounts.map((account) => (
                <li key={account.role}>
                  <button
                    type="button"
                    disabled={submitting !== null}
                    onClick={() => run(account.role, () => signInDemo(account.role))}
                    aria-label={`Open the ${account.role} demo as ${account.full_name}`}
                    aria-describedby={`demo-${account.role}-text`}
                    className="grid w-full grid-cols-[1fr_auto] items-center gap-4 rounded-card bg-card px-6 py-4 text-left shadow-card transition-shadow hover:ring-2 hover:ring-accent/30 disabled:opacity-60"
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
                    <span className="text-sm font-semibold text-accent">
                      {submitting === account.role ? 'Signing in…' : 'Open'}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  )
}
