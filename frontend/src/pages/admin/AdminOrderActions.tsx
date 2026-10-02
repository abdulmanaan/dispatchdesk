import { useState } from 'react'

import { Button } from '../../components/Button'
import { ErrorNote } from '../../components/Card'
import { CancelOrder } from '../../components/CancelOrder'
import { api } from '../../lib/api'
import { useOrderAction } from '../../lib/hooks'
import { isOpen } from '../../lib/status'
import type { DispatchResult, OrderDetail } from '../../lib/types'

const outcomeText: Record<string, string> = {
  no_driver: 'No available driver within range right now. The order stays in the queue.',
  locked: 'Someone else is updating this order. Try again in a moment.',
}

function DispatchNow({ order }: { order: OrderDetail }) {
  const [note, setNote] = useState<string | null>(null)
  const dispatch = useOrderAction(() =>
    api<DispatchResult>(`/dispatch/orders/${order.id}`, { method: 'POST' }),
  )

  return (
    <>
      <Button
        loading={dispatch.isPending}
        onClick={() =>
          dispatch.mutate(undefined, {
            onSuccess: (r) =>
              setNote(r.result.outcome === 'assigned' ? null : (outcomeText[r.result.outcome] ?? null)),
          })
        }
      >
        Dispatch now
      </Button>
      {note && <p className="w-full text-sm text-muted">{note}</p>}
      {dispatch.isError && <ErrorNote message={dispatch.error.message} />}
    </>
  )
}

/** Buttons an admin gets on an opened order. */
export function AdminOrderActions({ order }: { order: OrderDetail }) {
  if (!isOpen(order)) return null
  return (
    <>
      {order.status === 'pending' && <DispatchNow order={order} />}
      <CancelOrder order={order} />
    </>
  )
}
