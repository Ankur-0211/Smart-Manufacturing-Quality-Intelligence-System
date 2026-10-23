import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end suite (roadmap R2-P10, UD-12). It runs against the real system: the production build
 * served by the API (`scripts/e2e_server.py`), with Role 1's real intelligence, on a fresh
 * database. Tests share that database, so they run one at a time and create the runs they need.
 */
const PORT = 8001

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never', outputFolder: 'playwright-report' }]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    viewport: { width: 1440, height: 900 },
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
  ],
  webServer: {
    command: `npm run build && uv run python ../scripts/e2e_server.py --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/v1/health`,
    timeout: 180_000,
    reuseExistingServer: false,
    stdout: 'pipe',
  },
})
