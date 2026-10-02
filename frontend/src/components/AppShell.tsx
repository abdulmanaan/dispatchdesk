import { LogOut } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { roleName } from '../lib/format'
import type { Role } from '../lib/types'
import { Logo } from './Logo'

// Navigation per role. Step 10 adds the remaining screens.
const navigation: Record<Role, { to: string; label: string }[]> = {
  admin: [{ to: '/admin', label: 'Overview' }],
  business: [{ to: '/business', label: 'Orders' }],
  driver: [{ to: '/driver', label: 'Today' }],
}

export function AppShell() {
  const { user, signOut } = useAuth()
  if (!user) return null

  return (
    <div className="min-h-dvh">
      <header className="sticky top-[env(safe-area-inset-top,0px)] z-10 border-b border-line bg-page/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-6 px-5 sm:px-8">
          <Logo />
          <nav aria-label="Main" className="hidden gap-1 sm:flex">
            {navigation[user.role].map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) =>
                  `rounded-control px-3 py-2 text-[15px] font-medium transition-colors ${isActive ? 'bg-accent-soft text-accent' : 'text-muted hover:text-ink'}`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-4">
            <div className="hidden text-right leading-tight sm:block">
              <p className="text-sm font-medium">{user.full_name}</p>
              <p className="text-[13px] text-muted">
                {user.business?.name ?? roleName(user.role)}
              </p>
            </div>
            <button
              type="button"
              onClick={signOut}
              className="inline-flex items-center gap-2 rounded-control px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-subtle hover:text-ink"
            >
              <LogOut aria-hidden="true" className="size-4" />
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto grid max-w-5xl gap-8 px-5 py-10 sm:px-8">
        <Outlet />
      </main>
    </div>
  )
}
