import type { AuditEntry } from './types'

/** One audit entry as a short sentence a person understands. */
export function describeEvent(entry: AuditEntry): string {
  const d = entry.details
  switch (entry.action) {
    case 'order.created':
      return 'Order created'
    case 'order.assigned': {
      const km = typeof d.distance_km === 'number' ? ` ${d.distance_km.toFixed(1)} km away` : ''
      return entry.actor_id ? `Dispatched by an admin to a driver${km}` : `Assigned to a driver${km}`
    }
    case 'order.accepted':
      return 'Driver accepted'
    case 'order.picked_up':
      return 'Picked up'
    case 'order.delivered':
      return d.late ? 'Delivered, after the deadline' : 'Delivered'
    case 'order.failed':
      return `Driver could not deliver: ${String(d.reason ?? 'no reason given')}`
    case 'order.cancelled':
      return d.reason ? `Cancelled: ${String(d.reason)}` : 'Cancelled'
    case 'order.assignment_expired':
      return 'Driver did not accept in time, offered to someone else'
    case 'order.overdue':
      return 'Passed its delivery deadline'
    case 'driver.status_changed':
      return d.reason === 'acceptance_timeout'
        ? 'Driver set offline after missing an order'
        : `Driver went ${String(d.to)}`
    default:
      return entry.action
  }
}

/** Events that need attention are shown with a warning tone. */
export function isWarningEvent(entry: AuditEntry): boolean {
  return ['order.failed', 'order.cancelled', 'order.assignment_expired', 'order.overdue'].includes(
    entry.action,
  )
}
