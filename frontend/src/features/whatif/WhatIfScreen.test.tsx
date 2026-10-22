import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { FakeEventSource } from '@/test/fakeEventSource'
import { RUN_ID } from '@/test/fixtures/runEvents'
import { finishedBase, whatIfResult } from '@/test/fixtures/whatif'
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

function baseHandler() {
  return http.get(`${API}/simulation/runs/:id`, () => HttpResponse.json(envelope(finishedBase())))
}

async function parameters() {
  return screen.findByRole('region', { name: 'What-if parameters' })
}

async function setValue(user: ReturnType<typeof userEvent.setup>, label: string, value: string) {
  const input = within(await parameters()).getByRole('spinbutton', { name: label })
  await user.clear(input)
  await user.type(input, value)
  return input
}

describe('What-If workbench', () => {
  it('evaluates only the changed parameters and renders the server diff exactly', async () => {
    const user = userEvent.setup()
    let body: unknown = null
    server.use(
      baseHandler(),
      http.post(`${API}/whatif`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(envelope(whatIfResult()))
      }),
    )
    renderAt()
    const result = await screen.findByRole('region', { name: 'What-if result' })
    expect(within(result).getByRole('button', { name: 'Evaluate' })).toBeDisabled() // nothing changed
    await setValue(user, 'Cooling Time', '14')
    expect(await parameters()).toHaveTextContent('changed from 11 s')
    await user.click(within(result).getByRole('button', { name: 'Evaluate' }))
    await waitFor(() =>
      expect(body).toEqual({
        base_run_id: RUN_ID,
        overrides: { cooling_time_s: 14 },
        persist: false,
        label: null,
      }),
    )

    const diff = await screen.findByLabelText('What-if diff')
    const p = within(diff).getByRole('region', { name: 'Model-predicted failure probability' })
    expect(p).toHaveTextContent('0.62 → 0.31 (Δ -0.310)')
    expect(p).toHaveTextContent('Label FAIL → PASS')
    expect(p).toHaveTextContent('FLIPPED')
    expect(within(diff).getByRole('region', { name: 'Operational risk' })).toHaveTextContent(
      'HIGH → MEDIUM (-1 band)',
    )
    const changed = within(within(diff).getByRole('region', { name: 'Parameters changed' })).getAllByRole(
      'row',
    )
    expect(changed.map((r) => r.textContent)).toEqual([
      'ParameterBaseWhat-ifΔ',
      'Cooling Time1114+3.00 s',
      'Cycle Time2023+3.00 s',
    ])
    const stages = within(diff).getByRole('region', { name: 'Stages' })
    expect(stages).toHaveTextContent(
      'Recomputed: Cooling. Reused from the base run: Material, Thermal, Injection, Packing.',
    )
    expect(within(stages).getByRole('row', { name: 'COOLING improved' })).toHaveTextContent(
      '0.41 → 0.88HIGH → LOW',
    )
    expect(within(stages).getByRole('row', { name: 'PACKING unchanged' })).toBeInTheDocument()
    expect(within(diff).getByRole('region', { name: 'Constraint compliance' })).toHaveTextContent(
      'Warnings 1 → 0Critical 0 → 0',
    )
    expect(within(diff).getByRole('region', { name: 'Cycle time' })).toHaveTextContent(
      '20 s → 23 s (Δ +3.0 s, +15.0 %)',
    )
    expect(result).toHaveTextContent('Evaluated only; nothing was saved.')
  })

  it('Reset restores the parent exactly', async () => {
    const user = userEvent.setup()
    server.use(baseHandler())
    renderAt()
    await setValue(user, 'Melt Temperature', '240')
    await setValue(user, 'Cooling Time', '14')
    expect(await parameters()).toHaveTextContent('2 parameters changed.')
    await user.click(within(await parameters()).getByRole('button', { name: 'Reset to base' }))
    const p = await parameters()
    expect(within(p).getByRole('spinbutton', { name: 'Melt Temperature' })).toHaveValue(230)
    expect(within(p).getByRole('spinbutton', { name: 'Cooling Time' })).toHaveValue(11)
    expect(p).toHaveTextContent('No changes yet.')
    expect(screen.getByRole('button', { name: 'Evaluate' })).toBeDisabled()
  })

  it('setting a value back to the parent drops the override', async () => {
    const user = userEvent.setup()
    server.use(baseHandler())
    renderAt()
    await setValue(user, 'Melt Temperature', '240')
    await setValue(user, 'Melt Temperature', '230')
    expect(await parameters()).toHaveTextContent('No changes yet.')
  })

  it('saves a scenario and links the child run', async () => {
    const user = userEvent.setup()
    let body: Record<string, unknown> | null = null
    server.use(
      baseHandler(),
      http.post(`${API}/whatif`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(envelope(whatIfResult({ run_id: 'child-0001-0000' })))
      }),
    )
    renderAt()
    await setValue(user, 'Cooling Time', '14')
    const result = screen.getByRole('region', { name: 'What-if result' })
    await user.type(within(result).getByLabelText('Scenario label (optional)'), 'longer cooling')
    await user.click(within(result).getByRole('button', { name: 'Save as scenario' }))
    expect(await within(result).findByRole('link', { name: 'child-00' })).toHaveAttribute(
      'href',
      '/history/child-0001-0000',
    )
    expect(body).toMatchObject({ persist: true, label: 'longer cooling' })
  })

  it('maps 422 details onto the edited parameter', async () => {
    const user = userEvent.setup()
    server.use(
      baseHandler(),
      http.post(`${API}/whatif`, () =>
        HttpResponse.json(
          {
            data: null,
            error: {
              code: 'COUPLING_VIOLATION',
              message: 'CPL-002',
              field: 'overrides.melt_temp_c',
              details: [
                {
                  field: 'overrides.melt_temp_c',
                  code: 'COUPLING_VIOLATION',
                  message: 'CPL-002: melt must exceed mold by 120 °C',
                  limit: 120,
                  value: 100,
                },
              ],
            },
            meta: { request_id: 'r' },
          },
          { status: 422 },
        ),
      ),
    )
    renderAt()
    const melt = await setValue(user, 'Melt Temperature', '190')
    await user.click(screen.getByRole('button', { name: 'Evaluate' }))
    await waitFor(() => expect(melt).toHaveAttribute('aria-invalid', 'true'))
    expect(screen.getByRole('alert', { name: 'What-if errors' })).toHaveTextContent('CPL-002')
  })

  it('asks for a finished base run', async () => {
    renderAt('/what-if')
    expect(await screen.findByText('Choose a finished run to branch from.')).toBeInTheDocument()
  })
})
