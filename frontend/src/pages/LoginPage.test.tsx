import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthProvider'
import { RequireAuth, RequireRole } from '../auth/guards'
import { LoginPage } from './LoginPage'

const businessUser = {
  id: 'u1',
  email: 'shop@demo.pk',
  full_name: 'Sana Iqbal',
  role: 'business',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
  business: { id: 'b1', name: 'Liberty Pharmacy' },
  driver: null,
}

function renderApp(initialPath = '/login') {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      {
        element: <RequireAuth />,
        children: [
          {
            element: <RequireRole role="business" />,
            children: [{ path: '/business', element: <p>Business home</p> }],
          },
          { path: '/admin', element: <p>Admin home</p> },
        ],
      },
    ],
    { initialEntries: [initialPath] },
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

/** Stub fetch: /auth/demo answers with ``demo``, every other call with ``body``. */
function respondWith(status: number, body: unknown, demo: unknown = { enabled: false, accounts: [] }) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      Promise.resolve(
        url.endsWith('/auth/demo')
          ? new Response(JSON.stringify(demo), { status: 200 })
          : new Response(JSON.stringify(body), { status }),
      ),
    ),
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('LoginPage', () => {
  it('signs in and lands on the home page of the role', async () => {
    respondWith(200, { access_token: 't0k', token_type: 'bearer', expires_in: 3600, user: businessUser })
    renderApp()

    await userEvent.type(screen.getByLabelText('Email'), 'shop@demo.pk')
    await userEvent.type(screen.getByLabelText('Password'), 'shop-pass-123')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Business home')).toBeInTheDocument()
    expect(localStorage.getItem('dispatchdesk.token')).toBe('t0k')
  })

  it('shows the server error for wrong credentials', async () => {
    respondWith(401, { detail: 'Incorrect email or password' })
    renderApp()

    await userEvent.type(screen.getByLabelText('Email'), 'shop@demo.pk')
    await userEvent.type(screen.getByLabelText('Password'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password')
  })

  it('offers one-click demo logins when the backend has demo mode on', async () => {
    const demo = {
      enabled: true,
      accounts: [
        { role: 'admin', full_name: 'Ayesha Siddiqui', description: 'See every order.' },
        { role: 'business', full_name: 'Hamza Butt', description: 'Create orders.' },
      ],
    }
    respondWith(
      200,
      { access_token: 'demo', token_type: 'bearer', expires_in: 3600, user: businessUser },
      demo,
    )
    renderApp()

    const businessDemo = await screen.findByRole('button', { name: 'Open the business demo as Hamza Butt' })
    expect(screen.getByRole('button', { name: 'Open the admin demo as Ayesha Siddiqui' })).toBeInTheDocument()
    expect(businessDemo).toHaveAccessibleDescription('Create orders.')
    await userEvent.click(businessDemo)

    expect(await screen.findByText('Business home')).toBeInTheDocument()
    const calls = vi.mocked(fetch).mock.calls as unknown as [string, RequestInit][]
    const login = calls.find(([url]) => url.endsWith('/auth/demo-login'))
    expect(JSON.parse(String(login?.[1].body))).toEqual({ role: 'business' })
  })

  it('hides demo logins when demo mode is off', async () => {
    respondWith(200, {})
    renderApp()

    await screen.findByRole('heading', { name: 'Sign in' })
    expect(screen.queryByText(/try the demo/i)).not.toBeInTheDocument()
  })

  it('sends signed-out visitors of protected pages to login', async () => {
    renderApp('/business')

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })
})
