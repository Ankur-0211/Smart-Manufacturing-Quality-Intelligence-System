import type { Constraints } from '@/api/constraints'
import type { RunDiff } from '@/api/whatif'
import { unitLabel } from '@/components/params/recipeValidation'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import { STAGE_META, type RiskLevel, type StageName } from '@/features/process-control/model'
import { cn } from '@/lib/utils'

const CHANGE_STYLE = {
  improved: 'text-risk-normal',
  worsened: 'text-risk-critical',
  unchanged: 'text-text-muted',
} as const

function signed(value: number, digits = 3): string {
  const text = value.toFixed(digits)
  return value > 0 ? `+${text}` : text
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section aria-label={title} className="rounded border border-border bg-panel-raised p-3">
      <h4 className="mb-2 text-[11px] font-semibold tracking-widest text-text-muted uppercase">{title}</h4>
      {children}
    </section>
  )
}

/**
 * What-if diff (Plan §13.6, roadmap 7.16): parameters, stages, prediction, operational risk,
 * constraint compliance and cycle time. Every number is the server's diff; nothing is recomputed.
 */
export function DiffView({
  diff,
  constraints,
  recomputed,
  reused,
}: {
  diff: RunDiff
  constraints?: Constraints
  recomputed: string[]
  reused: string[]
}) {
  const spec = (name: string) => constraints?.parameters.find((p) => p.name === name)
  const p = diff.prediction
  const risk = diff.operational_risk
  const compliance = diff.constraint_compliance
  const cycle = diff.cycle_time
  return (
    <div className="flex flex-col gap-3" aria-label="What-if diff">
      <Section title="Model-predicted failure probability">
        <p className="numeric text-lg">
          {p.p_fail_from.toFixed(2)} → <span className="font-semibold">{p.p_fail_to.toFixed(2)}</span>{' '}
          <span
            className={cn(
              'text-sm',
              p.p_fail_delta < 0
                ? 'text-risk-normal'
                : p.p_fail_delta > 0
                  ? 'text-risk-critical'
                  : 'text-text-muted',
            )}
          >
            (Δ {signed(p.p_fail_delta)})
          </span>
        </p>
        <p className="text-sm">
          Label {p.label_from} → {p.label_to}
          {p.flipped && (
            <span className="ml-2 rounded border border-state-active px-1 text-xs font-semibold text-state-active">
              FLIPPED
            </span>
          )}
        </p>
      </Section>

      <Section title="Operational risk">
        <p className="text-sm">
          <span className={RISK_TEXT[risk.from as RiskLevel]}>{risk.from}</span> →{' '}
          <span className={RISK_TEXT[risk.to as RiskLevel]}>{risk.to}</span>{' '}
          <span className="ml-1 text-xs text-text-muted">
            (
            {risk.band_delta === 0 ? 'same band' : `${risk.band_delta > 0 ? '+' : ''}${risk.band_delta} band`}
            )
          </span>
        </p>
      </Section>

      <Section title="Parameters changed">
        <table className="numeric w-full text-xs">
          <thead className="text-left text-text-muted">
            <tr>
              <th className="font-normal">Parameter</th>
              <th className="text-right font-normal">Base</th>
              <th className="text-right font-normal">What-if</th>
              <th className="text-right font-normal">Δ</th>
            </tr>
          </thead>
          <tbody>
            {diff.parameters.map((row) => {
              const s = spec(row.name)
              const unit = unitLabel(s?.unit)
              return (
                <tr key={row.name}>
                  <td>{s?.display_name ?? row.name}</td>
                  <td className="text-right">{row.from}</td>
                  <td className="text-right">{row.to}</td>
                  <td className="text-right">
                    {signed(row.delta, 2)}
                    {unit ? ` ${unit}` : ''}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Section>

      <Section title="Stages">
        <p className="mb-2 text-xs text-text-muted">
          Recomputed:{' '}
          {recomputed.length ? recomputed.map((s) => STAGE_META[s as StageName].short).join(', ') : 'none'}.{' '}
          Reused from the base run:{' '}
          {reused.length ? reused.map((s) => STAGE_META[s as StageName].short).join(', ') : 'none'}.
        </p>
        <table className="numeric w-full text-xs">
          <thead className="text-left text-text-muted">
            <tr>
              <th className="font-normal">Stage</th>
              <th className="text-right font-normal">Health</th>
              <th className="text-right font-normal">Risk</th>
              <th className="text-right font-normal">Change</th>
            </tr>
          </thead>
          <tbody>
            {diff.stages.map((row) => (
              <tr key={row.stage} aria-label={`${row.stage} ${row.change}`}>
                <td>{STAGE_META[row.stage as StageName]?.long ?? row.stage}</td>
                <td className="text-right">
                  {row.health_from.toFixed(2)} → {row.health_to.toFixed(2)}
                </td>
                <td className="text-right">
                  <span className={RISK_TEXT[row.risk_from as RiskLevel]}>{row.risk_from}</span> →{' '}
                  <span className={RISK_TEXT[row.risk_to as RiskLevel]}>{row.risk_to}</span>
                </td>
                <td className={cn('text-right', CHANGE_STYLE[row.change])}>{row.change}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <div className="grid gap-3 md:grid-cols-2">
        <Section title="Constraint compliance">
          <p className="numeric text-xs">
            Warnings {compliance.warnings_from} → {compliance.warnings_to}
            <br />
            Critical {compliance.critical_from} → {compliance.critical_to}
          </p>
        </Section>
        <Section title="Cycle time">
          <p className="numeric text-xs">
            {cycle.from} s → {cycle.to} s (Δ {signed(cycle.delta_s, 1)} s, {signed(cycle.delta_pct, 1)} %)
          </p>
        </Section>
      </div>
    </div>
  )
}
