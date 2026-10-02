import { Check } from 'lucide-react'

import { orderStatusView, type StatusTone } from '../lib/status'
import type { Order } from '../lib/types'

const tones: Record<StatusTone, string> = {
  pending: 'bg-pending-bg text-pending-fg',
  waiting: 'bg-waiting-bg text-waiting-fg',
  moving: 'bg-moving-bg text-moving-fg',
  // Finished work: muted grey-green with a check, deliberately unlike the accent.
  done: 'bg-done-bg text-done-fg',
  failed: 'bg-failed-bg text-failed-fg',
}

export function StatusPill({ order }: { order: Pick<Order, 'status' | 'accepted_at'> }) {
  const { label, tone } = orderStatusView(order)
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[13px] font-medium whitespace-nowrap ${tones[tone]}`}
    >
      {tone === 'done' && <Check aria-hidden="true" className="size-3.5" strokeWidth={2.5} />}
      {label}
    </span>
  )
}

export function OverduePill() {
  return (
    <span className="inline-flex items-center rounded-full bg-failed-bg px-3 py-1 text-[13px] font-medium whitespace-nowrap text-failed-fg">
      Overdue
    </span>
  )
}
