# Integration Status

Both roles update this file (roadmap §10.1). A capability counts as **REAL** only when
`QualityIntelligence.capabilities()` reports it **and** this table says so.

_Last updated: 2026-10-15 by Role 2 (R2-P4 engine core)._

## Capability matrix

| Capability | Status | Since | Notes |
|---|---|---|---|
| `run_stage` (S1–S5) | NOT AVAILABLE | — | Needs `app.contracts` v0.1.0 (R1-P1), then mock (R2-P1) |
| `predict` | NOT AVAILABLE | — | Mock after contracts; real from `fusion-0.1.0` (R1-P4) |
| `explain` / `global_explanation` | NOT AVAILABLE | — | R1-P7 |
| `anomaly_global` | NOT AVAILABLE | — | R1-P7 (P1) |
| `recommend` | NOT AVAILABLE | — | R1-P8; UI gated on the "guard tested" statement |
| `sensitivity` | NOT AVAILABLE | — | R1-P8 (P1) |
| `spc` | NOT AVAILABLE | — | R1-P7 (P1) |

Status values: `NOT AVAILABLE` → `MOCK` → `HYBRID` → `REAL`.

## Shared artifacts

| Artifact | Version | Status |
|---|---|---|
| `backend/app/contracts` | part 1 (Role 1) | **Part 1 written by Role 1, not yet pushed** (version, enums, recipe, context, errors). Remainder bootstrapped by Role 2 after that push (CCR-002) |
| `backend/app/domain/constraints.yaml`, `remedies.yaml` | constraints-0.1.0 / remedies-0.1.0 | Bootstrapped by Role 2 (CCR-002); all values `unvalidated`; Role 1 to adopt. Loader + dependency graph wait for part 1 |
| `fleet.yaml` | fleet-0.1.0 | Bootstrapped (CCR-002): MC-01…04, PP-JBOX-42, 4 lots. Seed verified with it |
| Contract fixtures (`backend/tests/contract/fixtures`) | v0.1.0 | 5 `recipe_*.json` bootstrapped (CCR-002). Harness ready; runs once contracts exist |
| API (`docs/openapi.json`) | api_version 1 | `/health`, simulation queries/commands, SSE, scenario label |
| Event catalogue (`docs/events.md`) | EVENTS_VERSION 1 | Implemented and tested (R2-P4). Freeze at M4 once a real/mock executor runs end-to-end |
| DB schema | Alembic `0001` | Done (R2-P2): 10 tables, immutability guards, seed |
| Model bundles | — | R1-P4 onwards |

## Milestones

| # | Milestone | Status |
|---|---|---|
| M1 | Contracts approved | Open. Waiting for `app.contracts` v0.1.0 |
| M2 | Dataset feasibility & canonical schema | Open (Role 1) |
| M3 | Mock inference operational | Open. Blocked by M1 |

## Open CCRs

| CCR | Title | Status |
|---|---|---|
| [CCR-001](contract_changes/CCR-001-route-error-codes.md) | Add `ROUTE_NOT_FOUND`, `METHOD_NOT_ALLOWED` error codes | proposed |
| [CCR-002](contract_changes/CCR-002-role2-bootstraps-contracts.md) | Role 2 bootstraps the contracts remainder / registry / fixtures | approved for the remainder; data files delivered; code waits for part-1 push |

## Environments

| Member | OS | Python | uv | Node | npm | Last clean setup |
|---|---|---|---|---|---|---|
| Role 2 machine | Windows 11 | 3.12.10 (uv-managed) | 0.10.7 | 24.14.1 | 11.11.0 | 2026-10-15 |
| Role 1 machine | — | — | — | — | — | — |

## Blockers

- **Role 1: please push contracts part 1 to `role-1-ai-ml`.** The remaining contracts, the loader and Role 2's R2-P1 tasks 8–11 wait for it.

- **Role 2 is blocked on R2-P1 tasks 8–11 (mock intelligence, `/constraints`, registry-driven
  validation, real contract tests) until Role 1 delivers `app/contracts` v0.1.0 and the registry
  loader.** The contract-test harness exists and skips until then.
