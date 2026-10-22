import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { API, envelope, server } from '@/test/server'

const FILTERS = {
  include_whatif: false,
  include_mock: false,
  include_unfinished: false,
  created_from: null,
  created_to: null,
}

function outcome(runs: number, fail: number, scored = runs, mean: number | null = 0.4) {
  return {
    runs,
    with_prediction: scored,
    predicted_fail: fail,
    predicted_fail_rate: scored ? fail / scored : null,
    mean_p_fail: scored ? mean : null,
  }
}

function summaryPayload(over: Record<string, unknown> = {}) {
  return {
    filters: FILTERS,
    excluded: { whatif: 2, mock: 1, unfinished: 3 },
    ...outcome(12, 3),
    risk_levels: { LOW: 8, HIGH: 3, CRITICAL: 1 },
    not_releasable: 1,
    stage_risk_frequency: [{ stage: 'PLASTICIZING', counts: { NORMAL: 10, CRITICAL: 2 }, total: 12 }],
    runs_over_time: [
      { day: '2026-10-20', ...outcome(5, 1) },
      { day: '2026-10-21', ...outcome(7, 2) },
    ],
    ...over,
  }
}

function handlers(seen: URL[], summary = summaryPayload()) {
  const record = (request: Request) => seen.push(new URL(request.url))
  return [
    http.get(`${API}/analytics/summary`, ({ request }) => {
      record(request)
      return HttpResponse.json(envelope(summary))
    }),
    http.get(`${API}/analytics/by-machine`, ({ request }) => {
      record(request)
      return HttpResponse.json(
        envelope({
          filters: FILTERS,
          rows: [
            { key: 'MC-01', ...outcome(8, 3) },
            { key: 'MC-02', ...outcome(4, 0) },
          ],
        }),
      )
    }),
    http.get(`${API}/analytics/by-material`, ({ request }) => {
      record(request)
      const group = new URL(request.url).searchParams.get('group')
      const rows =
        group === 'resin_grade'
          ? [{ key: 'PP-H', ...outcome(12, 3) }]
          : [
              { key: 'A-771', ...outcome(9, 3) },
              { key: 'B-812', ...outcome(3, 0) },
            ]
      return HttpResponse.json(envelope({ filters: FILTERS, group, rows }))
    }),
    http.get(`${API}/analytics/by-parameter`, ({ request }) => {
      record(request)
      return HttpResponse.json(
        envelope({
          filters: FILTERS,
          parameter: 'melt_temp_c',
          unit: 'c',
          window: { min: 180, max: 280 },
          rows: [
            { lo: 180, hi: 230, ...outcome(6, 0) },
            { lo: 230, hi: 280, ...outcome(0, 0) },
          ],
        }),
      )
    }),
    http.get(`${API}/analytics/spc`, ({ request }) => {
      record(request)
      return HttpResponse.json(
        envelope({
          machine_id: 'MC-01',
          parameter: 'melt_temp_c',
          unit: 'c',
          filters: FILTERS,
          series: [
            { run_id: 'r1', created_at: '2026-10-20T08:00:00Z', value: 228 },
            { run_id: 'r2', created_at: '2026-10-20T09:00:00Z', value: 235 },
          ],
          spc: { available: false, reason: 'SPC alerts come from the intelligence layer (CCR-004 #10).' },
          alerts: null,
        }),
      )
    }),
  ]
}

function renderScreen() {
  return render(<App initialEntries={['/analytics']} queryClient={createQueryClient()} />)
}

const rows = (table: HTMLElement) =>
  within(table)
    .getAllByRole('row')
    .map((r) => r.textContent)

