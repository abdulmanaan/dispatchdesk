import { ChevronLeft, ChevronRight, Search } from 'lucide-react'
import { useId, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react'

/** Segmented tabs for switching between list filters. */
export function Tabs<T extends string>({
  value,
  options,
  onChange,
  label,
}: {
  value: T
  options: { value: T; label: string }[]
  onChange: (value: T) => void
  label: string
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className="flex flex-wrap gap-1 rounded-control bg-card p-1 shadow-card"
    >
      {options.map((option) => {
        const active = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(option.value)}
            className={`rounded-[9px] px-4 py-2 text-sm font-medium transition-colors ${active ? 'bg-accent-soft text-accent' : 'text-muted hover:text-ink'}`}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  placeholder: string
}) {
  return (
    <label className="relative flex min-w-0 basis-full sm:max-w-xs sm:flex-1 sm:basis-auto">
      <span className="sr-only">{placeholder}</span>
      <Search
        aria-hidden="true"
        className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted"
      />
      <input
        type="search"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="h-11 w-full rounded-control bg-card pr-4 pl-11 text-[15px] shadow-card ring-1 ring-transparent placeholder:text-muted focus:ring-accent focus:outline-none"
      />
    </label>
  )
}

export function Pagination({
  page,
  pages,
  total,
  pageSize,
  onPage,
}: {
  page: number
  pages: number
  total: number
  pageSize: number
  onPage: (page: number) => void
}) {
  if (total <= pageSize) return null
  const first = (page - 1) * pageSize + 1
  const last = Math.min(page * pageSize, total)
  const button =
    'inline-flex size-10 items-center justify-center rounded-control text-muted transition-colors hover:bg-card hover:text-ink disabled:pointer-events-none disabled:opacity-40'
  return (
    <div className="flex items-center justify-between gap-4 text-sm text-muted">
      <span className="tabular-nums">
        {first}–{last} of {total}
      </span>
      <div className="flex gap-1">
        <button
          type="button"
          className={button}
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          aria-label="Previous page"
        >
          <ChevronLeft className="size-5" />
        </button>
        <button
          type="button"
          className={button}
          disabled={page >= pages}
          onClick={() => onPage(page + 1)}
          aria-label="Next page"
        >
          <ChevronRight className="size-5" />
        </button>
      </div>
    </div>
  )
}

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string
  children: ReactNode
}

export function SelectField({ label, id, children, className = '', ...rest }: SelectProps) {
  const autoId = useId()
  const selectId = id ?? autoId
  return (
    <div className="grid gap-1.5">
      <label htmlFor={selectId} className="text-sm font-medium">
        {label}
      </label>
      <select
        id={selectId}
        className={`h-12 rounded-control bg-card px-4 text-[15px] ring-1 ring-line ring-inset focus:ring-2 focus:ring-accent focus:outline-none ${className}`}
        {...rest}
      >
        {children}
      </select>
    </div>
  )
}

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string
}

export function TextAreaField({ label, id, className = '', ...rest }: TextAreaProps) {
  const autoId = useId()
  const areaId = id ?? autoId
  return (
    <div className="grid gap-1.5">
      <label htmlFor={areaId} className="text-sm font-medium">
        {label}
      </label>
      <textarea
        id={areaId}
        rows={3}
        className={`rounded-control bg-card px-4 py-3 text-[15px] ring-1 ring-line ring-inset focus:ring-2 focus:ring-accent focus:outline-none ${className}`}
        {...rest}
      />
    </div>
  )
}

/** A quiet confirmation banner shown after an action elsewhere. */
export function Notice({ children, onClose }: { children: ReactNode; onClose?: () => void }) {
  return (
    <div
      role="status"
      className="flex items-start justify-between gap-4 rounded-card bg-accent-soft px-6 py-4 text-accent"
    >
      <div className="text-[15px]">{children}</div>
      {onClose && (
        <button type="button" onClick={onClose} className="text-sm font-medium hover:underline">
          Dismiss
        </button>
      )}
    </div>
  )
}
