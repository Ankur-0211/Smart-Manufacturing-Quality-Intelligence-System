import { render, screen, within } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import type { Schemas } from '@/api/client'
import { App } from '@/app/App'
import { createQueryClient } from '@/app/queryClient'
import { STATEMENT_SYNTHETIC_DATA } from '@/lib/disclaimers'
import { FakeEventSource } from '@/test/fakeEventSource'
import { API, envelope, server } from '@/test/server'

function activeModels(
  over: Partial<Schemas['ModelVersionOut']> = {},
  isMock = false,
): Schemas['ActiveModelsOut'] {
  return {
    is_mock: isMock,
    intelligence: {
      contracts_version: '0.1.0',
      constraints_version: 'constraints-1.0.0',
      model_version: 'fusion-1.0.0',
      is_mock: isMock,
      capabilities: { predict: true, explain: true, spc_check: false },
    },
    models: [
      {
        version: 'fusion-1.0.0',
        name: 'fusion',
        semver: '1.0.0',
        algorithm: 'xgboost',
        is_active: true,
        trained_at: null,
        metrics: {},
        feature_schema_hash: null,
        dataset_hash: null,
        git_sha: null,
        bundle_sha256: null,
        constraints_version: 'constraints-1.0.0',
        threshold: null,
        created_at: '2026-10-22T10:00:00Z',
        ...over,
      },
    ],
  }
}

const GLOBAL = {
  model_version: 'fusion-1.0.0',
  mean_abs_shap: [
    { feature: 'cooling_time_s', value: 0.58, stage: 'COOLING' },
    { feature: 'melt_temp_c', value: 0.44, stage: 'PLASTICIZING' },
  ],
  computed_on: '2026-10-15T00:00:00Z',
  n_rows: 2500,
}

function renderScreen(models: Schemas['ActiveModelsOut']) {
  server.use(
    http.get(`${API}/models/active`, () => HttpResponse.json(envelope(models))),
    http.get(`${API}/models/active/global-explanation`, () => HttpResponse.json(envelope(GLOBAL))),
  )
  return render(
    <App
      initialEntries={['/model-info']}
      queryClient={createQueryClient()}
      eventSourceFactory={(u) => new FakeEventSource(u)}
    />,
  )
}

describe('Model Info', () => {
  it('labels missing provenance as not reported and keeps the synthetic-data statement', async () => {
    renderScreen(activeModels())
    const model = await screen.findByRole('region', { name: 'Active model' })
    expect(await within(model).findByText('fusion-1.0.0')).toBeInTheDocument()
    expect(model).toHaveTextContent('Training datenot reported')
    expect(model).toHaveTextContent('Dataset hashnot reported')
    expect(model).toHaveTextContent('Generator versionnot reported')
    expect(screen.getByRole('region', { name: 'Serving' })).toHaveTextContent('Capabilitiespredict, explain')
    expect(screen.getByRole('region', { name: 'Threshold policy' })).toHaveTextContent(
      'does not record a threshold',
    )
    expect(screen.getByRole('region', { name: 'Evaluation metrics' })).toHaveTextContent(
      'No evaluation metrics reported by the active model.',
    )
    expect(screen.getByRole('note', { name: 'Synthetic data statement' })).toHaveTextContent(
      STATEMENT_SYNTHETIC_DATA,
    )
    expect(screen.queryByText(/running MOCK intelligence/)).toBeNull()
  })

  it('shows reported metrics, calibration, threshold and global importance', async () => {
    renderScreen(
      activeModels({
        trained_at: '2026-10-14T08:00:00Z',
        dataset_hash: 'sha256:abc',
        threshold: 0.35,
        metrics: { roc_auc: 0.9123, brier: 0.081, generator_version: 'gen-1.2.0', calibration: { bins: 10 } },
      }),
    )
    const model = await screen.findByRole('region', { name: 'Active model' })
    expect(await within(model).findByText('sha256:abc')).toBeInTheDocument()
    expect(model).toHaveTextContent('Generator versiongen-1.2.0')
    expect(screen.getByRole('region', { name: 'Threshold policy' })).toHaveTextContent('at or above 0.35')
    const metrics = screen.getByRole('table', { name: 'Metrics' })
    expect(
      within(metrics)
        .getAllByRole('row')
        .map((r) => r.textContent),
    ).toEqual(['roc_auc0.912', 'brier0.081'])
    expect(screen.getByRole('region', { name: 'Evaluation metrics' })).toHaveTextContent('"bins": 10')
    const importance = await screen.findByRole('table', { name: 'Global importance' })
    // display names come from GET /constraints once it has loaded
    expect(await within(importance).findByText('Cooling Time')).toBeInTheDocument()
    expect(
      within(importance)
        .getAllByRole('row')
        .map((r) => r.textContent),
    ).toEqual(['FeatureMean |SHAP|Stage', 'Cooling Time0.580Cooling', 'Melt Temperature0.440Thermal'])
    expect(screen.getByRole('region', { name: 'Global importance' })).toHaveTextContent(
      'Mean |SHAP| over 2500 rows',
    )
  })

  it('warns when the server runs mock intelligence', async () => {
    renderScreen(activeModels({}, true))
    expect(await screen.findByText(/running MOCK intelligence/)).toBeInTheDocument()
  })
})
