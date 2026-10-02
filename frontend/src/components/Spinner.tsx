export function Spinner({ className = 'size-5' }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Loading"
      className={`inline-block animate-spin rounded-full border-2 border-current border-r-transparent ${className}`}
    />
  )
}

export function FullPageSpinner() {
  return (
    <div className="grid min-h-dvh place-items-center text-muted">
      <Spinner className="size-6" />
    </div>
  )
}
