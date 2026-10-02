import type { ReactNode } from 'react'

import { useOrders } from '../lib/hooks'
import type { OrderDetail } from '../lib/types'
import { EmptyState, ErrorNote } from './Card'
import { Pagination } from './Controls'
import { OrderCard } from './OrderCard'
import { Spinner } from './Spinner'

const PAGE_SIZE = 10

interface OrderListProps {
  query: Record<string, string | number | string[] | undefined>
  page: number
  onPage: (page: number) => void
  empty: { title: string; text?: string }
  actions?: (order: OrderDetail) => ReactNode
  showBusiness?: boolean
}

export function OrderList({ query, page, onPage, empty, actions, showBusiness }: OrderListProps) {
  const orders = useOrders({ ...query, page, page_size: PAGE_SIZE })

  if (orders.isPending) return <Spinner className="size-6 text-muted" />
  if (orders.isError) return <ErrorNote message={orders.error.message} />

  const { items, total, pages } = orders.data
  if (items.length === 0) {
    return (
      <div className="rounded-card bg-card shadow-card">
        <EmptyState title={empty.title}>{empty.text}</EmptyState>
      </div>
    )
  }
  return (
    <div className="grid gap-4">
      <ul className="grid gap-3">
        {items.map((order) => (
          <OrderCard key={order.id} order={order} actions={actions} showBusiness={showBusiness} />
        ))}
      </ul>
      <Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} onPage={onPage} />
    </div>
  )
}
