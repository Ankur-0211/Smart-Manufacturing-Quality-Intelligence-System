# Integration Status

Both roles update this file (roadmap §10.1). A capability counts as **REAL** only when
`QualityIntelligence.capabilities()` reports it **and** this table says so.

_Last updated: 2026-10-22 by Role 2 (R2-P7 done incl. P1: live slider, A/B compare, sensitivity strip, Model Info)._

## Capability matrix

| Capability | Status | Since | Notes |
|---|---|---|---|
| `run_stage` (S1–S5) | REAL | 2026-10-21 | Role 1's `RealQualityIntelligence` (heuristic stage modules, `fusion-1.0.0`). Selected with `SMQI_INTELLIGENCE_BACKEND=real`; dev/test default stays `mock` |
| `predict` | REAL | 2026-10-21 | Threshold 0.35 (in code). Open defects: label forced to FAIL on critical breaches, risk-mass sum ([CCR-004](contract_changes/CCR-004-role1-integration-findings.md) #2-#3) |
| `explain` / `global_explanation` | REAL | 2026-10-21 | Signature `explain(inp, stage_results, prediction)` (CCR-004 #8) |
| `anomaly_global` | NOT AVAILABLE | — | Not in Role 1's Protocol (CCR-004 #8) |
| `recommend` | REAL | 2026-10-21 | `POST /recommend` live 2026-10-22. Candidates show no predicted improvement (CCR-004 #7a). UI gated on the "guard tested" statement |
| `sensitivity` | REAL | 2026-10-21 | `POST /whatif/sensitivity` live 2026-10-22 |
| `spc` | NOT AVAILABLE | — | Reported as `spc_check: true` but not implemented (CCR-004 #10) |

The mock (`app/intelligence_mock`) remains available for every capability above except SPC and is the
default backend in `dev`/`test`.

Status values: `NOT AVAILABLE` → `MOCK` → `HYBRID` → `REAL`.

## Shared artifacts

| Artifact | Version | Status |
|---|---|---|
| `backend/app/contracts` | 0.1.0 | Role 1's complete set (1a22d7b), replacing the CCR-002 bootstrap. Gaps vs §9.1 in CCR-004 |
| `backend/app/domain/constraints.yaml`, `remedies.yaml` | constraints-1.0.0 / remedies-1.0.0 | Role 1. Loader `load_constraint_registry()`; limits partly in code and no lot windows (CCR-004 #5-#6) |
| `fleet.yaml` | fleet-1.0.0 | Role 1: MC-01…04, PP-JBOX-42 and PP-JBOX-42-4C, lots A-771, B-812, C-904, D-105 (wet). Seed reads it |
| Contract fixtures (`backend/tests/contract/fixtures`) | v0.2.0 | Rebuilt by Role 2 from Role 1's fleet; harness runs mock **and** real facade |
| API (`docs/openapi.json`) | api_version 1 | `/health` (with `IntelligenceVersionInfo`), `/constraints` (ETag), `/machines`, `/products`, `/materials` (GET + POST), `POST /simulation/runs`, `POST /predict`, `GET /predict/{id}/explain`, `/models`, `/models/active`, simulation queries/commands, SSE, scenario label |
| Event catalogue (`docs/events.md`) | EVENTS_VERSION 1 | Implemented and tested (R2-P4). Freeze at M4 once a real/mock executor runs end-to-end |
| DB schema | Alembic `0001` | Done (R2-P2): 10 tables, immutability guards, seed |
| Model bundles | — | R1-P4 onwards |

## Role 2 phase status

| Phase | Status |
|---|---|
| R2-P1 | Tasks 1-12 done. Completion gate waits on M1 (Role 1 approves contracts v0.1.0 + CCR-003) |
| R2-P2 | Done |
| R2-P3 | Done: reference endpoints, `POST /simulation/runs`, `/predict` (persists `run_id=NULL` rows), explain, `/models`; `npm run check:api` fails on stale TS types |
| R2-P4 | Done; runs on the mock or Role 1's real facade |
| R2-P5 | Done. Serving-model registration, global explanation, `POST /whatif` (partial re-sim via Role 1's `invalidated_stages`, diff, persisted child runs; property-tested equal to full runs), `/whatif/compare`, `/whatif/sensitivity` (rate limited), `POST /recommend` (rows per candidate with `request_id` + model version), `GET /simulation/runs/{id}/lineage`. Dev default backend is now `real`. N/A with Role 1's artifact-free facade: tiny-bundle CI and missing-bundle 503 |
| R2-P6 | Done. Run setup (pickers, registry-driven sliders, Create lot dialog, 422 mapping), RUN creates + starts + follows runs; SSE with polling fallback (hook + screen tests); pipeline, stage panel, timeline, override, result card. Handoff: `docs/screenshots/` (stepwise, real intelligence) and `docs/coordination/UI_COPY_FOR_ROLE1.md` |
| R2-P7 | Done. What-If workbench (fork a finished run, edit, Evaluate / Save as scenario, Reset to parent, §7.16 diff view) and Recommendations (locked params, max changes, option cards with guard stamp, stability, EXTRAPOLATED, cycle time, `empty_reason`, permanent disclaimer, registry step-limit cross-check, Send to What-If). Explainability panel: signed SHAP bars + table, Features/Groups toggle, stage risk mass donut + share list, caveat banner, method note, permanent DISCLAIMER_SHAP; falls back to `GET /predict/{id}/explain`. P1 done: live slider (150 ms debounce, `persist=false`, superseded requests aborted), A/B compare page (`/what-if/compare`), sensitivity strip (curve with current / flip / threshold markers, parameter ranking by `range_swing`, sensitivity ≠ SHAP note), Model Info (version, provenance, metrics, calibration, threshold policy, global importance, STATEMENT_SYNTHETIC_DATA; missing fields shown as "not reported", CCR-004 #7d). Not built: dependence plot (P1, needs a per-feature SHAP-vs-value endpoint), 2-D response surface (P2) |

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Contracts approved | Open. Role 1's contracts are integrated; waiting on CCR-003/CCR-004 answers |
| M2 | Dataset feasibility & canonical schema | Open (Role 1) |
| M3 | Mock inference operational | **Reached 2026-10-16.** Mock passes the contract harness on all 5 fixtures; simulation runs end to end (auto, stepwise, BLOCKED + override) |

## Open CCRs

| CCR | Title | Status |
|---|---|---|
| [CCR-001](contract_changes/CCR-001-route-error-codes.md) | Add `ROUTE_NOT_FOUND`, `METHOD_NOT_ALLOWED` error codes | proposed |
| [CCR-002](contract_changes/CCR-002-role2-bootstraps-contracts.md) | Role 2 bootstraps the contracts remainder / registry / fixtures | closed: superseded by Role 1's files (merged 2026-10-21) |
| [CCR-003](contract_changes/CCR-003-part1-review-notes.md) | Review notes on contracts part 1 (`flat()` keys, missing files, formatting) | proposed (questions for Role 1) |
| [CCR-004](contract_changes/CCR-004-role1-integration-findings.md) | Findings from integrating Role 1's deliverables (defects, §9.1 gaps, roadmap revert on `main`) | proposed (for Role 1) |

## Environments

| Member | OS | Python | uv | Node | npm | Last clean setup |
|---|---|---|---|---|---|---|
| Role 2 machine | Windows 11 | 3.12.10 (uv-managed) | 0.10.7 | 24.14.1 | 11.11.0 | 2026-10-15 |
| Role 1 machine | — | — | — | — | — | — |

## Blockers

- None for Role 2. Role 1: please work through CCR-003 and CCR-004, and restore roadmap 1.0.1 on `main`.
