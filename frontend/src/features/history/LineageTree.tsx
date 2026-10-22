import { Link } from 'react-router-dom'

import { useLineage, type LineageNode } from '@/api/runs'
import { RISK_TEXT } from '@/components/pipeline/stateStyle'
import type { RiskLevel } from '@/features/process-control/model'
import { cn } from '@/lib/utils'

function Node({
  node,
  currentId,
  parentId,
  depth,
}: {
  node: LineageNode
  currentId: string
  parentId: string | null
  depth: number
}) {
  const run = node.run
  const current = run.run_id === currentId
  return (
    <li
      role="treeitem"
      aria-level={depth + 1}
      aria-current={current ? 'true' : undefined}
      aria-expanded={node.children.length ? true : undefined}
      aria-selected={current}
    >
      <div
        className={cn(
          'numeric flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded px-2 py-1 text-xs',
          current && 'bg-panel-raised',
        )}
      >
        {current ? (
          <span className="font-semibold">{run.run_id.slice(0, 8)} (this run)</span>
        ) : (
          <Link to={`/history/${run.run_id}`} className="text-state-active">
            {run.run_id.slice(0, 8)}
          </Link>
        )}
        <span className="text-text-muted">{run.is_whatif ? 'what-if' : 'root'}</span>
        {run.scenario_label && <span>“{run.scenario_label}”</span>}
        {run.p_fail != null ? (
          <span>
            P(fail) {run.p_fail.toFixed(2)} {run.label}
          </span>
        ) : (
          <span className="text-text-muted">{run.status}</span>
        )}
        {run.risk_level && <span className={RISK_TEXT[run.risk_level as RiskLevel]}>{run.risk_level}</span>}
        {run.model_version && <span className="text-text-muted">{run.model_version}</span>}
        {parentId && (
          <Link to={`/what-if/compare?a=${parentId}&b=${run.run_id}`} className="text-state-active">
            Compare with parent
          </Link>
        )}
      </div>
      {node.children.length > 0 && (
        <ul role="group" className="ml-4 border-l border-border pl-2">
          {node.children.map((child) => (
            <Node
              key={child.run.run_id}
              node={child}
              currentId={currentId}
              parentId={run.run_id}
              depth={depth + 1}
            />
          ))}
        </ul>
      )}
    </li>
  )
}

/**
 * What-if lineage (roadmap R2-P8 task 2, P1): the tree from the root run down through every
 * saved what-if, with this run highlighted. Numbers are each run's stored prediction.
 */
export function LineageTree({ runId }: { runId: string }) {
  const lineage = useLineage(runId)
  if (lineage.isPending) return <p className="text-xs text-text-muted">Loading lineage…</p>
  if (lineage.isError) {
    return (
      <p role="alert" className="text-xs text-risk-critical">
        Lineage unavailable: {lineage.error.message}
      </p>
    )
  }
  const { tree } = lineage.data
  if (tree.children.length === 0) {
    return <p className="text-xs text-text-muted">No what-if scenarios branch from this run yet.</p>
  }
  return (
    <ul role="tree" aria-label="Lineage" className="flex flex-col gap-1">
      <Node node={tree} currentId={runId} parentId={null} depth={0} />
    </ul>
  )
}
