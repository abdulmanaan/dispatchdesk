/** Brand mark: a dotted route from a pickup (filled) to a drop (ring). */
export function Logo({ withName = true }: { withName?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <svg viewBox="0 0 32 32" className="size-8" aria-hidden="true">
        <rect width="32" height="32" rx="9" fill="var(--color-accent)" />
        <path
          d="M10 22c0-6 12-6 12-12"
          fill="none"
          stroke="var(--color-accent-soft)"
          strokeWidth="2"
          strokeDasharray="2 3"
          strokeLinecap="round"
        />
        <circle cx="10" cy="22" r="3" fill="#fff" />
        <circle cx="22" cy="10" r="3" fill="none" stroke="#fff" strokeWidth="2" />
      </svg>
      {withName && <span className="text-[17px] font-semibold tracking-tight">DispatchDesk</span>}
    </span>
  )
}
