import { ChevronRight } from 'lucide-react'
import { useId, useState, type ReactNode } from 'react'

import { formatTime, formatWhen, orderRef, vehicleName } from '../lib/format'
import { formatKm, haversineKm } from '../lib/geo'
import { useOrderDetail, useOrderEvents } from '../lib/hooks'
import { isOpen } from '../lib/status'
import type { Order, OrderDetail } from '../lib/types'
import { ErrorNote } from './Card'
import { Spinner } from './Spinner'
import { OverduePill, StatusPill } from './StatusPill'
import { Timeline } from './Timeline'

interface OrderCardProps {
  order: Order
  /** Role-specific buttons shown under the details. */
  actions?: (order: OrderDetail) => ReactNode
  showBusiness?: boolean
}

/**
 * One order as a card. The summary shows only what matters (who, where, status,
 * deadline); details, people and the timeline load when the card is opened.
 */
export function OrderCard({ order, actions, showBusiness = false }: OrderCardProps) {
  const [open, setOpen] = useState(false)
  const panelId = useId()
  const done = !isOpen(order)

  return (
    <li className="rounded-card bg-card shadow-card">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[minmax(0,1fr)_16px] items-center gap-4 rounded-card px-6 py-5 text-left"
      >
        <span className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-4">
          <span className="grid min-w-0 gap-0.5">
            <span className="truncate font-semibold">
              {order.customer_name}
              <span className="font-normal text-muted tabular-nums"> · {orderRef(order.id)}</span>
            </span>
            <span className="truncate text-sm text-muted">{order.dropoff_address}</span>
          </span>
          {/* Phones: status and time sit on their own row. Wider screens: right column. */}
          <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5 sm:grid sm:justify-items-end">
            <span className="flex flex-wrap gap-2 sm:justify-end">
              {order.is_overdue && !done && <OverduePill />}
              <StatusPill order={order} />
            </span>
            <span className="text-[13px] text-muted tabular-nums">
              {order.status === 'delivered' && order.delivered_at
                ? `Delivered ${formatWhen(order.delivered_at)}`
                : order.status === 'failed'
                  ? `Closed ${formatWhen(order.failed_at ?? order.updated_at)}`
                  : `Due ${formatTime(order.deliver_by)}`}
            </span>
          </span>
        </span>
        <ChevronRight
          aria-hidden="true"
          className={`size-4 text-muted transition-transform ${open ? 'rotate-90' : ''}`}
        />
      </button>
      {open && (
        <div id={panelId}>
          <OrderDetails orderId={order.id} actions={actions} showBusiness={showBusiness} />
        </div>
      )}
    </li>
  )
}

function OrderDetails({
  orderId,
  actions,
  showBusiness,
}: {
  orderId: string
  actions?: (order: OrderDetail) => ReactNode
  showBusiness: boolean
}) {
  const detail = useOrderDetail(orderId, true)
  const events = useOrderEvents(orderId, true)

  if (detail.isPending) {
    return (
      <div className="px-6 pb-6 text-muted">
        <Spinner />
      </div>
    )
  }
  if (detail.isError) {
    return (
      <div className="px-6 pb-6">
        <ErrorNote message={detail.error.message} />
      </div>
    )
  }

  const o = detail.data
  const trip = haversineKm(o.pickup_lat, o.pickup_lng, o.dropoff_lat, o.dropoff_lng)
  const facts: [string, ReactNode][] = [
    ['Pickup', o.pickup_address],
    ['Drop-off', o.dropoff_address],
    ['Customer', `${o.customer_name}, ${o.customer_phone}`],
    [
      'Driver',
      o.driver
        ? `${o.driver.full_name}, ${vehicleName(o.driver.vehicle_type).toLowerCase()}, ${o.driver.phone}`
        : 'Not assigned yet',
    ],
    ['Trip', `${formatKm(trip)}, deliver by ${formatTime(o.deliver_by)}`],
  ]
  if (showBusiness) facts.unshift(['Business', `${o.business.name}, ${o.business.phone}`])
  if (o.notes) facts.push(['Notes', o.notes])
  if (o.failure_reason) facts.push(['Outcome', o.failure_reason])

  return (
    <div className="mx-6 grid gap-6 border-t border-line pt-5 pb-6">
      <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
        {facts.map(([label, value]) => (
          <div key={label} className="grid gap-0.5">
            <dt className="text-sm text-muted">{label}</dt>
            <dd className="text-[15px]">{value}</dd>
          </div>
        ))}
      </dl>
      {actions && <div className="flex flex-wrap gap-3">{actions(o)}</div>}
      <div className="grid gap-3">
        <h3 className="text-sm font-medium text-muted">Timeline</h3>
        {events.data ? <Timeline events={events.data} /> : <Spinner className="size-4 text-muted" />}
      </div>
    </div>
  )
}
