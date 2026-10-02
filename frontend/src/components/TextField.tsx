import { useId, type InputHTMLAttributes } from 'react'

interface TextFieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string
  hint?: string
}

export function TextField({ label, hint, id, className = '', ...rest }: TextFieldProps) {
  const autoId = useId()
  const inputId = id ?? autoId
  const hintId = hint ? `${inputId}-hint` : undefined
  return (
    <div className="grid gap-1.5">
      <label htmlFor={inputId} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={inputId}
        aria-describedby={hintId}
        className={`h-12 rounded-control bg-card px-4 text-[15px] ring-1 ring-line ring-inset placeholder:text-muted/70 focus:ring-2 focus:ring-accent focus:outline-none ${className}`}
        {...rest}
      />
      {hint && (
        <p id={hintId} className="text-sm text-muted">
          {hint}
        </p>
      )}
    </div>
  )
}
