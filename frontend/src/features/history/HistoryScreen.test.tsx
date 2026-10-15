import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { RUN_ID } from '@/test/fixtures/runEvents'
import { finishedRunState, summary } from '@/test/fixtures/runState'
import { API, envelope, server } from '@/test/server'

function listHandler(total: number, seen: URLSearchParams[]) {
  return http.get(`${API}/simulation/runs`, ({ request }) => {
    const params = new URL(request.url).searchParams
    seen.push(params)
    const offset = Number(params.get('offset'))
    const limit = Number(params.get('limit'))
    const rows = Array.from({ length: Math.max(0, Math.min(limit, total - offset)) }, (_, i) =>
      summary(
        offset + i,
        i === 0 ? { is_whatif: true, parent_run_id: RUN_ID, scenario_label: 'cooler melt' } : {},
      ),
    )
    return HttpResponse.json({ ...envelope(rows), meta: { ...envelope(rows).meta, total } })
  })
}

function renderAt(path: string) {
  return render(<App initialEntries={[path]} queryClient={createQueryClient()} />)
}

describe('HistoryScreen', () => {
  it('lists runs with mock labels, what-if badge and pagination', async () => {
    const seen: URLSearchParams[] = []
    server.use(listHandler(25, seen))
    renderAt('/history')
    const table = await screen.findByRole('table')
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows).toHaveLength(20)
    expect(rows[0]).toHaveTextContent('what-if')
    expect(rows[0]).toHaveTextContent('cooler melt')
    expect(rows[1]).toHaveTextContent('MOCK')
    expect(rows[1]).toHaveTextContent('0.71')
    const pager = screen.getByRole('navigation', { name: 'Pagination' })
    expect(pager).toHaveTextContent('1–20 of 25')
    await userEvent.click(within(pager).getByRole('button', { name: 'Next' }))
    await waitFor(() => expect(pager).toHaveTextContent('21–25 of 25'))
    expect(seen.at(-1)?.get('offset')).toBe('20')
    expect(within(pager).getByRole('button', { name: 'Next' })).toBeDisabled()
  })

  it('sends filters and resets to the first page', async () => {
    const seen: URLSearchParams[] = []
    server.use(listHandler(25, seen))
    renderAt('/history')
    await screen.findByRole('table')
    await userEvent.click(screen.getByRole('button', { name: 'Next' }))
    const filters = screen.getByRole('form', { name: 'Run filters' })
    await userEvent.selectOptions(within(filters).getByLabelText('Result'), 'FAIL')
    await userEvent.selectOptions(within(filters).getByLabelText('Run type'), 'original')
    await userEvent.selectOptions(within(filters).getByLabelText('Inference'), 'real')
    await waitFor(() => {
      const last = seen.at(-1)!
      expect(last.get('label')).toBe('FAIL')
      expect(last.get('is_whatif')).toBe('false')
      expect(last.get('inference_backend')).toBe('real')
      expect(last.get('offset')).toBe('0')
    })
  })

  it('shows an empty state', async () => {
    server.use(listHandler(0, []))
    renderAt('/history')
    expect(await screen.findByText('No runs match these filters.')).toBeInTheDocument()
  })

  it('opens the run detail and saves a scenario label', async () => {
    let patched: unknown = null
    server.use(
      listHandler(1, []),
      http.get(`${API}/simulation/runs/:id`, () => HttpResponse.json(envelope(finishedRunState()))),
      http.patch(`${API}/simulation/runs/:id/label`, async ({ request }) => {
        patched = await request.json()
        return HttpResponse.json(envelope(summary(0, { scenario_label: 'baseline' })))
      }),
    )
    renderAt(`/history/${RUN_ID}`)
    const pipeline = await screen.findByRole('list', { name: 'Process stages' })
    expect(
      within(pipeline).getByRole('listitem', { name: /Cooling \/ Ejection: completed, health 0.41/ }),
    ).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Model-predicted failure probability' })).toHaveTextContent(
      '0.71',
    )
    expect(screen.getByRole('link', { name: 'Open in Process Control' })).toHaveAttribute(
      'href',
      `/?run=${RUN_ID}`,
    )
    const form = screen.getByRole('form', { name: 'Scenario label' })
    await userEvent.type(within(form).getByLabelText('Scenario label'), 'baseline')
    await userEvent.click(within(form).getByRole('button', { name: 'Save scenario' }))
    await waitFor(() => expect(patched).toEqual({ scenario_label: 'baseline' }))
    expect(await within(form).findByText('Saved')).toBeInTheDocument()
  })
})
