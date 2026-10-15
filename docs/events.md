# Simulation engine, events and SSE (R2-P4)

The contract is roadmap §9.5. This file records the implementation. `EVENTS_VERSION = "1"`
(`backend/app/engine/events.py`).

## Components

| Module | Role |
|---|---|
| `engine/state_machine.py` | Pure transition table (`transition(state, command)`). Exhaustively tested: 11 statuses × 10 commands × 2 modes |
| `engine/cache.py` | In-process LRU of stage results. Key = SHA-256 of canonical JSON of (stage, input slice, upstream context, module version, constraints version). Numbers are normalised (`12` ≡ `12.0`), booleans are not |
| `engine/events.py` | Envelope builder, `EventBus` (per-run asyncio queues), SSE framing |
| `engine/ports.py` | `StageExecutor`, the engine's only route to intelligence (JSON in/out). Bound to the mock/real `QualityIntelligence` once `app.contracts` exists. Until then commands return **501 `CAPABILITY_UNAVAILABLE`** |
| `services/simulation_service.py` | Orchestration: auto/stepwise, pause/resume, block/override, reset, abort, errors, restart recovery |
| `api/sse.py`, `api/routes_simulation.py` | HTTP surface |

## Lifecycle rules as implemented

- **Persist-then-publish.** The state change, stage result/prediction rows and events of one step
  are committed in **one transaction**, then published. `seq` is gap-free per run.
- **Locking.** One `asyncio.Lock` per run serialises steps and commands. PAUSE waits for the
  current stage to finish. RESET/ABORT take the lock before cancelling the run task, so nothing
  commits after a reset.
- **Stage step.** `stage.started` → (cache or `executor.run_stage`) → presentation delay →
  `anomaly.flagged`* → `constraint.breached`* → `stage.completed`. The completion event carries
  the StageResult plus `presentation_ms` and `cache_hit`. `upstream_out` of stage *k* is passed
  unchanged as the upstream context of stage *k+1*.
- **BLOCKED.** If `result.blocked` and `halt_on_critical`, the run stops in `BLOCKED`. The pending
  result travels in the persisted `stage.blocked` event and is **not** written to `stage_results`,
  because rows are immutable. `POST …/override` writes it with `overridden=true`, increments
  `override_count`, then emits `stage.override_acknowledged` followed by `stage.completed`.
  With `halt_on_critical=false` the blocked result completes normally (`blocked=true`,
  `overridden=false`).
- **Quality stage.** `stage.started(QUALITY_INSPECTION)` → `executor.predict(process_input,
  stage_results)` → prediction row (model version resolved from `"<name>-<semver>"`) →
  `prediction.ready` → `run.completed`.
- **Timing.** Delay = `SMQI_STAGE_PRESENTATION_MS × {0.5x: 2, 1x: 1, 2x: 0.5, instant: 0}`. This
  is presentation time, never process time (Plan §7.4).
- **Errors.** Any executor exception → `run.error` + `run.aborted`
  (`abort_reason = ERROR:INTERNAL_ERROR`).
- **Restart recovery.** At startup (DB migrated), runs that were started but not finished →
  `ABORTED` (`SERVER_RESTART`) plus a `run.aborted` event. Completed stage rows stay inspectable.

## SSE (`GET /api/v1/simulation/runs/{id}/events`)

- Order: subscribe live → replay persisted events with `seq > Last-Event-ID` → stream live events,
  skipping duplicates and filling gaps from the DB.
- Frame: `id: <seq>`, `event: <type>`, `data: <single-line JSON envelope>`, blank line.
  `: keepalive` comments every 15 s while idle.
- Headers: `Cache-Control: no-cache`, `X-Accel-Buffering: no`.
- The stream closes after `run.completed` / `run.aborted`, or straight after replay if the run is
  already finished.
- Clients re-sync with `GET /simulation/runs/{id}` (it includes `last_seq` and the full timeline)
  and fall back to polling. The frontend hook already does this.

## Envelope

```json
{"run_id": "…", "seq": 7, "ts": "2026-10-15T12:04:06.120Z", "type": "stage.completed",
 "stage": "PLASTICIZING", "payload": { … }}
```

Event types: `run.started`, `stage.started`, `stage.progress` (reserved), `stage.completed`,
`anomaly.flagged`, `constraint.breached`, `stage.blocked`, `stage.override_acknowledged`,
`prediction.ready`, `run.completed`, `run.paused`, `run.resumed`, `run.reset`, `run.aborted`,
`run.error`.
