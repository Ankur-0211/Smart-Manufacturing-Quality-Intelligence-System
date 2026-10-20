import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { createQueryClient } from '@/app/queryClient'
import { API, envelope, server } from '@/test/server'

import { type PredictRequest, useExplanation, usePredict } from './predict'

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createQueryClient()}>{children}</QueryClientProvider>
}

describe('prediction hooks', () => {
  it('posts a prediction request and returns the id', async () => {
    let body: unknown = null
    server.use(
      http.post(`${API}/predict`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(envelope({ prediction_id: 'p-1', stage_results: [], prediction: {} }))
      }),
    )
    const request = { machine_id: 'MC-03', include_explanation: true } as unknown as PredictRequest
    const { result } = renderHook(() => usePredict(), { wrapper })
    let id: string | undefined
    await act(async () => {
      id = (await result.current.mutateAsync(request)).prediction_id
    })
    expect(body).toEqual(request)
    expect(id).toBe('p-1')
  })

  it('loads an explanation only once an id is known', async () => {
    let calls = 0
    server.use(
      http.get(`${API}/predict/:id/explain`, ({ params }) => {
        calls += 1
        return HttpResponse.json(
          envelope({ base_value: 0, attributions: [], background_version: String(params.id) }),
        )
      }),
    )
    const { result, rerender } = renderHook(({ id }: { id: string | null }) => useExplanation(id), {
      wrapper,
      initialProps: { id: null as string | null },
    })
    expect(result.current.fetchStatus).toBe('idle')
    rerender({ id: 'p-1' })
    await waitFor(() => expect(result.current.data?.background_version).toBe('p-1'))
    expect(calls).toBe(1)
  })
})
