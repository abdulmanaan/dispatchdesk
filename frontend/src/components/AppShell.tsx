import { LogOut } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'

import { useAuth } from '../auth/useAuth'
import { roleName } from '../lib/format'
import type { Role } from '../lib/types'
import { Logo } from './Logo'

const navigation: Record<Role, { to: string; label: string; end?: boolean }[]> = {
  admin: [
    { to: '/admin', label: 'Today', end: true },
    { to: '/admin/orders', label: 'Orders' },
    { to: '/admin/drivers', label: 'Drivers' },
    { to: '/admin/activity', label: 'Activity' },
  ],
  // "New order" is the prominent button on the orders page, so it is not repeated here.
  business: [{ to: '/business', label: 'Orders' }],
  driver: [{ to: '/driver', label: 'Today', end: true }],
}

function NavItems({ role }: { role: Role }) {
  return navigation[role].map((item) => (
    <NavLink
      key={item.to}
      to={item.to}
      end={item.end}
      className={({ isActive }) =>
        `shrink-0 rounded-control px-3 py-2 text-[15px] font-medium transition-colors ${isActive ? 'bg-accent-soft text-accent' : 'text-muted hover:text-ink'}`
      }
    >
      {item.label}
    </NavLink>
  ))
}

export function AppShell() {
  const { user, signOut } = useAuth()
  if (!user) return null

  return (
    <div className="min-h-dvh">
      <header className="sticky top-[env(safe-area-inset-top,0px)] z-10 border-b border-line bg-page/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-6 px-5 sm:px-8">
          <Logo />
          <nav aria-label="Main" className="hidden gap-1 md:flex">
            <NavItems role={user.role} />
          </nav>
          <div className="ml-auto flex items-center gap-4">
            <div className="hidden text-right leading-tight lg:block">
              <p className="text-sm font-medium">{user.full_name}</p>
              <p className="text-[13px] text-muted">{user.business?.name ?? roleName(user.role)}</p>
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
        {navigation[user.role].length > 1 && (
          <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-5 pb-3 md:hidden">
            <NavItems role={user.role} />
          </nav>
        )}
      </header>
      <main className="mx-auto grid max-w-5xl gap-8 px-5 py-10 sm:px-8">
        <Outlet />
      </main>
    </div>
  )
}
