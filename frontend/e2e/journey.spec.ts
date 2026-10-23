import { expect, test } from '@playwright/test'

import { API, runState, setParameter, setUpRun, stage, startRun } from './helpers'

const STAGES = [
  'Material Conditioning',
  'Plasticizing / Thermal',
  'Injection / Fill',
  'Packing / Holding',
  'Cooling / Ejection',
]

/**
 * The acceptance journey (roadmap §15.4, R2-P10 task 1): context → recipe → validation → run →
 * five stages → calibrated P(fail) → explanation → recommendations → what-if → saved scenario →
 * history → analytics, on the real intelligence. UI numbers are checked against the API payload.
 */
test('acceptance journey on the real intelligence', async ({ page, request }) => {
  const errors: string[] = []
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  page.on('pageerror', (e) => errors.push(e.message))

  // Context, recipe and client-side validation (a value outside the registry window is refused).
  const controls = await setUpRun(page, { mode: 'auto', speed: '1x' })
  await setParameter(page, 'Melt Temperature', 400)
  await expect(page.getByText('Allowed 180–295 °C')).toBeVisible()
  await expect(controls).toContainText('Fix the highlighted parameters to run.')
  await expect(controls.getByRole('button', { name: 'Run' })).toBeDisabled()
  await setParameter(page, 'Melt Temperature', 230)
  await expect(controls.getByRole('button', { name: 'Run' })).toBeEnabled()

  // Run at 1x and watch the five stages complete live over SSE.
  const runId = await startRun(page)
  await expect(page.getByLabel('Connection')).toHaveText('live (SSE)')
  for (const label of STAGES) {
    await expect(stage(page, label)).toHaveAttribute('aria-label', /: completed, health /, {
      timeout: 15_000,
    })
  }
  const quality = stage(page, 'Quality Inspection / Fusion')
  await expect(quality).toHaveAttribute('aria-label', /: (PASS|FAIL), predicted failure probability/)

  // The result card shows the backend's numbers, with prediction and operational risk apart.
  const final = await runState(request, runId)
  expect(final.status).toBe('FINAL_RESULT')
  const p = final.prediction
  const result = page.getByRole('region', { name: 'Quality result' })
  await expect(result.getByRole('region', { name: 'Model-predicted failure probability' })).toContainText(
    `${p.p_fail.toFixed(2)} (calibrated)`,
  )
  await expect(result.getByRole('region', { name: 'Model-predicted failure probability' })).toContainText(
    `Prediction: ${p.label}`,
  )
  await expect(result.getByRole('region', { name: 'Operational risk' })).toContainText(p.risk_level)
  await expect(result.getByRole('region', { name: 'Anomaly status' })).toBeVisible()
  await expect(quality).toHaveAttribute(
    'aria-label',
    `Quality Inspection / Fusion: ${p.label}, predicted failure probability ${p.p_fail.toFixed(2)}, operational risk ${p.risk_level}`,
  )
  const before = JSON.stringify(final)

  // Why: SHAP attributions from the stored explanation.
  await result.getByRole('link', { name: 'Why this prediction?' }).click()
  const attributions = page.getByRole('table', { name: 'Attributions' })
  await expect(attributions).toBeVisible()
  const top = p.explanation.attributions[0]
  await expect(attributions.getByRole('row').nth(1)).toContainText(top.display_name)
  await expect(page.getByRole('note', { name: 'SHAP disclaimer' })).toBeVisible()

  // What should I change: guarded options, then Send to What-If.
  await page.goto(`/recommendations?run=${runId}`)
  await page
    .getByRole('region', { name: 'Recommendation request' })
    .getByRole('button', { name: 'Find options' })
    .click()
  const options = page.getByRole('region', { name: 'Recommendation options' })
  await expect(options).toBeVisible()
  const first = options.getByRole('article').first()
  await expect(first.getByRole('region', { name: 'Guard checks' })).toBeVisible()
  await expect(page.getByRole('note', { name: 'Recommendation disclaimer' })).toBeVisible()
  await first.getByRole('button', { name: 'Send to What-If' }).click()

  // What-if: evaluate, then save the scenario as a child run.
  const params = page.getByRole('region', { name: 'What-if parameters' })
  await expect(params).toContainText('changed')
  const whatIf = page.getByRole('region', { name: 'What-if result' })
  await whatIf.getByRole('button', { name: 'Evaluate' }).click()
  await expect(whatIf.getByRole('region', { name: 'Model-predicted failure probability' })).toBeVisible()
  await whatIf.getByLabel('Scenario label (optional)').fill('e2e: recommended option')
  await whatIf.getByRole('button', { name: 'Save as scenario' }).click()
  await expect(whatIf).toContainText('Saved as scenario')
  const childId = (await whatIf.getByRole('link').first().getAttribute('href'))!.split('/').pop()!

  // What-if never rewrites the original run; the child points at it.
  expect(JSON.stringify(await runState(request, runId))).toBe(before)
  const child = await runState(request, childId)
  expect(child.parent_run_id).toBe(runId)
  expect(child.is_whatif).toBe(true)
  expect(child.scenario_label).toBe('e2e: recommended option')

  // History: the scenario row, and the lineage tree from its run detail.
  await page.getByRole('link', { name: 'History', exact: true }).click()
  await expect(page.getByRole('row', { name: new RegExp(childId.slice(0, 8)) })).toContainText('what-if')
  await page.goto(`/history/${childId}`)
  const tree = page.getByRole('tree', { name: 'Lineage' })
  await expect(tree.getByRole('link', { name: runId.slice(0, 8) })).toBeVisible()
  await expect(tree).toContainText(`${childId.slice(0, 8)} (this run)`)

  // Analytics: the what-if child is excluded by default and the exclusion is stated.
  await page.getByRole('link', { name: 'Analytics', exact: true }).click()
  await expect(page.getByLabel('Exclusions applied')).toContainText(/Excluded: \d+ what-if scenarios?/)
  const summary = (await (await request.get(`${API}/analytics/summary`)).json()).data
  expect(summary.excluded.whatif).toBeGreaterThanOrEqual(1)
  await expect(page.getByRole('region', { name: 'Totals' })).toContainText(`Runs${summary.runs}`)

  expect(errors).toEqual([])
})

test('an instant auto run completes and matches the API', async ({ page, request }) => {
  await setUpRun(page, { mode: 'auto', speed: 'instant' })
  const runId = await startRun(page)
  const quality = stage(page, 'Quality Inspection / Fusion')
  await expect(quality).toHaveAttribute('aria-label', /predicted failure probability/)
  const p = (await runState(request, runId)).prediction
  await expect(quality).toHaveAttribute('aria-label', new RegExp(`probability ${p.p_fail.toFixed(2)},`))
})
