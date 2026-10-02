import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'

import { useAuth } from '../../auth/useAuth'
import { PageHeader } from '../../components/Card'
import { CancelOrder } from '../../components/CancelOrder'
import { Notice, SearchInput, Tabs } from '../../components/Controls'
import { OrderList } from '../../components/OrderList'
import type { OrderDetail } from '../../lib/types'
import { useDebounced } from '../../lib/useDebounced'

type Filter = 'active' | 'completed'

/** Businesses can cancel until the driver has picked the order up. */
function businessActions(order: OrderDetail) {
  return order.status === 'pending' || order.status === 'assigned' ? <CancelOrder order={order} /> : null
}

export function BusinessOrders() {
  const { user } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const [filter, setFilter] = useState<Filter>('active')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const query = useDebounced(search.trim(), 300)
  const created = (location.state as { created?: string } | null)?.created

  return (
    <>
      <PageHeader
        title="Orders"
        subtitle={user?.business?.name}
        actions={
          <Link
            to="/business/new"
            className="inline-flex h-11 items-center gap-2 rounded-control bg-accent px-5 font-semibold text-white transition-colors hover:bg-accent-hover"
          >
            <Plus aria-hidden="true" className="size-4" strokeWidth={2.5} />
            New order
          </Link>
        }
      />
      {created && <Notice onClose={() => navigate('.', { replace: true, state: null })}>{created}</Notice>}
      <div className="flex flex-wrap items-center gap-3">
        <Tabs
          label="Filter orders"
          value={filter}
          onChange={(v) => {
            setFilter(v)
            setPage(1)
          }}
          options={[
            { value: 'active', label: 'In progress' },
            { value: 'completed', label: 'Completed' },
          ]}
        />
        <SearchInput
          value={search}
          onChange={(v) => {
            setSearch(v)
            setPage(1)
          }}
          placeholder="Search customer or address"
        />
      </div>
      <OrderList
        query={{
          status: filter === 'active' ? ['pending', 'assigned', 'picked_up'] : ['delivered', 'failed'],
          sort: filter === 'active' ? 'deliver_by' : '-created_at',
          search: query || undefined,
        }}
        page={page}
        onPage={setPage}
        empty={
          filter === 'active'
            ? {
                title: 'Nothing in progress',
                text: 'Create an order and it is sent to the nearest free driver.',
              }
            : { title: 'No completed orders yet' }
        }
        actions={businessActions}
      />
    </>
  )
}
