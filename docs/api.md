# API

Contract source: roadmap §9.3. Machine-readable snapshot: [`openapi.json`](openapi.json),
regenerated with `scripts/gen_api_types.(sh|ps1)`.

## Conventions

- Base path: `/api/v1`.
- Envelope: `{"data", "error", "meta": {"request_id", "latency_ms", "api_version", "contracts_version", "total"}}`.
- `X-Request-ID`: accepted when it matches `[A-Za-z0-9._:-]{1,128}`, otherwise generated. It is
  always echoed in the response header and in `meta.request_id`.
- `X-API-Key`: required on every route except `/health`, only when `SMQI_API_KEY` is set.
- CORS: limited to `SMQI_CORS_ORIGINS`.

## Implemented endpoints

| Method | Path | Phase | Notes |
|---|---|---|---|
| GET | `/health` | R2-P1 | Per-component availability. `status` is `degraded` while any component is missing |
| GET | `/simulation/runs` | R2-P4 | History with filters (`machine_id`, `product_id`, `material_lot_id`, `label`, `risk_level`, `is_whatif`, `inference_backend`, `from`, `to`), `limit`/`offset`, `meta.total` |
| GET | `/simulation/runs/{id}` | R2-P4 | Full SimulationState incl. `timeline` and `last_seq` (polling / re-sync) |
| GET | `/simulation/runs/{id}/stages/{stage}` | R2-P4 | One stage result |
| GET | `/simulation/runs/{id}/events` | R2-P4 | SSE (see `events.md`) |
| POST | `/simulation/runs/{id}/start` `{mode, speed_factor}` | R2-P4 | 501 `CAPABILITY_UNAVAILABLE` until intelligence is bound |
| POST | `/simulation/runs/{id}/advance` | R2-P4 | Stepwise: exactly one stage |
| POST | `/simulation/runs/{id}/pause`, `/resume` | R2-P4 | Auto mode only |
| POST | `/simulation/runs/{id}/reset` | R2-P4 | Non-finished runs only (finished → 409 `RUN_IMMUTABLE`) |
| POST | `/simulation/runs/{id}/abort` `{reason?}` | R2-P4 | |
| POST | `/simulation/runs/{id}/override` `{stage, acknowledgement}` | R2-P4 | From BLOCKED |
| PATCH | `/simulation/runs/{id}/label` `{scenario_label}` | R2-P4 | Save scenario (allowed on finished runs) |

`POST /simulation/runs` (create) follows with recipe validation once the contracts and the
registry loader are in (R2-P1 tasks 9–10 / R2-P3).

Expensive endpoints (`/recommend`, `/whatif/sensitivity`, when added) use the in-process token
bucket in `api/rate_limit.py` (`SMQI_RATE_LIMIT_PER_MIN`, per client and endpoint) → 429
`RATE_LIMITED`.

## Analytics (R2-P8)

Handoff for the report (roadmap R2-P8 §12). Every number is an SQL aggregation over stored runs
(`backend/app/services/analytics_service.py`); nothing is synthesised.

**Scope (all endpoints):**
- `include_whatif` (default `false`): what-if children (`process_runs.is_whatif`).
- `include_mock` (default `false`): runs whose prediction, or failing that the run itself, records `inference_backend = 'mock'`.
- `include_unfinished` (default `false`): runs whose status is not `FINAL_RESULT` (blocked, aborted, still running).
- `from` / `to`: `process_runs.created_at` range (inclusive).

**Definitions:**
- `runs`: runs in scope. `with_prediction`: those with a stored prediction.
- `predicted_fail`: runs whose prediction label is `FAIL`. `predicted_fail_rate` = `predicted_fail / with_prediction` (null when 0). This is the **model's predicted** FAIL share, not an observed defect rate.
- `mean_p_fail`: mean calibrated P(fail) over runs with a prediction.
- `not_releasable`: predictions with `constraint_override_applied` (an overridden critical breach, UD-07).
- `excluded`: for each active exclusion, how many runs in the date range it removes (counted separately; one run can fall under several).
- `stage_risk_frequency`: stage results of in-scope runs, counted per stage and risk level.
- `runs_over_time`: the outcome fields per calendar day (UTC) of `created_at`.

| Method | Path | Returns |
|---|---|---|
| GET | `/analytics/summary` | Totals, `excluded`, `risk_levels` (operational risk of each prediction), `not_releasable`, `stage_risk_frequency`, `runs_over_time` |
| GET | `/analytics/by-machine` | Outcome per machine code |
| GET | `/analytics/by-material?group=lot\|resin_grade` | Outcome per lot code or resin grade |
| GET | `/analytics/by-parameter?parameter=&buckets=2..20` | Outcome per equal-width bucket over the parameter's **registry window** (`min`–`max` from `constraints.yaml`); the last bucket includes `max`. Unknown parameter → 422 `UNKNOWN_PARAMETER` |
| GET | `/analytics/spc?machine_id=&parameter=&limit=` | The parameter's stored values on one machine, oldest first. `spc.available` is `false` and `alerts` is `null` until Role 1 delivers `spc_check` (CCR-004 #10); Role 2 does not implement SPC rules |

## Error codes

These are the roadmap §9.3.4 codes plus CCR-001 (proposed). The HTTP status comes from
`DEFAULT_STATUS` in `backend/app/api/errors.py`.

**Validation mapping (Pydantic → envelope):**

| Pydantic error type | Detail code |
|---|---|
| `greater_than*`, `less_than*` | `PARAM_OUT_OF_RANGE` (with `limit` and `value`) |
| `extra_forbidden` | `UNKNOWN_PARAMETER` |
| anything else | `VALIDATION_ERROR` |

The top-level `code` is `PARAM_OUT_OF_RANGE` or `UNKNOWN_PARAMETER` when every detail shares
that code. Otherwise it is `VALIDATION_ERROR`.

Unhandled exceptions return `500 INTERNAL_ERROR` with a hint to quote the `request_id`. Stack
traces are never returned to the client.
