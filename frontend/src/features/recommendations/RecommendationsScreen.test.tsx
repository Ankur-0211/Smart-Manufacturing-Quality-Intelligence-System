import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { delay, http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { useWhatIfDrafts } from '@/features/whatif/whatifStore'
import { DISCLAIMER_RECOMMENDATION } from '@/lib/disclaimers'
import { FakeEventSource } from '@/test/fakeEventSource'
import { RUN_ID } from '@/test/fixtures/runEvents'
import { constraintsPayload, paramSpec } from '@/test/fixtures/reference'
import { finishedBase, recommendOut } from '@/test/fixtures/whatif'
import { API, envelope, server } from '@/test/server'

function renderAt(path = `/recommendations?run=${RUN_ID}`) {
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

async function findOptions(user: ReturnType<typeof userEvent.setup>) {
  const request = screen.getByRole('region', { name: 'Recommendation request' })
  await waitFor(() => expect(within(request).getByRole('button', { name: 'Find options' })).toBeEnabled())
  await user.click(within(request).getByRole('button', { name: 'Find options' }))
  return screen.findByRole('region', { name: 'Recommendation options' })
}

describe('Recommendations screen', () => {
  it('always shows the disclaimer', async () => {
    renderAt('/recommendations')
    expect(await screen.findByRole('note', { name: 'Recommendation disclaimer' })).toHaveTextContent(
      DISCLAIMER_RECOMMENDATION,
    )
  })

  it('sends locked parameters and max changes, and renders guarded option cards', async () => {
    const user = userEvent.setup()
    let body: unknown = null
    server.use(
      baseHandler(),
      http.post(`${API}/recommend`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(envelope(recommendOut()))
      }),
    )
    renderAt()
    const request = screen.getByRole('region', { name: 'Recommendation request' })
    await user.click(await within(request).findByRole('checkbox', { name: 'Melt Temperature' }))
    await user.selectOptions(within(request).getByLabelText('Max changes per option'), '2')
    const options = await findOptions(user)
    expect(body).toEqual({
      run_id: RUN_ID,
      locked: ['melt_temp_c'],
      max_changes: 2,
      n_options: 3,
      objective: 'min_p_fail',
      enable_refinement: false,
    })
    expect(within(request).queryByRole('checkbox', { name: 'Cycle Time' })).toBeNull() // non-actionable

    const minimal = within(options).getByRole('article', { name: 'Option 1: Minimal change' })
    expect(within(minimal).getByRole('region', { name: 'Predicted failure probability' })).toHaveTextContent(
      'Predicted P(fail) 0.62 → 0.31 (Δ -0.310) · PASS',
    )
    expect(within(minimal).getByRole('table', { name: 'Changes' })).toHaveTextContent('Cooling Time1114 s')
    expect(within(minimal).getByRole('region', { name: 'Guard checks' })).toHaveTextContent('✓ box')
    expect(within(minimal).getByRole('region', { name: 'Stability and cost' })).toHaveTextContent(
      'Stability: 1/20 label flips (stable)',
    )
    expect(minimal).toHaveTextContent('Constraints satisfied')
    expect(minimal).toHaveTextContent('In distribution')
    expect(minimal).toHaveTextContent('Cycle time: +3.0 s (+15.0 %)')

    const aggressive = within(options).getByRole('article', { name: 'Option 2: Aggressive' })
    expect(aggressive).toHaveTextContent('Extrapolated')
    expect(aggressive).toHaveTextContent('Hypothesis for trial')
    expect(options).toHaveTextContent(
      '42 candidates evaluated · model fusion-1.0.0 · constraints-1.0.0 · rejected: couplings 3',
    )
  })

  it('shows the empty reason', async () => {
    const user = userEvent.setup()
    server.use(
      baseHandler(),
      http.post(`${API}/recommend`, () =>
        HttpResponse.json(
          envelope(recommendOut({ candidates: [], empty_reason: 'already at the best known point' })),
        ),
      ),
    )
    renderAt()
    const options = await findOptions(user)
    expect(options).toHaveTextContent('No option found: already at the best known point')
  })

  it('shows progress after a second', async () => {
    const user = userEvent.setup()
    server.use(
      baseHandler(),
      http.post(`${API}/recommend`, async () => {
        await delay(1500)
        return HttpResponse.json(envelope(recommendOut()))
      }),
    )
    renderAt()
    const request = screen.getByRole('region', { name: 'Recommendation request' })
    await waitFor(() => expect(within(request).getByRole('button', { name: 'Find options' })).toBeEnabled())
    await user.click(within(request).getByRole('button', { name: 'Find options' }))
    expect(screen.queryByRole('status')).toBeNull()
    expect(await screen.findByRole('status', {}, { timeout: 1400 })).toHaveTextContent('Searching')
    expect(
      await screen.findByRole('region', { name: 'Recommendation options' }, { timeout: 2000 }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('status')).toBeNull()
  })

  it('Send to What-If pre-fills the workbench with the option', async () => {
    const user = userEvent.setup()
    server.use(
      baseHandler(),
      http.post(`${API}/recommend`, () => HttpResponse.json(envelope(recommendOut()))),
    )
    renderAt()
    const options = await findOptions(user)
    const aggressive = within(options).getByRole('article', { name: 'Option 2: Aggressive' })
    await user.click(within(aggressive).getByRole('button', { name: 'Send to What-If' }))
    const params = await screen.findByRole('region', { name: 'What-if parameters' })
    expect(within(params).getByRole('spinbutton', { name: 'Cooling Time' })).toHaveValue(16)
    expect(within(params).getByRole('spinbutton', { name: 'Melt Temperature' })).toHaveValue(220)
    expect(params).toHaveTextContent('2 parameters changed.')
  })

  it('reports a server error with its code', async () => {
    const user = userEvent.setup()
    server.use(
      baseHandler(),
      http.post(`${API}/recommend`, () =>
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
    const request = screen.getByRole('region', { name: 'Recommendation request' })
    await waitFor(() => expect(within(request).getByRole('button', { name: 'Find options' })).toBeEnabled())
    await user.click(within(request).getByRole('button', { name: 'Find options' }))
    await waitFor(() =>
      expect(screen.getAllByRole('alert').map((a) => a.textContent)).toContain(
        'RATE_LIMITED: Too many requests — retry in 20 s',
      ),
    )
  })

  it('flags a step larger than the registry limit even if the guard reports a pass', async () => {
    const user = userEvent.setup()
    server.use(
      baseHandler(),
      http.get(`${API}/constraints`, () =>
        HttpResponse.json(
          envelope(
            constraintsPayload([
              paramSpec({
                name: 'cooling_time_s',
                stage: 'COOLING',
                unit: 's',
                display_name: 'Cooling Time',
                min: 3,
                max: 30,
                nominal: 11,
                step: 0.5,
                max_step_change: 2,
              }),
            ]),
          ),
        ),
      ),
      http.post(`${API}/recommend`, () => HttpResponse.json(envelope(recommendOut()))),
    )
    renderAt()
    const options = await findOptions(user)
    const minimal = within(options).getByRole('article', { name: 'Option 1: Minimal change' })
    expect(within(minimal).getByRole('alert', { name: 'Step limit warning' })).toHaveTextContent(
      'Cooling Time Δ 3 > 2 s',
    )
    expect(within(minimal).getByRole('region', { name: 'Guard checks' })).toHaveTextContent('✓ box') // shown as reported
  })
})
