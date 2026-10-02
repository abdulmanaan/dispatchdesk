import type { Order } from '../../lib/types'

export interface DriverStep {
  action: 'accept' | 'pickup' | 'deliver'
  label: string
  hint: string
}

/** The single next thing the driver should do with their current order. */
export function nextDriverStep(order: Pick<Order, 'status' | 'accepted_at'>): DriverStep | null {
  if (order.status === 'assigned' && !order.accepted_at) {
    return {
      action: 'accept',
      label: 'Accept order',
      hint: 'Accept soon, or the order goes to another driver.',
    }
  }
  if (order.status === 'assigned') {
    return { action: 'pickup', label: 'I picked it up', hint: 'Tap when you have the parcel.' }
  }
  if (order.status === 'picked_up') {
    return { action: 'deliver', label: 'Mark as delivered', hint: 'Tap when the customer has it.' }
  }
  return null
}

export const FAIL_REASONS = [
  'Customer not answering',
  'Wrong or incomplete address',
  'Customer refused the order',
  'Business could not hand over the order',
]
