# Checkpoint 1 — 2026-10-20

Written after three Role 2 phases were complete (R2-P2, R2-P3, R2-P4), per the
"checkpoint every 3 phases" rule. The source of truth for scope is
`PROJECT_DEVELOPMENT_ROADMAP.md` (v1.0.1, Appendix A approved). Live status is in
`docs/integration_status.md`.

**Repository:** `Ankur-0211/Smart-Manufacturing-Quality-Intelligence-System`

| Branch | Head | Contents |
|---|---|---|
| `role-2-application` | `6312b0c` | All work below |
| `role-1-ai-ml` | `bbc3785` | Initial commit only |
| `main` | `bbc3785` | Initial commit only |

**Tests at this checkpoint:** 529 backend tests pass (pytest) with no skips; ruff, `ruff format` and strict mypy are clean. 58 frontend tests pass (Vitest); `tsc`, ESLint and `npm run check:api` are clean.

---

## Phase status

| Phase | Title | Status |
|---|---|---|
| R2-P1 | Repository setup, contracts integration, mock intelligence | Role 2 tasks 1–12 done. The phase gate needs M1: Role 1 has to approve contracts v0.1.0 and answer CCR-003 |
| **R2-P2** | Database and persistence | **Done** |
| **R2-P3** | Backend schemas, validation and services | **Done** |
| **R2-P4** | Simulation state machine, event flow and SSE | **Done** (runs on the mock intelligence) |
| R2-P5 | Real intelligence integration | Not started: needs Role 1's facade in the repo |
| R2-P6 | Process Control UI | Partial: visual components and live run view are done; parameter sliders and run setup are not |
| R2-P8 | History | P0 part done (list, filters, run detail, scenario label) |
| R2-P7, R2-P9, R2-P10 | What-if / recommendations UI, analytics, system test | Not started |

**Milestones:**
- **M3** (mock inference operational): reached 2026-10-16.
- **M1** (contracts approved): open.

---

## Role 2: tasks completed

### R2-P1: Setup, contracts integration, mock (`062a560`, `dbbc5db`…`b80f350`)

**Tooling and repository:**
- Python 3.12 with uv (`pyproject.toml`, `uv.lock`); ruff, black and mypy (strict on Role 2 packages, contracts and domain); pytest.
- `.gitattributes` (LF), `.gitignore`, `CODEOWNERS`, `.env.example`, README.

**Backend skeleton:**
- `create_app` factory. Startup order: settings → registry → intelligence → DB.
- structlog JSON logs; request-ID middleware.
- `{data, error, meta}` envelope with stable error codes (CCR-001 adds `ROUTE_NOT_FOUND` and `METHOD_NOT_ALLOWED`).
- Optional `X-API-Key`; CORS; token-bucket rate limiter.

**Frontend scaffold:**
- React 18, TypeScript 5.9, Vite, Tailwind 4, TanStack Query, Zustand, React Router, Framer Motion.
- Vitest, React Testing Library, MSW; API types generated from `docs/openapi.json`.

**Contracts and registry:**
- Contracts part 1 from Role 1 committed unchanged. Review notes are in `docs/contract_changes/CCR-003-part1-review-notes.md`.
- CCR-002 bootstrap, which Role 1 will adopt or replace:
  - contracts: stage, anomaly, prediction, explanation, recommendation, sensitivity, interface;
  - `constraints.yaml`, `remedies.yaml`, `fleet.yaml` and five contract fixtures;
  - `constraint_loader.py` and `dependency_graph.py`.

**Mock intelligence (`app/intelligence_mock`):**
- Implements the full `QualityIntelligence` Protocol with deterministic, hash-derived placeholder values.
- BLOCKED comes from `check_hard_constraints`; every output is labelled MOCK.
- Hybrid router per capability, plus a `build_intelligence` factory. Real mode refuses to start without Role 1's facade or its P0 capabilities.

**Engine binding and health:**
- `IntelligenceStageExecutor` connects the simulation engine to the intelligence layer.
- `/health` reports `IntelligenceVersionInfo`.

**Constraints endpoint and validation:**
- `GET /constraints`, typed and served with an ETag.
- Registry-driven validation: tier 1 bounds through `create_model`; tier 2 coupling rules with the run's machine context.
- `IntelligenceError` is mapped onto the envelope.

**Checks:**
- The contract harness runs the mock on all five fixtures, checking schema, invariants, determinism and equivalence.
- An import-boundary test enforces B1, B2 and B7.

### R2-P2: Database (`055de79`)

**Schema:**
- SQLAlchemy 2.0 models for 10 tables; Alembic migration `0001`.
- SQLite (WAL, foreign keys on); `UTCDateTime` type.

**Repositories:**
- Reference, Run, StageResult, Prediction, Recommendation, Event and ModelVersion.

