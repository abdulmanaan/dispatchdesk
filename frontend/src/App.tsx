import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router'

import { AuthProvider } from './auth/AuthProvider'
import { RequireAuth, RequireRole, RoleRedirect } from './auth/guards'
import { AppShell } from './components/AppShell'
import { ApiError } from './lib/api'
import { AdminActivity } from './pages/admin/AdminActivity'
import { AdminDrivers } from './pages/admin/AdminDrivers'
import { AdminHome } from './pages/admin/AdminHome'
import { AdminOrders } from './pages/admin/AdminOrders'
import { BusinessOrders } from './pages/business/BusinessOrders'
import { NewOrderPage } from './pages/business/NewOrderPage'
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
          {
            path: 'admin',
            element: <RequireRole role="admin" />,
            children: [
              { index: true, element: <AdminHome /> },
              { path: 'orders', element: <AdminOrders /> },
              { path: 'drivers', element: <AdminDrivers /> },
              { path: 'activity', element: <AdminActivity /> },
            ],
          },
          {
            path: 'business',
            element: <RequireRole role="business" />,
            children: [
              { index: true, element: <BusinessOrders /> },
              { path: 'new', element: <NewOrderPage /> },
            ],
          },
          {
            path: 'driver',
            element: <RequireRole role="driver" />,
            children: [{ index: true, element: <DriverHome /> }],
          },
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
