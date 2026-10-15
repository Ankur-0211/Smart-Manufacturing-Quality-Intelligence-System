import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { afterEach, describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { FakeEventSource } from '@/test/fakeEventSource'
import { fullRun, RUN_ID, stageResult, StreamBuilder } from '@/test/fixtures/runEvents'
import { runState } from '@/test/fixtures/runState'
import { API, envelope, server } from '@/test/server'

const create = (url: string) => new FakeEventSource(url)

function renderAt(path: string) {
  return render(<App initialEntries={[path]} queryClient={createQueryClient()} eventSourceFactory={create} />)
}

function stream(): FakeEventSource {
  const es = FakeEventSource.instances.at(-1)
  if (!es) throw new Error('no EventSource opened')
  return es
}

afterEach(() => {
  FakeEventSource.instances = []
})

describe('ProcessControlScreen without a run', () => {
  it('shows an idle pipeline, disabled controls and a pointer to History', async () => {
    renderAt('/')
    const pipeline = await screen.findByRole('list', { name: 'Process stages' })
    expect(
      within(pipeline)
        .getAllByRole('listitem')
        .every((n) => n.dataset.state === 'PENDING'),
    ).toBe(true)
    const controls = screen.getByRole('group', { name: 'Run controls' })
    for (const button of within(controls).getAllByRole('button')) expect(button).toBeDisabled()
    expect(controls).toHaveTextContent('Open a run from History')
    expect(screen.getByRole('link', { name: 'Open a run from History' })).toHaveAttribute('href', '/history')
    expect(screen.getByRole('region', { name: 'Quality result' })).toHaveTextContent(
      'Awaiting the quality inspection stage.',
    )
    expect(FakeEventSource.instances).toHaveLength(0)
  })
})

describe('ProcessControlScreen with ?run=', () => {
  it('follows a run live over SSE', async () => {
    server.use(http.get(`${API}/simulation/runs/:id`, () => HttpResponse.json(envelope(runState()))))
    renderAt(`/?run=${RUN_ID}`)
    expect(await screen.findByText('MC-03')).toBeInTheDocument()
    expect(stream().url).toBe(`${API}/simulation/runs/${RUN_ID}/events`)
    act(() => stream().open())
    expect(screen.getByLabelText('Connection')).toHaveTextContent('live (SSE)')

    act(() => fullRun().forEach((e) => stream().emit(e)))
    const quality = screen.getByRole('listitem', { name: /Quality Inspection \/ Fusion: FAIL/ })
    expect(quality).toHaveTextContent('P 0.71')
    expect(screen.getByRole('region', { name: 'Operational risk' })).toHaveTextContent('HIGH')
    expect(screen.getByLabelText('Connection')).toHaveTextContent('finished')
    expect(screen.getByText(/run completed/)).toBeInTheDocument()
  })

  it('sends start with the chosen mode and speed and shows server errors', async () => {
    let body: unknown = null
    server.use(
      http.get(`${API}/simulation/runs/:id`, () => HttpResponse.json(envelope(runState()))),
      http.get(`${API}/simulation/runs`, () => HttpResponse.json(envelope([]))),
      http.post(`${API}/simulation/runs/:id/start`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(
          {
            data: null,
            error: {
              code: 'CAPABILITY_UNAVAILABLE',
              message: 'Simulation needs the intelligence layer',
              hint: 'wire it in',
            },
            meta: { request_id: 'req-501' },
          },
          { status: 501 },
        )
      }),
    )
    renderAt(`/?run=${RUN_ID}`)
    await screen.findByText('MC-03')
    const controls = screen.getByRole('group', { name: 'Run controls' })
    await userEvent.selectOptions(within(controls).getByLabelText('Mode'), 'stepwise')
    await userEvent.selectOptions(within(controls).getByLabelText('Presentation speed'), 'instant')
    await userEvent.click(within(controls).getByRole('button', { name: 'Run' }))
    const alert = (await screen.findAllByRole('alert')).find((a) =>
      a.textContent?.includes('CAPABILITY_UNAVAILABLE'),
    )!
    expect(alert).toHaveTextContent('CAPABILITY_UNAVAILABLE: Simulation needs the intelligence layer')
    expect(alert).toHaveTextContent('req-501')
    expect(body).toEqual({ mode: 'stepwise', speed_factor: 'instant' })
  })

  it('offers override when a stage is blocked and posts the acknowledgement', async () => {
    let body: unknown = null
    server.use(
      http.get(`${API}/simulation/runs/:id`, () =>
        HttpResponse.json(envelope(runState({ status: 'BLOCKED' }))),
      ),
      http.get(`${API}/simulation/runs`, () => HttpResponse.json(envelope([]))),
      http.post(`${API}/simulation/runs/:id/override`, async ({ request }) => {
        body = await request.json()
        return HttpResponse.json(envelope(runState({ status: 'INJECTION' })))
      }),
    )
    renderAt(`/?run=${RUN_ID}`)
    await screen.findByText('MC-03')
    const blocked = stageResult('PLASTICIZING', { blocked: true, block_reason: 'ceiling' })
    act(() =>
      new StreamBuilder()
        .push('run.started')
        .stage('MATERIAL_CONDITIONING')
        .push('stage.started', 'PLASTICIZING')
        .push('stage.blocked', 'PLASTICIZING', { reason: 'ceiling', result: blocked })
        .events.forEach((e) => stream().emit(e)),
    )
    const panel = screen.getByRole('region', { name: 'Blocked stage override' })
    const submit = within(panel).getByRole('button', { name: 'Override and continue' })
    expect(submit).toBeDisabled() // acknowledgement is required
    await userEvent.type(within(panel).getByLabelText('Acknowledgement (required)'), 'operator accepts')
    await userEvent.click(submit)
    await waitFor(() => expect(body).toEqual({ stage: 'PLASTICIZING', acknowledgement: 'operator accepts' }))
  })
})
