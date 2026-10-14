# Integration Status

Both roles update this file (roadmap §10.1). A capability counts as **REAL** only when
`QualityIntelligence.capabilities()` reports it **and** this table says so.

_Last updated: 2026-10-15 by Role 2 (R2-P2)._

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
| `backend/app/contracts` | — | **Awaited from Role 1 (R1-P1 task 1)** |
| `backend/app/domain/constraints.yaml` + loader | — | **Awaited from Role 1 (R1-P1 tasks 4–9)** |
| `fleet.yaml` | — | Awaited (R1-P1 task 8). The seed is ready and needs this file; format in `database.md` |
| Contract fixtures (`backend/tests/contract/fixtures`) | — | Awaited (R1-P1). Harness ready (R2-P1) |
| API (`docs/openapi.json`) | api_version 1 | `/api/v1/health` only |
| Event catalogue (`docs/events.md`) | draft | From roadmap §9.5. Frozen at M4 |
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
| [CCR-002](contract_changes/CCR-002-role2-bootstraps-contracts.md) | Role 2 bootstraps contracts v0.1.0 / registry / fixtures (one-time UD-19 exception) | proposed; waiting for Role 1 answer |

## Environments

| Member | OS | Python | uv | Node | npm | Last clean setup |
|---|---|---|---|---|---|---|
| Role 2 machine | Windows 11 | 3.12.10 (uv-managed) | 0.10.7 | 24.14.1 | 11.11.0 | 2026-10-15 |
| Role 1 machine | — | — | — | — | — | — |

## Blockers

- **Role 1: please read [`coordination/ROLE1_AGENT_INSTRUCTIONS.md`](coordination/ROLE1_AGENT_INSTRUCTIONS.md) before working on R1-P1.**

- **Role 2 is blocked on R2-P1 tasks 8–11 (mock intelligence, `/constraints`, registry-driven
  validation, real contract tests) until Role 1 delivers `app/contracts` v0.1.0 and the registry
  loader.** The contract-test harness exists and skips until then.
