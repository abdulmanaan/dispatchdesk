import { describe, expect, it } from 'vitest'

import { nextDriverStep } from './driverSteps'

describe('nextDriverStep', () => {
  it.each([
    [{ status: 'assigned', accepted_at: null }, 'accept'],
    [{ status: 'assigned', accepted_at: '2026-10-03T10:00:00Z' }, 'pickup'],
    [{ status: 'picked_up', accepted_at: '2026-10-03T10:00:00Z' }, 'deliver'],
  ] as const)('%o -> %s', (order, action) => {
    expect(nextDriverStep(order)?.action).toBe(action)
  })

  it('has nothing to do for finished or unassigned orders', () => {
    expect(nextDriverStep({ status: 'delivered', accepted_at: 'x' })).toBeNull()
    expect(nextDriverStep({ status: 'pending', accepted_at: null })).toBeNull()
  })
})