describe('Analytics screen', () => {
  it('states the default exclusions and renders the server aggregates', async () => {
    const seen: URL[] = []
    server.use(...handlers(seen))
    renderScreen()
    await screen.findByRole('region', { name: 'Totals' })
    expect(screen.getByLabelText('Exclusions applied')).toHaveTextContent(
      "Excluded: 2 what-if scenarios, 1 run scored by MOCK intelligence, 3 runs without a final result. Shares are the model's predicted FAIL labels, not observed defects.",
    )
    expect(seen.find((u) => u.pathname.endsWith('/summary'))!.search).toBe('') // defaults = server defaults
    const totals = screen.getByRole('region', { name: 'Totals' })
    expect(totals).toHaveTextContent('Predicted FAIL share25 % (3)')
    expect(totals).toHaveTextContent('NOT RELEASABLE (overridden critical)1')
    expect(rows(await screen.findByRole('table', { name: 'By machine' }))).toEqual([
      'MachineRunsPredicted FAILShareMean P(fail)',
      'MC-0183/838 %0.40',
      'MC-0240/40 %0.40',
    ])
    expect(rows(screen.getByRole('table', { name: 'Stage risk frequency' }))[1]).toBe(
      'Plasticizing / Thermal100002',
    )
    expect(screen.getByLabelText('Operational risk distribution')).toHaveTextContent('LOW 8HIGH 3CRITICAL 1')
    expect(rows(await screen.findByRole('table', { name: 'By parameter' }))).toEqual([
      'Melt Temperature (°C)RunsPredicted FAILShareMean P(fail)',
      '180–23060/60 %0.40',
      '230–28000/0——',
    ])
  })

  it('sends a toggled exclusion and a date range to every endpoint', async () => {
    const user = userEvent.setup()
    const seen: URL[] = []
    server.use(...handlers(seen))
    renderScreen()
    const filters = await screen.findByRole('region', { name: 'Analytics filters' })
    await user.click(within(filters).getByRole('checkbox', { name: 'Include what-if scenarios' }))
    await waitFor(() =>
      expect(
        seen.some(
          (u) => u.pathname.endsWith('/by-machine') && u.searchParams.get('include_whatif') === 'true',
        ),
      ).toBe(true),
    )
    await user.type(within(filters).getByLabelText('From'), '2026-10-21')
    await waitFor(() => {
      const last = seen.filter((u) => u.pathname.endsWith('/summary')).at(-1)!
      expect(last.searchParams.get('from')).toBe('2026-10-21T00:00:00Z')
      expect(last.searchParams.get('include_whatif')).toBe('true')
    })
  })

  it('switches material grouping to resin grade', async () => {
    const user = userEvent.setup()
    const seen: URL[] = []
    server.use(...handlers(seen))
    renderScreen()
    const panel = await screen.findByRole('region', { name: 'By material' })
    await user.click(within(panel).getByRole('button', { name: 'Resin grade' }))
    await waitFor(() =>
      expect(rows(within(panel).getByRole('table', { name: 'By material' }))).toEqual([
        'Resin gradeRunsPredicted FAILShareMean P(fail)',
        'PP-H123/1225 %0.40',
      ]),
    )
  })

  it('shows the SPC series and says why there are no control limits', async () => {
    server.use(...handlers([]))
    renderScreen()
    const panel = await screen.findByRole('region', { name: 'SPC drift' })
    expect(await within(panel).findByRole('note', { name: 'SPC status' })).toHaveTextContent('CCR-004 #10')
    expect(within(panel).getByLabelText('SPC series summary')).toHaveTextContent(
      '2 runs · min 228 · max 235 °C',
    )
  })

  it('shows an empty state and a caution for few runs', async () => {
    server.use(
      ...handlers([], summaryPayload({ ...outcome(0, 0), runs_over_time: [], stage_risk_frequency: [] })),
    )
    renderScreen()
    expect(await screen.findAllByText('No stored runs match these filters.')).not.toHaveLength(0)
  })

  it('cautions when there are few scored runs', async () => {
    server.use(...handlers([], summaryPayload({ ...outcome(4, 1) })))
    renderScreen()
    expect(
      await screen.findByText(/Only 4 scored runs: treat the shares below as anecdotal./),
    ).toBeInTheDocument()
  })
})
