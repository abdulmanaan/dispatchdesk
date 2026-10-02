import { describe, expect, it } from 'vitest'

import { isOpen, orderStatusView } from './status'

describe('orderStatusView', () => {
  it.each([
    [{ status: 'pending', accepted_at: null }, 'Pending', 'pending'],
    [{ status: 'assigned', accepted_at: null }, 'Awaiting accept', 'waiting'],
    [{ status: 'assigned', accepted_at: '2026-10-03T10:00:00Z' }, 'Heading to pickup', 'moving'],
    [{ status: 'picked_up', accepted_at: '2026-10-03T10:00:00Z' }, 'On the way', 'moving'],
    [{ status: 'delivered', accepted_at: '2026-10-03T10:00:00Z' }, 'Delivered', 'done'],
    [{ status: 'failed', accepted_at: null }, 'Failed', 'failed'],
  ] as const)('%o -> %s', (order, label, tone) => {
    expect(orderStatusView(order)).toEqual({ label, tone })
  })

  it('treats delivered and failed orders as closed', () => {
    expect(isOpen({ status: 'delivered' })).toBe(false)
    expect(isOpen({ status: 'failed' })).toBe(false)
    expect(isOpen({ status: 'picked_up' })).toBe(true)
  })
})
