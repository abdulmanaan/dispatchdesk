import { useQuery } from '@tanstack/react-query'

import { useAuth } from '../../auth/useAuth'
import { Card, EmptyState, ErrorNote, PageHeader } from '../../components/Card'
import { Spinner } from '../../components/Spinner'
import { OverduePill, StatusPill } from '../../components/StatusPill'
import { api } from '../../lib/api'
import { formatTime } from '../../lib/format'
import { isOpen } from '../../lib/status'
import type { Order, Page } from '../../lib/types'

export function BusinessHome() {
  const { user } = useAuth()
  const orders = useQuery({
    queryKey: ['orders', 'recent'],
    queryFn: () => api<Page<Order>>('/orders', { query: { page_size: 8 } }),
    refetchInterval: 15_000,
  })

  return (
    <>
      <PageHeader title="Orders" subtitle={user?.business?.name} />
      {orders.isPending && <Spinner className="size-6 text-muted" />}
      {orders.isError && <ErrorNote message={orders.error.message} />}
      {orders.data && (
        <Card className="overflow-hidden">
          {orders.data.items.length === 0 ? (
            <EmptyState title="No orders yet">
              Orders you create appear here, most recent first.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {orders.data.items.map((order) => (
                <li key={order.id} className="flex items-center gap-4 px-6 py-5">
                  <div className="grid min-w-0 flex-1 gap-0.5">
                    <span className="font-semibold">{order.customer_name}</span>
                    <span className="truncate text-sm text-muted">{order.dropoff_address}</span>
                  </div>
                  <div className="grid justify-items-end gap-1.5">
                    <div className="flex gap-2">
                      {order.is_overdue && isOpen(order) && <OverduePill />}
                      <StatusPill order={order} />
                    </div>
                    <span className="text-[13px] text-muted tabular-nums">
                      Due {formatTime(order.deliver_by)}
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
    </>
  )
}
