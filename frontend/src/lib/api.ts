// Minimal typed client for the DispatchDesk API.

const API_URL = (import.meta.env.VITE_API_URL ?? '/api').replace(/\/$/, '')
const TOKEN_KEY = 'dispatchdesk.token'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Turn a FastAPI error body into one readable sentence. */
export function errorMessage(status: number, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    // Validation errors: [{loc: [..., "field"], msg: "..."}]
    const first = detail[0] as { loc?: unknown[]; msg?: string }
    const field = first.loc?.at(-1)
    const msg = first.msg?.replace(/^Value error, /, '') ?? 'Invalid value'
    // "body"/"query" mean the whole request (a model-level rule), not one field.
    const named = typeof field === 'string' && !['body', 'query'].includes(field)
    return named ? `${field.replaceAll('_', ' ')}: ${msg}` : msg
  }
  if (status === 429) return 'Too many requests. Wait a moment and try again.'
  if (status >= 500) return 'The server had a problem. Try again in a moment.'
  return `Request failed (${status})`
}

// Storage can be unavailable (private mode, blocked site data); never crash on it.
export const tokenStore = {
  get(): string | null {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string): void {
    try {
      localStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* session-only login */
    }
  },
  clear(): void {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* nothing stored */
    }
  },
}

let onUnauthorized: (() => void) | null = null

/** Called when an authenticated request gets 401 (expired or revoked token). */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

type Query = Record<string, string | number | boolean | string[] | null | undefined>

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'
  json?: unknown
  form?: Record<string, string>
  query?: Query
  signal?: AbortSignal
}

function buildUrl(path: string, query?: Query): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === null || value === undefined || value === '') continue
    if (Array.isArray(value)) value.forEach((v) => params.append(key, v))
    else params.append(key, String(value))
  }
  const qs = params.toString()
  return `${API_URL}${path}${qs ? `?${qs}` : ''}`
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  const token = tokenStore.get()
  if (token) headers.Authorization = `Bearer ${token}`

  let body: BodyInit | undefined
  if (options.json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.json)
  } else if (options.form) {
    body = new URLSearchParams(options.form)
  }

  let response: Response
  try {
    response = await fetch(buildUrl(path, options.query), {
      method: options.method ?? (body ? 'POST' : 'GET'),
      headers,
      body,
      signal: options.signal,
    })
  } catch (error) {
    if ((error as Error).name === 'AbortError') throw error
    throw new ApiError(0, 'Cannot reach the server. Check your connection.')
  }

  const data: unknown = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized?.()
    throw new ApiError(response.status, errorMessage(response.status, data))
  }
  return data as T
}
