import type { RiskLevel } from '@/features/process-control/model'
import type { StageVisualState } from '@/features/process-control/runReducer'

/**
 * Visual state language (Plan §15.4). Colour is never the only carrier of meaning:
 * every state also has a glyph and a text label.
 */
export const STATE_GLYPH: Record<StageVisualState, string> = {
  PENDING: '[ ]',
  ACTIVE: '[*]',
  COMPLETED: '[X]',
  BLOCKED: '[/]',
}

export const RISK_STROKE: Record<RiskLevel, string> = {
  NORMAL: 'stroke-risk-normal',
  LOW: 'stroke-risk-low',
  MEDIUM: 'stroke-risk-medium',
  HIGH: 'stroke-risk-high',
  CRITICAL: 'stroke-risk-critical',
}

export const RISK_TEXT: Record<RiskLevel, string> = {
  NORMAL: 'text-risk-normal',
  LOW: 'text-risk-low',
  MEDIUM: 'text-risk-medium',
  HIGH: 'text-risk-high',
  CRITICAL: 'text-risk-critical',
}

export const RISK_FILL: Record<RiskLevel, string> = {
  NORMAL: 'fill-risk-normal',
  LOW: 'fill-risk-low',
  MEDIUM: 'fill-risk-medium',
  HIGH: 'fill-risk-high',
  CRITICAL: 'fill-risk-critical',
}

export function strokeFor(state: StageVisualState, risk: RiskLevel | null): string {
  if (state === 'BLOCKED') return 'stroke-blocked'
  if (state === 'ACTIVE') return 'stroke-state-active'
  if (state === 'COMPLETED' && risk) return RISK_STROKE[risk]
  return 'stroke-state-pending'
}
