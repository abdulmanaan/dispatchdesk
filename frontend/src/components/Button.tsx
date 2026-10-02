import type { ButtonHTMLAttributes } from 'react'

import { Spinner } from './Spinner'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

const variants: Record<Variant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-hover',
  secondary: 'bg-card text-ink ring-1 ring-inset ring-line hover:bg-subtle',
  ghost: 'text-muted hover:bg-subtle hover:text-ink',
  danger: 'bg-card text-danger ring-1 ring-inset ring-line hover:bg-danger-soft',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
  size?: 'md' | 'lg'
}

export function Button({
  variant = 'primary',
  loading = false,
  size = 'md',
  disabled,
  className = '',
  children,
  type = 'button',
  ...rest
}: ButtonProps) {
  const sizing = size === 'lg' ? 'h-13 px-6 text-base' : 'h-11 px-5 text-[15px]'
  return (
    <button
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`inline-flex items-center justify-center gap-2 rounded-control font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${sizing} ${variants[variant]} ${className}`}
      {...rest}
    >
      {loading && <Spinner className="size-4" />}
      {children}
    </button>
  )
}
