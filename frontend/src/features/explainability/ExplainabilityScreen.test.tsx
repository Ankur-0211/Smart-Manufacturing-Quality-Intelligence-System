import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { DISCLAIMER_SHAP } from '@/lib/disclaimers'
import { FakeEventSource } from '@/test/fakeEventSource'
import { prediction, RUN_ID } from '@/test/fixtures/runEvents'
import { runState } from '@/test/fixtures/runState'
import { API, envelope, server } from '@/test/server'

const EXPLANATION = {
  method: 'tree_shap',
  output_space: 'log_odds',
  base_value: -0.512,
  attributions: [
    {
      feature: 'cooling_time_s',
      display_name: 'Cooling Time',
      value: 11,
      shap_value: 0.42,
      direction: 'toward_fail',
      stage: 'COOLING',
      group: 'time',
    },
    {
      feature: 'melt_temp_c',
      display_name: 'Melt Temperature',
      value: 230,
      shap_value: -0.18,
      direction: 'toward_pass',
      stage: 'PLASTICIZING',
      group: 'temperature',
    },
  ],
  grouped_attributions: [
    { group: 'time', shap_sum: 0.42 },
    { group: 'temperature', shap_sum: -0.18 },
  ],
  stage_risk_mass: [
    { stage: 'COOLING', share: 0.6 },
    { stage: 'PLASTICIZING', share: 0.4 },
  ],
  background_version: 'bg-1.0.0',
  show_caveat_banner: false,
}

function runWith(explanation: unknown, over: Record<string, unknown> = {}) {
  return http.get(`${API}/simulation/runs/:id`, () =>
    HttpResponse.json(
      envelope(
        runState({
          status: 'FINAL_RESULT',
          prediction: { ...prediction(), prediction_id: 'pred-1', explanation, ...over } as never,
        }),
      ),
    ),
  )
}

function renderAt(path = `/explainability?run=${RUN_ID}`) {
  return render(
    <App
      initialEntries={[path]}
      queryClient={createQueryClient()}
      eventSourceFactory={(u) => new FakeEventSource(u)}
    />,
  )
}

describe('Explainability screen', () => {
  it('shows the stored attributions with direction, stage and the SHAP disclaimer', async () => {
    server.use(runWith(EXPLANATION))
    renderAt()
    const table = await screen.findByRole('table', { name: 'Attributions' })
    const rows = within(table)
      .getAllByRole('row')
      .map((r) => r.textContent)
    expect(rows).toEqual([
      'FeatureValueSHAPDirectionStage',
      'Cooling Time11+0.420toward FAILCooling',
      'Melt Temperature230-0.180toward PASSThermal',
    ])
    expect(screen.getByRole('region', { name: 'Explained run' })).toHaveTextContent(
      'Predicted P(fail) 0.71 FAIL',
    )
    expect(screen.getByRole('region', { name: 'Explained run' })).toHaveTextContent('Operational risk HIGH')
    expect(screen.getByText(/log_odds margin \(base value -0.512, background bg-1.0.0\)/)).toBeInTheDocument()
    expect(screen.getByRole('note', { name: 'SHAP disclaimer' })).toHaveTextContent(DISCLAIMER_SHAP)
    expect(screen.queryByRole('alert', { name: 'Explanation caveats' })).toBeNull()
  })

  it('switches to grouped attributions', async () => {
    const user = userEvent.setup()
    server.use(runWith(EXPLANATION))
    renderAt()
    const view = await screen.findByRole('group', { name: 'Attribution view' })
    await user.click(within(view).getByRole('button', { name: 'Groups' }))
    expect(within(view).getByRole('button', { name: 'Groups' })).toHaveAttribute('aria-pressed', 'true')
    const table = screen.getByRole('table', { name: 'Grouped attributions' })
    expect(
      within(table)
        .getAllByRole('row')
        .map((r) => r.textContent),
    ).toEqual(['GroupSHAP sum', 'time0.420', 'temperature-0.180'])
  })

  it('lists the stage risk mass', async () => {
    server.use(runWith(EXPLANATION))
    renderAt()
    const shares = await screen.findByRole('list', { name: 'Stage shares' })
    expect(
      within(shares)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Cooling / Ejection60 %', 'Plasticizing / Thermal40 %'])
  })

  it('shows the caveat banner when the model flags the input', async () => {
    server.use(
      runWith(
        { ...EXPLANATION, show_caveat_banner: true },
        {
          caveats: [
            {
              code: 'OUT_OF_DISTRIBUTION',
              message: 'melt_temp_c outside training range',
              features: ['melt_temp_c'],
            },
          ],
        },
      ),
    )
    renderAt()
    expect(await screen.findByRole('alert', { name: 'Explanation caveats' })).toHaveTextContent(
      'OUT_OF_DISTRIBUTION: melt_temp_c outside training range',
    )
  })

  it('fetches the explanation when the prediction did not store one', async () => {
    let calls = 0
    server.use(
      runWith(null),
      http.get(`${API}/predict/:id/explain`, ({ params }) => {
        calls += 1
        expect(params.id).toBe('pred-1')
        return HttpResponse.json(envelope(EXPLANATION))
      }),
    )
    renderAt()
    expect(await screen.findByRole('table', { name: 'Attributions' })).toBeInTheDocument()
    await waitFor(() => expect(calls).toBe(1))
  })

  it('asks for a run, and keeps the disclaimer visible', async () => {
    renderAt('/explainability')
    expect(await screen.findByText('Choose a finished run to explain its prediction.')).toBeInTheDocument()
    expect(screen.getByRole('note', { name: 'SHAP disclaimer' })).toBeInTheDocument()
  })
})
