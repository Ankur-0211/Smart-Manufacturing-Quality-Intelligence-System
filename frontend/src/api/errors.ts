/**
 * Stable API error codes (roadmap 9.3.4). Mirrors `ErrorCode` in backend/app/api/errors.py.
 * Adding a code is a MINOR contract change; renaming or removing one is MAJOR.
 */
export const ERROR_CODES = [
  'VALIDATION_ERROR',
  'PARAM_OUT_OF_RANGE',
  'COUPLING_VIOLATION',
  'UNKNOWN_PARAMETER',
  'PARAMETER_NOT_ACTIONABLE',
  'REFERENCE_NOT_FOUND',
  'RUN_NOT_FOUND',
  'PREDICTION_NOT_FOUND',
  'INVALID_STATE_TRANSITION',
  'RUN_IMMUTABLE',
  'STAGE_RESULTS_INCOMPLETE',
  'MODEL_NOT_LOADED',
  'MODEL_ARTIFACT_INVALID',
  'FEATURE_SCHEMA_MISMATCH',
  'CAPABILITY_UNAVAILABLE',
  'UPSTREAM_CONTEXT_MISSING',
  'INVALID_INTELLIGENCE_INPUT',
  'REGISTRY_INVALID',
  'RATE_LIMITED',
  'UNAUTHORIZED',
  'PAYLOAD_TOO_LARGE',
  'INTERNAL_ERROR',
  // CCR-001 (proposed, additive)
  'ROUTE_NOT_FOUND',
  'METHOD_NOT_ALLOWED',
] as const

export type ErrorCode = (typeof ERROR_CODES)[number]

/** Client-side codes for failures that never reached the API envelope. */
export type ClientErrorCode = 'NETWORK_ERROR' | 'INVALID_RESPONSE'

const MESSAGES: Record<ErrorCode, string> = {
  VALIDATION_ERROR: 'Some values are invalid.',
  PARAM_OUT_OF_RANGE: 'A parameter is outside its admissible window.',
  COUPLING_VIOLATION: 'Parameters violate a coupling rule.',
  UNKNOWN_PARAMETER: 'An unknown parameter was sent.',
  PARAMETER_NOT_ACTIONABLE: 'This parameter cannot be changed by the operator.',
  REFERENCE_NOT_FOUND: 'Machine, product or material lot not found.',
  RUN_NOT_FOUND: 'Simulation run not found.',
  PREDICTION_NOT_FOUND: 'Prediction not found.',
  INVALID_STATE_TRANSITION: 'That action is not allowed in the current run state.',
  RUN_IMMUTABLE: 'Completed runs cannot be changed. Re-run as a new run instead.',
  STAGE_RESULTS_INCOMPLETE: 'All five stages must complete before quality inspection.',
  MODEL_NOT_LOADED: 'The quality model is not loaded.',
  MODEL_ARTIFACT_INVALID: 'The model artifacts failed verification.',
  FEATURE_SCHEMA_MISMATCH: 'Model feature schema mismatch.',
  CAPABILITY_UNAVAILABLE: 'This capability is not available yet.',
  UPSTREAM_CONTEXT_MISSING: 'Internal stage-sequencing error.',
  INVALID_INTELLIGENCE_INPUT: 'The intelligence layer rejected the input.',
  REGISTRY_INVALID: 'The constraint registry is invalid.',
  RATE_LIMITED: 'Too many requests. Please wait a moment.',
  UNAUTHORIZED: 'Missing or invalid API key.',
  PAYLOAD_TOO_LARGE: 'The upload is too large.',
  INTERNAL_ERROR: 'Unexpected server error.',
  ROUTE_NOT_FOUND: 'API route not found.',
  METHOD_NOT_ALLOWED: 'Method not allowed.',
}

export function isErrorCode(value: unknown): value is ErrorCode {
  return typeof value === 'string' && (ERROR_CODES as readonly string[]).includes(value)
}

export function messageForCode(code: string): string {
  return isErrorCode(code) ? MESSAGES[code] : 'Unexpected error.'
}
