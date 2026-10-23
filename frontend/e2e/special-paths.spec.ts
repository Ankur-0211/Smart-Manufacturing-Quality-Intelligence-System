import { expect, test } from '@playwright/test'

import { runState, setUpRun, stage, startRun } from './helpers'

/** Special paths (roadmap R2-P10 task 2) on the real intelligence. */

test('BLOCKED at a critical breach, then override → NOT RELEASABLE, never an ordinary PASS', async ({
  page,
  request,
}) => {
  // 290 °C is inside the melt window (180–295) but above the PP-H ceiling: HC-001 blocks Thermal.
  await setUpRun(page, { values: { 'Melt Temperature': 290 }, mode: 'auto', speed: 'instant' })
  const runId = await startRun(page)
  await expect(stage(page, 'Plasticizing / Thermal')).toHaveAttribute(
    'aria-label',
    /: blocked by a critical constraint breach/,
  )
  await expect(stage(page, 'Injection / Fill')).toHaveAttribute('aria-label', /: pending/)
  expect((await runState(request, runId)).status).toBe('BLOCKED')

  const override = page.getByRole('region', { name: 'Blocked stage override' })
  const submit = override.getByRole('button', { name: 'Override and continue' })
  await expect(submit).toBeDisabled() // an acknowledgement is required
  await override.getByLabel('Acknowledgement (required)').fill('E2E: proceed for inspection only')
  await submit.click()

  const result = page.getByRole('region', { name: 'Quality result' })
  await expect(result.getByRole('alert')).toContainText('NOT RELEASABLE')
  const final = await runState(request, runId)
  expect(final.status).toBe('FINAL_RESULT')
  expect(final.prediction.constraint_override_applied).toBe(true)
  expect(final.prediction.risk_level).toBe('CRITICAL')
  await expect(stage(page, 'Quality Inspection / Fusion')).toHaveAttribute(
    'aria-label',
    /: NOT RELEASABLE, predicted failure probability .*, operational risk CRITICAL/,
  )
  await expect(result.getByRole('region', { name: 'Operational risk' })).toContainText('CRITICAL')
  await expect(result.getByRole('list', { name: 'Caveats' })).toContainText('CRITICAL_CONSTRAINT_OVERRIDDEN')
  await expect(stage(page, 'Plasticizing / Thermal')).toHaveAttribute(
    'aria-label',
    /critical breach overridden/,
  )
})

test('abort mid-run keeps the partial state inspectable', async ({ page, request }) => {
  await setUpRun(page, { mode: 'auto', speed: '1x' })
  const runId = await startRun(page)
  await expect(stage(page, 'Material Conditioning')).toHaveAttribute('aria-label', /: completed/)
  await page.getByRole('group', { name: 'Run controls' }).getByRole('button', { name: 'Abort' }).click()

  await expect.poll(async () => (await runState(request, runId)).status).toBe('ABORTED')
  const aborted = await runState(request, runId)
  expect(aborted.abort_reason).toBe('Operator abort')
  expect(aborted.prediction).toBeNull()
  const done = aborted.stage_results.length
  expect(done).toBeGreaterThanOrEqual(1)
  expect(done).toBeLessThan(5)

  // The run detail shows exactly the stages that completed before the abort.
  await page.goto(`/history/${runId}`)
  await expect(page.getByText('status ABORTED')).toBeVisible()
  await expect(stage(page, 'Material Conditioning')).toHaveAttribute('aria-label', /: completed/)
  await expect(stage(page, 'Cooling / Ejection')).toHaveAttribute('aria-label', /: pending/)
  await expect(page.getByRole('region', { name: 'Quality result' })).toHaveText(
    /No prediction: the run was aborted before quality inspection\./,
  )
})

test('reset returns a stepwise run to its initial state', async ({ page, request }) => {
  const controls = await setUpRun(page, { mode: 'stepwise', speed: 'instant' })
  const runId = await startRun(page)
  await controls.getByRole('button', { name: 'Step' }).click()
  await expect(stage(page, 'Material Conditioning')).toHaveAttribute('aria-label', /: completed/)
  await controls.getByRole('button', { name: 'Step' }).click()
  await expect(stage(page, 'Plasticizing / Thermal')).toHaveAttribute('aria-label', /: completed/)

  await controls.getByRole('button', { name: 'Reset' }).click()
  await expect(stage(page, 'Material Conditioning')).toHaveAttribute('aria-label', /: pending/)
  await expect(stage(page, 'Plasticizing / Thermal')).toHaveAttribute('aria-label', /: pending/)
  const reset = await runState(request, runId)
  expect(reset.status).toBe('INITIALIZED')
  expect(reset.stage_results).toEqual([])
})

test('when the event stream drops, the run view falls back to polling and still finishes', async ({
  page,
  request,
}) => {
  // Simulate a proxy that kills the SSE stream: every events request fails.
  await page.route('**/simulation/runs/*/events**', (route) => route.abort('connectionreset'))
  await setUpRun(page, { mode: 'auto', speed: '1x' })
  const runId = await startRun(page)
  await expect(page.getByLabel('Connection')).toHaveText('live (polling)', { timeout: 15_000 })
  const quality = stage(page, 'Quality Inspection / Fusion')
  await expect(quality).toHaveAttribute('aria-label', /predicted failure probability/, { timeout: 30_000 })
  const p = (await runState(request, runId)).prediction
  await expect(quality).toHaveAttribute('aria-label', new RegExp(`probability ${p.p_fail.toFixed(2)},`))
})
