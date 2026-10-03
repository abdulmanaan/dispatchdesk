import { Phone } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link } from 'react-router'

import { homePath, useAuth } from '../auth/useAuth'
import { DemoAccounts } from '../components/DemoAccounts'
import { Logo } from '../components/Logo'
import { OverduePill, StatusPill } from '../components/StatusPill'
import { Timeline } from '../components/Timeline'
import { formatTime } from '../lib/format'
import { AUTHOR } from '../lib/site'
import type { AuditEntry, Order } from '../lib/types'

// Everything below the hero shows static copies of real app screens, filled with
// example data. They look like the app but never call the API.

const minutesFromNow = (m: number) => new Date(Date.now() + m * 60_000).toISOString()

/** A sample order history for the hero, built with the app's own timeline. */
function exampleTimeline(): AuditEntry[] {
  const entry = (id: number, action: string, m: number, actor: string | null, details = {}): AuditEntry => ({
    id,
    action,
    actor_id: actor ? String(id) : null,
    actor_email: null,
    actor_name: actor,
    entity_type: 'order',
    entity_id: 'example',
    details,
    created_at: minutesFromNow(-m),
  })
  return [
    entry(1, 'order.created', 24, 'Hamza Butt'),
    entry(2, 'order.assigned', 23, null, { distance_km: 0.6 }),
    entry(3, 'order.accepted', 23, 'Kamran Ali'),
    entry(4, 'order.picked_up', 14, 'Kamran Ali'),
    entry(5, 'order.delivered', 2, 'Kamran Ali'),
  ]
}

type ExampleOrder = Pick<Order, 'status' | 'accepted_at' | 'is_overdue'> & {
  customer: string
  address: string
  note: string
}

const BUSINESS_ORDERS: ExampleOrder[] = [
  {
    customer: 'Hina Malik',
    address: 'House 12, Street 5, Model Town',
    status: 'assigned',
    accepted_at: null,
    is_overdue: false,
    note: `Due ${formatTime(minutesFromNow(52))}`,
  },
  {
    customer: 'Saad Qureshi',
    address: '45-C, DHA Phase 5',
    status: 'assigned',
    accepted_at: 'yes',
    is_overdue: false,
    note: `Due ${formatTime(minutesFromNow(38))}`,
  },
  {
    customer: 'Ayesha Khan',
    address: 'Flat 3B, Gulberg Heights',
    status: 'picked_up',
    accepted_at: 'yes',
    is_overdue: false,
    note: `Due ${formatTime(minutesFromNow(17))}`,
  },
  {
    customer: 'Omar Farooq',
    address: '88-E, Iqbal Town',
    status: 'delivered',
    accepted_at: 'yes',
    is_overdue: false,
    note: `Delivered ${formatTime(minutesFromNow(-9))}`,
  },
]

const ATTENTION_ORDERS: ExampleOrder[] = [
  {
    customer: 'Zainab Shah',
    address: 'House 31, Sector B, Township',
    status: 'picked_up',
    accepted_at: 'yes',
    is_overdue: true,
    note: `Was due ${formatTime(minutesFromNow(-6))}`,
  },
  {
    customer: 'Danish Iqbal',
    address: 'House 5, Wapda Town Phase 1',
    status: 'pending',
    accepted_at: null,
    is_overdue: false,
    note: `Due ${formatTime(minutesFromNow(25))}`,
  },
]

function OrderRow({ order }: { order: ExampleOrder }) {
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 rounded-card bg-card px-5 py-4 shadow-card sm:px-6">
      <div className="grid min-w-0 gap-0.5">
        <span className="truncate font-semibold">{order.customer}</span>
        <span className="truncate text-sm text-muted">{order.address}</span>
      </div>
      <div className="grid justify-items-end gap-1.5">
        <div className="flex flex-wrap justify-end gap-2">
          {order.is_overdue && <OverduePill />}
          <StatusPill order={order} />
        </div>
        <span className="text-[13px] text-muted tabular-nums">{order.note}</span>
      </div>
    </div>
  )
}

