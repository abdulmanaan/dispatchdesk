import { useQuery } from '@tanstack/react-query'
import { Phone } from 'lucide-react'
import { useState } from 'react'

import { useAuth } from '../../auth/useAuth'
import { Button } from '../../components/Button'
import { Card, EmptyState, ErrorNote, PageHeader } from '../../components/Card'
import { SelectField } from '../../components/Controls'
import { DriverStatusPill } from '../../components/DriverStatusPill'
import { Spinner } from '../../components/Spinner'
import { OverduePill, StatusPill } from '../../components/StatusPill'
import { api } from '../../lib/api'
import { findArea, LAHORE_AREAS, nearestArea } from '../../lib/areas'
import { formatTime, formatWhen } from '../../lib/format'
import { formatKm, haversineKm } from '../../lib/geo'
import { useOrderAction, useOrders } from '../../lib/hooks'
import type { DriverProfile, OrderDetail } from '../../lib/types'
import { FAIL_REASONS, nextDriverStep } from './driverSteps'

export function DriverHome() {
  const { user } = useAuth()
  const current = useQuery({
    queryKey: ['driver', 'current-order'],
    queryFn: () => api<OrderDetail | null>('/drivers/me/order'),
    refetchInterval: 5_000,
  })
  const driver = user?.driver

  return (
    <>
      <PageHeader title={`Hi, ${user?.full_name.split(' ')[0] ?? ''}`} />
      <div className="grid max-w-xl gap-6">
        {driver && <AvailabilityCard driver={driver} />}
        {current.isPending && <Spinner className="size-6 text-muted" />}
        {current.isError && <ErrorNote message={current.error.message} />}
        {current.isSuccess &&
          (current.data ? (
            <CurrentOrder order={current.data} />
          ) : (
            <Card>
              <EmptyState title="No active order">
                {driver?.status === 'available'
                  ? 'You are online. New orders appear here as soon as they are assigned to you.'
                  : 'Go online to start receiving orders.'}
              </EmptyState>
            </Card>
          ))}
        <RecentDeliveries />
      </div>
    </>
  )
}

function AvailabilityCard({ driver }: { driver: DriverProfile }) {
  const [choosing, setChoosing] = useState(false)
  const [area, setArea] = useState('')
  const [geoError, setGeoError] = useState<string | null>(null)
  const setStatus = useOrderAction((body: { status: 'available' | 'offline'; lat?: number; lng?: number }) =>
    api('/drivers/me/status', { method: 'PUT', json: body }),
  )
  const setLocation = useOrderAction((body: { lat: number; lng: number }) =>
    api('/drivers/me/location', { method: 'PUT', json: body }),
  )

  const place =
    driver.current_lat !== null && driver.current_lng !== null
      ? nearestArea(driver.current_lat, driver.current_lng).name
      : null
  const busy = driver.status === 'busy'

  function shareDeviceLocation() {
    setGeoError(null)
    if (!('geolocation' in navigator)) {
      setGeoError('This device cannot share its location. Choose an area instead.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation.mutate({ lat: pos.coords.latitude, lng: pos.coords.longitude })
        setChoosing(false)
      },
      () => setGeoError('Location permission was denied. Choose an area instead.'),
      { timeout: 8000 },
    )
  }

  function saveArea() {
    const chosen = findArea(area)
    if (!chosen) return
    setLocation.mutate({ lat: chosen.lat, lng: chosen.lng })
    setChoosing(false)
  }

  const error = setStatus.error?.message ?? setLocation.error?.message ?? geoError

  return (
    <Card className="grid gap-5 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="grid gap-1">
          <span className="text-lg font-semibold">
            {driver.status === 'offline'
              ? 'You are offline'
              : busy
                ? 'You are on a delivery'
                : 'You are online'}
          </span>
          <span className="text-sm text-muted">{place ? `Near ${place}` : 'Location not shared yet'}</span>
        </div>
        <DriverStatusPill status={driver.status} />
      </div>

      {error && <ErrorNote message={error} />}

      {choosing ? (
        <div className="grid gap-4 rounded-control bg-subtle p-4">
          <SelectField
            id="driver-area"
            label="Where are you?"
            value={area}
            onChange={(e) => setArea(e.target.value)}
          >
            <option value="" disabled>
              Choose an area in Lahore
            </option>
            {LAHORE_AREAS.map((a) => (
              <option key={a.name} value={a.name}>
                {a.name}
              </option>
            ))}
          </SelectField>
          <div className="flex flex-wrap gap-3">
            <Button onClick={saveArea} disabled={!area} loading={setLocation.isPending}>
              Save location
            </Button>
            <Button variant="secondary" onClick={shareDeviceLocation}>
              Use device location
            </Button>
            <Button variant="ghost" onClick={() => setChoosing(false)}>
              Close
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex flex-wrap gap-3">
          {driver.status === 'offline' ? (
            <Button loading={setStatus.isPending} onClick={() => setStatus.mutate({ status: 'available' })}>
              Go online
            </Button>
          ) : (
            <Button
              variant="secondary"
              disabled={busy}
              loading={setStatus.isPending}
              onClick={() => setStatus.mutate({ status: 'offline' })}
            >
              Go offline
            </Button>
          )}
          <Button variant="ghost" onClick={() => setChoosing(true)}>
            Update location
          </Button>
        </div>
      )}
      {busy && <p className="text-sm text-muted">Finish your current order before going offline.</p>}
    </Card>
  )
}

