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

## Role 1: delivered and integrated (updated 2026-10-22)

**Delivered:** Role 1 pushed `1a22d7b` (author `lucky-ai03`, merged to `main` as PR #1). It contains:
- the complete contracts;
- `constraints.yaml` (constraints-1.0.0), `remedies.yaml` and `fleet.yaml`;
- `constraint_loader.py` and `dependency_graph.py`;
- `app/intelligence/stages.py` and `facade.py` (`RealQualityIntelligence`, pure Python, threshold 0.35);
- `verify_ml.py`, `test_contracts_part1.py`, `test_parameter_dictionary.py` and `docs/parameter_dictionary.md`.

**Integrated into `role-2-application`** (merge `ea53a34`, then follow-up commits):
- Role 1's files are kept as owner and replace the CCR-002 bootstrap.
- Role 2's config, `pyproject.toml`, `uv.lock`, `.python-version` and roadmap 1.0.1 are kept.
- Role 2 code now runs on Role 1's interface: the mock, hybrid, factory, executor, validation, `/constraints` and `/predict`.
- `SMQI_INTELLIGENCE_BACKEND=real` serves Role 1's facade. The contract harness runs mock and real.

**Findings for Role 1:** [CCR-004](docs/contract_changes/CCR-004-role1-integration-findings.md). The main items:
- the 4-cavity product is always blocked;
- the label is forced to FAIL on critical breaches;
- stage risk mass doesn't sum to 1;
- limits are written into the loader code;
- lot attributes have no windows;
- §9.1 interface gaps;
- `main` carries a reverted roadmap (1.0.0 draft).

---

## Next

1. **Role 1:** work through CCR-003 and CCR-004, and restore roadmap 1.0.1 on `main`.
2. **R2-P5:** done on 2026-10-22: what-if, compare, sensitivity, recommend, lineage, serving-model registration, the demo profile, and `real` as the default backend.
3. **R2-P6:** done on 2026-10-22: run setup, Create lot, polling fallback, screenshots, and the UI-copy list for Role 1.
4. **R2-P7:** what-if and recommendation screens on top of the R2-P5 endpoints.