/** The driver's phone screen with a new order, as in the driver app. */
function DriverPhone() {
  const stops = [
    { label: 'Pick up from', title: 'Lahori Biryani Corner', detail: 'MM Alam Road, Gulberg', filled: false },
    { label: 'Deliver to', title: 'House 12, Street 5', detail: 'Model Town', filled: true },
  ]
  return (
    <div className="mx-auto w-full max-w-[320px] rounded-[36px] bg-ink p-2.5 shadow-card">
      <div className="grid gap-5 rounded-[28px] bg-page px-5 pt-8 pb-6">
        <div className="grid gap-1">
          <span className="text-sm text-muted">New order for you</span>
          <span className="text-xl font-semibold">Hina Malik</span>
        </div>
        <ol className="grid gap-4">
          {stops.map((stop) => (
            <li key={stop.label} className="grid grid-cols-[12px_1fr_auto] items-start gap-3">
              <span
                className={`mt-1.5 size-3 rounded-full border-2 border-accent ${stop.filled ? 'bg-accent' : ''}`}
              />
              <span className="grid gap-0.5">
                <span className="text-[13px] text-muted">{stop.label}</span>
                <span className="text-[15px] font-semibold">{stop.title}</span>
                <span className="text-[13px] text-muted">{stop.detail}</span>
              </span>
              <span className="grid size-9 place-items-center rounded-full bg-accent-soft text-accent">
                <Phone className="size-4" />
              </span>
            </li>
          ))}
        </ol>
        <div className="flex gap-8">
          <span className="grid">
            <span className="text-lg font-semibold tabular-nums">4.1 km</span>
            <span className="text-[13px] text-muted">Trip</span>
          </span>
          <span className="grid">
            <span className="text-lg font-semibold tabular-nums">{formatTime(minutesFromNow(52))}</span>
            <span className="text-[13px] text-muted">Deliver by</span>
          </span>
        </div>
        <span className="grid h-12 place-items-center rounded-control bg-accent font-semibold text-white">
          Accept order
        </span>
      </div>
    </div>
  )
}

/** One benefit: a short text next to the piece of the app that delivers it. */
function Feature({
  title,
  children,
  visual,
  visualLabel,
  visualFirst = false,
}: {
  title: string
  children: ReactNode
  visual: ReactNode
  visualLabel: string
  visualFirst?: boolean
}) {
  return (
    <section className="grid items-center gap-10 py-16 sm:py-20 md:grid-cols-2 md:gap-16">
      <div className={`grid max-w-md gap-4 ${visualFirst ? 'md:order-2' : ''}`}>
        <h2 className="text-[26px] leading-tight font-semibold tracking-tight sm:text-[30px]">{title}</h2>
        <div className="grid gap-3 text-[17px] leading-relaxed text-muted">{children}</div>
      </div>
      {/* Example screen: described once for screen readers, details hidden. */}
      <figure aria-label={visualLabel} className={visualFirst ? 'md:order-1' : ''}>
        <div aria-hidden="true">{visual}</div>
      </figure>
    </section>
  )
}

