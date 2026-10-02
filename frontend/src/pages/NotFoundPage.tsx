import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="grid min-h-dvh place-items-center px-5">
      <div className="grid justify-items-center gap-3 text-center">
        <h1 className="text-[28px] font-semibold tracking-tight">Page not found</h1>
        <p className="text-muted">This address does not match any page.</p>
        <Link to="/" className="mt-2 font-semibold text-accent hover:text-accent-hover">
          Go to your home page
        </Link>
      </div>
    </div>
  )
}
