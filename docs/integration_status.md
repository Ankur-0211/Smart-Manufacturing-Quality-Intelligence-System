# Integration Status

Both roles update this file (roadmap §10.1). A capability counts as **REAL** only when
`QualityIntelligence.capabilities()` reports it **and** this table says so.

_Last updated: 2026-10-22 by Role 2 (R2-P9: single-process deployment, clean-clone check, benchmarks)._

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
| R2-P8 | Done (P0 + P1). History list, filters, run detail, scenario label; lineage tree on run detail (climbs to the root, links each scenario and "Compare with parent"); `/analytics/summary`, `/by-machine`, `/by-material`, `/by-parameter` (registry-window buckets), `/spc` (stored series; alerts wait on Role 1's `spc_check`, CCR-004 #10); Analytics screen with stated exclusions, toggles, date range, empty and few-runs states. Definitions in `docs/api.md`. Model metrics are on Model Info (R2-P7). Not built: batch CSV scoring (P2) |
| R2-P9 | Role 2's P0 work done; **2 items wait on others**. Done: the API serves `frontend/dist` at `/` (SPA fallback, `/api` keeps its envelope, no path traversal); production build calls same-origin `/api/v1`; startup log lists contracts, capabilities, constraints, DB revision and frontend; charts code-split (main chunk 943 → 545 kB); configuration audit (`SMQI_FRONTEND_DIST` added to `.env.example`); clean-clone run-through (below); `scripts/benchmark.py`, all §24.4 budgets met; `docs/deployment.md`, `docs/troubleshooting.md`; README check list fixed (`ruff format`, not `black`). Waiting: (1) the clean-machine run on **Role 1's machine** (task 3), (2) Role 1's model archive: their `fusion-1.0.0` loads no bundle, so MANIFEST verification and the missing-bundle failure test can't be done yet (task 1). Not built: Docker Compose and CI (P2) |

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
| Role 2 machine | Windows 11 | 3.12.10 (uv-managed) | 0.10.7 | 24.14.1 | 11.11.0 | 2026-10-22 (fresh clone, see setup log) |
| Role 1 machine | — | — | — | — | — | — |

## Setup log (R2-P9)

**2026-10-22, Role 2 machine** (Windows 11, uv 0.10.7, Node 24.14.1). This was a fresh `git clone` of `role-2-application` (`7a12ddd`) into an empty folder, following the README only (`deployment.md` was written from this run):

| Step | Result |
|---|---|
| `uv sync --frozen` | OK, 8 s (warm uv cache) |
| `alembic upgrade head` | OK, revision `0001` |
| `python -m app.db.seed` (repo root) | OK: 4 machines, 2 products, 4 lots |
| `npm ci` / `npm run build` | OK, 31 s / 7 s (warm npm cache), 0 vulnerabilities |
| API, `SMQI_ENV=demo`, real intelligence | `/health` ok, `fusion-1.0.0`, `is_mock=false`; `/` and `/analytics` serve the SPA |
| `seed_demo_runs.py` | 3 runs: PASS 0.236, PASS 0.295, BLOCKED at Plasticizing |
| Journey in the browser on :8010 | run (instant) → explanation with charts → recommendations → live what-if → run detail and lineage → analytics → Model Info; **no console errors** |

- **Clone to running system:** 87 s. Caches were warm; a cold machine also downloads Python 3.12 and the packages. The < 10 min target (Plan Phase 14) still needs the run on Role 1's machine.
- **Friction found and fixed:**
  - README listed `black --check`, which fails: the project formats with `ruff format`.
  - `benchmark.py` crashed on the Windows cp1252 console; it now writes UTF-8.

**Benchmarks** (`uv run python scripts/benchmark.py --n 60`, same machine, Python 3.12.10, 12 CPUs; times in ms):

| Operation | p50 | p95 | max | Budget |
|---|---|---|---|---|
| intelligence `run_stage` (per stage) | 0.0 | 0.0 | 0.0 | ✓ p95 < 5 |
| intelligence `evaluate` (no explanation) | 0.1 | 0.1 | 0.2 | ✓ p95 < 150 |
| intelligence `explain` | 0.0 | 0.1 | 0.1 | ✓ p95 < 300 |
| API `POST /predict` (no explanation) | 5.0 | 5.8 | 6.2 | ✓ p95 < 150 |
| API `GET /predict/{id}/explain` | 2.6 | 3.0 | 3.3 | ✓ p95 < 300 |
| API full run (create, start, 6 × advance) | 106.5 | 111.3 | 156.5 | ✓ p95 < 300 |
| API `POST /whatif` (persist=false) | 5.3 | 6.2 | 6.6 | — |
| API `POST /whatif/sensitivity` (40 points) | 11.3 | 11.8 | 11.8 | ✓ < 1500 |
| API `POST /recommend` | 9.0 | 9.9 | 9.9 | ✓ < 5000 |
| API `GET /analytics/summary` | 5.3 | 6.5 | 6.6 | — |

The intelligence rows measure Role 1's current arithmetic-only facade. Re-run the benchmark when a trained bundle replaces it.

## Known issues

See `troubleshooting.md` § Known issues (all open with Role 1 under CCR-004).

## Blockers

- Role 2's R2-P9 needs (a) a clean-machine run on Role 1's machine and (b) Role 1's model archive, if one is planned.
- Role 1: please work through CCR-003 and CCR-004, and restore roadmap 1.0.1 on `main`.
