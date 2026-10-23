import { expect, type APIRequestContext, type Page } from '@playwright/test'

export const API = '/api/v1'

/** Fleet used throughout (Role 1's fleet.yaml): MC-03 cannot run the nominal recipe (CPL-003). */
export const CONTEXT = { machine: 'MC-02', product: 'PP-JBOX-42', lot: 'A-771' } as const

export interface SetupOptions {
  machine?: string
  product?: string
  lot?: string
  /** Display name -> value typed into that parameter's number input. */
  values?: Record<string, number>
  mode?: 'auto' | 'stepwise'
  speed?: '0.5x' | '1x' | '2x' | 'instant'
}

/** Fill the Process Control run setup (context pickers, recipe, mode and speed). */
export async function setUpRun(page: Page, options: SetupOptions = {}) {
  await page.goto('/')
  const context = page.getByRole('group', { name: 'Run context selection' })
  await context.getByLabel('Machine').selectOption(options.machine ?? CONTEXT.machine)
  await context.getByLabel('Product').selectOption(options.product ?? CONTEXT.product)
  await context.getByLabel('Material lot').selectOption(options.lot ?? CONTEXT.lot)
  await page.getByRole('button', { name: 'Load nominal recipe' }).click()
  for (const [name, value] of Object.entries(options.values ?? {})) {
    await setParameter(page, name, value)
  }
  const controls = page.getByRole('group', { name: 'Run controls' })
  await controls.getByLabel('Mode').selectOption(options.mode ?? 'auto')
  await controls.getByLabel('Presentation speed').selectOption(options.speed ?? 'instant')
  return controls
}

export async function setParameter(page: Page, displayName: string, value: number) {
  const input = page
    .getByRole('region', { name: 'Parameter panel' })
    .getByRole('spinbutton', { name: displayName, exact: true })
  await input.fill(String(value))
}

/** Press Run and return the new run's id (RUN creates, starts and opens `?run=`). */
export async function startRun(page: Page): Promise<string> {
  await page.getByRole('group', { name: 'Run controls' }).getByRole('button', { name: 'Run' }).click()
  await expect(page).toHaveURL(/[?&]run=/)
  return new URL(page.url()).searchParams.get('run')!
}

export function stage(page: Page, label: string) {
  return page
    .getByRole('list', { name: 'Process stages' })
    .getByRole('listitem', { name: new RegExp(`^${label}:`) })
}

export async function runState(request: APIRequestContext, runId: string) {
  const response = await request.get(`${API}/simulation/runs/${runId}`)
  expect(response.ok()).toBeTruthy()
  return (await response.json()).data
}
