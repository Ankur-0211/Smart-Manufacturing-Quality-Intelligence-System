import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { FakeEventSource } from '@/test/fakeEventSource'
import { whatIfDiff } from '@/test/fixtures/whatif'
import { API, envelope, server } from '@/test/server'

function renderAt(path: string) {
  return render(
    <App
      initialEntries={[path]}
      queryClient={createQueryClient()}
      eventSourceFactory={(u) => new FakeEventSource(u)}
    />,
  )
}

function compareHandler(bodies: unknown[]) {
  return http.post(`${API}/whatif/compare`, async ({ request }) => {
    bodies.push(await request.json())
    return HttpResponse.json(envelope(whatIfDiff()))
  })
}

describe('A/B compare', () => {
  it('diffs two saved runs with A/B columns and no stage-reuse line', async () => {
    const bodies: unknown[] = []
    server.use(compareHandler(bodies))
    renderAt('/what-if/compare?a=run-a&b=run-b')
    const comparison = await screen.findByRole('region', { name: 'Comparison' })
    expect(bodies).toEqual([{ run_id_a: 'run-a', run_id_b: 'run-b' }])
    const params = within(comparison).getByRole('region', { name: 'Parameters changed' })
    expect(
      within(params)
        .getAllByRole('columnheader')
        .map((h) => h.textContent),
    ).toEqual(['Parameter', 'A', 'B', 'Δ'])
    expect(comparison).toHaveTextContent('0.62 → 0.31 (Δ -0.310)')
    expect(comparison).not.toHaveTextContent('Recomputed:')
  })

  it('swaps A and B', async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    server.use(compareHandler(bodies))
    renderAt('/what-if/compare?a=run-a&b=run-b')
    await screen.findByRole('region', { name: 'Comparison' })
    await user.click(screen.getByRole('button', { name: 'Swap A ⇄ B' }))
    await waitFor(() => expect(bodies.at(-1)).toEqual({ run_id_a: 'run-b', run_id_b: 'run-a' }))
  })

  it('asks for two runs before calling the server', async () => {
    const bodies: unknown[] = []
    server.use(compareHandler(bodies))
    renderAt('/what-if/compare?a=run-a')
    expect(await screen.findByText('Choose two finished runs to compare.')).toBeInTheDocument()
    expect(bodies).toEqual([])
  })
})
