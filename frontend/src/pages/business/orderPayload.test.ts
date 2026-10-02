import { describe, expect, it } from 'vitest'

import { buildOrderPayload, type NewOrderValues } from './orderPayload'

const base: NewOrderValues = {
  customerName: '  Hina Malik ',
  customerPhone: '+92 300-123 4567',
  street: 'House 12, Street 5',
  area: 'Model Town',
  useCoordinates: false,
  lat: '',
  lng: '',
  windowMinutes: 45,
  notes: '  ',
}
const now = new Date('2026-10-03T12:00:00Z')

describe('buildOrderPayload', () => {
  it('uses the area centre and appends the area to the address', () => {
    const payload = buildOrderPayload(base, now)

    expect(payload).toMatchObject({
      customer_name: 'Hina Malik',
      customer_phone: '+923001234567',
      dropoff_address: 'House 12, Street 5, Model Town',
      dropoff_lat: 31.484,
      dropoff_lng: 74.322,
      deliver_by: '2026-10-03T12:45:00.000Z',
    })
    expect(payload.notes).toBeUndefined()
  })

  it('accepts exact coordinates', () => {
    const payload = buildOrderPayload({ ...base, useCoordinates: true, lat: '31.52', lng: '74.35' }, now)

    expect(payload.dropoff_lat).toBe(31.52)
    expect(payload.dropoff_address).toBe('House 12, Street 5')
  })

  it.each([
    [{ area: '' }, /choose the drop-off area/i],
    [{ useCoordinates: true, lat: '95', lng: '74' }, /valid latitude/i],
    [{ useCoordinates: true, lat: 'abc', lng: '74' }, /valid latitude/i],
    [{ useCoordinates: true, lat: '', lng: '' }, /valid latitude/i],
  ])('rejects %o', (change, message) => {
    expect(() => buildOrderPayload({ ...base, ...change }, now)).toThrow(message)
  })
})
