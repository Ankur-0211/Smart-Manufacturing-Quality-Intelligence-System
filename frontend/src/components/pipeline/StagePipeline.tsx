import { motion, useReducedMotion } from 'framer-motion'

import {
  STAGE_META,
  STAGE_ORDER,
  type PredictionView,
  type StageName,
} from '@/features/process-control/model'
import type { StageView } from '@/features/process-control/runReducer'
import { cn } from '@/lib/utils'

import { RISK_FILL, STATE_GLYPH, strokeFor } from './stateStyle'

const W = 960
const H = 150
const NODE_W = 128
const NODE_H = 100
const TOP = 30
const GAP = (W - STAGE_ORDER.length * NODE_W) / (STAGE_ORDER.length - 1)

interface StagePipelineProps {
  stages: Record<StageName, StageView>
  prediction: PredictionView | null
  onSelectStage?: (stage: StageName) => void
  selectedStage?: StageName | null
}

interface NodeText {
  value: string
  status: string
  aria: string
}

function describe(name: StageName, view: StageView, prediction: PredictionView | null): NodeText {
  const label = STAGE_META[name].long
  const anomaly = view.anomaly ? ', anomaly flagged' : ''
  const overridden = view.overridden ? ', critical breach overridden' : ''

  if (name === 'QUALITY_INSPECTION' && prediction) {
    const verdict = prediction.constraint_override_applied ? 'NOT RELEASABLE' : prediction.label
    return {
      value: `P ${prediction.p_fail.toFixed(2)}`,
      status: prediction.constraint_override_applied ? 'NOT REL.' : prediction.label,
      aria: `${label}: ${verdict}, predicted failure probability ${prediction.p_fail.toFixed(2)}, operational risk ${prediction.risk_level}`,
    }
  }
  switch (view.state) {
    case 'PENDING':
      return { value: '—', status: 'PENDING', aria: `${label}: pending` }
    case 'ACTIVE':
      return { value: '…', status: 'ACTIVE', aria: `${label}: active${anomaly}` }
    case 'BLOCKED':
      return {
        value: view.result ? view.result.health_score.toFixed(2) : '—',
        status: 'BLOCKED',
        aria: `${label}: blocked by a critical constraint breach${anomaly}`,
      }
    case 'COMPLETED': {
      const health = view.result?.health_score
      const risk = view.result?.risk_level ?? 'NORMAL'
      return {
        value: health === undefined ? '—' : health.toFixed(2),
        status: risk,
        aria: `${label}: completed, health ${health?.toFixed(2) ?? 'unknown'}, risk ${risk}${anomaly}${overridden}`,
      }
    }
  }
}

/** Horizontal six-stage process pipeline (Plan §15.2). Hand-built SVG, no graph library. */
export function StagePipeline({ stages, prediction, onSelectStage, selectedStage }: StagePipelineProps) {
  const reduceMotion = useReducedMotion()

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="h-auto w-full select-none"
      role="list"
      aria-label="Process stages"
    >
      {STAGE_ORDER.slice(0, -1).map((name, i) => {
        const next = STAGE_ORDER[i + 1]!
        const reached = stages[next].state !== 'PENDING'
        const x1 = i * (NODE_W + GAP) + NODE_W
        const y = TOP + NODE_H / 2
        return (
          <line
            key={`c-${name}`}
            x1={x1}
            y1={y}
            x2={x1 + GAP}
            y2={y}
            aria-hidden="true"
            className={cn('stroke-[3]', reached ? 'stroke-state-active' : 'stroke-border')}
            strokeDasharray={reached ? undefined : '4 4'}
          />
        )
      })}

      {STAGE_ORDER.map((name, i) => {
        const view = stages[name]
        const x = i * (NODE_W + GAP)
        const risk =
          name === 'QUALITY_INSPECTION' ? (prediction?.risk_level ?? null) : (view.result?.risk_level ?? null)
        const text = describe(name, view, prediction)
        const stroke = strokeFor(view.state, risk)
        const selected = selectedStage === name
        const interactive = Boolean(onSelectStage)

        return (
          <g
            key={name}
            role="listitem"
            aria-label={text.aria}
            data-stage={name}
            data-state={view.state}
            transform={`translate(${x}, ${TOP})`}
            className={cn(interactive && 'cursor-pointer')}
            onClick={interactive ? () => onSelectStage?.(name) : undefined}
          >
            <motion.rect
              width={NODE_W}
              height={NODE_H}
              rx={8}
              className={cn('fill-panel-raised stroke-2', stroke)}
              strokeDasharray={view.state === 'BLOCKED' ? '6 3' : undefined}
              animate={view.state === 'ACTIVE' && !reduceMotion ? { opacity: [1, 0.55, 1] } : { opacity: 1 }}
              transition={
                view.state === 'ACTIVE' && !reduceMotion
                  ? { duration: 1.2, repeat: Infinity, ease: 'easeInOut' }
                  : { duration: 0.2 }
              }
            />
            {selected && (
              <rect
                x={-4}
                y={-4}
                width={NODE_W + 8}
                height={NODE_H + 8}
                rx={10}
                className="fill-none stroke-text-muted"
                strokeDasharray="2 3"
                aria-hidden="true"
              />
            )}
            <text x={10} y={20} className="fill-text-muted text-[11px] font-semibold tracking-widest">
              {STAGE_META[name].short.toUpperCase()}
            </text>
            <text x={NODE_W - 10} y={20} textAnchor="end" className="fill-text-muted font-mono text-[11px]">
              {STATE_GLYPH[view.state]}
            </text>
            <text x={10} y={56} className="numeric fill-text text-[22px]">
              {text.value}
            </text>
            <text
              x={10}
              y={84}
              className={cn(
                'text-[12px] font-semibold tracking-wide',
                view.state === 'BLOCKED'
                  ? 'fill-blocked'
                  : view.state === 'ACTIVE'
                    ? 'fill-state-active'
                    : risk && (view.state === 'COMPLETED' || name === 'QUALITY_INSPECTION')
                      ? RISK_FILL[risk]
                      : 'fill-text-muted',
              )}
            >
              {text.status}
            </text>
            {view.anomaly && (
              <g transform={`translate(${NODE_W - 2}, -6)`} aria-hidden="true">
                <circle r={11} className="fill-anomaly" />
                <text textAnchor="middle" y={4} className="fill-white text-[13px] font-bold">
                  !
                </text>
              </g>
            )}
            {view.overridden && (
              <text x={NODE_W / 2} y={NODE_H + 16} textAnchor="middle" className="fill-blocked text-[10px]">
                overridden
              </text>
            )}
          </g>
        )
      })}
    </svg>
  )
}
