import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router'

import { homePath, useAuth } from '../auth/useAuth'
import { Button } from '../components/Button'
import { Card, ErrorNote } from '../components/Card'
import { DemoAccounts } from '../components/DemoAccounts'
import { Logo } from '../components/Logo'
import { TextField } from '../components/TextField'
import { ApiError } from '../lib/api'
import { useDemoInfo } from '../lib/hooks'

export function LoginPage() {
  const { status, user, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const demo = useDemoInfo()

  if (status === 'signed-in' && user) return <Navigate to={homePath[user.role]} replace />

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      const signedIn = await signIn(email.trim(), password)
      // Return to the page that asked for login, if it belongs to this role.
      const from = (location.state as { from?: string } | null)?.from
      const home = homePath[signedIn.role]
      navigate(from?.startsWith(home) ? from : home, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-dvh place-items-center px-5 py-12">
      <div className="grid w-full max-w-[420px] gap-8">
        <div className="grid justify-items-center gap-6 text-center">
          <Link to="/" aria-label="DispatchDesk home">
            <Logo />
          </Link>
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
            <Button type="submit" size="lg" loading={submitting} className="mt-1 w-full">
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
            <DemoAccounts />
          </section>
        )}
      </div>
    </div>
  )
}
