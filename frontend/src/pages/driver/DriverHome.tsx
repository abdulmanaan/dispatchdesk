import { useQuery } from '@tanstack/react-query'

import { useAuth } from '../../auth/useAuth'
import { Card, EmptyState, ErrorNote, PageHeader } from '../../components/Card'
import { Spinner } from '../../components/Spinner'
import { StatusPill } from '../../components/StatusPill'
import { api } from '../../lib/api'
import type { DriverStatus, Order } from '../../lib/types'

const statusText: Record<DriverStatus, string> = {
  available: 'You are online and can receive orders.',
  busy: 'You are on a delivery.',
  offline: 'You are offline. Go online to receive orders.',
}

export function DriverHome() {
  const { user } = useAuth()
  const current = useQuery({
    queryKey: ['driver', 'current-order'],
    queryFn: () => api<Order | null>('/drivers/me/order'),
    refetchInterval: 10_000,
  })

  const firstName = user?.full_name.split(' ')[0]
  return (
    <>
      <PageHeader
        title={`Hi, ${firstName}`}
        subtitle={user?.driver ? statusText[user.driver.status] : undefined}
      />
      {current.isPending && <Spinner className="size-6 text-muted" />}
      {current.isError && <ErrorNote message={current.error.message} />}
      {current.isSuccess && (
        <Card className="max-w-md">
          {current.data ? (
            <div className="grid gap-3 p-6">
              <div className="flex items-start justify-between gap-3">
                <span className="text-lg font-semibold">{current.data.customer_name}</span>
                <StatusPill order={current.data} />
              </div>
              <p className="text-sm text-muted">{current.data.dropoff_address}</p>
            </div>
          ) : (
            <EmptyState title="No active order">New orders show up here as soon as they are assigned to you.</EmptyState>
          )}
        </Card>
      )}
    </>
  )
}
