import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'

import { Card, EmptyState, ErrorNote, PageHeader, Stat } from '../../components/Card'
import { OrderCard } from '../../components/OrderCard'
import { Spinner } from '../../components/Spinner'
import { api } from '../../lib/api'
import { useOrders } from '../../lib/hooks'
import type { StatsOverview } from '../../lib/types'
import { AdminOrderActions } from './AdminOrderActions'

export function AdminHome() {
  const stats = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: () => api<StatsOverview>('/stats/overview'),
    refetchInterval: 15_000,
  })
  // Needs attention: late orders first, then orders still waiting for a driver.
  const overdue = useOrders({
    is_overdue: 'true',
    status: ['pending', 'assigned', 'picked_up'],
    sort: 'deliver_by',
    page_size: 5,
  })
  const waiting = useOrders({ status: 'pending', sort: 'deliver_by', page_size: 5 })

  const attention = [...(overdue.data?.items ?? []), ...(waiting.data?.items ?? [])].filter(
    (order, index, all) => all.findIndex((o) => o.id === order.id) === index,
  )
  const s = stats.data

  return (
    <>
      <PageHeader title="Today" subtitle="What needs attention across all businesses." />
      {stats.isError && <ErrorNote message={stats.error.message} />}
      {s ? (
        <Card className="grid grid-cols-2 gap-8 p-7 sm:grid-cols-4">
          <Stat value={s.orders_by_status.pending} label="Waiting for a driver" />
          <Stat value={s.orders_by_status.assigned + s.orders_by_status.picked_up} label="On the road" />
          <Stat
            value={s.overdue_open_orders}
            label="Overdue"
            tone={s.overdue_open_orders > 0 ? 'danger' : 'default'}
          />
          <Stat value={s.drivers_by_status.available} label="Drivers free" />
        </Card>
      ) : (
        !stats.isError && <Spinner className="size-6 text-muted" />
      )}

      <section className="grid gap-4">
        <div className="flex items-baseline justify-between gap-4">
          <h2 className="text-xl font-semibold">Needs attention</h2>
          <Link to="/admin/orders" className="text-sm font-medium text-accent hover:text-accent-hover">
            All orders
          </Link>
        </div>
        {overdue.isPending || waiting.isPending ? (
          <Spinner className="size-5 text-muted" />
        ) : attention.length === 0 ? (
          <Card>
            <EmptyState title="All clear">No overdue orders and nobody is waiting for a driver.</EmptyState>
          </Card>
        ) : (
          <ul className="grid gap-3">
            {attention.map((order) => (
              <OrderCard
                key={order.id}
                order={order}
                actions={(o) => <AdminOrderActions order={o} />}
                showBusiness
              />
            ))}
          </ul>
        )}
      </section>

      {s && (
        <section className="grid gap-4">
          <h2 className="text-xl font-semibold">Last 24 hours</h2>
          <Card className="grid grid-cols-2 gap-8 p-7 sm:grid-cols-4">
            <Stat value={s.last_24h.delivered} label="Delivered" />
            <Stat
              value={s.last_24h.on_time_rate === null ? '–' : `${Math.round(s.last_24h.on_time_rate * 100)}%`}
              label="On time"
            />
            <Stat
              value={
                s.last_24h.avg_delivery_minutes === null
                  ? '–'
                  : `${Math.round(s.last_24h.avg_delivery_minutes)} min`
              }
              label="Average delivery"
            />
            <Stat value={s.last_24h.failed} label="Failed or cancelled" />
          </Card>
        </section>
      )}
    </>
  )
}
