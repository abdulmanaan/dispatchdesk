import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { AuthProvider } from '../auth/AuthProvider'
import { LandingPage } from './LandingPage'

const businessUser = {
  id: 'u1',
  email: 'biryani@demo.dispatchdesk.test',
  full_name: 'Hamza Butt',
  role: 'business',
  is_active: true,
  created_at: '2026-10-01T00:00:00Z',
  business: { id: 'b1', name: 'Lahori Biryani Corner' },
  driver: null,
}

const demoOn = {
  enabled: true,
  accounts: [
    { role: 'admin', full_name: 'Ayesha Siddiqui', description: 'See every order.' },
    { role: 'business', full_name: 'Hamza Butt', description: 'Create orders.' },
    { role: 'driver', full_name: 'Kamran Ali', description: 'Deliver orders.' },
  ],
}

/** Route fetch calls by path; each call gets a fresh Response. */
function stubApi(routes: Record<string, unknown>) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      const path = Object.keys(routes).find((p) => url.endsWith(p))
      return Promise.resolve(
        path
          ? new Response(JSON.stringify(routes[path]), { status: 200 })
          : new Response('{}', { status: 404 }),
      )
    }),
  )
}

function renderLanding() {
  const router = createMemoryRouter(
    [
      { path: '/', element: <LandingPage /> },
      { path: '/login', element: <p>Login page</p> },
      { path: '/business', element: <p>Business home</p> },
    ],
    { initialEntries: ['/'] },
  )
  render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

afterEach(() => vi.unstubAllGlobals())

describe('LandingPage', () => {
  it('pairs each benefit with a piece of the app, not developer details', () => {
    stubApi({ '/auth/demo': demoOn })
    renderLanding()

    expect(
      screen.getByRole('heading', { level: 1, name: 'Delivery dispatch for local businesses' }),
    ).toBeInTheDocument()
    const benefits = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(benefits).toEqual([
      'Try the live demo',
      'No more dispatching on WhatsApp',
      'See where every order is',
      'Late orders flag themselves',
    ])
    expect(screen.getByRole('figure', { name: /driver's phone/i })).toBeInTheDocument()
    expect(screen.getByRole('figure', { name: /order list/i })).toBeInTheDocument()
    expect(screen.getByRole('figure', { name: /needs attention/i })).toBeInTheDocument()
    expect(screen.queryByText(/tech stack|under the hood/i)).not.toBeInTheDocument()
  })

  it('credits the author and links the source code', () => {
    stubApi({ '/auth/demo': demoOn })
    renderLanding()

    expect(screen.getByRole('link', { name: 'Abdul Manan' })).toHaveAttribute(
      'href',
      'https://www.linkedin.com/in/abdulmanaan/',
    )
    expect(screen.getByRole('link', { name: 'Source code on GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/abdulmanaan/dispatchdesk',
    )
  })

  it('signs in to a demo role with one click', async () => {
    stubApi({
      '/auth/demo': demoOn,
      '/auth/demo-login': { access_token: 't', token_type: 'bearer', expires_in: 3600, user: businessUser },
    })
    renderLanding()

    await userEvent.click(await screen.findByRole('button', { name: 'Open the business demo as Hamza Butt' }))

    expect(await screen.findByText('Business home')).toBeInTheDocument()
  })

  it('offers a normal sign-in when demo mode is off', async () => {
    stubApi({ '/auth/demo': { enabled: false, accounts: [] } })
    renderLanding()

    const hero = await screen.findAllByRole('link', { name: 'Sign in' })
    expect(hero.length).toBeGreaterThan(0)
    hero.forEach((link) => expect(link).toHaveAttribute('href', '/login'))
    expect(screen.queryByRole('button', { name: /demo as/ })).not.toBeInTheDocument()
  })

  it('points signed-in visitors to their dashboard', async () => {
    localStorage.setItem('dispatchdesk.token', 'existing')
    stubApi({ '/auth/demo': demoOn, '/auth/me': businessUser })
    renderLanding()

    const link = await screen.findByRole('link', { name: 'Open your dashboard' })
    expect(link).toHaveAttribute('href', '/business')
  })
})
