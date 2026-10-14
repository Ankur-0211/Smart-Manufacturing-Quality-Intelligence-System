import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { API, envelope, server } from '@/test/server'

import { ApiClientError, apiGet, apiPost } from './client'

describe('apiRequest', () => {
  it('unwraps data and meta and sends a request id', async () => {
    let sentId: string | null = null
    server.use(
      http.get(`${API}/thing`, ({ request }) => {
        sentId = request.headers.get('X-Request-ID')
        return HttpResponse.json(envelope({ value: 42 }))
      }),
    )
    const result = await apiGet<{ value: number }>('/thing')
    expect(result.data).toEqual({ value: 42 })
    expect(result.meta.request_id).toBe('test-req')
    expect(sentId).toBeTruthy()
  })

  it('raises ApiClientError with the envelope error code', async () => {
    server.use(
      http.post(`${API}/thing`, () =>
        HttpResponse.json(
          {
            data: null,
            error: {
              code: 'PARAM_OUT_OF_RANGE',
              message: 'melt_temp_c 312 exceeds admissible maximum 295',
              field: 'melt_temp_c',
              details: [
                {
                  field: 'melt_temp_c',
                  code: 'PARAM_OUT_OF_RANGE',
                  message: 'too high',
                  limit: 295,
                  value: 312,
                },
              ],
              constraint_version: null,
              hint: 'Reduce melt temperature',
            },
            meta: {
              request_id: 'req-422',
              latency_ms: 1,
              api_version: '1',
              contracts_version: null,
              total: null,
            },
          },
          { status: 422 },
        ),
      ),
    )
    const err = await apiPost('/thing', { melt_temp_c: 312 }).catch((e: unknown) => e)
    expect(err).toBeInstanceOf(ApiClientError)
    const apiErr = err as ApiClientError
    expect(apiErr.code).toBe('PARAM_OUT_OF_RANGE')
    expect(apiErr.status).toBe(422)
    expect(apiErr.requestId).toBe('req-422')
    expect(apiErr.field).toBe('melt_temp_c')
    expect(apiErr.details?.[0]?.limit).toBe(295)
    expect(apiErr.hint).toBe('Reduce melt temperature')
  })

  it('maps network failures to NETWORK_ERROR', async () => {
    server.use(http.get(`${API}/down`, () => HttpResponse.error()))
    const err = (await apiGet('/down').catch((e: unknown) => e)) as ApiClientError
    expect(err.code).toBe('NETWORK_ERROR')
    expect(err.status).toBe(0)
  })

  it('maps non-JSON responses to INVALID_RESPONSE', async () => {
    server.use(http.get(`${API}/html`, () => new HttpResponse('<html>', { status: 502 })))
    const err = (await apiGet('/html').catch((e: unknown) => e)) as ApiClientError
    expect(err.code).toBe('INVALID_RESPONSE')
    expect(err.status).toBe(502)
  })
})