function CurrentOrder({ order }: { order: OrderDetail }) {
  const step = nextDriverStep(order)
  const [failing, setFailing] = useState(false)
  const [reason, setReason] = useState(FAIL_REASONS[0])
  const advance = useOrderAction((action: string) => api(`/orders/${order.id}/${action}`, { method: 'POST' }))
  const fail = useOrderAction((why: string) => api(`/orders/${order.id}/fail`, { json: { reason: why } }))
  const trip = haversineKm(order.pickup_lat, order.pickup_lng, order.dropoff_lat, order.dropoff_lng)

  return (
    <Card className="grid gap-6 p-6">
      <div className="flex items-start justify-between gap-4">
        <div className="grid gap-1">
          <span className="text-sm text-muted">
            {step?.action === 'accept' ? 'New order for you' : 'Current order'}
          </span>
          <span className="text-[22px] leading-tight font-semibold">{order.customer_name}</span>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          {order.is_overdue && <OverduePill />}
          <StatusPill order={order} />
        </div>
      </div>

      <ol className="grid gap-5">
        <Stop
          kind="pickup"
          title={order.business.name}
          detail={order.pickup_address}
          phone={order.business.phone}
          done={order.status === 'picked_up'}
        />
        <Stop
          kind="drop"
          title={order.dropoff_address}
          detail={order.customer_name}
          phone={order.customer_phone}
        />
      </ol>

      <div className="flex gap-10">
        <div className="grid">
          <span className="text-xl font-semibold tabular-nums">{formatKm(trip)}</span>
          <span className="text-[13px] text-muted">Trip</span>
        </div>
        <div className="grid">
          <span className="text-xl font-semibold tabular-nums">{formatTime(order.deliver_by)}</span>
          <span className="text-[13px] text-muted">Deliver by</span>
        </div>
      </div>

      {order.notes && <p className="rounded-control bg-subtle px-4 py-3 text-[15px]">{order.notes}</p>}
      {(advance.error || fail.error) && <ErrorNote message={(advance.error ?? fail.error)!.message} />}

      {step && !failing && (
        <div className="grid gap-3">
          <Button
            size="lg"
            className="w-full"
            loading={advance.isPending}
            onClick={() => advance.mutate(step.action)}
          >
            {step.label}
          </Button>
          <p className="text-center text-sm text-muted">{step.hint}</p>
          {step.action !== 'accept' && (
            <button
              type="button"
              onClick={() => setFailing(true)}
              className="justify-self-center text-sm font-medium text-muted hover:text-danger"
            >
              I can't deliver this order
            </button>
          )}
        </div>
      )}

      {failing && (
        <div className="grid gap-4 rounded-control bg-subtle p-4">
          <SelectField
            id="fail-reason"
            label="What went wrong?"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          >
            {FAIL_REASONS.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </SelectField>
          <div className="flex flex-wrap gap-3">
            <Button variant="danger" loading={fail.isPending} onClick={() => fail.mutate(reason)}>
              Report problem
            </Button>
            <Button variant="ghost" onClick={() => setFailing(false)}>
              Back
            </Button>
          </div>
        </div>
      )}
    </Card>
  )
}

function Stop({
  kind,
  title,
  detail,
  phone,
  done = false,
}: {
  kind: 'pickup' | 'drop'
  title: string
  detail: string
  phone: string
  done?: boolean
}) {
  return (
    <li className="grid grid-cols-[14px_1fr_auto] items-start gap-3">
      <span
        aria-hidden="true"
        className={`mt-1.5 size-3 rounded-full border-2 border-accent ${kind === 'drop' || done ? 'bg-accent' : ''}`}
      />
      <div className="grid gap-0.5">
        <span className="text-sm text-muted">
          {kind === 'pickup' ? (done ? 'Picked up from' : 'Pick up from') : 'Deliver to'}
        </span>
        <span className="font-semibold">{title}</span>
        <span className="text-sm text-muted">{detail}</span>
      </div>
      <a
        href={`tel:${phone}`}
        className="inline-flex size-10 items-center justify-center rounded-full bg-accent-soft text-accent hover:bg-accent hover:text-white"
        aria-label={`Call ${kind === 'pickup' ? title : detail}`}
      >
        <Phone aria-hidden="true" className="size-4" />
      </a>
    </li>
  )
}

function RecentDeliveries() {
  const recent = useOrders({ status: ['delivered', 'failed'], sort: '-created_at', page_size: 5 }, 30_000)
  if (!recent.data || recent.data.items.length === 0) return null
  return (
    <section className="grid gap-3">
      <h2 className="text-lg font-semibold">Recent</h2>
      <Card className="overflow-hidden">
        <ul className="divide-y divide-line">
          {recent.data.items.map((o) => (
            <li key={o.id} className="flex items-center justify-between gap-4 px-6 py-4">
              <div className="grid min-w-0 gap-0.5">
                <span className="truncate font-medium">{o.dropoff_address}</span>
                <span className="text-[13px] text-muted tabular-nums">
                  {formatWhen(o.delivered_at ?? o.failed_at ?? o.updated_at)}
                </span>
              </div>
              <StatusPill order={o} />
            </li>
          ))}
        </ul>
      </Card>
    </section>
  )
}
