/**
 * MSW server for TESTS ONLY (roadmap R2-P6/P7): never imported by production code.
 * Payloads mirror backend envelopes; later phases load them from backend/tests/contract/fixtures.
 */
import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'

import type { Schemas } from '@/api/client'

export const API = 'http://localhost:8000/api/v1'

export function envelope<T>(data: T) {
  return {
    data,
    error: null,
    meta: { request_id: 'test-req', latency_ms: 1, api_version: '1', contracts_version: null, total: null },
  }
}

export function healthPayload(overrides: Partial<Schemas['HealthData']> = {}): Schemas['HealthData'] {
  return {
    status: 'degraded',
    env: 'test',
    intelligence_backend: 'mock',
    db: false,
    model_loaded: false,
    intelligence: null,
    components: [{ name: 'api', available: true, detail: 'running' }],
    ...overrides,
  }
}

export const defaultHandlers = [http.get(`${API}/health`, () => HttpResponse.json(envelope(healthPayload())))]

export const server = setupServer(...defaultHandlers)
