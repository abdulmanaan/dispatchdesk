// Display helpers. Times are shown in the viewer's local time zone.

const timeFormat = new Intl.DateTimeFormat(undefined, { hour: '2-digit', minute: '2-digit' })

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso))
}

/** Short, human order reference derived from the UUID, e.g. "4F2A". */
export function orderRef(id: string): string {
  return id.slice(0, 4).toUpperCase()
}

const roleNames = { admin: 'Admin', business: 'Business', driver: 'Driver' } as const

export function roleName(role: keyof typeof roleNames): string {
  return roleNames[role]
}
