import { expect, test } from '@playwright/test'

import { API, CONTEXT, runState, setParameter, setUpRun, stage, startRun } from './helpers'

/**
 * Keeps docs/demo_script.md true (roadmap R2-P10 task 7): replays the script's steps on the real
 * intelligence and checks the numbers the presenters will say. If this fails after a Role 1
 * release, update the script.
 */
test('demo script: high injection pressure → FAIL → why → what-if flip → cooling-only recompute', async ({
  page,
}) => {
  // 0:45 context and validation
  await setUpRun(page, { mode: 'auto', speed: 'instant' })
  await setParameter(page, 'Melt Temperature', 400)
  await expect(page.getByText('Allowed 180–295 °C')).toBeVisible()
  await setParameter(page, 'Melt Temperature', 230)

  // 1:30 live run with an anomaly on Injection
  await setParameter(page, 'Injection Pressure', 1800)
  await startRun(page)
  await expect(stage(page, 'Injection / Fill')).toHaveAttribute('aria-label', /, anomaly flagged/)

  // 2:30 result: FAIL 0.59 calibrated, operational risk HIGH, risk origin Injection 86 %
  const result = page.getByRole('region', { name: 'Quality result' })
  const probability = result.getByRole('region', { name: 'Model-predicted failure probability' })
  await expect(probability).toContainText('0.59 (calibrated)')
  await expect(probability).toContainText('Prediction: FAIL')
  await expect(probability).toContainText('threshold 0.35')
  await expect(result.getByRole('region', { name: 'Operational risk' })).toContainText('HIGH')
  await expect(result).toContainText('INJECTION 86%')

  // 3:00 why: Injection Pressure tops the SHAP table, toward FAIL
  await result.getByRole('link', { name: 'Why this prediction?' }).click()
  await expect(page.getByRole('table', { name: 'Attributions' }).getByRole('row').nth(1)).toContainText(
    /Injection Pressure.*\+0\.800.*toward FAIL/,
  )
  await page.goBack()

  // 4:45 what-if: 1100 bar flips FAIL → PASS; Material and Thermal are reused
  await page
    .getByRole('region', { name: 'Quality result' })
    .getByRole('link', { name: 'Try a what-if' })
    .click()
  const params = page.getByRole('region', { name: 'What-if parameters' })
  const whatIf = page.getByRole('region', { name: 'What-if result' })
  await params.getByRole('spinbutton', { name: 'Injection Pressure', exact: true }).fill('1100')
  await whatIf.getByRole('button', { name: 'Evaluate' }).click()
  const diff = whatIf.getByLabel('What-if diff')
  await expect(diff).toContainText('0.59 → 0.24')
  await expect(diff).toContainText('FLIPPED')
  await expect(diff.getByRole('region', { name: 'Operational risk' })).toContainText('HIGH → LOW')
  await expect(diff).toContainText(
    'Recomputed: Injection, Packing, Cooling. Reused from the base run: Material, Thermal.',
  )

  // ... and a cooling-only change recomputes only Cooling
  await params.getByRole('button', { name: 'Reset to base' }).click()
  await params.getByRole('spinbutton', { name: 'Cooling Time', exact: true }).fill('12')
  await whatIf.getByRole('button', { name: 'Evaluate' }).click()
  await expect(whatIf.getByLabel('What-if diff')).toContainText(
    'Recomputed: Cooling. Reused from the base run: Material, Thermal, Injection, Packing.',
  )
})

test('demo script: a BLOCKED run opened from History is overridden to NOT RELEASABLE', async ({
  page,
  request,
}) => {
  // The seeded "melt above ceiling" run: left BLOCKED at Thermal for the live override.
  const nominal = (await (await request.get(`${API}/constraints`)).json()).data.parameters as {
    name: string
    kind: string
    nominal: number
  }[]
  const recipe = Object.fromEntries(
    nominal.filter((p) => p.kind === 'setpoint').map((p) => [p.name, p.nominal]),
  )
  const created = await request.post(`${API}/simulation/runs`, {
    data: {
      machine_id: CONTEXT.machine,
      product_id: CONTEXT.product,
      material_lot_id: CONTEXT.lot,
      parameters: { ...recipe, melt_temp_c: 290 },
      scenario_label: 'e2e: melt above ceiling',
    },
  })
  const runId = (await created.json()).data.run_id as string
  await request.post(`${API}/simulation/runs/${runId}/start`, { data: { mode: 'stepwise' } })
  for (let i = 0; i < 6 && (await runState(request, runId)).status !== 'BLOCKED'; i += 1) {
    await request.post(`${API}/simulation/runs/${runId}/advance`)
  }
  expect((await runState(request, runId)).status).toBe('BLOCKED')

  await page.goto(`/history/${runId}`)
  await page.getByRole('link', { name: 'Open in Process Control' }).click()
  const override = page.getByRole('region', { name: 'Blocked stage override' })
  await expect(override).toContainText('Plasticizing / Thermal is BLOCKED')
  await override.getByLabel('Acknowledgement (required)').fill('Demo: shown for inspection only')
  await override.getByRole('button', { name: 'Override and continue' }).click()
  // The seeded run is stepwise: after the override, STEP through the remaining stages.
  const step = page.getByRole('group', { name: 'Run controls' }).getByRole('button', { name: 'Step' })
  const quality = stage(page, 'Quality Inspection / Fusion')
  for (let i = 0; i < 4 && !/NOT RELEASABLE/.test((await quality.getAttribute('aria-label')) ?? ''); i += 1) {
    await expect(step).toBeEnabled()
    await step.click()
  }
  await expect(quality).toHaveAttribute('aria-label', /: NOT RELEASABLE,/)
  const result = page.getByRole('region', { name: 'Quality result' })
  await expect(result.getByRole('alert')).toContainText('NOT RELEASABLE')
  await expect(result.getByRole('region', { name: 'Operational risk' })).toContainText('CRITICAL')
})
