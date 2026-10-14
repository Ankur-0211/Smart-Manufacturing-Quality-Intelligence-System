import { isMockIntelligence, useHealth } from '@/api/health'
import { DISCLAIMER_SIMULATION, MOCK_BANNER_TEXT } from '@/lib/disclaimers'

/** Persistent red banner whenever mock/hybrid intelligence may be producing outputs (roadmap 9.2). */
export function MockBanner() {
  const { data } = useHealth()
  if (!isMockIntelligence(data)) return null
  return (
    <div
      role="alert"
      className="bg-mock px-4 py-1.5 text-center text-sm font-semibold tracking-wide text-white"
    >
      {MOCK_BANNER_TEXT}{' '}
      <span className="font-normal opacity-80">(backend: {data?.intelligence_backend})</span>
    </div>
  )
}

/** API reachability / degraded components indicator for the header. */
export function ApiStatus() {
  const { data, isError, isPending } = useHealth()
  let label = 'API: connecting'
  let tone = 'text-text-muted'
  if (isError) {
    label = 'API: unreachable'
    tone = 'text-risk-critical'
  } else if (!isPending && data) {
    label = data.status === 'ok' ? 'API: ok' : 'API: degraded'
    tone = data.status === 'ok' ? 'text-risk-normal' : 'text-risk-medium'
  }
  const degraded = data?.components.filter((c) => !c.available).map((c) => c.name) ?? []
  return (
    <span
      className={`numeric text-xs ${tone}`}
      title={degraded.length ? `Unavailable: ${degraded.join(', ')}` : undefined}
    >
      {label}
    </span>
  )
}

/** Permanent software-simulation disclaimer (roadmap 1.7). */
export function SimulationDisclaimer() {
  return (
    <footer className="border-t border-border bg-panel px-4 py-2 text-xs leading-snug text-text-muted">
      {DISCLAIMER_SIMULATION}
    </footer>
  )
}
