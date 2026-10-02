import { findArea } from '../../lib/areas'

export interface NewOrderValues {
  customerName: string
  customerPhone: string
  street: string
  area: string
  useCoordinates: boolean
  lat: string
  lng: string
  windowMinutes: number
  notes: string
}

/** Build the API payload. Throws a readable message for invalid input. */
export function buildOrderPayload(v: NewOrderValues, now: Date = new Date()) {
  let lat: number
  let lng: number
  if (v.useCoordinates) {
    lat = Number(v.lat)
    lng = Number(v.lng)
    if (
      !v.lat ||
      !v.lng ||
      Number.isNaN(lat) ||
      Number.isNaN(lng) ||
      Math.abs(lat) > 90 ||
      Math.abs(lng) > 180
    ) {
      throw new Error('Enter a valid latitude (-90 to 90) and longitude (-180 to 180).')
    }
  } else {
    const area = findArea(v.area)
    if (!area) throw new Error('Choose the drop-off area.')
    lat = area.lat
    lng = area.lng
  }
  const address = v.useCoordinates ? v.street.trim() : `${v.street.trim()}, ${v.area}`
  return {
    customer_name: v.customerName.trim(),
    customer_phone: v.customerPhone.replace(/[\s-]/g, ''),
    dropoff_address: address,
    dropoff_lat: lat,
    dropoff_lng: lng,
    deliver_by: new Date(now.getTime() + v.windowMinutes * 60_000).toISOString(),
    notes: v.notes.trim() || undefined,
  }
}
