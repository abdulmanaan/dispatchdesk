import type { DriverStatus } from '../lib/types'

const styles: Record<DriverStatus, { label: string; className: string }> = {
  available: { label: 'Available', className: 'bg-accent-soft text-accent' },
  busy: { label: 'On a delivery', className: 'bg-moving-bg text-moving-fg' },
  offline: { label: 'Offline', className: 'bg-pending-bg text-pending-fg' },
}

export function DriverStatusPill({ status }: { status: DriverStatus }) {
  const { label, className } = styles[status]
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-[13px] font-medium whitespace-nowrap ${className}`}
    >
      {label}
    </span>
  )
}
