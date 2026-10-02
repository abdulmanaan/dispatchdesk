import { afterEach, describe, expect, it, vi } from 'vitest'

import { api, ApiError, errorMessage, setUnauthorizedHandler, tokenStore } from './api'

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
  setUnauthorizedHandler(null)
})

describe('errorMessage', () => {
  it('uses a plain detail string', () => {
    expect(errorMessage(409, { detail: 'Order has already been accepted' })).toBe(
      'Order has already been accepted',
    )
  })

  it('summarises the first validation error with its field', () => {
    const body = { detail: [{ loc: ['body', 'customer_phone'], msg: 'String should match pattern' }] }
    expect(errorMessage(422, body)).toBe('customer phone: String should match pattern')
  })

  it('strips the "Value error" prefix from model validators', () => {
    const body = { detail: [{ loc: ['body'], msg: 'Value error, deliver_by must be in the future' }] }
    expect(errorMessage(422, body)).toBe('deliver_by must be in the future')
  })

  it('falls back to friendly messages', () => {
    expect(errorMessage(429, null)).toMatch(/too many requests/i)
    expect(errorMessage(502, null)).toMatch(/server had a problem/i)
  })
})

describe('api', () => {
  it('sends the bearer token and query parameters', async () => {
    tokenStore.set('abc')
    const fetchMock = mockFetch(200, { items: [] })

    await api('/orders', { query: { status: ['pending', 'assigned'], page: 2, search: '' } })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/orders?status=pending&status=assigned&page=2')
    expect(init.headers.Authorization).toBe('Bearer abc')
  })

  it('throws ApiError with the server message', async () => {
    mockFetch(404, { detail: 'Order not found' })

    await expect(api('/orders/x')).rejects.toEqual(new ApiError(404, 'Order not found'))
  })

  it('signals an expired session on 401 when a token was sent', async () => {
    tokenStore.set('expired')
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    mockFetch(401, { detail: 'Could not validate credentials' })

    await expect(api('/auth/me')).rejects.toBeInstanceOf(ApiError)
    expect(handler).toHaveBeenCalledOnce()
  })

  it('does not treat a failed login (no token) as an expired session', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    mockFetch(401, { detail: 'Incorrect email or password' })

    await expect(api('/auth/login', { form: { username: 'a', password: 'b' } })).rejects.toThrow(
      'Incorrect email or password',
    )
    expect(handler).not.toHaveBeenCalled()
  })

  it('reports network failures in plain words', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(api('/health')).rejects.toThrow(/cannot reach the server/i)
  })
})
