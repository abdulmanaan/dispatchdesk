import { useState } from 'react'

import { PageHeader } from '../../components/Card'
import { SearchInput, Tabs } from '../../components/Controls'
import { OrderList } from '../../components/OrderList'
import { useDebounced } from '../../lib/useDebounced'
import { AdminOrderActions } from './AdminOrderActions'

type Filter = 'all' | 'waiting' | 'active' | 'delivered' | 'failed'

const statuses: Record<Filter, string[] | undefined> = {
  all: undefined,
  waiting: ['pending'],
  active: ['assigned', 'picked_up'],
  delivered: ['delivered'],
  failed: ['failed'],
}

export function AdminOrders() {
  const [filter, setFilter] = useState<Filter>('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const query = useDebounced(search.trim(), 300)

  return (
    <>
      <PageHeader title="Orders" subtitle="Every order from every business." />
      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          label="Filter orders"
          value={filter}
          onChange={(v) => {
            setFilter(v)
            setPage(1)
          }}
          options={[
            { value: 'all', label: 'All' },
            { value: 'waiting', label: 'Waiting' },
            { value: 'active', label: 'On the road' },
            { value: 'delivered', label: 'Delivered' },
            { value: 'failed', label: 'Failed' },
          ]}
        />
        <SearchInput
          value={search}
          onChange={(v) => {
            setSearch(v)
            setPage(1)
          }}
          placeholder="Search customer, phone or address"
        />
      </div>
      <OrderList
        query={{
          status: statuses[filter],
          search: query || undefined,
          sort: filter === 'active' || filter === 'waiting' ? 'deliver_by' : '-created_at',
        }}
        page={page}
        onPage={setPage}
        empty={{ title: 'No matching orders', text: 'Try another filter or search.' }}
        actions={(o) => <AdminOrderActions order={o} />}
        showBusiness
      />
    </>
  )
}
