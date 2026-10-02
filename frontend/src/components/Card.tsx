import type { HTMLAttributes } from 'react'

export function Card({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div className={`rounded-card bg-card shadow-card ${className}`} {...rest} />
}

/** Page title with an optional muted subtitle and actions on the right. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div className="grid gap-1">
        <h1 className="text-[28px] leading-tight font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex gap-3">{actions}</div>}
    </div>
  )
}

/** A big number with a small muted label underneath. */
export function Stat({
  value,
  label,
  tone = 'default',
}: {
  value: React.ReactNode
  label: string
  tone?: 'default' | 'danger'
}) {
  return (
    <div className="grid gap-1">
      <span
        className={`text-[34px] leading-none font-semibold tracking-tight tabular-nums ${tone === 'danger' ? 'text-danger' : ''}`}
      >
        {value}
      </span>
      <span className="text-sm text-muted">{label}</span>
    </div>
  )
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="grid justify-items-center gap-2 px-6 py-12 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="max-w-sm text-sm text-muted">{children}</div>}
    </div>
  )
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <p role="alert" className="rounded-control bg-danger-soft px-4 py-3 text-sm text-failed-fg">
      {message}
    </p>
  )
}
