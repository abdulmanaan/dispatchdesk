import { ArrowLeft } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'

import { useAuth } from '../../auth/useAuth'
import { Button } from '../../components/Button'
import { Card, ErrorNote, PageHeader } from '../../components/Card'
import { SelectField, TextAreaField } from '../../components/Controls'
import { TextField } from '../../components/TextField'
import { api } from '../../lib/api'
import { LAHORE_AREAS } from '../../lib/areas'
import { useOrderAction } from '../../lib/hooks'
import type { Order } from '../../lib/types'
import { buildOrderPayload, type NewOrderValues } from './orderPayload'

const WINDOWS = [30, 45, 60, 90, 120]

export function NewOrderPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [values, setValues] = useState<NewOrderValues>({
    customerName: '',
    customerPhone: '',
    street: '',
    area: '',
    useCoordinates: false,
    lat: '',
    lng: '',
    windowMinutes: 60,
    notes: '',
  })
  const [formError, setFormError] = useState<string | null>(null)
  const create = useOrderAction((payload: ReturnType<typeof buildOrderPayload>) =>
    api<Order>('/orders', { json: payload }),
  )

  const set = <K extends keyof NewOrderValues>(key: K, value: NewOrderValues[K]) =>
    setValues((current) => ({ ...current, [key]: value }))

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setFormError(null)
    let payload
    try {
      payload = buildOrderPayload(values)
    } catch (error) {
      setFormError((error as Error).message)
      return
    }
    create.mutate(payload, {
      onSuccess: (order) => {
        const message =
          order.status === 'assigned'
            ? `Order for ${order.customer_name} created and sent to the nearest driver.`
            : `Order for ${order.customer_name} created. It will go to the next free driver nearby.`
        navigate('/business', { state: { created: message } })
      },
    })
  }

  const error = formError ?? (create.isError ? create.error.message : null)

  return (
    <>
      <Link
        to="/business"
        className="inline-flex w-fit items-center gap-2 text-sm font-medium text-muted hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="size-4" />
        Orders
      </Link>
      <PageHeader
        title="New order"
        subtitle={user?.business ? `Pickup from ${user.business.address}` : undefined}
      />
      <Card className="max-w-2xl p-7 sm:p-8">
        <form onSubmit={handleSubmit} className="grid gap-8">
          {error && <ErrorNote message={error} />}

          <fieldset className="grid gap-5">
            <legend className="mb-4 text-lg font-semibold">Customer</legend>
            <div className="grid gap-5 sm:grid-cols-2">
              <TextField
                id="customer-name"
                label="Name"
                required
                maxLength={120}
                value={values.customerName}
                onChange={(e) => set('customerName', e.target.value)}
              />
              <TextField
                id="customer-phone"
                label="Phone"
                type="tel"
                required
                placeholder="+92 300 1234567"
                value={values.customerPhone}
                onChange={(e) => set('customerPhone', e.target.value)}
              />
            </div>
          </fieldset>

          <fieldset className="grid gap-5">
            <legend className="mb-4 text-lg font-semibold">Drop-off</legend>
            <TextField
              id="street"
              label="Street address"
              required
              maxLength={200}
              placeholder="House 12, Street 5"
              value={values.street}
              onChange={(e) => set('street', e.target.value)}
            />
            {values.useCoordinates ? (
              <div className="grid gap-5 sm:grid-cols-2">
                <TextField
                  id="lat"
                  label="Latitude"
                  inputMode="decimal"
                  placeholder="31.5204"
                  value={values.lat}
                  onChange={(e) => set('lat', e.target.value)}
                />
                <TextField
                  id="lng"
                  label="Longitude"
                  inputMode="decimal"
                  placeholder="74.3587"
                  value={values.lng}
                  onChange={(e) => set('lng', e.target.value)}
                />
              </div>
            ) : (
              <SelectField
                id="area"
                label="Area"
                required
                value={values.area}
                onChange={(e) => set('area', e.target.value)}
              >
                <option value="" disabled>
                  Choose an area in Lahore
                </option>
                {LAHORE_AREAS.map((area) => (
                  <option key={area.name} value={area.name}>
                    {area.name}
                  </option>
                ))}
              </SelectField>
            )}
            <button
              type="button"
              onClick={() => set('useCoordinates', !values.useCoordinates)}
              className="w-fit text-sm font-medium text-accent hover:text-accent-hover"
            >
              {values.useCoordinates ? 'Choose an area instead' : 'Enter exact coordinates instead'}
            </button>
          </fieldset>

          <fieldset className="grid gap-5">
            <legend className="mb-4 text-lg font-semibold">Delivery</legend>
            <SelectField
              id="window"
              label="Deliver within"
              value={values.windowMinutes}
              onChange={(e) => set('windowMinutes', Number(e.target.value))}
            >
              {WINDOWS.map((m) => (
                <option key={m} value={m}>
                  {m < 60 ? `${m} minutes` : m === 60 ? '1 hour' : `${m / 60} hours`}
                </option>
              ))}
            </SelectField>
            <TextAreaField
              id="notes"
              label="Note for the driver (optional)"
              maxLength={500}
              placeholder="For example: call on arrival"
              value={values.notes}
              onChange={(e) => set('notes', e.target.value)}
            />
          </fieldset>

          <div className="flex flex-wrap gap-3">
            <Button type="submit" size="lg" loading={create.isPending}>
              Create order
            </Button>
            <Link
              to="/business"
              className="inline-flex h-13 items-center rounded-control px-6 font-semibold text-muted hover:bg-subtle hover:text-ink"
            >
              Cancel
            </Link>
          </div>
        </form>
      </Card>
    </>
  )
}
