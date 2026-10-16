# Integration Status

Both roles update this file (roadmap §10.1). A capability counts as **REAL** only when
`QualityIntelligence.capabilities()` reports it **and** this table says so.

_Last updated: 2026-10-16 by Role 2 (R2-P3 started: run creation + reference endpoints)._

## Capability matrix

| Capability | Status | Since | Notes |
|---|---|---|---|
| `run_stage` (S1–S5) | MOCK | 2026-10-16 | `MockQualityIntelligence`; BLOCKED driven by `check_hard_constraints`. HC-002/HC-004 need derived values only real stage modules produce, so the mock never fires them |
| `predict` | MOCK | 2026-10-16 | Hash-derived placeholder `p_fail`, threshold 0.5, `MOCK_INFERENCE` caveat; real from `fusion-0.1.0` (R1-P4) |
| `explain` / `global_explanation` | MOCK | 2026-10-16 | Placeholder attributions; real in R1-P7 |
| `anomaly_global` | MOCK | 2026-10-16 | `detect_anomaly` placeholder; `PredictionResult.anomaly_global` stays null (MVP); real R1-P7 (P1) |
| `recommend` | MOCK | 2026-10-16 | Registry-guarded one-step candidates scored through the same mock pipeline; real R1-P8. UI gated on the "guard tested" statement |
| `sensitivity` | MOCK | 2026-10-16 | Real R1-P8 (P1) |
| `spc` | NOT AVAILABLE | — | Mock raises `CAPABILITY_UNAVAILABLE`; R1-P7 (P1) |

Status values: `NOT AVAILABLE` → `MOCK` → `HYBRID` → `REAL`.

## Shared artifacts

| Artifact | Version | Status |
|---|---|---|
| `backend/app/contracts` | 0.1.0 | Part 1 by Role 1 (committed unchanged, review in [CCR-003](contract_changes/CCR-003-part1-review-notes.md)). Remainder (`stage`, `anomaly`, `prediction`, `explanation`, `recommendation`, `sensitivity`, `interface`) bootstrapped by Role 2 (CCR-002); Role 1 to adopt |
| `backend/app/domain/constraints.yaml`, `remedies.yaml` | constraints-0.1.0 / remedies-0.1.0 | Bootstrapped by Role 2 (CCR-002); all values `unvalidated`; Role 1 to adopt. `constraint_loader.py` + `dependency_graph.py` bootstrapped (CCR-002) with tests |
| `fleet.yaml` | fleet-0.1.0 | Bootstrapped (CCR-002): MC-01…04, PP-JBOX-42, 4 lots. Seed verified with it |
| Contract fixtures (`backend/tests/contract/fixtures`) | v0.1.0 | 5 `recipe_*.json` bootstrapped (CCR-002). All validate against `ProcessInput`; the harness runs them against the mock (determinism + equivalence) |
| API (`docs/openapi.json`) | api_version 1 | `/health` (with `IntelligenceVersionInfo`), `/constraints` (ETag), `/machines`, `/products`, `/materials` (GET + POST), `POST /simulation/runs`, simulation queries/commands, SSE, scenario label |
| Event catalogue (`docs/events.md`) | EVENTS_VERSION 1 | Implemented and tested (R2-P4). Freeze at M4 once a real/mock executor runs end-to-end |
| DB schema | Alembic `0001` | Done (R2-P2): 10 tables, immutability guards, seed |
| Model bundles | — | R1-P4 onwards |

## Role 2 phase status

| Phase | Status |
|---|---|
| R2-P1 | Tasks 1-12 done. Completion gate waits on M1 (Role 1 approves contracts v0.1.0 + CCR-003) |
| R2-P2 | Done |
| R2-P3 | In progress: reference endpoints and `POST /simulation/runs` (tiers 1-2 from the registry) done; `/predict`, `/predict/{id}/explain`, `/models/active` next |
| R2-P4 | Engine, SSE, recovery and `create_run` done, all running on the mock |
| R2-P6 | Visual components and live run viewing done; parameter sliders next (they use `GET /constraints`) |

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Contracts approved | Open. v0.1.0 complete on `role-2-application`; awaiting Role 1 review of the bootstrap + CCR-003 answers |
| M2 | Dataset feasibility & canonical schema | Open (Role 1) |
| M3 | Mock inference operational | **Reached 2026-10-16.** Mock passes the contract harness on all 5 fixtures; simulation runs end to end (auto, stepwise, BLOCKED + override) |

## Open CCRs

| CCR | Title | Status |
|---|---|---|
| [CCR-001](contract_changes/CCR-001-route-error-codes.md) | Add `ROUTE_NOT_FOUND`, `METHOD_NOT_ALLOWED` error codes | proposed |
| [CCR-002](contract_changes/CCR-002-role2-bootstraps-contracts.md) | Role 2 bootstraps the contracts remainder / registry / fixtures | approved for the remainder; delivered (data 72e06e0; code on 2026-10-16) |
| [CCR-003](contract_changes/CCR-003-part1-review-notes.md) | Review notes on contracts part 1 (`flat()` keys, missing files, formatting) | proposed (questions for Role 1) |

## Environments

| Member | OS | Python | uv | Node | npm | Last clean setup |
|---|---|---|---|---|---|---|
| Role 2 machine | Windows 11 | 3.12.10 (uv-managed) | 0.10.7 | 24.14.1 | 11.11.0 | 2026-10-15 |
| Role 1 machine | — | — | — | — | — | — |

## Blockers

- None for Role 2. **Role 1, please:**
  - answer the CCR-003 questions;
  - run `ruff format` on the part-1 files;
  - send `tests/contract/test_contracts_part1.py`;
  - review the bootstrapped contracts, loader and dependency graph.
