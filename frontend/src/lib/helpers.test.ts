import { describe, expect, it } from 'vitest'

import { nearestArea } from './areas'
import { describeEvent } from './events'
import { timeAgo } from './format'
import { formatKm, haversineKm } from './geo'
import type { AuditEntry } from './types'

const entry = (
  action: string,
  details: Record<string, unknown> = {},
  actor_id: string | null = null,
): AuditEntry => ({
  id: 1,
  actor_id,
  actor_email: null,
  actor_name: null,
  action,
  entity_type: 'order',
  entity_id: 'x',
  details,
  created_at: '2026-10-03T10:00:00Z',
})

describe('geo', () => {
  it('matches the backend distance for a known Lahore pair', () => {
    // Liberty Market to Minar-e-Pakistan, about 9.6 km (same as the backend test).
    expect(haversineKm(31.5104, 74.3416, 31.5925, 74.3095)).toBeCloseTo(9.6, 0)
  })

  it('formats short trips with one decimal', () => {
    expect(formatKm(4.137)).toBe('4.1 km')
    expect(formatKm(12.6)).toBe('13 km')
  })

  it('names the nearest area', () => {
    expect(nearestArea(31.4845, 74.323).name).toBe('Model Town')
  })
})

describe('describeEvent', () => {
  it.each([
    [entry('order.assigned', { distance_km: 1.234 }), 'Assigned to a driver 1.2 km away'],
    [
      entry('order.assigned', { distance_km: 2 }, 'admin-id'),
      'Dispatched by an admin to a driver 2.0 km away',
    ],
    [entry('order.delivered', { late: true }), 'Delivered, after the deadline'],
    [
      entry('order.failed', { reason: 'Customer not answering' }),
      'Driver could not deliver: Customer not answering',
    ],
    [entry('order.cancelled', { reason: null }), 'Cancelled'],
    [
      entry('driver.status_changed', { to: 'offline', reason: 'acceptance_timeout' }),
      'Driver set offline after missing an order',
    ],
    [entry('driver.status_changed', { to: 'available' }), 'Driver went available'],
  ])('%#', (event, text) => {
    expect(describeEvent(event)).toBe(text)
  })
})

describe('timeAgo', () => {
  const now = new Date('2026-10-03T12:00:00Z')
  it.each([
    ['2026-10-03T11:59:40Z', 'just now'],
    ['2026-10-03T11:55:00Z', '5 min ago'],
    ['2026-10-03T09:00:00Z', '3 h ago'],
    ['2026-10-02T12:00:00Z', '1 day ago'],
  ])('%s -> %s', (iso, text) => {
    expect(timeAgo(iso, now)).toBe(text)
  })
})
