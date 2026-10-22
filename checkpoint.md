# Checkpoint 2 — 2026-10-22

Written after six Role 2 phases were complete (R2-P2 … R2-P7), per the "checkpoint every 3
phases" rule. Checkpoint 1 (2026-10-20, after R2-P2/P3/P4) is folded into this file, so it lists
everything done up to now. The source of truth for scope is `PROJECT_DEVELOPMENT_ROADMAP.md`
(v1.0.1, Appendix A approved). Live status is in `docs/integration_status.md`.

**Repository:** `Ankur-0211/Smart-Manufacturing-Quality-Intelligence-System`

| Branch | Contents |
|---|---|
| `role-2-application` | All Role 2 work below, with `main` (Role 1's PR #1) merged in |
| `main` | Initial commit + Role 1's deliverables (`1a22d7b`, PR #1) |
| `role-1-ai-ml` | Role 1's working branch |

**Tests at this checkpoint:**
- Backend: 497 pytest tests pass, 5 xfail (strict, the real facade's CCR-004 #3–#4 gaps); ruff, `ruff format` and strict mypy are clean.
- Frontend: 89 Vitest tests pass in 17 files; `tsc`, ESLint, `vite build` and `npm run check:api` are clean.

---

## Phase status

| Phase | Title | Status |
|---|---|---|
| R2-P1 | Repository setup, contracts integration, mock intelligence | Role 2 tasks done. M1 (contracts approved) waits on Role 1 closing CCR-003 / CCR-004 |
| **R2-P2** | Database and persistence | **Done** |
| **R2-P3** | Backend schemas, validation and services | **Done** |
| **R2-P4** | Simulation state machine, event flow and SSE | **Done** |
| **R2-P5** | Real intelligence integration, what-if, recommend | **Done** |
| **R2-P6** | Process Control UI | **Done** |
| **R2-P7** | What-if, recommendations and explainability UI | **Done** (P0; P1 added after this checkpoint except the dependence plot, which has no API) |
| R2-P8 | History and analytics | P0 done at this checkpoint; P1 (lineage, analytics, SPC series) added after it |
| R2-P9, R2-P10 | Analytics, system test and release | Not started |

**Milestones:**
- **M3** (mock inference operational): reached 2026-10-16.
- Real intelligence (Role 1's `fusion-1.0.0`) serving end to end: 2026-10-22.
- **M1** (contracts approved): open.

---

## Role 2: tasks completed

### R2-P1: Setup, contracts integration, mock (`062a560`, `dbbc5db`…`b80f350`)

**Tooling and repository:**
- Python 3.12 with uv (`pyproject.toml`, `uv.lock`); ruff, mypy (strict on Role 2 packages); pytest.
- `.gitattributes` (LF), `.gitignore`, `CODEOWNERS`, `.env.example`, README.

**Backend skeleton:**
- `create_app` factory. Startup order: settings → registry → intelligence → DB.
- structlog JSON logs; request-ID middleware.
- `{data, error, meta}` envelope with stable error codes (CCR-001 adds `ROUTE_NOT_FOUND` and `METHOD_NOT_ALLOWED`).
- Optional `X-API-Key`; CORS; token-bucket rate limiter.

**Frontend scaffold:**
- React 18, TypeScript, Vite, Tailwind 4, TanStack Query, Zustand, React Router, Recharts, Framer Motion.
- Vitest, React Testing Library, MSW; API types generated from `docs/openapi.json`.

**Contracts and registry:**
- Contracts part 1 from Role 1 committed unchanged; review notes in CCR-003.
- CCR-002 bootstrap of the remaining contracts, registry, loader and dependency graph — since replaced by Role 1's own files.

**Mock intelligence (`app/intelligence_mock`):**
- Implements the full `QualityIntelligence` Protocol with deterministic, hash-derived placeholders; BLOCKED comes from the registry's hard constraints; every output is labelled MOCK.
- Hybrid router per capability, plus the `build_intelligence` factory. Real mode refuses to start without Role 1's facade or its P0 capabilities.

**Engine binding, health, constraints:**
- `IntelligenceStageExecutor` connects the simulation engine to the intelligence layer.
- `/health` reports `IntelligenceVersionInfo`.
- `GET /constraints`, typed and served with an ETag.
- Registry-driven validation: tier 1 bounds through `create_model`; tier 2 coupling rules with the run's machine context.

**Checks:** the contract harness (schema, invariants, determinism, equivalence) and an import-boundary test (B1, B2, B7).

### R2-P2: Database (`055de79`, fix `9ee2286`)

- SQLAlchemy 2.0 models for 10 tables; Alembic migration `0001`; SQLite (WAL, foreign keys on).
- Repositories: Reference, Run, StageResult, Prediction, Recommendation, Event, ModelVersion.
- Immutability guards for finished runs and append-only tables; lineage tree; seed from `fleet.yaml`.
- Concurrent model-version registration no longer aborts runs (savepoint upsert).

### R2-P3: Schemas, validation, services (`0b6b9f6`, `6312b0c`)

- `GET /machines`, `/products`, `/materials`; `POST /materials` (lot code format, registry box check, 409 on duplicates).
- `POST /simulation/runs`: references resolve or 404; then `PARAM_OUT_OF_RANGE` / `COUPLING_VIOLATION` with per-field details. Hard constraints stay runtime BLOCKs.
- `POST /predict`, `GET /predict/{id}/explain`, `GET /models`, `/models/active`.
- `npm run check:api` fails when the generated TypeScript types are stale.

### R2-P4: Simulation engine (`6022373` plus later commits)

- Pure state machine with transition guards; persist-then-publish event bus; LRU stage cache.
- `SimulationService`: create, start (auto/stepwise), advance, pause, resume, reset, abort, override, label; a lock per run; restart recovery.
- SSE with `Last-Event-ID` replay, keepalive and gap fill; every endpoint from roadmap §9.3.2.

### Role 1 integration (`ea53a34`, `b76edf7`, `4a9fa77`, `168490c`)

- Merged `main` (Role 1's PR #1). Role 1's contracts, domain and facade kept as owner; Role 2's config, `pyproject.toml`, `uv.lock` and roadmap 1.0.1 kept.
- Role 2 code adapted to Role 1's interface: mock, hybrid, factory, executor, validation, `/constraints`, `/predict`.
- Fixtures regenerated from Role 1's fleet; the contract harness runs mock and real.
- Findings raised as [CCR-004](docs/contract_changes/CCR-004-role1-integration-findings.md).

### R2-P5: Real intelligence, what-if, recommend (`9bbda78`, `41eb28f`)

- Serving-model registration at startup (exactly one active `model_versions` row); global explanation endpoint.
- `real` is the dev default backend; `SMQI_ENV=demo` requires it; `scripts/seed_demo_runs.py` seeds history through the API.
- `POST /whatif`: partial re-simulation through Role 1's `invalidated_stages` (reuse only when model and limits versions match), §7.16 diff, persisted child runs inheriting the parent's context; property-tested equal to full runs.
- `/whatif/compare`, `/whatif/sensitivity` (rate limited), `POST /recommend` (rows per candidate with `request_id` and model version), `GET /simulation/runs/{id}/lineage`.

### R2-P6: Process Control UI (`628532f`, `dcf982c`, `5d6cee6`)

- Stage pipeline with health and risk, MOCK banner, result card with the critical-breach rule (UD-07), live run over SSE, run controls, override panel.
- Run setup: machine / product / lot pickers, registry-driven sliders and inputs grouped by stage, 422 mapping onto fields; RUN creates, starts and follows a run.
- Create lot dialog validated by the API; polling fallback with hook- and screen-level tests.
- Handoff: `docs/screenshots/01…08` and `docs/coordination/UI_COPY_FOR_ROLE1.md`.

### R2-P7: What-if, recommendations, explainability UI (`da66078` and this commit)

- **What-If workbench:** fork a finished run, edit parameters, Evaluate / Save as scenario, Reset to parent, §7.16 diff view.
- **Recommendations:** locked parameters, max changes, option cards with guard stamp, stability, EXTRAPOLATED, cycle time, `empty_reason`, permanent disclaimer, a cross-check against the registry's `max_step_change` (CCR-004 #7b), Send to What-If.
- **Explainability:** signed SHAP bars with a matching table, Features/Groups toggle, stage risk mass donut and share list, caveat banner, method note (output space, base value, background), permanent DISCLAIMER_SHAP; falls back to `GET /predict/{id}/explain`.
- Result card links: Why this prediction?, What should I change?, Try a what-if, Save scenario.
- Screenshots `docs/screenshots/09…12` on the real facade.

### R2-P8 (partial, `8e78f8b`)

- History: filters, pagination, run detail, scenario label.

---

## Role 1: delivered and integrated

**Delivered:** `1a22d7b` (author `lucky-ai03`, merged to `main` as PR #1):
- the complete contracts;
- `constraints.yaml` (constraints-1.0.0), `remedies.yaml`, `fleet.yaml`;
- `constraint_loader.py`, `dependency_graph.py`;
- `app/intelligence/stages.py` and `facade.py` (`RealQualityIntelligence`, pure Python, threshold 0.35);
- `verify_ml.py`, `test_contracts_part1.py`, `test_parameter_dictionary.py`, `docs/parameter_dictionary.md`.

**Open findings for Role 1:** [CCR-003](docs/contract_changes/CCR-003-part1-review-notes.md) and [CCR-004](docs/contract_changes/CCR-004-role1-integration-findings.md). The main CCR-004 items:
- the 4-cavity product is always blocked; MC-03's clamp is below the nominal recipe's need;
- the label is forced to FAIL on critical breaches;
- stage risk mass doesn't sum to 1; some indicators lack provenance;
- limits are written into the loader code; lot attributes have no windows;
- recommendations with no predicted gain (#7a) and a step-size guard that passes oversized steps (#7b);
- §9.1 interface gaps;
- `main` carries a reverted roadmap (1.0.0 draft).

---

## Next

1. **Role 1:** work through CCR-003 and CCR-004, and restore roadmap 1.0.1 on `main`.
2. **R2-P7 P1:** done on 2026-10-22 after this checkpoint: live slider, A/B compare page, sensitivity strip, Model Info (CCR-004 #7c, #7d raised). The dependence plot is not built.
3. **R2-P8:** done on 2026-10-22 after this checkpoint: lineage tree, `/analytics/*`, Analytics screen with SPC series (alerts wait on CCR-004 #10). Batch CSV scoring (P2) not built. Completed phases are now R2-P2…R2-P8 (seven); checkpoint 3 is due after R2-P10.
4. **R2-P9:** Role 2's P0 work done on 2026-10-22 after this checkpoint (single-process deployment, clean-clone run, benchmarks, deployment and troubleshooting docs). Waiting on Role 1: a clean-machine run on their machine and a model archive. Not built: Compose and CI (P2).
5. **R2-P10:** system testing and the demonstration.
