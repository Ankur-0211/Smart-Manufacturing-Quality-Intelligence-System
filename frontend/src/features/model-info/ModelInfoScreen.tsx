import { useConstraints } from '@/api/constraints'
import { useActiveModels, useGlobalExplanation } from '@/api/predict'
import { ShapBars } from '@/components/charts/lazy'
import { STAGE_META, type StageName } from '@/features/process-control/model'
import { STATEMENT_SYNTHETIC_DATA } from '@/lib/disclaimers'

const NOT_REPORTED = 'not reported'

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="rounded border border-border bg-panel p-4">
      <h3 className="mb-2 text-xs font-semibold tracking-widest text-text-muted uppercase">{title}</h3>
      {children}
    </section>
  )
}

function Facts({ label, rows }: { label: string; rows: [string, React.ReactNode][] }) {
  return (
    <dl aria-label={label} className="numeric grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-text-muted">{k}</dt>
          <dd className="[overflow-wrap:anywhere]">{v ?? NOT_REPORTED}</dd>
        </div>
      ))}
    </dl>
  )
}

function metricText(value: unknown): string {
  if (typeof value === 'number') return Number.isInteger(value) ? String(value) : value.toFixed(3)
  if (typeof value === 'string' || typeof value === 'boolean') return String(value)
  return JSON.stringify(value)
}

/**
 * Model Info (roadmap R2-P7 task 7, P1): the active model's version and provenance, its reported
 * metrics and calibration, the threshold policy, global importance, and STATEMENT_SYNTHETIC_DATA.
 * Shows only what /models/active and /models/active/global-explanation report; a missing field is
 * labelled "not reported", never filled in.
 */
export function ModelInfoScreen() {
  const active = useActiveModels()
  const global = useGlobalExplanation()
  const constraints = useConstraints().data
  const info = active.data?.intelligence
  const model = active.data?.models.find((m) => m.is_active) ?? active.data?.models[0] ?? null
  const metrics = (model?.metrics ?? {}) as Record<string, unknown>
  const calibration = metrics.calibration ?? metrics.reliability ?? null
  const otherMetrics = Object.entries(metrics).filter(
    ([k]) => !['calibration', 'reliability', 'generator_version'].includes(k),
  )
  const displayName = (feature: string) =>
    constraints?.parameters.find((p) => p.name === feature)?.display_name ?? feature
  const importance = global.data?.mean_abs_shap ?? []

  return (
    <div className="flex flex-col gap-4">
      <h2 className="text-sm font-semibold tracking-widest text-text-muted uppercase">Model Info</h2>

      {active.isError && (
        <p role="alert" className="text-sm text-risk-critical">
          Model information is unavailable: {active.error.message}
        </p>
      )}
      {active.data?.is_mock && (
        <p role="alert" className="text-sm text-anomaly">
          The server is running MOCK intelligence; there is no trained model behind these outputs.
        </p>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Active model">
          {model ? (
            <Facts
              label="Model facts"
              rows={[
                ['Model version', model.version],
                ['Algorithm', model.algorithm],
                ['Training date', model.trained_at ?? NOT_REPORTED],
                ['Dataset hash', model.dataset_hash ?? NOT_REPORTED],
                [
                  'Generator version',
                  metrics.generator_version != null ? metricText(metrics.generator_version) : NOT_REPORTED,
                ],
                ['Feature schema hash', model.feature_schema_hash ?? NOT_REPORTED],
                ['Bundle SHA-256', model.bundle_sha256 ?? NOT_REPORTED],
                ['Code revision', model.git_sha ?? NOT_REPORTED],
                ['Registered', model.created_at],
              ]}
            />
          ) : (
            !active.isError && <p className="text-sm text-text-muted">Loading…</p>
          )}
        </Panel>

        <Panel title="Serving">
          {info ? (
            <Facts
              label="Serving facts"
              rows={[
                ['Intelligence', info.is_mock ? 'MOCK' : 'real'],
                ['Contracts version', info.contracts_version],
                ['Constraints version', info.constraints_version],
                [
                  'Capabilities',
                  Object.entries(info.capabilities)
                    .filter(([, on]) => on)
                    .map(([name]) => name)
                    .join(', '),
                ],
              ]}
            />
          ) : (
            !active.isError && <p className="text-sm text-text-muted">Loading…</p>
          )}
        </Panel>

        <Panel title="Threshold policy">
          <p className="text-xs">
            {model?.threshold != null ? (
              <>
                The label is FAIL when the calibrated P(fail) is at or above{' '}
                <span className="numeric font-semibold">{model.threshold}</span>.
              </>
            ) : (
              'The model registry does not record a threshold for this version. Each prediction carries the threshold it was labelled with (shown as “threshold” next to P(fail)).'
            )}
          </p>
          <p className="mt-2 text-xs text-text-muted">
            The predicted P(fail), the operational risk band and the anomaly status are separate outputs; the
            threshold applies to P(fail) only.
          </p>
        </Panel>

        <Panel title="Evaluation metrics">
          {otherMetrics.length > 0 ? (
            <table className="numeric w-full text-xs" aria-label="Metrics">
              <tbody>
                {otherMetrics.map(([k, v]) => (
                  <tr key={k}>
                    <td className="text-text-muted">{k}</td>
                    <td className="text-right">{metricText(v)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-text-muted">No evaluation metrics reported by the active model.</p>
          )}
          <h4 className="mt-3 mb-1 text-[11px] font-semibold tracking-widest text-text-muted uppercase">
            Calibration / reliability
          </h4>
          {calibration != null ? (
            <pre className="numeric overflow-x-auto text-xs">{JSON.stringify(calibration, null, 2)}</pre>
          ) : (
            <p className="text-sm text-text-muted">No calibration data reported by the active model.</p>
          )}
        </Panel>
      </div>

      <Panel title="Global importance">
        {global.isError && (
          <p className="text-sm text-text-muted">Global importance is unavailable: {global.error.message}</p>
        )}
        {importance.length > 0 && (
          <>
            <p className="mb-2 text-xs text-text-muted">
              Mean |SHAP| over {global.data!.n_rows} rows (computed {global.data!.computed_on}, model{' '}
              {global.data!.model_version}). Size only: how much each input moves the model&apos;s log-odds
              margin on average, in either direction.
            </p>
            <ShapBars
              unsigned
              valueName="mean |SHAP|"
              bars={importance.map((g) => ({
                key: g.feature,
                label: displayName(g.feature),
                value: g.value,
              }))}
            />
            <table className="numeric mt-3 w-full text-xs" aria-label="Global importance">
              <thead className="text-left text-text-muted">
                <tr>
                  <th className="font-normal">Feature</th>
                  <th className="text-right font-normal">Mean |SHAP|</th>
                  <th className="text-right font-normal">Stage</th>
                </tr>
              </thead>
              <tbody>
                {importance.map((g) => (
                  <tr key={g.feature}>
                    <td>{displayName(g.feature)}</td>
                    <td className="text-right">{g.value.toFixed(3)}</td>
                    <td className="text-right">{STAGE_META[g.stage as StageName]?.short ?? g.stage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {global.data && importance.length === 0 && (
          <p className="text-sm text-text-muted">The active model reports no global importance.</p>
        )}
      </Panel>

      <p
        role="note"
        aria-label="Synthetic data statement"
        className="rounded border border-border px-3 py-2 text-xs"
      >
        {STATEMENT_SYNTHETIC_DATA}
      </p>
    </div>
  )
}
