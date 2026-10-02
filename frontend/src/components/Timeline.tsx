import { describeEvent, isWarningEvent } from '../lib/events'
import { formatWhen } from '../lib/format'
import type { AuditEntry } from '../lib/types'

/** An order's history, oldest first, as a quiet vertical list. */
export function Timeline({ events }: { events: AuditEntry[] }) {
  return (
    <ol className="grid gap-4">
      {events.map((event, index) => (
        <li key={event.id} className="relative grid grid-cols-[14px_1fr] gap-3">
          {index < events.length - 1 && (
            <span
              aria-hidden="true"
              className="absolute top-4 left-[6px] h-[calc(100%+4px)] border-l border-line"
            />
          )}
          <span
            aria-hidden="true"
            className={`relative mt-1.5 size-3 rounded-full ring-4 ring-card ${isWarningEvent(event) ? 'bg-danger' : 'bg-accent/60'}`}
          />
          <div className="grid gap-0.5">
            <span className="text-[15px]">{describeEvent(event)}</span>
            <span className="text-[13px] text-muted tabular-nums">
              {formatWhen(event.created_at)}
              {event.actor_name && ` · ${event.actor_name}`}
            </span>
          </div>
        </li>
      ))}
    </ol>
  )
}
