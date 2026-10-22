/**
 * Single API client (roadmap 9.6 error-handling conventions).
 * Unwraps the `{data, error, meta}` envelope and raises `ApiClientError` with the stable code.
 * The frontend never hand-writes API types: they come from `./generated/schema.d.ts`.
 */
import type { components } from './generated/schema'
import { messageForCode, type ClientErrorCode, type ErrorCode } from './errors'

export type Schemas = components['schemas']
export type Meta = Schemas['Meta']
export type ErrorBody = Schemas['ErrorBody']

/** A production build is served by the API itself (same origin, R2-P9); dev talks to port 8000. */
export const API_BASE_URL: string =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  (import.meta.env.PROD ? '/api/v1' : 'http://localhost:8000/api/v1')

export class ApiClientError extends Error {
  readonly code: ErrorCode | ClientErrorCode | string
  readonly status: number
  readonly requestId: string | null
  readonly field: string | null
  readonly details: ErrorBody['details']
  readonly hint: string | null

  constructor(args: {
    code: string
    message: string
    status: number
    requestId: string | null
    field?: string | null
    details?: ErrorBody['details']
    hint?: string | null
  }) {
    super(args.message)
    this.name = 'ApiClientError'
    this.code = args.code
    this.status = args.status
    this.requestId = args.requestId
    this.field = args.field ?? null
    this.details = args.details ?? null
    this.hint = args.hint ?? null
  }

  /** Human-readable message for UI display. */
  get userMessage(): string {
    return this.message || messageForCode(this.code)
  }
}

export interface ApiResult<T> {
  data: T
  meta: Meta
}

interface EnvelopeShape<T> {
  data?: T | null
  error?: ErrorBody | null
  meta: Meta
}

function newRequestId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `req-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  baseUrl: string = API_BASE_URL,
): Promise<ApiResult<T>> {
  const requestId = newRequestId()
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  headers.set('X-Request-ID', requestId)
  if (init.body !== undefined && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, { ...init, headers })
  } catch (cause) {
    if (init.signal?.aborted) throw cause // superseded by a newer request, not a network failure
    throw new ApiClientError({
      code: 'NETWORK_ERROR',
      message: 'Cannot reach the API server.',
      status: 0,
      requestId,
      hint: cause instanceof Error ? cause.message : null,
    })
  }

  let body: EnvelopeShape<T>
  try {
    body = (await response.json()) as EnvelopeShape<T>
  } catch {
    throw new ApiClientError({
      code: 'INVALID_RESPONSE',
      message: `Unexpected non-JSON response (HTTP ${response.status}).`,
      status: response.status,
      requestId: response.headers.get('X-Request-ID') ?? requestId,
    })
  }

  const echoedId = body.meta?.request_id ?? response.headers.get('X-Request-ID') ?? requestId
  if (!response.ok || body.error) {
    const error = body.error
    throw new ApiClientError({
      code: error?.code ?? 'INTERNAL_ERROR',
      message: error?.message ?? messageForCode(error?.code ?? 'INTERNAL_ERROR'),
      status: response.status,
      requestId: echoedId,
      field: error?.field ?? null,
      details: error?.details ?? null,
      hint: error?.hint ?? null,
    })
  }
  if (body.data === undefined || body.data === null) {
    throw new ApiClientError({
      code: 'INVALID_RESPONSE',
      message: 'Response envelope has no data.',
      status: response.status,
      requestId: echoedId,
    })
  }
  return { data: body.data, meta: body.meta }
}

export const apiGet = <T>(path: string): Promise<ApiResult<T>> => apiRequest<T>(path)

/** `signal` lets a caller abort a superseded request (what-if live mode, roadmap R2-P7 §9). */
export const apiPost = <T>(path: string, payload: unknown, signal?: AbortSignal): Promise<ApiResult<T>> =>
  apiRequest<T>(path, { method: 'POST', body: JSON.stringify(payload), signal })