export function LandingPage() {
  const { status, user } = useAuth()
  const signedIn = status === 'signed-in' && user

  return (
    <div className="min-h-dvh">
      <header className="mx-auto flex h-20 max-w-5xl items-center justify-between gap-4 px-5 sm:px-8">
        <Logo />
        {signedIn ? (
          <Link
            to={homePath[user.role]}
            className="rounded-control px-4 py-2 text-[15px] font-semibold text-accent hover:bg-accent-soft"
          >
            Open your dashboard
          </Link>
        ) : (
          <Link
            to="/login"
            className="rounded-control px-4 py-2 text-[15px] font-semibold text-muted hover:bg-card hover:text-ink"
          >
            Sign in
          </Link>
        )}
      </header>

      <main className="mx-auto max-w-5xl px-5 sm:px-8">
        {/* Hero: what it is, and the way in. */}
        <section className="grid items-start gap-14 pt-10 pb-12 sm:pt-16 sm:pb-16 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-16">
          <div className="grid gap-10">
            <div className="grid gap-5">
              <h1 className="text-[36px] leading-[1.1] font-semibold tracking-tight sm:text-[48px]">
                Delivery dispatch for local businesses
              </h1>
              <p className="max-w-xl text-lg text-muted sm:text-xl sm:leading-relaxed">
                Restaurants, pharmacies and shops create delivery orders, and DispatchDesk hands each one to
                the best available driver nearby, never giving a driver two orders at once.
              </p>
            </div>

            <div className="grid max-w-xl gap-4">
              <div className="grid gap-1">
                <h2 className="text-lg font-semibold">Try the live demo</h2>
                <p className="text-sm text-muted">
                  Sample data around Lahore. Pick a role and you are signed in. No sign-up needed.
                </p>
              </div>
              <DemoAccounts
                fallback={
                  <Link
                    to="/login"
                    className="inline-flex h-12 w-fit items-center rounded-control bg-accent px-6 font-semibold text-white hover:bg-accent-hover"
                  >
                    Sign in
                  </Link>
                }
              />
            </div>
          </div>

          <figure className="grid gap-5 rounded-card bg-card p-6 shadow-card sm:p-7">
            <figcaption className="text-sm text-muted">Example order</figcaption>
            <div className="flex items-start justify-between gap-3">
              <div className="grid gap-0.5">
                <span className="text-lg font-semibold">Zainab Shah</span>
                <span className="text-sm text-muted">Lahori Biryani Corner to Township</span>
              </div>
              <StatusPill order={{ status: 'delivered', accepted_at: 'yes' }} />
            </div>
            <div className="border-t border-line pt-5">
              <Timeline events={exampleTimeline()} />
            </div>
          </figure>
        </section>

        <Feature
          title="No more dispatching on WhatsApp"
          visual={<DriverPhone />}
          visualLabel="Example: the driver's phone showing a new order with an Accept button"
        >
          <p>
            Each new order goes straight to the nearest free driver’s phone, with the pickup, the address and
            a call button. Nobody has to post it in a group and wait for someone to reply.
          </p>
          <p>If the driver doesn’t accept within three minutes, the next driver gets it.</p>
        </Feature>

        <Feature
          title="See where every order is"
          visualFirst
          visual={
            <div className="grid gap-3">
              {BUSINESS_ORDERS.map((order) => (
                <OrderRow key={order.customer} order={order} />
              ))}
            </div>
          }
          visualLabel="Example: a business's order list with a status for each order"
        >
          <p>
            Every order shows where it stands, from waiting for a driver to delivered. Open one to see who has
            it and when each step happened.
          </p>
        </Feature>

        <Feature
          title="Late orders flag themselves"
          visual={
            <div className="grid gap-4">
              <span className="text-lg font-semibold">Needs attention</span>
              <div className="grid gap-3">
                {ATTENTION_ORDERS.map((order) => (
                  <OrderRow key={order.customer} order={order} />
                ))}
              </div>
            </div>
          }
          visualLabel="Example: the admin's needs attention list with an overdue order at the top"
        >
          <p>
            Every order has a delivery deadline. When one runs late, it is marked overdue and moves to the top
            of the list, so you can call the customer before they call you.
          </p>
        </Feature>
      </main>

      <footer className="mt-8 border-t border-line">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-x-8 gap-y-3 px-5 py-10 sm:px-8">
          <p className="font-medium">
            Built by{' '}
            <a href={AUTHOR.linkedin} target="_blank" rel="noreferrer" className="hover:text-accent">
              {AUTHOR.name}
            </a>
          </p>
          <a
            href={AUTHOR.github}
            target="_blank"
            rel="noreferrer"
            className="text-sm font-medium text-muted hover:text-ink"
          >
            Source code on GitHub
          </a>
        </div>
      </footer>
    </div>
  )
}
