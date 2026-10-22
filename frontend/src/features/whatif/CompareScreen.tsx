import { Link, useSearchParams } from 'react-router-dom'

import { ApiClientError } from '@/api/client'
import { useConstraints } from '@/api/constraints'
import { useCompare } from '@/api/whatif'

import { DiffView } from './DiffView'
import { FinishedRunPicker } from './FinishedRunPicker'

/**
 * Scenario A/B compare (roadmap R2-P7 task 3, P1): the §7.16 diff between any two finished runs
 * from POST /whatif/compare. A is the reference; every Δ reads A → B.
 */
export function CompareScreen() {
  const [params, setParams] = useSearchParams()
  const a = params.get('a')
  const b = params.get('b')
  const constraints = useConstraints().data
  const compare = useCompare(a, b)

  const set = (key: 'a' | 'b', id: string) => {
    const next = new URLSearchParams(params)
    next.set(key, id)
    setParams(next)
  }
  const swap = () => {
    const next = new URLSearchParams()
    if (b) next.set('a', b)
    if (a) next.set('b', a)
    setParams(next)
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold tracking-widest text-text-muted uppercase">A/B compare</h2>
        <Link to={a ? `/what-if?base=${a}` : '/what-if'} className="text-xs text-state-active">
          Back to the workbench
        </Link>
      </div>

      <section
        aria-label="Runs to compare"
        className="flex flex-wrap items-end gap-3 rounded border border-border bg-panel px-4 py-3"
      >
        <FinishedRunPicker label="Run A (reference)" value={a} onChange={(id) => set('a', id)} />
        <button
          type="button"
          onClick={swap}
          disabled={!a && !b}
          className="rounded border border-border px-2 py-1 text-xs text-text hover:bg-panel-raised disabled:opacity-40"
        >
          Swap A ⇄ B
        </button>
        <FinishedRunPicker label="Run B" value={b} onChange={(id) => set('b', id)} />
      </section>

      {(!a || !b) && <p className="text-sm text-text-muted">Choose two finished runs to compare.</p>}
      {a && b && a === b && <p className="text-sm text-text-muted">Choose two different runs.</p>}
      {compare.isPending && compare.fetchStatus === 'fetching' && (
        <p className="text-sm text-text-muted">Comparing…</p>
      )}
      {compare.isError && (
        <p role="alert" className="text-sm text-risk-critical">
          {compare.error instanceof ApiClientError ? `${compare.error.code}: ` : ''}
          {compare.error.message}
        </p>
      )}
      {compare.data && (
        <section aria-label="Comparison" className="rounded border border-border bg-panel p-4">
          <p className="mb-3 text-xs text-text-muted">
            <Link to={`/history/${a}`} className="text-state-active">
              A {a!.slice(0, 8)}
            </Link>{' '}
            →{' '}
            <Link to={`/history/${b}`} className="text-state-active">
              B {b!.slice(0, 8)}
            </Link>
            . Machine, product and lot can differ between the two runs; the diff covers parameters and
            outcomes.
          </p>
          <DiffView diff={compare.data} constraints={constraints} columns={{ from: 'A', to: 'B' }} />
        </section>
      )}
    </div>
  )
}
