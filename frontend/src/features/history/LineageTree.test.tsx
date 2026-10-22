import { render, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { RUN_ID } from '@/test/fixtures/runEvents'
import { finishedRunState, summary } from '@/test/fixtures/runState'
import { API, envelope, server } from '@/test/server'

const CHILD = 'child-00000001'
const GRANDCHILD = 'grand-00000002'
const SIBLING = 'sibl-00000003'
const PARENT_OF: Record<string, string | null> = {
  [RUN_ID]: null,
  [CHILD]: RUN_ID,
  [SIBLING]: RUN_ID,
  [GRANDCHILD]: CHILD,
}

function node(runId: string, over: Record<string, unknown>, children: unknown[] = []) {
  return { run: summary(0, { run_id: runId, ...over }), children }
}

const TREE = node(RUN_ID, { is_whatif: false, p_fail: 0.62, label: 'FAIL', risk_level: 'HIGH' }, [
  node(
    CHILD,
    { is_whatif: true, parent_run_id: RUN_ID, scenario_label: 'cooler', p_fail: 0.31, label: 'PASS' },
    [node(GRANDCHILD, { is_whatif: true, parent_run_id: CHILD, p_fail: 0.25, label: 'PASS' })],
  ),
  node(SIBLING, { is_whatif: true, parent_run_id: RUN_ID, p_fail: 0.7, label: 'FAIL' }),
])

function handlers(lineageRequests: string[]) {
  return [
    http.get(`${API}/simulation/runs/:id`, ({ params }) => {
      const id = String(params.id)
      return HttpResponse.json(
        envelope(
          finishedRunState({ run_id: id, parent_run_id: PARENT_OF[id] ?? null, is_whatif: id !== RUN_ID }),
        ),
      )
    }),
    http.get(`${API}/simulation/runs/:id/lineage`, ({ params }) => {
      lineageRequests.push(String(params.id))
      return HttpResponse.json(envelope(TREE))
    }),
  ]
}

describe('What-if lineage tree', () => {
  it('climbs to the root and shows the whole tree with this run highlighted', async () => {
    const requested: string[] = []
    server.use(...handlers(requested))
    render(<App initialEntries={[`/history/${GRANDCHILD}`]} queryClient={createQueryClient()} />)
    const tree = await screen.findByRole('tree', { name: 'Lineage' })
    expect(requested).toEqual([RUN_ID]) // the root, not the run being viewed

    const items = within(tree).getAllByRole('treeitem')
    expect(items.map((i) => i.getAttribute('aria-level'))).toEqual(['1', '2', '3', '2'])
    const current = items.find((i) => i.getAttribute('aria-current') === 'true')!
    expect(current.firstElementChild).toHaveTextContent('grand-00 (this run)')
    expect(items[1]!.firstElementChild).toHaveTextContent('what-if“cooler”P(fail) 0.31 PASS')
    expect(
      within(items[1]!.firstElementChild as HTMLElement).getByRole('link', { name: 'child-00' }),
    ).toHaveAttribute('href', `/history/${CHILD}`)
    expect(
      within(current.firstElementChild as HTMLElement).getByRole('link', { name: 'Compare with parent' }),
    ).toHaveAttribute('href', `/what-if/compare?a=${CHILD}&b=${GRANDCHILD}`)
    // the root has no parent to compare with
    expect(
      within(items[0]!.firstElementChild as HTMLElement).queryByRole('link', { name: 'Compare with parent' }),
    ).toBeNull()
  })

  it('says so when no scenario branches from the run', async () => {
    server.use(
      http.get(`${API}/simulation/runs/:id`, () => HttpResponse.json(envelope(finishedRunState()))),
      http.get(`${API}/simulation/runs/:id/lineage`, () => HttpResponse.json(envelope(node(RUN_ID, {})))),
    )
    render(<App initialEntries={[`/history/${RUN_ID}`]} queryClient={createQueryClient()} />)
    const section = await screen.findByRole('region', { name: 'What-if lineage' })
    expect(
      await within(section).findByText('No what-if scenarios branch from this run yet.'),
    ).toBeInTheDocument()
  })
})
