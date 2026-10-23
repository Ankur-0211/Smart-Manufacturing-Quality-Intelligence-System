import { expect, test } from '@playwright/test'

import { setUpRun, stage, startRun } from './helpers'

/**
 * Plan §24.4 "60 fps animation" (roadmap R2-P10 task 6). Counts requestAnimationFrame callbacks
 * while a 1x run animates the pipeline and timeline, next to an idle baseline on the same page.
 *
 * Headless Chromium paints in software (no GPU), so this is a regression guard, not the 60 fps
 * measurement: that is done with DevTools on the demo machine (docs/system_test_report.md).
 * Headless today: 60 fps idle, 48–53 fps during a run, no long tasks, main thread mostly idle.
 */
test('a 1x run animates without long frames (regression guard)', async ({ page }, testInfo) => {
  await setUpRun(page, { mode: 'auto', speed: '1x' })
  // Idle baseline on the same page: what this browser delivers with nothing animating.
  const idleFps = await page.evaluate(
    () =>
      new Promise<number>((resolve) => {
        const times: number[] = []
        const tick = (t: number) => {
          times.push(t)
          if (t - times[0]! < 3000) requestAnimationFrame(tick)
          else resolve((times.length - 1) / ((t - times[0]!) / 1000))
        }
        requestAnimationFrame(tick)
      }),
  )
  await page.evaluate(() => {
    const w = window as unknown as { __frames: number[]; __stop: boolean }
    w.__frames = []
    w.__stop = false
    const tick = (t: number) => {
      w.__frames.push(t)
      if (!w.__stop) requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
  await startRun(page)
  // No locator polling while measuring: Playwright's selector engine runs on the page's main
  // thread and would itself cost frames. Six stages at 1.5 s, plus margin.
  await page.waitForTimeout(10_500)
  const frames = await page.evaluate(() => {
    const w = window as unknown as { __frames: number[]; __stop: boolean }
    w.__stop = true
    return w.__frames
  })
  const gaps = frames.slice(1).map((t, i) => t - frames[i]!)
  const seconds = (frames.at(-1)! - frames[0]!) / 1000
  const fps = gaps.length / seconds
  const longest = Math.max(...gaps)
  const over50ms = gaps.filter((g) => g > 50).length
  const summary = `idle ${idleFps.toFixed(1)} fps; during the run ${fps.toFixed(1)} fps over ${seconds.toFixed(1)} s; longest frame ${longest.toFixed(1)} ms; frames > 50 ms: ${over50ms}`
  testInfo.annotations.push({ type: 'fps', description: summary })
  console.log(`[perf] ${summary}`)
  await expect(stage(page, 'Quality Inspection / Fusion')).toHaveAttribute(
    'aria-label',
    /predicted failure probability/,
  )
  expect(fps).toBeGreaterThanOrEqual(40)
  expect(longest).toBeLessThan(100)
})