**Rules:**
- Immutability guards: finished runs and append-only tables cannot change.
- Lineage tree; seed from `fleet.yaml` with exit codes 0/2/3.

**Fix (`9ee2286`):** concurrent model-version registration no longer aborts runs.

### R2-P3: Schemas, validation, services (`0b6b9f6`, `6312b0c`)

**Reference data:**
- `GET /machines`, `/products`, `/materials`.
- `POST /materials`: lot code format, registry box check, 409 on a duplicate code.

**Run creation, `POST /simulation/runs`:**
- Body is the contract `ProcessRecipe`; references resolve, or 404 `REFERENCE_NOT_FOUND` with the field.
- Then registry tier 1 → `PARAM_OUT_OF_RANGE` and tier 2 → `COUPLING_VIOLATION`, with per-field details.
- Hard constraints stay runtime BLOCKs, never HTTP errors.

**Stateless prediction:**
- `POST /predict`: same validation as run creation; full pipeline through `evaluate()`; persists a `predictions` row with `run_id = NULL` and the input snapshot.
- `GET /predict/{id}/explain`: the stored explanation, or a deterministic recomputation; 503 `MODEL_NOT_LOADED` if the model has changed.

**Models:** `GET /models` and `/models/active`; the mock's model version is registered at startup.

**Types:** `npm run check:api` fails when the generated TypeScript types are stale.

### R2-P4: Simulation engine (`6022373` plus later commits)

**Engine:**
- Pure state machine with transition guards.
- Persist-then-publish event bus; LRU stage cache with canonical keys.

**Run orchestration (`SimulationService`):**
- `create_run`, `start` (auto/stepwise), `advance`, `pause`, `resume`, `reset`, `abort`, `override` and set label.
- A lock per run; the BLOCKED path carries the pending result.
- Restart recovery for auto-mode runs that were executing.

**Streaming and API:**
- SSE with `Last-Event-ID` replay, keepalive and gap fill.
- Every simulation endpoint from roadmap §9.3.2.

**Verified end to end with the mock:**
- auto and stepwise runs;
- wet lot A-790 → BLOCKED (HC-006) → override → **NOT RELEASABLE**;
- 10 concurrent runs.

### R2-P6 / R2-P8 (partial, `628532f`, `8e78f8b`)

**Process Control:**
- Stage pipeline with health and risk, MOCK banner, result card with the critical-breach rule (UD-07).
- Live run viewing over SSE, run controls, override panel.

**History:** filters, pagination, run detail, scenario label.

**API hooks for upcoming screens:** constraints, reference, run creation, predict and explanation.

---

## Role 1: status as reported

**Source:** `aboutrole1.md`, added 2026-10-20. None of this code is in the repository yet: `role-1-ai-ml` has only the initial commit.

**In the repository:** contracts part 1 (`version`, `enums`, `recipe`, `context`, `errors`), committed in `dbbc5db`.

**Reported as built:**
- `constraints.yaml` (constraints-1.0.0), `remedies.yaml` (remedies-1.0.0) and `fleet.yaml`.
- `constraint_loader.py` and `dependency_graph.py`.
- All contract modules.
- `app/intelligence/stages.py` and `facade.py` (`RealQualityIntelligence`).
- `verify_ml.py`, `test_contracts_part1.py` and `test_parameter_dictionary.py`.

**Known differences from Role 2's bootstrap, to reconcile when the code arrives:**
- Loader API:
  - Role 1 uses `check_box(param, value)` returning a tuple and `check_couplings(recipe, context)`;
  - Role 2's bootstrap uses `check_box(values)` and `check_couplings(values)`, both returning `ConstraintBreach` lists as in roadmap §8.4;
  - Role 1 adds `load_constraint_registry()`.
- Facade construction: Role 1 uses `RealQualityIntelligence(registry=…)`; Role 2's factory calls `RealQualityIntelligence.from_settings(settings, registry)`.
- Contract class names: Role 1 uses `CaveatItem`, `OodReport`, `FeatureAttribution`, `StageRiskShare`; Role 2's bootstrap uses `Caveat`, `OodInfo`, `Attribution`, `StageShare`.
- Fleet:
  - Role 1 has lots B-812, C-904, D-105 and product PP-JBOX-42-4C;
  - Role 2's demo data and tests use lots A-772, B-310 and A-790 (the wet-lot demo).
- Registry version: constraints-1.0.0 (Role 1) vs constraints-0.1.0 (Role 2 bootstrap).
- Fusion threshold: Role 1 reports 0.35; the mock uses 0.5.

---

## Next

1. **Bring in Role 1's code.** Push it to `role-1-ai-ml`, or drop the files in, then reconcile the differences above (CCR-004).
2. **R2-P5:** bind `RealQualityIntelligence` through `build_intelligence`, then switch to hybrid and real mode.
3. **R2-P6:** run setup screen with parameter sliders from `GET /constraints`.
4. **R2-P7:** what-if and recommendations.
