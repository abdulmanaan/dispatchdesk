import { useState } from 'react'

import { api } from '../lib/api'
import { useOrderAction } from '../lib/hooks'
import type { Order } from '../lib/types'
import { Button } from './Button'
import { ErrorNote } from './Card'

/** "Cancel order" that asks for confirmation (and an optional reason) inline. */
export function CancelOrder({ order }: { order: Order }) {
  const [confirming, setConfirming] = useState(false)
  const [reason, setReason] = useState('')
  const cancel = useOrderAction((r: string) =>
    api(`/orders/${order.id}/cancel`, { json: r ? { reason: r } : {} }),
  )

  if (!confirming) {
    return (
      <Button variant="danger" onClick={() => setConfirming(true)}>
        Cancel order
      </Button>
    )
  }
  return (
    <div className="grid w-full gap-3 rounded-control bg-subtle p-4">
      <label htmlFor={`cancel-${order.id}`} className="text-sm font-medium">
        Reason for cancelling (optional)
      </label>
      <input
        id={`cancel-${order.id}`}
        value={reason}
        maxLength={200}
        onChange={(e) => setReason(e.target.value)}
        placeholder="For example: customer called to cancel"
        className="h-11 rounded-control bg-card px-4 ring-1 ring-line ring-inset focus:ring-2 focus:ring-accent focus:outline-none"
      />
      {cancel.isError && <ErrorNote message={cancel.error.message} />}
      <div className="flex flex-wrap gap-3">
        <Button variant="danger" loading={cancel.isPending} onClick={() => cancel.mutate(reason.trim())}>
          Yes, cancel order
        </Button>
        <Button variant="ghost" onClick={() => setConfirming(false)}>
          Keep order
        </Button>
      </div>
    </div>
  )
}
