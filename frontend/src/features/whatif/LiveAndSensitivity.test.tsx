import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { FakeEventSource } from '@/test/fakeEventSource'
import { RUN_ID } from '@/test/fixtures/runEvents'
import { finishedBase, sensitivityResult, whatIfResult } from '@/test/fixtures/whatif'
import { API, envelope, server } from '@/test/server'

import { useWhatIfDrafts } from './whatifStore'

function renderAt(path = `/what-if?base=${RUN_ID}`) {
  useWhatIfDrafts.setState({ drafts: {} })
  return render(
    <App
      initialEntries={[path]}
      queryClient={createQueryClient()}
      eventSourceFactory={(u) => new FakeEventSource(u)}
    />,
  )
}

const baseHandler = () =>
  http.get(`${API}/simulation/runs/:id`, () => HttpResponse.json(envelope(finishedBase())))

describe('What-If live mode', () => {
  it('sends one persist=false request per pause in editing, with the latest draft', async () => {
    const user = userEvent.setup()
    const bodies: unknown[] = []
    server.use(
      baseHandler(),
      http.post(`${API}/whatif`, async ({ request }) => {
        bodies.push(await request.json())
        return HttpResponse.json(envelope(whatIfResult()))
      }),
    )
    renderAt()
    const result = await screen.findByRole('region', { name: 'What-if result' })
    await user.click(within(result).getByRole('checkbox', { name: /Live/ }))

    const params = await screen.findByRole('region', { name: 'What-if parameters' })
    const input = within(params).getByRole('spinbutton', { name: 'Cooling Time' })
    await user.clear(input)
    await user.type(input, '14') // "1" then "14", inside one 150 ms pause
    expect(await within(result).findByText('FLIPPED')).toBeInTheDocument()
    expect(bodies).toEqual([{ base_run_id: RUN_ID, overrides: { cooling_time_s: 14 }, persist: false }])
    expect(result).toHaveTextContent('Live preview; nothing was saved.')
    expect(within(result).getByRole('button', { name: 'Evaluate' })).toBeDisabled() // live replaces it

    await user.type(input, '.5') // a second pause → a second request
    await waitFor(() => expect(bodies).toHaveLength(2))
    expect(bodies[1]).toEqual({ base_run_id: RUN_ID, overrides: { cooling_time_s: 14.5 }, persist: false })
  })
})

describe('Sensitivity strip', () => {
  it('sweeps one parameter with 40 steps and states the curve numbers', async () => {
    const user = userEvent.setup()
    let body: unknown = null
    server.use(
      baseHandler(),
      http.post(`${API}/whatif/sensitivity`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(envelope(sensitivityResult('cooling_time_s')))
      }),
    )
    renderAt()
    const panel = await screen.findByRole('region', { name: 'Sensitivity' })
    await user.selectOptions(within(panel).getByLabelText('Parameter'), 'cooling_time_s')
    await user.click(within(panel).getByRole('button', { name: 'Sweep' }))
    expect(await within(panel).findByLabelText('Sweep summary')).toHaveTextContent(
      'Cooling Time: current 11 s · range swing 0.610 · local gradient -0.0310 per s · label flips at 17.5 s (3 points)',
    )
    expect(body).toEqual({ base_run_id: RUN_ID, parameter: 'cooling_time_s', steps: 40 })
    expect(panel).toHaveTextContent('Sensitivity is not SHAP.')
  })

  it('ranks every actionable parameter by range swing', async () => {
    const user = userEvent.setup()
    const asked: string[] = []
    const steps: number[] = []
    const swing: Record<string, number> = { drying_time_h: 0.05, melt_temp_c: 0.3, cooling_time_s: 0.61 }
    server.use(
      baseHandler(),
      http.post(`${API}/whatif/sensitivity`, async ({ request }) => {
        const body = (await request.json()) as { parameter: string; steps: number }
        asked.push(body.parameter)
        steps.push(body.steps)
        return HttpResponse.json(
          envelope(
            sensitivityResult(body.parameter, {
              range_swing: swing[body.parameter],
              flip_point: body.parameter === 'cooling_time_s' ? 17.5 : null,
            }),
          ),
        )
      }),
    )
    renderAt()
    const panel = await screen.findByRole('region', { name: 'Sensitivity' })
    await user.click(within(panel).getByRole('button', { name: 'Rank parameters' }))
    const table = await within(panel).findByRole('table', { name: 'Parameter ranking' })
    await waitFor(() => expect(within(table).getAllByRole('row')).toHaveLength(4))
    expect(asked).toEqual(['drying_time_h', 'melt_temp_c', 'cooling_time_s']) // Cycle Time is not actionable
    expect(steps).toEqual([12, 12, 12])
    expect(
      within(table)
        .getAllByRole('row')
        .slice(1)
        .map((r) => r.textContent),
    ).toEqual([
      '1Cooling Time0.610-0.031017.5',
      '2Melt Temperature0.300-0.0310—',
      '3Drying Time0.050-0.0310—',
    ])
    await user.click(within(table).getByRole('button', { name: 'Melt Temperature' }))
    expect(within(panel).getByLabelText('Sweep summary')).toHaveTextContent('Melt Temperature: current 11')
  })

  it('reports a rate limit with its code', async () => {
    const user = userEvent.setup()
    server.use(
      baseHandler(),
      http.post(`${API}/whatif/sensitivity`, () =>
        HttpResponse.json(
          {
            data: null,
            error: { code: 'RATE_LIMITED', message: 'Too many requests', hint: 'retry in 20 s' },
            meta: { request_id: 'r' },
          },
          { status: 429 },
        ),
      ),
    )
    renderAt()
    const panel = await screen.findByRole('region', { name: 'Sensitivity' })
    await user.click(within(panel).getByRole('button', { name: 'Sweep' }))
    expect(await within(panel).findByRole('alert', { name: 'Sensitivity error' })).toHaveTextContent(
      'RATE_LIMITED: Too many requests — retry in 20 s',
    )
  })
})
