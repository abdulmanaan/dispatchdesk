// Display helpers. Times are shown in the viewer's local time zone.

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })
const dayTimeFormat = new Intl.DateTimeFormat(undefined, {
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso))
}

/** Time only for today, day and time otherwise. */
export function formatWhen(iso: string, now: Date = new Date()): string {
  const date = new Date(iso)
  return date.toDateString() === now.toDateString() ? timeFormat.format(date) : dayTimeFormat.format(date)
}

/** "just now", "5 min ago", "2 h ago", "3 days ago". */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const minutes = Math.round((now.getTime() - new Date(iso).getTime()) / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} h ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

/** Short, human order reference derived from the UUID, e.g. "4F2A". */
export function orderRef(id: string): string {
  return id.slice(0, 4).toUpperCase()
}

const roleNames = { admin: 'Admin', business: 'Business', driver: 'Driver' } as const

export function roleName(role: keyof typeof roleNames): string {
  return roleNames[role]
}

const vehicleNames = { motorbike: 'Motorbike', car: 'Car', bicycle: 'Bicycle' } as const

export function vehicleName(vehicle: keyof typeof vehicleNames): string {
  return vehicleNames[vehicle]
}
