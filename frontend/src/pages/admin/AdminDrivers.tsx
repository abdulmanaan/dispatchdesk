import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { Card, EmptyState, ErrorNote, PageHeader } from '../../components/Card'
import { Pagination, SearchInput, Tabs } from '../../components/Controls'
import { DriverStatusPill } from '../../components/DriverStatusPill'
import { Spinner } from '../../components/Spinner'
import { api } from '../../lib/api'
import { nearestArea } from '../../lib/areas'
import { orderRef, timeAgo, vehicleName } from '../../lib/format'
import type { DriverAdmin, DriverStatus, Page } from '../../lib/types'
import { useDebounced } from '../../lib/useDebounced'

const PAGE_SIZE = 12

export function AdminDrivers() {
  const [status, setStatus] = useState<DriverStatus | 'all'>('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const query = useDebounced(search.trim(), 300)

  const drivers = useQuery({
    queryKey: ['drivers', status, query, page],
    queryFn: () =>
      api<Page<DriverAdmin>>('/drivers', {
        query: {
          status: status === 'all' ? undefined : status,
          search: query || undefined,
          page,
          page_size: PAGE_SIZE,
        },
      }),
    refetchInterval: 15_000,
    placeholderData: (previous) => previous,
  })

  return (
    <>
      <PageHeader title="Drivers" subtitle="Who is online, where, and what they are doing." />
      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          label="Filter drivers"
          value={status}
          onChange={(v) => {
            setStatus(v)
            setPage(1)
          }}
          options={[
            { value: 'all', label: 'All' },
            { value: 'available', label: 'Available' },
            { value: 'busy', label: 'On a delivery' },
            { value: 'offline', label: 'Offline' },
          ]}
        />
        <SearchInput
          value={search}
          onChange={(v) => {
            setSearch(v)
            setPage(1)
          }}
          placeholder="Search name, email or phone"
        />
      </div>

      {drivers.isPending && <Spinner className="size-6 text-muted" />}
      {drivers.isError && <ErrorNote message={drivers.error.message} />}
      {drivers.data &&
        (drivers.data.items.length === 0 ? (
          <Card>
            <EmptyState title="No matching drivers" />
          </Card>
        ) : (
          <div className="grid gap-4">
            <Card className="overflow-hidden">
              <ul className="divide-y divide-line">
                {drivers.data.items.map((d) => (
                  <li key={d.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 px-6 py-5">
                    <div className="grid min-w-0 gap-0.5">
                      <span className="font-semibold">{d.full_name}</span>
                      <span className="truncate text-sm text-muted">
                        {vehicleName(d.vehicle_type)} · {d.phone}
                        {d.current_lat !== null &&
                          d.current_lng !== null &&
                          ` · near ${nearestArea(d.current_lat, d.current_lng).name}`}
                      </span>
                    </div>
                    <div className="grid justify-items-end gap-1.5">
                      <DriverStatusPill status={d.status} />
                      <span className="text-[13px] text-muted">
                        {d.active_order_id
                          ? `Order ${orderRef(d.active_order_id)}`
                          : d.location_updated_at
                            ? `Seen ${timeAgo(d.location_updated_at)}`
                            : 'No location yet'}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </Card>
            <Pagination
              page={page}
              pages={drivers.data.pages}
              total={drivers.data.total}
              pageSize={PAGE_SIZE}
              onPage={setPage}
            />
          </div>
        ))}
    </>
  )
}
