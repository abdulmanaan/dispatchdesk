import { useQuery } from '@tanstack/react-query'

import { Card, ErrorNote, PageHeader, Stat } from '../../components/Card'
import { Spinner } from '../../components/Spinner'
import { api } from '../../lib/api'
import type { StatsOverview } from '../../lib/types'

export function AdminHome() {
  const stats = useQuery({
    queryKey: ['stats', 'overview'],
    queryFn: () => api<StatsOverview>('/stats/overview'),
    refetchInterval: 15_000,
  })

  return (
    <>
      <PageHeader title="Today" subtitle="What needs attention across all businesses." />
      {stats.isPending && <Spinner className="size-6 text-muted" />}
      {stats.isError && <ErrorNote message={stats.error.message} />}
      {stats.data && (
        <Card className="grid grid-cols-2 gap-8 p-7 sm:grid-cols-4">
          <Stat value={stats.data.orders_by_status.pending} label="Waiting for a driver" />
          <Stat
            value={stats.data.orders_by_status.assigned + stats.data.orders_by_status.picked_up}
            label="On the road"
          />
          <Stat
            value={stats.data.overdue_open_orders}
            label="Overdue"
            tone={stats.data.overdue_open_orders > 0 ? 'danger' : 'default'}
          />
          <Stat value={stats.data.drivers_by_status.available} label="Drivers free" />
        </Card>
      )}
    </>
  )
}
