import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { FakeEventSource } from '@/test/fakeEventSource'
import { constraintsPayload, paramSpec } from '@/test/fixtures/reference'
import { RUN_ID } from '@/test/fixtures/runEvents'
import { runState } from '@/test/fixtures/runState'
import { API, envelope, server } from '@/test/server'

const create = (url: string) => new FakeEventSource(url)

function renderAt(path = '/') {
  return render(<App initialEntries={[path]} queryClient={createQueryClient()} eventSourceFactory={create} />)
}

afterEach(() => {
  FakeEventSource.instances = []
})

async function panel() {
  return screen.findByRole('region', { name: 'Parameter panel' })
}

async function chooseContext(user: ReturnType<typeof userEvent.setup>) {
  const context = await screen.findByRole('group', { name: 'Run context selection' })
  await waitFor(() => expect(within(context).getAllByRole('option').length).toBeGreaterThan(5))
  await user.selectOptions(within(context).getByLabelText('Machine'), 'MC-02')
  await user.selectOptions(within(context).getByLabelText('Product'), 'PP-JBOX-42')
  await user.selectOptions(within(context).getByLabelText('Material lot'), 'A-771')
}

describe('Run setup panel', () => {
  it('builds every control from /constraints, grouped by stage', async () => {
    renderAt()
    const p = await panel()
    const melt = await within(p).findByRole('spinbutton', { name: 'Melt Temperature' })
    expect(melt).toHaveAttribute('min', '180')
    expect(melt).toHaveAttribute('max', '295')
    expect(melt).toHaveAttribute('step', '1')
    expect(melt).toHaveValue(230) // registry nominal
    expect(within(p).getByRole('slider', { name: 'Melt Temperature slider' })).toHaveAttribute('max', '295')
    expect(within(p).getByRole('group', { name: 'Cooling / Ejection' })).toHaveTextContent('Cycle Time')
    expect(p).toHaveTextContent('(not a recommendation knob)')
  })

  it('changes bounds when the registry changes', async () => {
    server.use(
      http.get(`${API}/constraints`, () =>
        HttpResponse.json(
          envelope(
            constraintsPayload([
              paramSpec({
                name: 'melt_temp_c',
                display_name: 'Melt Temperature',
                min: 190,
                max: 260,
                nominal: 225,
              }),
            ]),
          ),
        ),
      ),
    )
    renderAt()
    const melt = await within(await panel()).findByRole('spinbutton', { name: 'Melt Temperature' })
    expect(melt).toHaveAttribute('min', '190')
    expect(melt).toHaveAttribute('max', '260')
    expect(melt).toHaveValue(225)
  })

  it('flags out-of-range values and blocks RUN until fixed; nominal restores', async () => {
    const user = userEvent.setup()
    renderAt()
    await chooseContext(user)
    const p = await panel()
    const melt = within(p).getByRole('spinbutton', { name: 'Melt Temperature' })
    await user.clear(melt)
    await user.type(melt, '400')
    expect(melt).toHaveAttribute('aria-invalid', 'true')
    expect(p).toHaveTextContent('Allowed 180–295 °C')
    const controls = screen.getByRole('group', { name: 'Run controls' })
    expect(within(controls).getByRole('button', { name: 'Run' })).toBeDisabled()
    expect(controls).toHaveTextContent('Fix the highlighted parameters to run.')
    await user.click(within(p).getByRole('button', { name: 'Load nominal recipe' }))
    expect(within(p).getByRole('spinbutton', { name: 'Melt Temperature' })).toHaveValue(230)
    expect(within(controls).getByRole('button', { name: 'Run' })).toBeEnabled()
  })

  it('RUN creates the run from the setup, starts it and follows it live', async () => {
    const user = userEvent.setup()
    let created: Record<string, unknown> | null = null
    let started: unknown = null
    server.use(
      http.post(`${API}/simulation/runs`, async ({ request }) => {
        created = (await request.json()) as Record<string, unknown>
        return HttpResponse.json(envelope(runState()), { status: 201 })
      }),
      http.post(`${API}/simulation/runs/:id/start`, async ({ request }) => {
        started = await request.json()
        return HttpResponse.json(envelope(runState({ status: 'MATERIAL_CONDITIONING' })))
      }),
      http.get(`${API}/simulation/runs/:id`, () => HttpResponse.json(envelope(runState()))),
    )
    renderAt()
    await chooseContext(user)
    const controls = screen.getByRole('group', { name: 'Run controls' })
    await user.selectOptions(within(controls).getByLabelText('Mode'), 'stepwise')
    await user.click(within(controls).getByRole('button', { name: 'Run' }))
    await waitFor(() => expect(started).toEqual({ mode: 'stepwise', speed_factor: '1x' }))
    expect(created).toMatchObject({
      machine_id: 'MC-02',
      product_id: 'PP-JBOX-42',
      material_lot_id: 'A-771',
      mode: 'stepwise',
      parameters: { drying_time_h: 1.5, melt_temp_c: 230, cooling_time_s: 11, cycle_time_s: 20 },
    })
    await waitFor(() =>
      expect(FakeEventSource.instances.at(-1)?.url).toBe(`${API}/simulation/runs/${RUN_ID}/events`),
    )
    act(() => FakeEventSource.instances.at(-1)!.open())
    expect(screen.getByLabelText('Connection')).toHaveTextContent('live (SSE)')
  })

  it('maps a 422 onto fields and lists coupling rules', async () => {
    const user = userEvent.setup()
    server.use(
      http.post(`${API}/simulation/runs`, () =>
        HttpResponse.json(
          {
            data: null,
            error: {
              code: 'COUPLING_VIOLATION',
              message: '2 coupling rules violated',
              field: 'parameters.melt_temp_c',
              details: [
                {
                  field: 'parameters.melt_temp_c',
                  code: 'COUPLING_VIOLATION',
                  message: 'CPL-002: Melt temperature must exceed mold temperature by 120 °C',
                  limit: 120,
                  value: 100,
                },
              ],
            },
            meta: { request_id: 'req-422' },
          },
          { status: 422 },
        ),
      ),
    )
    renderAt()
    await chooseContext(user)
    await user.click(
      within(screen.getByRole('group', { name: 'Run controls' })).getByRole('button', { name: 'Run' }),
    )
    const errors = await screen.findByRole('alert', { name: 'Run setup errors' })
    expect(errors).toHaveTextContent('CPL-002')
    const melt = within(await panel()).getByRole('spinbutton', { name: 'Melt Temperature' })
    expect(melt).toHaveAttribute('aria-invalid', 'true')
    expect(await panel()).toHaveTextContent('(limit 120)')
    expect(FakeEventSource.instances).toHaveLength(0) // nothing was created
  })

  it("copies an open run's setup into the draft", async () => {
    const user = userEvent.setup()
    server.use(
      http.get(`${API}/simulation/runs/:id`, () =>
        HttpResponse.json(
          envelope(
            runState({
              status: 'FINAL_RESULT',
              context: {
                machine: { machine_id: 'MC-03' },
                product: { product_id: 'PP-JBOX-42' },
                material_lot: { material_lot_id: 'D-105' },
              },
              parameters: { drying_time_h: 2, melt_temp_c: 250, cooling_time_s: 12, cycle_time_s: 21 },
            }),
          ),
        ),
      ),
    )
    renderAt(`/?run=${RUN_ID}`)
    const p = await panel()
    await user.click(await within(p).findByRole('button', { name: "Use this run's setup" }))
    expect(within(p).getByRole('spinbutton', { name: 'Melt Temperature' })).toHaveValue(250)
    expect(within(p).getByLabelText('Material lot')).toHaveValue('D-105')
    expect(within(p).getByLabelText('Machine')).toHaveValue('MC-03')
  })
})
