import type { Order } from './types'

/** Visual tone of a status pill. Kept separate from the accent colour. */
export type StatusTone = 'pending' | 'waiting' | 'moving' | 'done' | 'failed'

export interface StatusView {
  label: string
  tone: StatusTone
}

/**
 * What an order's status means to a person, which is finer than the raw status:
 * an "assigned" order is either still awaiting the driver's accept or accepted.
 */
export function orderStatusView(order: Pick<Order, 'status' | 'accepted_at'>): StatusView {
  switch (order.status) {
    case 'pending':
      return { label: 'Pending', tone: 'pending' }
    case 'assigned':
      return order.accepted_at
        ? { label: 'Heading to pickup', tone: 'moving' }
        : { label: 'Awaiting accept', tone: 'waiting' }
    case 'picked_up':
      return { label: 'On the way', tone: 'moving' }
    case 'delivered':
      return { label: 'Delivered', tone: 'done' }
    case 'failed':
      return { label: 'Failed', tone: 'failed' }
  }
}

export function isOpen(order: Pick<Order, 'status'>): boolean {
  return order.status !== 'delivered' && order.status !== 'failed'
}
