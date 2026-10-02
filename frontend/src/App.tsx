import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router'

import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth, RequireRole, RoleRedirect } from './auth/guards'
import { AppShell } from './components/AppShell'
import { ApiError } from './lib/api'
import { AdminHome } from './pages/admin/AdminHome'
import { BusinessHome } from './pages/business/BusinessHome'
import { DriverHome } from './pages/driver/DriverHome'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Retry network hiccups, but not client errors such as 401/403/404.
      retry: (count, error) => !(error instanceof ApiError && error.status < 500) && count < 2,
      refetchOnWindowFocus: true,
    },
  },
})

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { index: true, element: <RoleRedirect /> },
          { element: <RequireRole role="admin" />, children: [{ path: 'admin', element: <AdminHome /> }] },
          {
            element: <RequireRole role="business" />,
            children: [{ path: 'business', element: <BusinessHome /> }],
          },
          { element: <RequireRole role="driver" />, children: [{ path: 'driver', element: <DriverHome /> }] },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>
  )
}
