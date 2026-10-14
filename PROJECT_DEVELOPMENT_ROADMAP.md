# PROJECT DEVELOPMENT ROADMAP
## Smart Manufacturing Quality Intelligence System
### Injection Molding Process Quality Prediction, Simulation, Explanation & Recommendation

| Item | Value |
|---|---|
| Document | `PROJECT_DEVELOPMENT_ROADMAP.md`, the single source of truth for role allocation, shared contracts, phase-wise development and integration |
| Source of truth for design intent | `Smart_Manufacturing_Quality_Intelligence_Project_Plan.pdf` (38 pages, "Design baseline, pre-implementation"), referred to below as **"the Plan"** |
| Roadmap version | 1.0.1 (Appendix A decisions UD-01 to UD-20 approved 2026-10-15) |
| Date | 2026-10-14 |
| Team | 2 members: **Role 1** (AI/ML, Manufacturing Intelligence & Recommendation) and **Role 2** (Backend, Simulation, Database & Frontend) |
| Schedule basis | 12 weeks (Plan §22.1), expressed as **W1–W12** relative to kickoff |
| Status | No implementation exists yet. The working folder contains only the Plan PDF and is not yet a git repository |

> **Normative language.** **MUST** / **MUST NOT** mark binding rules. **SHOULD** marks strong defaults. Items tagged **[ASSUMPTION]** or **[PROPOSED]** are not fixed by the Plan and need team approval (Section 2.5 and Appendix A). Plan section references look like *(Plan §9.6)*.

---

## Table of Contents

1. [Project overview and objectives](#1-project-overview-and-objectives)
2. [Source-plan analysis and assumptions](#2-source-plan-analysis-and-assumptions)
3. [System architecture and end-to-end data flow](#3-system-architecture-and-end-to-end-data-flow)
4. [Shared repository structure and module ownership](#4-shared-repository-structure-and-module-ownership)
5. [Role definitions and responsibility boundaries](#5-role-definitions-and-responsibility-boundaries)
6. [User-selected role mode for the coding agent](#6-user-selected-role-mode-for-the-coding-agent)
7. [Shared domain schemas and data contracts](#7-shared-domain-schemas-and-data-contracts)
8. [Shared constraint registry](#8-shared-constraint-registry)
9. [Shared API, inference, database and event contracts](#9-shared-api-inference-database-and-event-contracts)
10. [Integration and contract-change procedures](#10-integration-and-contract-change-procedures)
11. [Role 1: complete phase-wise development roadmap](#11-role-1-complete-phase-wise-development-roadmap)
12. [Role 2: complete phase-wise development roadmap](#12-role-2-complete-phase-wise-development-roadmap)
13. [Cross-role dependencies and milestone table](#13-cross-role-dependencies-and-milestone-table)
14. [Parallel development and Git workflow](#14-parallel-development-and-git-workflow)
15. [Testing strategy and quality gates](#15-testing-strategy-and-quality-gates)
16. [Deployment and final demonstration plan](#16-deployment-and-final-demonstration-plan)
17. [Scope priorities and exclusions](#17-scope-priorities-and-exclusions)
18. [Technical risks and mitigation](#18-technical-risks-and-mitigation)
19. [Final acceptance checklist](#19-final-acceptance-checklist)
20. [Definition of done](#20-definition-of-done)
- [Appendix A: Decisions (approved)](#appendix-a-decisions-approved)
- [Appendix B: Phase completion report template](#appendix-b-phase-completion-report-template)
- [Appendix C: Glossary](#appendix-c-glossary)

---

## 1. Project overview and objectives

### 1.1 Vision (Plan §1.1)

The system is a **software-based manufacturing quality intelligence system**. A virtual production batch moves through the stages of an injection-molding process. At each stage a dedicated **stage intelligence module** evaluates only the parameters that physically belong to that stage. It emits a **stage health score**, a **risk level** and an **anomaly flag**, then passes an enriched process state forward.

A final **fusion quality engine** combines four inputs to predict whether the part will pass quality inspection:
- raw process parameters
- stage-level intelligence outputs
- engineered interaction features
- machine and product context

The system then:
- explains the prediction with SHAP feature attribution,
- lets the user change parameters in an interactive **what-if simulation**, and
- runs a **constrained recommendation search** that answers *"what should I change to make it pass?"*, always inside documented, physically admissible parameter windows.

### 1.2 Problem statement and why this domain fits (Plan §2–3)

The problem statement names six parameter families: Temperature, Pressure, Machine Speed, Production Time, Raw Material Measurements and Machine ID. Each one maps onto a named physical quantity in injection molding:

| Problem-statement parameter | Injection-molding realisation | Stage where it dominates |
|---|---|---|
| Temperature | Barrel zone temps, nozzle temp, melt temp, mold temp | Plasticizing/Thermal, Cooling |
| Pressure | Injection, packing/holding, back pressure, clamp force | Injection, Packing |
| Machine Speed | Injection velocity (mm/s), screw RPM | Injection, Thermal |
| Production Time | Cycle, injection (fill), hold, cooling times | All stages |
| Raw Material Measurements | Resin moisture %, MFI, regrind %, colourant % | Material |
| Machine ID | Machine/tool identity, cavity count, machine age, maintenance gap | Context (all stages) |

### 1.3 Selected manufacturing domain (Plan §2.2)

- **Process:** thermoplastic **polypropylene (PP) injection molding** of a small technical component.
- **Product:** a **30–60 g PP electrical junction-box housing**. The demo product code is `PP-JBOX-42` (42 g shot weight).
- **Shop floor:** multiple machines (hydraulic and electric), single-cavity or 4-cavity tooling.
- **Defect modes behind the PASS/FAIL label (Plan §3.2):** short shot, flash, sink marks/voids, warpage, splay/silver streaks, burn marks/degradation.
- **Key couplings the architecture MUST respect (Plan §3.3):**
  - melt temp × injection pressure
  - injection velocity × melt temp
  - packing pressure × hold time × thickness
  - mold temp × cooling time
  - resin moisture × melt temp

  These couplings are why the design uses **per-stage intelligence** and rejects per-parameter agents.

### 1.4 The six-stage manufacturing workflow (Plan §7.2)

| # | Canonical stage enum | Display name | Purpose | Intelligence |
|---|---|---|---|---|
| S1 | `MATERIAL_CONDITIONING` | Material Conditioning | Resin lot fitness, dryness, viscosity expectation | Material module |
| S2 | `PLASTICIZING` | Plasticizing / Thermal | Barrel heating, screw recovery, melt preparation | Thermal module |
| S3 | `INJECTION` | Injection / Fill | Velocity-controlled cavity filling | Injection module |
| S4 | `PACKING` | Packing / Holding | Pressure-controlled compensation until gate freeze | Packing module |
| S5 | `COOLING` | Cooling / Ejection | In-mold solidification, ejection | Cooling module |
| S6 | `QUALITY_INSPECTION` | Quality Inspection / Fusion | Final PASS/FAIL and calibrated failure probability | Fusion engine + risk engine |

There are **five stage-intelligence modules (S1–S5)** and **one fusion quality engine (S6)**.

### 1.5 Objectives

| ID | Objective | Primary owner |
|---|---|---|
| O1 | A server-side six-stage simulation state machine that mirrors the real injection-molding cycle | Role 2 |
| O2 | Five stateless, deterministic, tested stage-intelligence modules producing health, risk, anomaly and indicators | Role 1 |
| O3 | A calibrated fusion quality model (GBDT primary) returning PASS/FAIL and calibrated P(fail) | Role 1 |
| O4 | SHAP local and global explanations, including the **stage risk mass** construct | Role 1 (compute), Role 2 (display) |
| O5 | What-if simulation with dependency-graph partial re-simulation and A/B diffs | Role 2 (engine, UI); Role 1 (dependency graph, sensitivity) |
| O6 | A constrained recommendation engine with a six-check feasibility guard | Role 1 (algorithm), Role 2 (API, persistence, UI) |
| O7 | A professional React + TypeScript process-control frontend with live SSE updates | Role 2 |
| O8 | Honest scoping: the four claim categories enforced in code, UI and report | Both |

### 1.6 The three headline features (Plan §4.2)

1. **Staged intelligence pipeline.** The architecture mirrors the physical process.
2. **What-if plus counterfactual recommendation under hard constraints.** The system goes beyond classification.
3. **Explainable, honestly scoped decision support.** Risk semantics are kept separate from model confidence.

### 1.7 Four claim categories (binding on both roles; Plan §1.4, §29)

| Category | Meaning | Claim strength |
|---|---|---|
| **PREDICTS** | A statistical model estimates P(fail) from process parameters learned from data | Statistical association |
| **SIMULATES** | A software state machine advances a virtual batch through stages and computes stage indicators from rules and models | Workflow-level, **not** material-physics-level |
| **RECOMMENDS** | A constrained search over admissible windows finds configurations with lower **model-predicted** failure probability | Model-relative, not plant-validated |
| **CANNOT CLAIM** | Verified real-world quality improvement, reduced scrap, improved part strength, better cycle economics or tool life | Requires physical trials and metrology, which do not exist in this project |

**Mandatory permanent UI and report texts.** These appear in the Plan and are owned by Role 2 for display. Role 1 supplies the wording for the report.

| Key | Where | Text (from the Plan) |
|---|---|---|
| `DISCLAIMER_SIMULATION` | Process Control workspace, report §7.1, viva | "This system performs a software-level process simulation. It advances a virtual batch through a modelled sequence of manufacturing stages and evaluates each stage using rules and machine-learning models fitted to process data. It does not solve the physics of polymer melt flow, heat transfer, or shrinkage, and it does not compute material behaviour. Stage indicators are data-driven and rule-driven abstractions, not physical field solutions." |
| `DISCLAIMER_SHAP` | Explainability panel footnote | "Attributions describe how this model reached its output for these inputs. They are statistical associations learned from historical data, not verified physical causes." |
| `DISCLAIMER_RECOMMENDATION` | Every recommendation surface | "These options reduce the FAILURE PROBABILITY ESTIMATED BY THIS MODEL for the given inputs. They are not validated process improvements. Applying them on a real machine requires a trial run and physical inspection." |
| `STATEMENT_SYNTHETIC_DATA` | Report, dataset card, Model Info screen | "The primary training corpus is synthetic. It is generated from documented process-engineering relationships and is intended to exercise and evaluate the system architecture. Model performance figures on synthetic data measure the system's ability to recover the generator's structure; they are not evidence of real-world accuracy." |

The words "solves", "physics" (as a claim), "digital twin" and "validated improvement" **MUST NOT** be used to describe this system (Plan R11).

### 1.8 Final deliverables (Plan §26) and owners

| ID | Deliverable | Owner | Acceptance (Plan) |
|---|---|---|---|
| D1 | Working integrated software (Docker Compose is P2) | Role 2 (Role 1 supports) | Full journey executes end-to-end |
| D2 | Trained models: fusion bundle, stage sub-models (P1), anomaly detector, calibrator | Role 1 | Reproducible from the training command with a recorded seed |
| D3 | Dataset: Tier-1 anchor (if found, with licence) + Tier-2 generator, config, seed, corpus | Role 1 | Regenerable byte-identically from config + seed |
| D4 | Dataset card | Role 1 | Written, reviewed by Role 2 |
| D5 | Preprocessing pipeline (serialized, leak-free, shared by training and serving) | Role 1 | Skew test passes |
| D6 | Five stage intelligence modules | Role 1 | Unit + golden tests pass |
| D7 | Fusion quality engine (calibrated classifier + risk engine) | Role 1 | Metrics report attached |
| D8 | Explainability system (SHAP local/global, stage risk mass, caveats) | Role 1 (compute), Role 2 (UI) | Latency target met |
| D9 | Anomaly detection (per-stage, global Isolation Forest, SPC; autoencoder optional) | Role 1 | Detection-rate report |
| D10 | Recommendation engine (funnel + feasibility guard) | Role 1 | 100% constraint-compliance test |
| D11 | What-if simulation (partial re-sim, sweeps, A/B compare) | Role 2 (Role 1: dependency graph, sweep) | Equivalence property test passes |
| D12 | Interactive visualization (animated stage pipeline) | Role 2 | Demonstrable live |
| D13 | Backend API (REST + SSE, OpenAPI) | Role 2 | All endpoints tested |
| D14 | Database (schema, migrations, seed) | Role 2 | Migrations run clean from empty |
| D15 | Frontend (seven-screen SPA) | Role 2 | All screens functional |
| D16 | Test suite (unit, property, integration, e2e, ML regression, leakage) | Both (each for own modules); Role 2 owns CI | All tests pass; CI green if CI is adopted |
| D17 | Architecture documentation (diagrams, ADRs, module specs) | Both (each documents own modules); Role 2 owns `architecture.md` | Matches implementation |
| D18 | ML evaluation report | Role 1 | Reproducible |
| D19 | Model card | Role 1 | Written |
| D20 | Final project report incl. limitations chapter | Both | Submitted |
| D21 | Presentation deck (~15 slides) | Both | Rehearsed |
| D22 | Demo script (8 min) + recorded backup video | Role 2 (Role 1 co-presents ML parts) | Recorded before demo day |

---

## 2. Source-plan analysis and assumptions

### 2.1 Decisions fixed by the Plan (MUST be preserved)

| Area | Decision fixed by the Plan | Plan ref |
|---|---|---|
| Architecture style | **Modular monolith**: one FastAPI process with strict internal package boundaries plus a separate SPA. No microservices | §6.1 |
| Intelligence integration | In-process Python interfaces. The API never imports scikit-learn. The simulation engine never loads model files. Stage modules are pure functions of `(stage_inputs, upstream_context)` | §6.3 |
| Constraint registry | One versioned YAML/JSON file used by Pydantic validation, UI sliders, recommendation bounds and the risk engine | §6.3, §8.4 |
| Agents | **Zero autonomous agents.** Deterministic modules and a deterministic constrained optimizer | §8.1 |
| Backend | Python, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0, Alembic, pydantic-settings, structlog/stdlib JSON logging, pytest + httpx | §16.1, §20 |
| Database | SQLite (dev), PostgreSQL (demo, optional). JSON columns for flexible fields. Wide typed `run_parameters` table. Scenarios are runs (no separate table) | §17 |
| Live updates | **SSE** for server→client state; **REST** for all commands. Polling is the fallback. WebSocket is rejected | §18 |
| Frontend | React 18 + TypeScript + Vite, Tailwind, shadcn/ui (Radix), hand-built SVG pipeline, Recharts, TanStack Query, Zustand, Framer Motion (light). No Three.js | §15.5 |
| ML | scikit-learn pipelines, **XGBoost primary**, LightGBM comparison, Optuna, MLflow (local file backend), joblib bundles, SHAP TreeExplainer, Isolation Forest | §9, §20 |
| Calibration | Mandatory isotonic (or Platt if the calibration set is small) on a held-out calibration split, persisted in the bundle | §9.9 |
| Splitting | GroupKFold by `batch_id`; temporal final holdout (last ~20%); leave-one-machine-out diagnostic; calibration carved from training | §9.6 |
| Selection metrics | PR-AUC and FAIL-recall. Accuracy is never used for selection | §9.7, §24.1 |
| Dataset | Three-tier anchored hybrid: Tier-1 real anchor, Tier-2 mechanism-based synthetic generator (primary corpus), Tier-3 augmentation (P1) | §19 |
| Recommendation | Three-stage funnel: rule-guided proposal → constrained coordinate search → optional differential-evolution refinement, plus a **six-check feasibility guard**. Bayesian optimization rejected | §14 |
| Auth | None for the MVP. CORS restricted. In-process rate limiting. Optional static `X-API-Key` | §16.6 |
| Model bundle | Directory `models/<name>/<semver>/` containing preprocessor, model, calibrator, SHAP background, `feature_schema.json`, `metrics.json`, `metadata.json`, `constraints_version.txt`. The bundle is loaded whole | §9.10 |

### 2.2 Adaptation from a 3–4 member team to a 2-role team

The Plan (§21.3) assumed four roles. This roadmap maps them onto two:

| Plan role | Maps to | Notes |
|---|---|---|
| ML engineer | **Role 1** | Unchanged |
| Integrator / domain lead (constraint registry, remedy tables, domain justification) | **Role 1** (domain content) + **Role 2** (testing, demo, deployment) | Role 1 owns the registry **content** and loader. Role 2 consumes it everywhere |
| Backend engineer | **Role 2**, except the recommendation **algorithm** | Recommendation search, guard and ranking go to Role 1. The `/recommend` endpoint, persistence and UI stay with Role 2 |
| Frontend engineer | **Role 2** | Unchanged |

### 2.3 Reconciliations of inconsistencies or gaps in the Plan

| # | Observation in the Plan | Resolution in this roadmap |
|---|---|---|
| RC-01 | F4 says "Six stage intelligence modules", but §8 specifies five stage modules plus a fusion engine (S6) | **Five** stage-intelligence modules (S1–S5) plus the fusion engine at S6 |
| RC-02 | Uses both `thickness_mm` and `wall_thickness_mm` | Canonical name is **`wall_thickness_mm`** |
| RC-03 | `barrel_temp_rear/mid/front` has no unit suffix | Canonical names are `barrel_temp_rear_c`, `barrel_temp_mid_c`, `barrel_temp_front_c` |
| RC-04 | Stage referred to as both THERMAL and PLASTICIZING (e.g. `"stage:THERMAL"`) | Canonical enum value is **`PLASTICIZING`**; display label is "Plasticizing / Thermal". Anomaly scope strings use the enum, e.g. `"stage:PLASTICIZING"` |
| RC-05 | Generator samples regrind on [0, 0.30] (fraction), but the UI and journey use 15 % (percent) | Canonical unit is **percent (0–100)** for every `_pct` field. The generator converts internally |
| RC-06 | Stage risk examples use LOW/MEDIUM/HIGH; prediction uses NORMAL…CRITICAL | One shared 5-level `RiskLevel` enum `NORMAL < LOW < MEDIUM < HIGH < CRITICAL` with ordinals 0–4 for both |
| RC-07 | BLOCKED is a stage substate and also a "To" state in the FSM table | `BLOCKED` is both a stage substate and a run status (`RunStatus.BLOCKED`, with `blocked_stage` set) |
| RC-08 | `make train` assumed; the dev machine is Windows without `make` | Use cross-platform `uv run python -m ml_pipeline.cli <command>`. A Makefile MAY be added as a thin wrapper for Unix users |
| RC-09 | `ml_pipeline/01_ingest/ …` directories are not importable Python packages (leading digits) | `ml_pipeline/` becomes an importable package with modules `ingest.py`, `validate.py`, `eda.py`, … (Section 4) |
| RC-10 | Plan phase order runs ML phases 0–9 before the backend (Phase 10) | Both roles start in **W1**. Role 2 builds against mocks from W1–W2 (Plan §22.1 parallelisation note, R14, R19) |
| RC-11 | Plan Phase 4 (advanced ML) precedes Phase 5 (stage modules), yet "the fusion feature set cannot be frozen before [stage modules] complete" | Role 1 order: baselines/GBDT on raw+engineered (R1-P4) → stage modules (R1-P5) → fusion v1 + calibration (R1-P6). This keeps the Plan's gates |
| RC-12 | Rolling features (§9.3) need shot history, but `/predict` and the simulation score **one** recipe with no history | Rolling features are **excluded from the fusion model**. They MAY appear only in offline SPC/analytics (documented in the feature schema as "unavailable at serving time") |
| RC-13 | Stage sub-models (S3 short-shot/flash, S5 warp, S2 ridge, S4 sink) are described, but the MVP (§23.1) says "rule + indicator based" | MVP modules are rule + indicator + statistics only. Supervised sub-models are **P1**, MUST be trained out-of-fold, and sit behind a registry feature flag |
| RC-14 | MLP benchmark: Plan F18 = P2, but it appears in Plan Phase 4 | **P2**, started only after all P0 work is integrated |
| RC-15 | Autoencoder: Plan §12.2 says P1, §23.3 says showcase | **P2** |
| RC-16 | Recommendation guard check 4 uses an Isolation Forest score, but Isolation Forest is P1 (F15) | In P0, check 4 uses **per-feature training percentile bounds** (from `feature_schema.json`). The Isolation Forest score is added in P1 |
| RC-17 | Plan §21.3 puts the recommendation service with the backend engineer | Split by a stable interface: algorithm = Role 1 (`app/recommendation/`); service/endpoint/persistence/UI = Role 2 |
| RC-18 | Event catalogue has no `run.resumed`, override acknowledgement or error event; the API has no abort endpoint although the FSM has ABORT | Added as **[PROPOSED]**: `run.resumed`, `stage.override_acknowledged`, `run.error`, `POST /simulation/runs/{id}/abort` |
| RC-19 | "Save scenario" UI action exists, but no endpoint for it | Added as **[PROPOSED]**: `PATCH /simulation/runs/{id}/label` (only `scenario_label` is mutable) |
| RC-20 | Analytics screen mentions failure rate by resin lot; the API lists only by-machine / by-parameter | Added as **[PROPOSED]**: `GET /analytics/by-material` |
| RC-21 | Plan says Python 3.11+. The machine defaults to Python 3.14.x; 3.12 is also installed | Pin **Python 3.12** for the project (Appendix A, UD-01) |

### 2.4 Assumptions

| ID | Assumption | Consequence if wrong |
|---|---|---|
| A-01 | No suitable openly licensed injection-molding dataset with named parameters, lot attributes, machine identity and a binary label is assumed to exist (Plan §19.1). Tier-1 availability is **unknown** until R1-P1 completes | If none is found, the report states that no real-data validation was possible (Plan R2) |
| A-02 | Every numeric window, threshold and weight in Section 8 is a **[PROPOSED] placeholder** until R1-P1 attaches a literature citation or marks it `heuristic` / `unvalidated` | Values may change via the contract-change procedure |
| A-03 | The Tier-2 synthetic generator is the primary training corpus | All synthetic-data metrics are reported as "recovering the generator", never as industrial accuracy |
| A-04 | Single-user, single-tenant local prototype. No authentication | — |
| A-05 | Both members can run Python 3.12 + uv and Node 24 + npm locally (verified on this development machine on 2026-10-14: Python 3.12 and 3.14, uv 0.10.7, Node 24.14.1, npm 11.11.0, Docker 29.5.2 / Compose v5.1.4; no `make`, no `pnpm`) | If a member's machine differs, record it in `docs/integration_status.md` |
| A-06 | Model artifacts are gitignored (Plan §21.1). They are transferred between members as versioned bundle archives with SHA-256 manifests (Section 14.5) | — |
| A-07 | The decision threshold is a product decision recorded in the bundle (Plan §24.1). The initial operating point is FAIL-recall ≥ 0.85 **[PROPOSED]** | Threshold may change |
| A-08 | Risk band thresholds start from the [PROPOSED] values in Section 8.6 and are re-derived from empirical failure rates per probability decile in R1-P6 (Plan R13) | Registry minor-version bump |
| A-09 | API and contract identifiers for reference entities are their **codes** (`machine_id = "MC-03"`, `product_id = "PP-JBOX-42"`, `material_lot_id = "A-771"`). Integer surrogate keys stay internal to the DB | — |

### 2.5 Architectural decisions (summary; full list in Appendix A)

**All of UD-01 to UD-20 were approved on 2026-10-15**, as recommended in Appendix A. The highest-impact approved items:
- **UD-01** Python 3.12 pin.
- **UD-02** Repository hosting and artifact transfer.
- **UD-07** How an overridden critical breach is displayed.
- **UD-08** RESET after FINAL_RESULT.
- **UD-09** Cycle-time coupling in what-if.
- **UD-11** Hybrid mock/real intelligence mode.
- **UD-19** Ownership of `app/contracts/`.

---

## 3. System architecture and end-to-end data flow

### 3.1 Layered architecture with ownership (Plan §6.2, §27)

```
+===========================================================================+
| PRESENTATION  React 18 + TS + Vite + Tailwind + shadcn/ui        [Role 2] |
|  Process Control | Explainability | What-If | Recommendations             |
|  History | Analytics | Model Info                                         |
|  TanStack Query (server state) + Zustand (UI/draft state) + EventSource   |
+=================+=========================================+===============+
                  | REST /api/v1 (commands, queries)        | SSE (state events)
+=================v=========================================v===============+
| API LAYER  FastAPI + Pydantic v2                                  [Role 2] |
|  routers: simulation, predict, whatif, recommend, analytics, meta, ref     |
|  validation tiers: schema (registry ranges) -> coupling (registry rules)   |
|  error envelope | request/run correlation IDs | rate limits | CORS         |
+=================+=========================================================+
                  |
+=================v=========================================================+
| APPLICATION SERVICES                                              [Role 2] |
|  simulation_service (FSM, stage runner, event bus, LRU stage cache)        |
|  inference_service / explain_service (thin wrappers over the interface)    |
|  whatif_service (dependency-graph partial re-sim, diffs, lineage)          |
|  recommendation_service (calls interface, persists results)               |
|  analytics_service (DB aggregations)                                       |
+=================+=========================================================+
                  |  in-process Python call through ONE interface:
                  |  app.contracts.interface.QualityIntelligence
+=================v=========================================================+
| INTELLIGENCE LAYER  (pure, no DB, no HTTP)                        [Role 1] |
|  S1 Material -> S2 Thermal -> S3 Injection -> S4 Packing -> S5 Cooling     |
|  feature builder -> fusion model (XGBoost) + calibrator -> risk engine     |
|  explainability (TreeSHAP, stage risk mass) | anomaly (z/IQR, IsoForest)   |
|  recommendation funnel + feasibility guard | sensitivity sweeps | SPC      |
|  CONSTRAINT REGISTRY constraints.yaml + remedies.yaml + fleet.yaml        |
|  (content + loader: Role 1; consumed by every layer)                       |
+=================+=========================================================+
                  |
+=================v=========================================================+
| DATA LAYER                                                                 |
|  Application DB: SQLAlchemy 2.0 + Alembic, SQLite / PostgreSQL    [Role 2] |
|  Model store: models/<name>/<semver>/ bundles (read-only to app) [Role 1] |
|  Dataset store: data/raw|interim|processed|synthetic|reports      [Role 1] |
+===========================================================================+
  OFFLINE, never in the request path                               [Role 1]
  ml_pipeline: ingest -> validate -> EDA -> features -> split -> train ->
               tune -> evaluate -> calibrate -> explain -> package -> register
```

### 3.2 Module boundary rules (Plan §6.3, §27.2), binding

| # | Rule | Enforced by |
|---|---|---|
| B1 | `app/api/`, `app/schemas/`, `app/services/`, `app/engine/`, `app/db/` MUST NOT import scikit-learn, xgboost, shap, joblib or `ml_pipeline` | Import-boundary test `tests/test_import_boundaries.py` (Role 2 owns; Role 1 reviews) |
| B2 | The simulation engine MUST NOT load model files. It calls `QualityIntelligence` only | Same test |
| B3 | `app/intelligence/`, `app/ml/`, `app/recommendation/`, `app/domain/` MUST NOT import `app.db`, `app.api`, `app.services`, `app.engine`, `sqlalchemy`, `fastapi`, and MUST NOT perform network or DB I/O. File reads are allowed only during facade construction (bundle and registry loading) | Import-boundary test (Role 1 owns this half) |
| B4 | Stage modules are pure and deterministic: same inputs + same loaded references ⇒ identical output. No clock, no randomness, no global mutable state | Purity tests (Role 1) |
| B5 | The recommendation module may only call the inference pipeline and the constraint registry. It cannot mutate simulation state (Plan §6.3 rule 4) | Code review + import test |
| B6 | Parameter limits exist **only** in `constraints.yaml`. The frontend reads them from `GET /api/v1/constraints`. The backend reads them through the loader | Grep test for hardcoded limits in `frontend/src` (Role 2); review |
| B7 | `ml_pipeline` is never invoked from a request handler (Plan §27.2) | Import-boundary test |
| B8 | Training and serving use the **same** feature builder (`app/ml/features.py`) and feature order from `feature_schema.json` (Plan §9.10, R18) | Skew test (Role 1) |

### 3.3 Integration mode decision

- The agreed integration is **direct in-process Python interfaces** (modular monolith).
- An HTTP inference microservice MUST NOT be introduced. The Plan explicitly rejects microservices (§6.1, F25).
- Role 2 depends only on `app.contracts` (types, interface, errors) and on a factory that returns either the real implementation (`app.intelligence.facade.RealQualityIntelligence`) or the mock (`app.intelligence_mock.MockQualityIntelligence`).

### 3.4 End-to-end flow with owners (Plan §5, §28)

| Step | What happens | Owner |
|---|---|---|
| 1 | UI loads `GET /constraints`, `/machines`, `/products`, `/materials`. Sliders are built from the registry | R2 (registry content: R1) |
| 2 | User selects machine `MC-03`, product `PP-JBOX-42`, lot `A-771` and edits the recipe. Client-side validation mirrors the registry | R2 |
| 3 | `POST /simulation/runs` runs schema validation (registry ranges) then coupling validation (`registry.check_couplings`), persists `process_runs` + `run_parameters`, and returns `run_id` with status `INITIALIZED` | R2 (check functions: R1) |
| 4 | UI opens the SSE stream `GET /simulation/runs/{id}/events`, then calls `POST …/start {mode:"auto", speed_factor:1}` | R2 |
| 5 | FSM emits `run.started`. For each stage S1…S5: `stage.started` → stage runner selects the input slice (`registry.stage_inputs(stage)`) → LRU cache lookup → `intelligence.run_stage(...)` → persist `stage_results` → emit `anomaly.flagged` / `constraint.breached` / `stage.blocked` as applicable → `stage.completed` → pass `upstream_out` forward | R2 orchestrates; R1 computes |
| 6 | On a critical breach with `halt_on_critical=true`: status `BLOCKED`, `stage.blocked` is emitted, and the UI shows an override dialog. `POST …/override` records the acknowledgement and continues | R2 (block decision content: R1) |
| 7 | S6 QUALITY_INSPECTION: `intelligence.predict(...)` builds features in schema order → XGBoost → isotonic calibrator → threshold → label; global anomaly; OOD caveats; risk engine; local SHAP + stage risk mass | R1 |
| 8 | Persist `predictions`, emit `prediction.ready` then `run.completed` | R2 |
| 9 | UI renders the result card, SHAP bars, stage-risk donut and caveat banner | R2 |
| 10 | "What should I change?" → `POST /recommend` → `intelligence.recommend(...)` (proposal → coordinate search → guard → ranking → optional DE) → persist `recommendations` | R1 algorithm; R2 endpoint/persistence/UI |
| 11 | "Send to what-if" → `POST /whatif` → `registry.invalidated_stages(changed)` → reuse parent stages upstream → re-run invalidated stages + fusion → child run (`is_whatif=true`, `parent_run_id`) → diff | R2 (dependency graph: R1) |
| 12 | Sensitivity sweep `POST /whatif/sensitivity` → `intelligence.sensitivity(...)` | R1 compute; R2 endpoint/UI |
| 13 | Save scenario (`PATCH …/label`) → History lineage tree → Analytics (excludes what-if and mock rows by default) | R2 |

### 3.5 Online vs offline separation

- **Online (request path):** API, services, engine, intelligence facade, loaded bundles.
- **Offline:** `ml_pipeline` (generation, training, tuning, evaluation, packaging). It runs from the CLI only.
- The application DB stores **runs**, never the training corpus (Plan §17.5). Training from live application tables is forbidden.

---

## 4. Shared repository structure and module ownership

**[PROPOSED] (UD-02):** the repository root is the current project folder (`minor project/`, logical name `smart-mfg-quality`). Owners: **R1** = Role 1, **R2** = Role 2, **JOINT** = both must approve changes, with the primary author listed first.

```
smart-mfg-quality/                         (repo root)
├── PROJECT_DEVELOPMENT_ROADMAP.md         JOINT (this file)
├── Smart_Manufacturing_Quality_Intelligence_Project_Plan.pdf   JOINT (read-only reference)
├── README.md                              R2 (R1 adds the ML quickstart section)
├── CODEOWNERS                             R2 (content mirrors this section)
├── .python-version                        R2  -> "3.12"
├── pyproject.toml                         R2  (dependency group "ml"/"dl": R1, JOINT approval)
├── uv.lock                                R2  (regenerated by whoever changes deps, in the same PR)
├── .env.example                           R2  (R1 adds SMQI_DATA_DIR / MLflow vars by PR)
├── .gitignore / .gitattributes            R2
│
├── backend/
│   ├── alembic.ini                        R2
│   ├── alembic/versions/*.py              R2
│   ├── app/
│   │   ├── main.py                        R2  FastAPI app factory, startup checks
│   │   ├── core/        config.py logging.py ids.py                      R2
│   │   ├── contracts/   __init__.py (CONTRACTS_VERSION) enums.py recipe.py context.py
│   │   │                stage.py anomaly.py prediction.py explanation.py
│   │   │                recommendation.py sensitivity.py errors.py interface.py version.py
│   │   │                                   JOINT (primary author R1; R2 approval mandatory)
│   │   ├── domain/      constraints.yaml remedies.yaml fleet.yaml CHANGELOG.md
│   │   │                constraint_loader.py dependency_graph.py         JOINT (primary R1)
│   │   ├── intelligence/ base.py derivations.py material.py thermal.py injection.py
│   │   │                packing.py cooling.py risk_engine.py anomaly.py spc.py
│   │   │                references.py pipeline.py facade.py              R1
│   │   ├── ml/          features.py bundle.py predict.py explain.py ood.py           R1
│   │   ├── recommendation/ funnel.py proposals.py search.py guard.py ranking.py
│   │   │                refine.py sensitivity.py                         R1
│   │   ├── intelligence_mock/ mock.py hybrid.py                          R2
│   │   ├── api/         routes_simulation.py routes_prediction.py routes_whatif.py
│   │   │                routes_recommend.py routes_analytics.py routes_meta.py
│   │   │                routes_reference.py deps.py errors.py sse.py     R2
│   │   ├── schemas/     envelope.py simulation.py prediction.py whatif.py
│   │   │                recommend.py analytics.py reference.py           R2
│   │   ├── services/    simulation_service.py inference_service.py explain_service.py
│   │   │                whatif_service.py recommendation_service.py
│   │   │                analytics_service.py reference_service.py        R2
│   │   ├── engine/      state_machine.py stage_runner.py events.py cache.py run_registry.py  R2
│   │   └── db/          base.py models.py session.py repositories.py seed.py  R2
│   └── tests/
│       ├── contract/    fixtures/*.json  test_interface_contract.py      JOINT (fixtures R1, harness R2)
│       ├── domain/ intelligence/ ml/ recommendation/                     R1
│       ├── api/ engine/ db/ services/ schemas/                           R2
│       ├── fixtures/model_bundle_tiny/   (small real bundle for CI)      R1
│       ├── test_import_boundaries.py                                     R2 (R1 reviews)
│       └── e2e/                                                         R2 (R1 contributes)
│
├── ml_pipeline/                           R1 (offline; importable package)
│   ├── __init__.py  cli.py  config/*.yaml
│   ├── ingest.py validate.py eda.py clean.py preprocess.py split.py
│   ├── train_baselines.py train_fusion.py tune.py calibrate.py evaluate.py
│   ├── explain_offline.py anomaly_train.py stage_reference_stats.py
│   ├── package_bundle.py registry_update.py recommend_eval.py
│   ├── synthetic/  generator.py mechanisms.py generator_config.yaml
│   ├── tests/                             R1
│   └── notebooks/                         R1 (exploratory only; nothing depends on them)
│
├── data/              raw/ interim/ processed/ synthetic/ reports/   R1 (gitignored except
│                      */source_manifest.json, */MANIFEST.sha256, README.md)
├── models/            fusion/<semver>/ anomaly/<semver>/ stage_stats/<semver>/   R1 produces,
│                      registry.json  MANIFEST.sha256                  R2 reads only
│                      (bundles gitignored; registry.json + manifests committed)
├── mlruns/            R1 (gitignored)
├── var/               R2 (gitignored; SQLite DB file var/smqi.db, logs)
│
├── frontend/                              R2
│   ├── package.json package-lock.json vite.config.ts tsconfig*.json
│   ├── tailwind.config.ts postcss.config.js components.json(shadcn) .eslintrc.cjs
│   ├── src/api/generated/schema.d.ts      R2 (generated from OpenAPI; never hand-edited)
│   ├── src/api/client.ts  src/api/sse.ts
│   ├── src/stores/  src/features/{process-control,explainability,whatif,
│   │                recommendations,history,analytics,model-info}/
│   ├── src/components/ (pipeline SVG, charts, primitives)
│   └── src/test/ (Vitest + RTL + MSW fixtures copied from backend/tests/contract/fixtures)
│
├── docs/
│   ├── architecture.md api.md events.md database.md demo_script.md       R2
│   ├── integration_status.md                                             JOINT (both update)
│   ├── contracts/*.schema.json (generated from app.contracts)            JOINT (generated)
│   ├── contract_changes/CCR-*.md                                         JOINT
│   ├── parameter_dictionary.md dataset_feasibility.md dataset_card.md
│   │   synthetic_generator_spec.md model_card.md ml_evaluation_report.md
│   │   recommendation_evaluation_report.md intelligence_interface.md
│   │   stage_specs/S1..S5.md leakage_checklist.md                       R1
│   └── decisions/ADR-*.md                 author of the decision; JOINT review
├── scripts/       gen_api_types.(ps1|sh) export_contract_schemas.py dev helpers  R2 (R1: ML scripts)
├── docker/        Dockerfile.api Dockerfile.web compose.yaml (P2)       R2
└── .github/workflows/ci.yml (P2)                                       R2
```

### 4.1 Packaging decision

- One root `pyproject.toml` (uv-managed, Python 3.12) installs two importable packages in editable mode:
  - `app` from `backend/app`
  - `ml_pipeline`
- This lets offline training import the **same** `app.ml.features` and `app.intelligence` code used at serving time (Plan R18).
- Dependency groups:

| Group | Contents (versions resolved by `uv lock` in R2-P1 and recorded in `uv.lock`; no versions are invented here) | Owner |
|---|---|---|
| default (runtime) | fastapi, uvicorn, pydantic (v2), pydantic-settings, sqlalchemy (2.0), alembic, pyyaml, structlog, numpy, pandas, pyarrow, scikit-learn, xgboost, shap, joblib, scipy | R2 (ML runtime libs: R1) |
| `ml` (training only) | lightgbm, optuna, mlflow, matplotlib, imbalanced-learn, hypothesis (shared with dev), jupyter | R1 |
| `dl` (P2) | torch | R1 |
| `dev` | pytest, pytest-asyncio, httpx, hypothesis, ruff, black, mypy, psycopg (for the optional PG test) | R2 |

### 4.2 Responsibility matrix

| Module / artifact | Primary owner | Consumer(s) | Integration point |
|---|---|---|---|
| `app/contracts/` | JOINT (R1 authors) | Both | Python types + `QualityIntelligence` Protocol; JSON Schemas in `docs/contracts/` |
| `app/domain/constraints.yaml`, `remedies.yaml`, `fleet.yaml`, loader, dependency graph | R1 | R2 (validation, `/constraints`, seed, what-if), frontend (via API) | `ConstraintRegistry` API (Section 8.4) |
| Stage modules S1–S5 | R1 | R2 stage runner | `run_stage()` |
| Feature builder, bundle loader, predict, calibrator, risk engine | R1 | R2 inference/simulation services | `predict()` |
| SHAP explanations, stage risk mass, global explanation | R1 | R2 explain service + UI | `explain()`, `global_explanation()` |
| Anomaly (L1 stage, L2 Isolation Forest, SPC) | R1 | R2 | Inside `StageResult` / `PredictionResult`; `spc_check()` |
| Recommendation funnel + guard + ranking | R1 | R2 recommendation service | `recommend()` |
| Sensitivity sweep | R1 | R2 what-if service | `sensitivity()` |
| Synthetic generator, data pipeline, training, evaluation | R1 | — (offline) | Bundles in `models/` |
| Mock + hybrid intelligence | R2 | R2 | Implements `QualityIntelligence` |
| FastAPI app, routers, API schemas, errors, SSE | R2 | Frontend | OpenAPI `/api/v1/openapi.json` |
| Simulation FSM, stage runner, LRU cache, event bus | R2 | API | Internal |
| What-if service (partial re-sim, diff, lineage) | R2 | API | Uses `invalidated_stages()`, `run_stage()`, `predict()` |
| Database models, migrations, repositories, seed | R2 | Services | Internal |
| Frontend (7 screens) | R2 | User | REST + SSE |
| Contract test fixtures | R1 | Both | `backend/tests/contract/fixtures/*.json` |
| Contract test harness | R2 | Both | Parametrized over mock and real implementations |
| E2E tests, deployment, demo | R2 | Both | — |

---

## 5. Role definitions and responsibility boundaries

### 5.1 ROLE 1: AI/ML, Manufacturing Intelligence & Recommendation Engineer

**Primary ownership:**
- the data science, ML, stage-intelligence algorithms, model inference, explainability, anomaly detection and constrained recommendations;
- the **domain content** of the constraint registry, remedy table and virtual fleet.

**Responsibilities:**
- Dataset discovery, licensing and provenance.
- Tier-2 synthetic generator, data validation, EDA and preprocessing.
- Leakage-safe splitting, feature engineering, baselines, the GBDT fusion model, calibration and threshold.
- MLP benchmark (P2).
- Model serialization, metadata and versioning.
- The five stateless stage modules, health aggregation, risk levels, rule indicators, L1 anomalies.
- Fusion features and inference, the risk engine and OOD caveats.
- SHAP local and global explanations with stage risk mass.
- Isolation Forest (P1), SPC rules (P1), autoencoder (P2).
- The recommendation funnel and feasibility guard, plus the sensitivity sweep.
- Contracts v0.x authorship, contract fixtures, intelligence unit, property and regression tests.
- Dataset card, model card, ML and recommendation evaluation reports.
- The integration package for Role 2.

**MUST NOT:**
- Redefine backend architecture, DB schema, API routes, event formats or frontend behaviour.
- Write to the application DB.
- Add HTTP endpoints.

**May contribute (only when assigned):**
- E2E test scenarios.
- Review of Role 2 PRs that touch the contracts or registry.
- Report text for frontend explanations.

### 5.2 ROLE 2: Backend, Simulation, Database & Frontend Engineer

**Primary ownership:** application infrastructure, persistence, simulation orchestration, API, event streaming, UI, deployment and system integration.

**Responsibilities:**
- Repository and tooling setup; FastAPI architecture; API Pydantic schemas.
- Registry-driven validation using the R1 loader.
- SQLAlchemy models and Alembic migrations.
- Simulation FSM and stage lifecycle; LRU stage cache; event bus; SSE.
- Mock and hybrid intelligence.
- Integration of real intelligence.
- The what-if engine (partial re-simulation, diff, lineage) and scenario persistence.
- The React + TypeScript SPA (7 screens) and history/analytics.
- Logging, errors and configuration.
- Docker Compose (P2), CI (P2).
- Backend, frontend and E2E tests; the final demonstration.

**MUST NOT:**
- Recreate or approximate ML models, stage rules, risk logic, SHAP or recommendation search outside the mock.
- Invent prediction results.
- Hardcode parameter limits.
- Present mock outputs as genuine inference.

**May contribute (only when assigned):**
- Contract-fixture review.
- Integration tests that call the real facade.
- Interface feedback through CCRs.

### 5.3 Modules spanning both roles: split by stable interface

| Capability | Role 1 side | Role 2 side | Stable interface |
|---|---|---|---|
| Parameter validation | Registry content, `check_box`, `check_couplings`, `check_hard_constraints` | Pydantic schemas and validators calling those functions; HTTP 422 shaping; UI form validation from `/constraints` | `ConstraintRegistry` |
| Stage execution | `run_stage()` computes the `StageResult` | FSM ordering, timing, caching, persistence, events | `run_stage()` + `StageResult` |
| BLOCKED behaviour | Decides `blocked` + `block_reason` from registry hard constraints | Halts the FSM, emits `stage.blocked`, records the override | `StageResult.blocked` |
| What-if | `invalidated_stages()`, `stage_inputs()`, pure re-evaluation | Partial re-sim orchestration, parent reuse, child runs, diff, persistence | Registry dependency graph + `run_stage()`/`predict()` |
| Recommendations | Candidate generation, guard, ranking, stability, cycle-time delta | Request handling, rate limiting, persistence, UI cards, send-to-what-if | `recommend()` + `RecommendationResponse` |
| Explainability | SHAP numbers, grouping, stage risk mass, caveat flag | Rendering, disclaimers, caveat banner | `LocalExplanation`, `GlobalExplanation` |
| Model traceability | `metadata.json`, `registry.json`, `version_info()` | `model_versions` table rows, `/models`, Model Info screen | `IntelligenceVersionInfo` |

---

## 6. User-selected role mode for the coding agent

### 6.1 Mandatory rule

The coding agent works in **exactly one role at a time**:
- `ROLE 1: AI/ML, Manufacturing Intelligence, and Recommendation Engineer`
- `ROLE 2: Backend, Simulation, Database, and Frontend Engineer`

### 6.2 Before implementation begins

1. If the user has **not** specified a role in the current conversation, the agent MUST ask exactly:
   > **"Which role should I follow: Role 1 (AI/ML and Manufacturing Intelligence) or Role 2 (Backend, Simulation, Database, and Frontend)?"**

   The agent MUST NOT write implementation code until the role is clear.
2. If the role has already been specified in the current conversation, the agent uses it without asking again.
3. The agent then:
   - reads this entire roadmap, the Plan, `docs/integration_status.md` and the relevant existing source files;
   - inspects the repository (never assumes it is empty; never recreates existing files);
   - identifies the **earliest incomplete phase** of the selected role, or the phase the user named after checking its prerequisites.

### 6.3 Behaviour per role

| | Role 1 selected | Role 2 selected |
|---|---|---|
| Implements | Section 11 phases only | Section 12 phases only |
| May create/modify | `backend/app/{intelligence,ml,recommendation}/`, `ml_pipeline/`, `data/` manifests, `models/registry.json`, R1 test dirs, R1 docs, `backend/tests/contract/fixtures/`. **JOINT** files (`contracts/`, `domain/`) only through the CCR procedure (Section 10.4) | `backend/app/{api,schemas,services,engine,db,core,intelligence_mock}/`, `main.py`, `alembic/`, `frontend/`, `docker/`, `scripts/`, CI, R2 test dirs, R2 docs, `pyproject.toml`/`uv.lock`. **JOINT** files only through CCR |
| Must deliver to the other role | Contract updates, fixtures, sample payloads, bundles + manifests, interface docs, tests | Mock behaviour, OpenAPI schema, integration feedback, E2E results |
| Must avoid | Backend routes, DB models, FSM, SSE, frontend | Training pipelines, model logic, stage rules, SHAP, recommendation search |
| If the other role's interface is missing | Write against the contract and test with contract fixtures | Use the mock or hybrid backend. Never invent a competing interface |

### 6.4 Role change

1. Stop work on the current role.
2. Summarize status with the Appendix B template: completed tasks, incomplete tasks, integration dependencies.
3. Update `docs/integration_status.md`.
4. Switch only after the user explicitly names the new role.

A role change **does not authorize** rewriting the other role's existing work.

### 6.5 Phase discipline

- Follow the phase order. Check dependencies and compatibility before coding (Section 15.6 gate list).
- Run the phase's tests. A phase is never complete just because code exists.
- If tests cannot run, report exactly what is unverified.
- After each phase, report with Appendix B, then **stop and request confirmation** before the next phase, unless the user explicitly authorized multiple phases.

---

## 7. Shared domain schemas and data contracts

All shared types live in `backend/app/contracts/` as **frozen Pydantic v2 models**. JSON Schemas are exported to `docs/contracts/` by `scripts/export_contract_schemas.py`. The frontend receives the same shapes through the OpenAPI schema, from which its TypeScript types are generated. Field names below are **canonical**: the same spelling is used in the dataset, the feature schema, the registry, the DB columns, the API JSON and the TypeScript types.

### 7.1 Conventions (binding)

| Topic | Rule |
|---|---|
| Naming | `snake_case` fields; `UPPER_SNAKE` enum values; `PascalCase` type names |
| Units | Encoded as suffixes: `_c` °C, `_bar` bar, `_s` seconds, `_h` hours, `_mm` mm, `_mm_s` mm/s, `_pct` percent 0–100, `_ton` metric ton-force, `_g` grams, `_cm2` cm², `_days` days, `_ms` milliseconds. `mfi` is g/10 min with no suffix (Plan name kept). `screw_rpm` is rev/min. `*_proxy`, `*_index` and `*_score` values are dimensionless |
| Numbers | Floats are IEEE-754 doubles. Probabilities and health scores are in `[0, 1]`. No NaN or Infinity in any API payload: missing means `null` |
| IDs | `run_id`, `prediction_id`, `request_id`, `event` IDs are UUIDv4 strings. Reference entities use **codes** (`machine_id="MC-03"`) (A-09) |
| Time | ISO-8601 UTC with a `Z` suffix (`2026-10-14T12:04:01.123Z`) |
| Versions | SemVer strings: `model_version="fusion-1.0.0"`, `constraints_version="constraints-1.0.0"`, `CONTRACTS_VERSION="0.1.0"`, `module_version="material-1.0.0"` |
| Provenance tag | Every derived indicator, threshold and weight carries `DataProvenance`: `dataset_derived`, `specification_derived`, `heuristic`, `learned`, `synthetic`, `unvalidated` |

### 7.2 Enumerations (`contracts/enums.py`)

| Enum | Values |
|---|---|
| `StageName` | `MATERIAL_CONDITIONING`, `PLASTICIZING`, `INJECTION`, `PACKING`, `COOLING`, `QUALITY_INSPECTION`. Sequence order is fixed (index 1–6). `QUALITY_INSPECTION` is executed by `predict()`, not `run_stage()` |
| `RunStatus` | `INITIALIZED`, `MATERIAL_CONDITIONING`, `PLASTICIZING`, `INJECTION`, `PACKING`, `COOLING`, `QUALITY_INSPECTION`, `FINAL_RESULT`, `PAUSED`, `BLOCKED`, `ABORTED` |
| `StageSubstate` | `PENDING`, `RUNNING`, `COMPLETED`, `BLOCKED` |
| `RiskLevel` | `NORMAL`(0), `LOW`(1), `MEDIUM`(2), `HIGH`(3), `CRITICAL`(4). The ordinal is exposed as `risk_ordinal` |
| `PredictionLabel` | `PASS`, `FAIL` |
| `ConstraintSeverity` | `INFO`, `WARNING`, `CRITICAL` |
| `AnomalyMethod` | `zscore`, `iqr`, `percentile_band`, `spec_limit`, `isolation_forest`, `autoencoder`, `spc` |
| `RunMode` | `auto`, `stepwise` |
| `SpeedFactor` | `0.5`, `1`, `2`, `instant` (serialized as strings `"0.5x"`, `"1x"`, `"2x"`, `"instant"`) |
| `InferenceBackend` | `real`, `mock` |
| `SourceTier` (dataset only) | `real`, `synthetic`, `augmented` |
| `DataProvenance` | see 7.1 |
| `ParameterKind` | `setpoint` (recipe knob), `lot_attribute`, `product_context`, `machine_context` |
| `CandidateFlag` | `EXTRAPOLATED`, `UNSTABLE`, `NEAR_WINDOW_EDGE` |

### 7.3 Machine profile: `MachineProfile` (`contracts/context.py`)

| Field | Type | Unit | Validation | Notes |
|---|---|---|---|---|
| `machine_id` | str | — | matches a code in `fleet.yaml` / DB | e.g. `MC-03` |
| `machine_type` | enum `HYDRAULIC`/`ELECTRIC`/`HYBRID` | — | — | |
| `tonnage_ton` | float | t | registry `machine_context` range | Nominal clamp tonnage |
| `max_inj_pressure_bar` | float | bar | > 0 | Used in the headroom rule |
| `max_clamp_force_ton` | float | t | > 0 | Used in the clamp guard |
| `machine_age_days` | int | days | ≥ 0 | Derived by R2 from `installed_on` at run creation, then snapshotted |
| `days_since_maintenance` | int | days | ≥ 0 | Derived from `last_maintenance_on`, snapshotted |

### 7.4 Product and mold context: `ProductContext`

The Plan models products and molds as one entity (`products(molds)`), so `mold_id == product_id`.

| Field | Type | Unit | Validation |
|---|---|---|---|
| `product_id` | str | — | code, e.g. `PP-JBOX-42` |
| `name` | str | — | — |
| `cavity_count` | int | — | ∈ {1, 4} (Plan §2.2) **[PROPOSED]**: registry `allowed_values` |
| `nominal_shot_weight_g` | float | g | 30–60 for this product family |
| `wall_thickness_mm` | float | mm | registry range |
| `projected_area_cm2` | float | cm² | registry range (per cavity) |

### 7.5 Material lot: `MaterialLot`

| Field | Type | Unit | Validation |
|---|---|---|---|
| `material_lot_id` | str | — | code, e.g. `A-771` |
| `resin_grade` | str | — | must be a key in `constraints.yaml → resin_grades` |
| `mfi` | float | g/10 min | registry range |
| `moisture_pct` | float | % | registry range (box). Spec max is per grade |
| `regrind_pct` | float | % | 0–100 box; plant policy max in registry |
| `colourant_pct` | float | % | registry range |

### 7.6 Process parameter recipe: `ProcessRecipe` (`contracts/recipe.py`)

These are setpoints the operator controls (`kind=setpoint`). Ranges, steps, nominals, `actionable` and `change_cost` come **only** from the registry. The table shows unit, owning stage and default actionability.

| Field | Unit | First consuming stage | Actionable (default) |
|---|---|---|---|
| `drying_time_h` | h | MATERIAL_CONDITIONING | yes |
| `dryer_temp_c` | °C | MATERIAL_CONDITIONING | yes |
| `barrel_temp_rear_c` | °C | PLASTICIZING | yes |
| `barrel_temp_mid_c` | °C | PLASTICIZING | yes |
| `barrel_temp_front_c` | °C | PLASTICIZING | yes |
| `nozzle_temp_c` | °C | PLASTICIZING | yes |
| `melt_temp_c` | °C | PLASTICIZING | yes |
| `screw_rpm` | rpm | PLASTICIZING | yes |
| `back_pressure_bar` | bar | PLASTICIZING | yes |
| `residence_time_s` | s | PLASTICIZING | yes (high change cost) |
| `inj_velocity_mm_s` | mm/s | INJECTION | yes |
| `inj_pressure_bar` | bar | INJECTION | yes |
| `fill_time_s` | s | INJECTION | yes |
| `shot_size_mm` | mm | INJECTION | yes |
| `switchover_position_mm` | mm | INJECTION | yes |
| `clamp_force_ton` | t | INJECTION | yes |
| `hold_pressure_bar` | bar | PACKING | yes |
| `hold_time_s` | s | PACKING | yes |
| `cushion_mm` | mm | PACKING | yes |
| `mold_temp_c` | °C | PACKING (gate-freeze heuristic, 7.10). Dominant effect in COOLING. **Deviation:** Plan §13.2 lists it under S5 only. Invalidation must start at S4 for partial-re-sim correctness | yes |
| `cooling_time_s` | s | COOLING | yes |
| `cycle_time_s` | s | COOLING | derived-by-rule in what-if (UD-09) |
| `ejection_force_proxy` | — | COOLING | no (measured proxy) |

**Non-actionable by default (never changed by recommendations, Plan §14.7):**
- `machine_id` and all machine context
- `product_id`, `wall_thickness_mm`, `cavity_count`, `projected_area_cm2`, `nominal_shot_weight_g`
- the lot attributes `resin_grade`, `mfi`, `moisture_pct`, `regrind_pct`, `colourant_pct`

What-if MAY change any field. Recommendations MAY change only `actionable=true` fields that are not in the request's `locked` list.

### 7.7 Combined input: `RunContext` and `ProcessInput`

```
RunContext   = { machine: MachineProfile, product: ProductContext, material_lot: MaterialLot }
ProcessInput = { context: RunContext, recipe: ProcessRecipe }
```

`ProcessInput.flat()` returns the canonical flat dict (all raw fields, with `machine_id`, `product_id`, `resin_grade` as categoricals). This is the **canonical raw model input schema** and matches the dataset's required columns (Plan §19.5), minus identity, target and diagnostic columns.

### 7.8 Upstream context: `UpstreamContext` (`contracts/stage.py`)

Every field is optional. Each stage may only **add** the keys it owns.

| Key | Type / unit | Produced by | Consumed by |
|---|---|---|---|
| `viscosity_class` | enum `LOW`/`NOMINAL`/`HIGH` (viscosity, from MFI tertiles) | S1 | S2 |
| `moisture_flag` | bool | S1 | S2 |
| `effective_melt_temp_c` | float °C | S2 | S3, S4, S5 |
| `viscosity_proxy` | float (dimensionless, normalised) | S2 | S3 |
| `fill_completion_proxy` | float [0, 1] | S3 | S4 |
| `cavity_pressure_estimate_bar` | float bar | S3 | S4 |
| `residual_stress_proxy` | float (dimensionless) | S4 | S5 |

### 7.9 Stage intelligence output: `StageResult`

| Field | Type | Notes |
|---|---|---|
| `stage_name` | `StageName` | S1–S5 only |
| `sequence_index` | int 1–5 | |
| `substate` | `StageSubstate` | `COMPLETED` or `BLOCKED` when returned by `run_stage()` |
| `inputs_used` | dict[str, float \| str \| None] | Snapshot of the exact input slice values |
| `upstream_in` | `UpstreamContext` | What this stage received |
| `upstream_out` | `UpstreamContext` | What this stage publishes (cumulative) |
| `health_score` | float [0, 1] | Section 7.10 formula |
| `risk_level` | `RiskLevel` | From registry `risk_bands.stage_health`, escalated to `CRITICAL` by any critical breach |
| `risk_ordinal` | int 0–4 | |
| `anomaly` | `StageAnomaly` {`flag`: bool, `score`: float [0, 1], `method`: `AnomalyMethod`, `contributors`: list[{`feature`, `deviation`}], `note`: str} | L1 anomaly (Plan §12.2) |
| `indicators` | dict[str, float \| str \| bool] | Fixed key set per stage (7.10) |
| `indicator_provenance` | dict[str, `DataProvenance`] | One entry per indicator key |
| `notes` | list[str] | Human-readable findings (English, ≤ 160 chars each) |
| `constraint_breaches` | list[`ConstraintBreach`] | |
| `blocked` | bool | True only when a critical rule with `blocks_stage=true` fires |
| `block_reason` | str \| None | |
| `module_version` | str | |
| `constraints_version` | str | |
| `compute_ms` | float | Pure compute time. The FSM's presentation duration is stored separately by R2 |

`ConstraintBreach` = {`rule_id`: str, `severity`: `ConstraintSeverity`, `parameters`: list[str], `value`: float \| None, `limit`: float \| None, `message`: str, `hint`: str \| None, `provenance`: `DataProvenance`, `constraints_version`: str}.

### 7.10 Health score, risk level and per-stage indicator contract (Plan §8.3, §8.4)

**Aggregation (identical for all stages):**

```
penalty  = Σ_i weight_i × severity_i                (weights from registry stage_checks)
health   = clip(1 − penalty, 0, 1)
severity_i (range check)   = 0 if lo ≤ v ≤ hi else min(1, distance_outside / tolerance)
severity_i (z-score check) = min(1, max(0, (|z| − 2) / 2))
severity_i (probability-like risk indicator, e.g. short_shot_risk) = the indicator value itself
risk_level = band(health) from registry risk_bands.stage_health; any CRITICAL breach ⇒ CRITICAL
```

Weights are **documented domain assumptions, not learned parameters** (Plan §8.4). Fitting weights against outcomes is a P1 option and would be a separately versioned module.

**Per-stage contract:**

| Stage | Input fields (raw slice) | Upstream in | Indicators (fixed keys) | Upstream out | BLOCK condition (critical) |
|---|---|---|---|---|---|
| S1 `MATERIAL_CONDITIONING` | `moisture_pct`, `mfi`, `regrind_pct`, `drying_time_h`, `dryer_temp_c`, `resin_grade`, `colourant_pct` | — | `dryness_margin` (spec), `mfi_z` (dataset), `moisture_z` (dataset), `moisture_risk` (heuristic), `regrind_margin` (spec), `viscosity_class` (dataset) | `viscosity_class`, `moisture_flag` | `moisture_pct > spec_max(grade) × critical_factor` |
| S2 `PLASTICIZING` | `barrel_temp_rear_c`, `barrel_temp_mid_c`, `barrel_temp_front_c`, `nozzle_temp_c`, `melt_temp_c`, `screw_rpm`, `back_pressure_bar`, `residence_time_s`, `mfi`, `moisture_pct`, `resin_grade` | `viscosity_class`, `moisture_flag` | `thermal_exposure` (heuristic), `degradation_exposure` (heuristic), `shear_heat_offset_c` (heuristic), `effective_melt_temp_c` (heuristic), `temp_profile_slope` (spec), `profile_monotonic` (spec), `splay_risk` (heuristic), `melt_consistency` (learned, P1; `null` in MVP) | `effective_melt_temp_c`, `viscosity_proxy` | `melt_temp_c > degradation_ceiling_c(grade)` |
| S3 `INJECTION` | `inj_velocity_mm_s`, `inj_pressure_bar`, `fill_time_s`, `shot_size_mm`, `switchover_position_mm`, `clamp_force_ton`, `max_inj_pressure_bar`, `max_clamp_force_ton`, `projected_area_cm2`, `cavity_count` | `effective_melt_temp_c`, `viscosity_proxy` | `fill_index` (heuristic), `shear_rate_proxy` (heuristic), `pressure_headroom` (spec), `cavity_pressure_estimate_bar` (heuristic), `required_clamp_force_ton` (heuristic), `short_shot_risk` (heuristic; learned in P1), `flash_risk` (heuristic; learned in P1), `fill_completion_proxy` (heuristic) | `fill_completion_proxy`, `cavity_pressure_estimate_bar` | `clamp_force_ton < required_clamp_force_ton` (machine-safety class, Plan §8.3 S3.8) |
| S4 `PACKING` | `hold_pressure_bar`, `hold_time_s`, `cushion_mm`, `wall_thickness_mm`, `mold_temp_c` | `fill_completion_proxy`, `cavity_pressure_estimate_bar`, `effective_melt_temp_c` | `packing_integral` (bar·s), `gate_freeze_estimate_s` (heuristic, labelled), `hold_vs_freeze_ratio` (heuristic), `sink_void_risk` (heuristic), `over_pack_risk` (heuristic), `cushion_ok` (spec), `residual_stress_proxy` (heuristic) | `residual_stress_proxy` | none (Plan: no hard block) |
| S5 `COOLING` | `mold_temp_c`, `cooling_time_s`, `wall_thickness_mm`, `cycle_time_s`, `ejection_force_proxy`, `fill_time_s`, `hold_time_s` | `residual_stress_proxy`, `effective_melt_temp_c` | `required_cooling_estimate_s` (heuristic, thickness² family), `cooling_adequacy` (heuristic), `warp_risk` (heuristic; learned in P1), `ejection_risk` (heuristic), `dimensional_stability_index` (heuristic), `cycle_consistency` (heuristic), `cycle_balance` (dataset/engineered) | — (all five stage vectors go to fusion) | none |

**[PROPOSED] stage-health risk bands** (registry `risk_bands.stage_health`, chosen to reproduce every example in Plan §5 and §13.6):

| Health | ≥ 0.90 | 0.70 – < 0.90 | 0.50 – < 0.70 | 0.30 – < 0.50 | < 0.30 |
|---|---|---|---|---|---|
| Risk | NORMAL | LOW | MEDIUM | HIGH | CRITICAL |

### 7.11 Anomaly result: `AnomalyResult` (Plan §12.5)

| Field | Type | Notes |
|---|---|---|
| `scope` | str | `"global"` or `"stage:<StageName>"` |
| `method` | `AnomalyMethod` | |
| `score` | float [0, 1] | Normalised; higher = more anomalous |
| `is_anomaly` | bool | Threshold from a training-set percentile (e.g. top 2%) stored in the anomaly bundle |
| `threshold` | float | |
| `top_contributors` | list[{`feature`: str, `deviation`: float}] | Largest robust-z deviation or reconstruction error |
| `note` | str | Human-readable |
| `model_version` | str \| None | e.g. `anomaly-1.0.0`. `null` for rule-based L1 |

### 7.12 Final quality prediction: `PredictionResult` (Plan §10.4, extended)

| Field | Type | Notes |
|---|---|---|
| `label` | `PredictionLabel` | `FAIL` iff `p_fail ≥ threshold_used` |
| `p_fail` | float [0, 1] | **Calibrated** failure probability |
| `p_fail_raw` | float [0, 1] | Uncalibrated model output (diagnostics, Model Info) |
| `threshold_used` | float | Read from the bundle `metadata.json`; never a silent 0.5 |
| `model_version` | str | e.g. `fusion-1.0.0` or `mock-0.0.0` |
| `risk_level` | `RiskLevel` | **Operational risk** from the risk engine (7.13) |
| `risk_drivers` | list[{`source`: `model`\|`anomaly`\|`constraint`, `detail`: str, `weight`: float}] | |
| `stage_risk_mass` | list[{`stage`: `StageName`, `share`: float}] | Shares sum to 1 (± 1e-6) |
| `explanation` | `LocalExplanation` \| None | Present when `include_explanation=true` |
| `uncertainty` | {`method`: `"none"`\|`"ensemble_spread"`, `value`: float \| None} | `"none"` in the MVP; ensemble spread is P1 |
| `anomaly_global` | `AnomalyResult` \| None | `null` until Isolation Forest is delivered (P1) |
| `ood` | {`is_out_of_distribution`: bool, `features_outside`: list[{`feature`, `value`, `p01`, `p99`}]} | From `feature_schema.json` percentile bounds |
| `caveats` | list[{`code`: str, `message`: str, `features`: list[str]}] | Codes: `OUT_OF_DISTRIBUTION`, `ANOMALY_DETECTED`, `CRITICAL_CONSTRAINT_OVERRIDDEN`, `MOCK_INFERENCE`, `CONSTRAINTS_VERSION_MISMATCH`, `STAGE_SUBMODEL_DISABLED` |
| `constraint_override_applied` | bool | True if any stage passed through BLOCKED via override |
| `inference_backend` | `InferenceBackend` | |
| `is_mock` | bool | Must equal `inference_backend == "mock"` |
| `feature_schema_hash` | str | SHA-256 of the bundle's `feature_schema.json` |
| `constraints_version` | str | |
| `compute_ms` | float | |

**Critical-breach rule (Plan §7.3):** if any stage result contains a `CRITICAL` breach (blocked-and-overridden, or `halt_on_critical=false`):
- `risk_level` MUST be `CRITICAL`;
- a `CRITICAL_CONSTRAINT_OVERRIDDEN` caveat MUST be present;
- the UI MUST render the result as **"NOT RELEASABLE — critical constraint breach"**, with the model label shown only as secondary text (**[PROPOSED] UD-07**).

A critical breach can therefore never appear as an ordinary confident PASS.

### 7.13 Risk semantics: three distinct concepts (Plan §12.3, §28 step 11)

| Concept | Field | Source | Shown as |
|---|---|---|---|
| Model-predicted failure probability | `p_fail`, `label` | Calibrated fusion model | "Predicted P(fail) 0.71 (calibrated)" |
| Operational risk | `risk_level`, `risk_drivers` | Risk engine: `max(band(p_fail), constraint band)`; any critical breach ⇒ CRITICAL | "Operational risk: HIGH" |
| Anomaly status | `anomaly_global`, `StageResult.anomaly`, caveats | Unsupervised detectors and L1 rules | Purple "!" badge and caveat banner. Anomalies **widen uncertainty / add caveats**; they do not by themselves raise the risk band |

**[PROPOSED] p_fail → operational-risk bands** (registry `risk_bands.p_fail`; re-derived in R1-P6 from empirical decile failure rates, Plan R13). These are consistent with the Plan's examples (0.71 → HIGH, 0.18 → LOW):

| p_fail | < 0.10 | 0.10 – < 0.30 | 0.30 – < 0.50 | 0.50 – < 0.85 | ≥ 0.85 |
|---|---|---|---|---|---|
| Band | NORMAL | LOW | MEDIUM | HIGH | CRITICAL |

### 7.14 Explanation contracts (Plan §11)

`LocalExplanation`:

| Field | Type | Notes |
|---|---|---|
| `method` | `"tree_shap"` | |
| `output_space` | `"log_odds"` | TreeSHAP explains the **uncalibrated** model margin. The UI states this in Model Info. The isotonic calibrator is monotone, so attribution signs carry over to P(fail) |
| `base_value` | float | |
| `attributions` | list[{`feature`, `display_name`, `value`, `shap_value`, `direction`: `"toward_fail"`\|`"toward_pass"`, `stage`: `StageName`\|`"CONTEXT"`, `group`: str}] | Top-k (default k = 10), signed, sorted by \|shap\| |
| `grouped_attributions` | list[{`group`, `shap_sum`}] | e.g. `temperature`, `pressure`, `time`, `material`, `context` (Plan §11.4.2) |
| `stage_risk_mass` | list[{`stage`, `share`}] | Plan §11.2. Cross-stage features are split 50/50 as declared in the feature schema |
| `background_version` | str | Version of the SHAP background sample |
| `show_caveat_banner` | bool | True if OOD or anomaly caveats exist (Plan §11.4.5) |

`GlobalExplanation` = {`model_version`, `mean_abs_shap`: list[{`feature`, `value`, `stage`}], `computed_on`: str, `n_rows`: int}. It is precomputed offline and shipped in the bundle.

### 7.15 Recommendation contracts (Plan §14)

`RecommendationRequest` (interface level): {`locked`: list[str] (in addition to the registry's non-actionable fields), `max_changes`: int (default 3, 1–6), `n_options`: int (default 3), `objective`: `"min_p_fail"` (only value in P0), `enable_refinement`: bool (default false; P1 DE), `time_budget_s`: float (default 5.0), `seed`: int (default 0)}.

`RecommendationCandidate`:

| Field | Type | Notes |
|---|---|---|
| `option_rank` | int 1..n | |
| `option_label` | `"Minimal change"`\|`"Balanced"`\|`"Aggressive"` | Assigned by rule: fewest changes / best score / lowest p_fail |
| `changes` | list[{`parameter`, `from_value`, `to_value`, `delta`, `unit`}] | Only actionable, unlocked parameters |
| `predicted_p_fail` / `predicted_label` / `delta_p_fail` | float / label / float | Computed through the **same** `predict()` pipeline |
| `stage_health_after` | list[{`stage`, `health_score`, `risk_level`}] | |
| `constraint_status` | `"ALL_SATISFIED"` | Returned candidates MUST have this value. Anything else is never returned |
| `guard_checks` | list[{`check`: `box`\|`hard_constraints`\|`couplings`\|`distribution`\|`step_size`\|`stability`, `passed`: bool, `detail`: str}] | |
| `stability` | {`trials`: 20, `flips`: int, `stable`: bool} | Unstable if flips > 20% (Plan §14.4) |
| `in_distribution` | bool | |
| `flags` | list[`CandidateFlag`] | `EXTRAPOLATED` options are ranked last and carry a "hypothesis for trial" note |
| `cycle_time_delta_s` / `cycle_time_delta_pct` | float | Always reported (Plan §14.7) |
| `change_cost` / `score` | float | Composite ranking (Plan §14.5) |
| `rationale` | list[str] | Links to stage risk / remedy rules |
| `search_method` | `"rule_proposal"`\|`"coordinate"`\|`"pairwise"`\|`"differential_evolution"` | |

`RecommendationResponse` = {`base_p_fail`, `base_label`, `candidates`: list, `evaluated_count`, `rejected_counts`: dict[check, int], `empty_reason`: str \| None, `model_version`, `constraints_version`, `disclaimer_key`: `"DISCLAIMER_RECOMMENDATION"`, `compute_ms`}.

### 7.16 What-if, sensitivity and scenario contracts (Plan §13)

- `SensitivityResult` = {`parameter`, `unit`, `current_value`, `points`: list[{`value`, `p_fail`, `label`}] (≈ 40 points across the admissible window), `local_gradient` (Δp_fail per unit at the current point, finite difference), `range_swing` (max − min p_fail), `flip_point` (nearest value where the label flips, or `null`)}.
- `WhatIfResult` (API, R2) = {`run_id` (child or `null` if not persisted), `parent_run_id`, `recomputed_stages`, `reused_stages`, `stage_results`, `prediction`, `diff`}.
- `diff` = {`parameters`: [{`name`, `from`, `to`, `delta`}], `stages`: [{`stage`, `health_from`, `health_to`, `risk_from`, `risk_to`, `change`: `improved`\|`worsened`\|`unchanged`}], `prediction`: {`label_from`, `label_to`, `p_fail_from`, `p_fail_to`, `p_fail_delta`, `flipped`}, `operational_risk`: {`from`, `to`, `band_delta`}, `constraint_compliance`: {`warnings_from`, `warnings_to`, `critical_from`, `critical_to`}, `cycle_time`: {`from`, `to`, `delta_s`, `delta_pct`}}. This matches the Plan §16.4 example and the §13.6 diff table.
- `ScenarioSummary` (history rows) = {`run_id`, `parent_run_id`, `is_whatif`, `scenario_label`, `status`, `created_at`, `machine_id`, `product_id`, `material_lot_id`, `label`, `p_fail`, `risk_level`, `model_version`, `inference_backend`}.

### 7.17 Simulation state and event schemas (R2-owned API objects; Plan §7.5)

- `SimulationState` = {`run_id`, `status`, `mode`, `speed_factor`, `halt_on_critical`, `blocked_stage`, `current_stage`, `created_at`, `updated_at`, `context` (snapshot), `parameters`, `stage_results[]`, `aggregate_risk` {`level`, `drivers[]`}, `prediction`, `explanation`, `recommendations[]` (latest request), `timeline[]` (events), `parent_run_id`, `is_whatif`, `scenario_label`, `last_seq`}.
- `SimulationEvent` envelope: Section 9.5.

---

## 8. Shared constraint registry

### 8.1 Files, ownership and versioning

| File | Purpose | Owner | Version key |
|---|---|---|---|
| `backend/app/domain/constraints.yaml` | Parameter windows, units, steps, nominals, actionability, change costs, max step change, resin-grade limits, coupling rules, hard constraints, stage check weights, risk bands, recommendation weights, dependency graph | R1 content, JOINT approval | `registry_version: constraints-MAJOR.MINOR.PATCH` |
| `backend/app/domain/remedies.yaml` | Rule-guided remedy table for recommendation Stage 1 (Plan §14.3) | R1 | `remedies_version` |
| `backend/app/domain/fleet.yaml` | Virtual machines, products, resin grades and **demo** lots. The generator samples the fleet from here, and the R2 seed imports its demo subset, so DB entities and training data share one definition | R1 content; R2 seed consumes | `fleet_version` |
| `backend/app/domain/CHANGELOG.md` | Every registry change with CCR reference | JOINT | — |

**Versioning rules:**
- **PATCH:** text, citation or provenance change only.
- **MINOR:** a numeric window, weight or threshold changes, or a new optional rule is added.
- **MAJOR:** a parameter is added, removed or renamed, or a rule's semantics change. This requires retraining or rebuilding dependent bundles.

### 8.2 Registry schema (structure is binding; numbers are [PROPOSED])

```yaml
registry_version: constraints-1.0.0
units_allowed: [c, bar, s, h, mm, mm_s, pct, ton, g, cm2, days, rpm, g_10min, dimensionless]
resin_grades:
  PP-H:                       # homopolymer; placeholder grades, confirm in R1-P1
    melt_window_c: [200, 260]
    degradation_ceiling_c: 285          # critical; blocks PLASTICIZING
    moisture_spec_max_pct: 0.10
    moisture_critical_factor: 2.0       # blocks MATERIAL_CONDITIONING above 2x spec
    mfi_nominal: 12
    provenance: unvalidated
    citation: null                      # MUST be filled or provenance kept "unvalidated"
parameters:
  melt_temp_c:
    kind: setpoint
    stage: PLASTICIZING                 # first consuming stage (dependency graph)
    also_used_by: [INJECTION, PACKING, COOLING]   # via upstream context (documentation)
    unit: c
    dtype: float
    min: 180
    max: 295                            # box (HTTP 422 above this)
    nominal: 230
    step: 1
    tolerance: 10                       # for range-check severity
    actionable: true
    change_cost: 0.6                    # 0..1 relative operational disruption
    max_step_change: 20                 # recommendation step limit
    display_name: "Melt temperature"
    provenance: unvalidated
    citation: null
  # ... one entry per field in Sections 7.3-7.6
coupling_rules:                         # tier-2 validation (HTTP 422) AND guard check 3
  - id: CPL-001
    description: hold_pressure_bar <= inj_pressure_bar
    params: [hold_pressure_bar, inj_pressure_bar]
    severity: CRITICAL
  - id: CPL-002
    description: melt_temp_c >= mold_temp_c + melt_mold_delta_min_c
    params: [melt_temp_c, mold_temp_c]
    constants: {melt_mold_delta_min_c: 120}
    severity: CRITICAL
  - id: CPL-003
    description: clamp_force_ton <= max_clamp_force_ton
    severity: CRITICAL
  - id: CPL-004
    description: inj_pressure_bar <= max_inj_pressure_bar
    severity: CRITICAL
hard_constraints:                       # runtime domain/safety tier and guard check 2
  - id: HC-001  # degradation ceiling
    stage: PLASTICIZING
    blocks_stage: true
    severity_in_simulation: CRITICAL
    enforced_in_guard: true
  - id: HC-002  # clamp sufficiency: clamp_force_ton >= required_clamp_force_ton
    stage: INJECTION
    blocks_stage: true
    severity_in_simulation: CRITICAL
    enforced_in_guard: true
  - id: HC-003  # pressure headroom: inj_pressure_bar <= 0.9 * max_inj_pressure_bar
    stage: INJECTION
    blocks_stage: false
    severity_in_simulation: WARNING
    enforced_in_guard: true
  - id: HC-004  # cooling_time_s >= thickness-based minimum
    stage: COOLING
    blocks_stage: false
    severity_in_simulation: WARNING
    enforced_in_guard: true
  - id: HC-005  # cushion_mm within [cushion_min, cushion_max]
    stage: PACKING
    blocks_stage: false
    severity_in_simulation: WARNING
    enforced_in_guard: true
  - id: HC-006  # moisture critical factor
    stage: MATERIAL_CONDITIONING
    blocks_stage: true
    severity_in_simulation: CRITICAL
    enforced_in_guard: true
stage_checks:                           # health aggregation weights (Plan 8.4)
  MATERIAL_CONDITIONING:
    - {check_id: S1-MOIST, type: range, target: moisture_pct, weight: 0.35, provenance: heuristic}
    - {check_id: S1-MFIZ, type: zscore, target: mfi, weight: 0.20, provenance: heuristic}
    # ...
risk_bands:
  stage_health: {NORMAL: 0.90, LOW: 0.70, MEDIUM: 0.50, HIGH: 0.30}   # lower bounds
  p_fail:       {LOW: 0.10, MEDIUM: 0.30, HIGH: 0.50, CRITICAL: 0.85} # lower bounds
recommendation:
  default_max_changes: 3
  coordinate_levels: 7
  pairwise_top_k: 3
  stability_trials: 20
  stability_noise_fraction_of_step: 0.5
  max_unstable_flip_rate: 0.20
  weights: {w1_improvement: 1.0, w2_change_cost: 0.15, w3_instability: 0.5,
            w4_extrapolation: 0.5, w5_cycle_time: 0.2}
  cycle_time_follows_stage_times: true   # UD-09
submodels:
  enabled: false                         # P1 stage sub-models (RC-13)
```

### 8.3 [PROPOSED] initial parameter windows (placeholders until R1-P1 attaches citations)

All values below are **[PROPOSED] / provenance `unvalidated`**. They exist so both roles can start. R1-P1 MUST replace each with a cited value or keep it explicitly flagged `heuristic`/`unvalidated`.

| Parameter | Min | Nominal | Max | Step | Max step change | Change cost |
|---|---|---|---|---|---|---|
| drying_time_h | 0 | 1.0 | 4 | 0.25 | 1 | 0.2 |
| dryer_temp_c | 60 | 80 | 90 | 1 | 10 | 0.2 |
| barrel_temp_rear_c | 180 | 200 | 230 | 1 | 15 | 0.6 |
| barrel_temp_mid_c | 190 | 215 | 250 | 1 | 15 | 0.6 |
| barrel_temp_front_c | 200 | 225 | 260 | 1 | 15 | 0.6 |
| nozzle_temp_c | 200 | 230 | 260 | 1 | 15 | 0.5 |
| melt_temp_c | 180 | 230 | 295 (ceiling PP-H 285 ⇒ BLOCK) | 1 | 20 | 0.6 |
| screw_rpm | 40 | 100 | 200 | 5 | 30 | 0.3 |
| back_pressure_bar | 20 | 60 | 150 | 5 | 30 | 0.3 |
| residence_time_s | 10 | 30 | 120 | 1 | 15 | 0.8 |
| inj_velocity_mm_s | 20 | 100 | 200 | 5 | 30 | 0.3 |
| inj_pressure_bar | 300 | 900 | 1800 | 10 | 150 | 0.3 |
| fill_time_s | 0.3 | 1.4 | 5.0 | 0.05 | 0.5 | 0.3 |
| shot_size_mm | 10 | 45 | 120 | 0.5 | 5 | 0.4 |
| switchover_position_mm | 2 | 12 | 30 | 0.5 | 4 | 0.3 |
| clamp_force_ton | 40 | 150 | 300 | 5 | 30 | 0.3 |
| hold_pressure_bar | 200 | 600 | 1200 | 10 | 100 | 0.2 |
| hold_time_s | 0.5 | 2.5 | 15 | 0.1 | 2 | 0.2 |
| cushion_mm | 0.5 | 5 | 15 | 0.5 | 3 | 0.3 |
| mold_temp_c | 15 | 40 | 80 | 1 | 10 | 0.5 |
| cooling_time_s | 5 | 22 | 60 | 0.5 | 8 | 0.1 |
| cycle_time_s | 15 | 38 | 90 | 0.5 | — (derived) | — |
| ejection_force_proxy | 0 | 0.5 | 1 | 0.01 | — (non-actionable) | — |
| mfi (lot) | 2 | 12 | 40 | 0.1 | — | — |
| moisture_pct (lot) | 0 | 0.03 | 0.30 | 0.01 | — | — |
| regrind_pct (lot) | 0 | 15 | 30 (policy max 25) | 1 | — | — |
| colourant_pct (lot) | 0 | 2 | 5 | 0.1 | — | — |
| wall_thickness_mm | 1.5 | 2.5 | 4.0 | 0.1 | — | — |
| projected_area_cm2 | 30 | 100 | 250 | 1 | — | — |

### 8.4 Loader API (`constraint_loader.py`, R1, pure)

```python
class ConstraintRegistry:                     # immutable after load
    version: str                              # "constraints-1.0.0"
    content_hash: str                         # SHA-256 of canonical YAML
    @classmethod
    def load(cls, path: Path) -> "ConstraintRegistry"  # Pydantic-validated, fail-fast
    def parameter(self, name: str) -> ParameterSpec
    def parameters(self, kind: ParameterKind | None = None) -> list[ParameterSpec]
    def resin_grade(self, grade: str) -> ResinGradeSpec
    def check_box(self, values: Mapping[str, Any]) -> list[ConstraintBreach]
    def check_couplings(self, values: Mapping[str, Any]) -> list[ConstraintBreach]
    def check_hard_constraints(self, values: Mapping[str, Any],
                               derived: Mapping[str, float] | None = None) -> list[ConstraintBreach]
    def stage_inputs(self, stage: StageName) -> list[str]          # raw slice for a stage
    def invalidated_stages(self, changed: Iterable[str]) -> list[StageName]  # earliest + downstream
    def to_public_dict(self) -> dict          # payload of GET /api/v1/constraints
```

- The backend loads the registry **once at startup** (`SMQI_CONSTRAINTS_PATH`) and keeps it on app state. Invalid YAML aborts startup with `REGISTRY_INVALID`.
- Each model bundle records the `constraints_version` it was trained with. At load the facade compares versions:
  - **MAJOR mismatch** ⇒ `MODEL_ARTIFACT_INVALID`, and the backend refuses `real` mode;
  - **MINOR mismatch** ⇒ a `CONSTRAINTS_VERSION_MISMATCH` caveat on every prediction.
- The frontend MUST build every slider, bound, step and unit label from `GET /constraints`. No limit literals in `frontend/src` (B6).

### 8.5 Consumers (single source of truth)

| Consumer | Uses | Owner |
|---|---|---|
| Pydantic API validation (tier 1 ranges, tier 2 couplings) | `check_box`, `check_couplings` | R2 |
| Frontend sliders and client validation | `/constraints` payload | R2 |
| Stage rules, health weights, block decisions | `stage_checks`, `hard_constraints`, `resin_grades` | R1 |
| Risk engine bands | `risk_bands` | R1 |
| Recommendation bounds, steps, costs, locked defaults, guard | `parameters`, `hard_constraints`, `coupling_rules`, `recommendation` | R1 |
| What-if invalidation | `invalidated_stages` | R2 calls, R1 implements |
| Synthetic generator nominal windows | `parameters`, `resin_grades`, `fleet.yaml` | R1 |
| Constraint-compliance reporting (UI stamps, diff) | Breaches from stage results and the guard | R1 produces, R2 displays |

### 8.6 Change approval

- Any change to `constraints.yaml`, `remedies.yaml` or `fleet.yaml` goes through a **CCR** (Section 10.4) with both members' approval.
- The change must include: a CHANGELOG entry, a version bump, updated contract fixtures, and passing tests on both sides.
- **There MUST be no other copy of any limit anywhere** (no constants in Python, no TypeScript literals, no notebook-only values used by code).

---

## 9. Shared API, inference, database and event contracts

### 9.1 Intelligence interface (`contracts/interface.py`)

This is the **only** surface through which Role 2 code reaches Role 1 functionality.

```python
class QualityIntelligence(Protocol):
    def version_info(self) -> IntelligenceVersionInfo: ...
        # {contracts_version, constraints_version, module_versions{stage: ver},
        #  fusion_model_version, anomaly_model_version, stage_stats_version,
        #  feature_schema_hash, inference_backend, is_mock, capabilities{name: bool}}
    def capabilities(self) -> dict[str, bool]: ...
        # keys: run_stage, predict, explain, global_explanation, anomaly_global,
        #       recommend, sensitivity, spc

    # ---- stage intelligence (S1-S5), pure ----
    def run_stage(self, stage: StageName, inp: ProcessInput,
                  upstream: UpstreamContext) -> StageResult: ...
    def run_all_stages(self, inp: ProcessInput) -> list[StageResult]: ...

    # ---- fusion (S6) ----
    def build_features(self, inp: ProcessInput,
                       stage_results: Sequence[StageResult]) -> FeatureVector: ...
        # FeatureVector = {names: list[str] (schema order), values: list[float|None],
        #                  feature_schema_hash}
    def predict(self, inp: ProcessInput, stage_results: Sequence[StageResult],
                include_explanation: bool = True) -> PredictionResult: ...
    def explain(self, inp: ProcessInput,
                stage_results: Sequence[StageResult], top_k: int = 10) -> LocalExplanation: ...
    def global_explanation(self) -> GlobalExplanation: ...
    def detect_anomaly(self, inp: ProcessInput,
                       stage_results: Sequence[StageResult]) -> AnomalyResult: ...

    # ---- convenience: full pure pipeline (used by /predict and by recommendation) ----
    def evaluate(self, inp: ProcessInput,
                 include_explanation: bool = False) -> PipelineResult: ...
        # PipelineResult = {stage_results: list[StageResult], prediction: PredictionResult}

    # ---- decision support ----
    def recommend(self, inp: ProcessInput, stage_results: Sequence[StageResult],
                  prediction: PredictionResult,
                  request: RecommendationRequest) -> RecommendationResponse: ...
    def sensitivity(self, inp: ProcessInput, parameter: str,
                    steps: int = 40) -> SensitivityResult: ...
    def spc_check(self, series: SpcSeries) -> list[SpcAlert]: ...   # P1
```

**Guarantees:**

1. **Determinism.** Outputs are identical across calls for identical inputs, loaded artifacts and `seed` arguments.
2. **Statelessness.** The interface holds no state between calls except immutable loaded artifacts and pure memoization caches.
3. **Thread safety.** Calls are safe from FastAPI's thread pool. Role 2 calls the synchronous methods via `run_in_threadpool`, or directly for sub-10 ms calls.
4. **Equivalence.** `evaluate(inp)` equals `run_all_stages` + `predict` exactly. A partial re-run that reuses upstream results equals a full re-run (property test, Plan §22 Phase 9).
5. **Single path for recommendations.** Recommendation candidates are scored through the identical `run_stage`/`predict` path (Plan §14, Phase 9 handoff).

**Performance budgets (Plan §24.4), measured on the dev machine:**

| Operation | Budget |
|---|---|
| `run_stage` | p95 < 5 ms |
| `evaluate` without explanation | p95 < 150 ms |
| `explain` | p95 < 300 ms |
| `sensitivity` (40 points) | < 1.5 s |
| `recommend` | < 5 s (hard budget) |

**Errors (`contracts/errors.py`).** All Role 1 failures raise subclasses of `IntelligenceError(code, message, field=None, hint=None, details=None)`. Role 2 maps them to the HTTP envelope (9.3.4). Role 1 never raises bare exceptions across the interface, and never raises for a *domain* breach: breaches are data (`constraint_breaches`, `blocked`).

| Exception / code | Raised when | HTTP mapping (R2) |
|---|---|---|
| `InvalidInputError` / `INVALID_INTELLIGENCE_INPUT` | Missing or unknown field, wrong type, value outside the box | 422 |
| `UnknownParameterError` / `UNKNOWN_PARAMETER` | Override or sensitivity on a non-existent parameter | 422 |
| `LockedParameterError` / `PARAMETER_NOT_ACTIONABLE` | Sensitivity or recommendation requested on a non-actionable parameter | 422 |
| `UpstreamMissingError` / `UPSTREAM_CONTEXT_MISSING` | `run_stage` called without the required upstream keys | 500 (programming error in the orchestrator) |
| `StageResultsIncompleteError` / `STAGE_RESULTS_INCOMPLETE` | `predict` called with fewer than 5 stage results | 409 |
| `ModelNotLoadedError` / `MODEL_NOT_LOADED` | Capability needs an artifact that is absent | 503 |
| `ArtifactInvalidError` / `MODEL_ARTIFACT_INVALID` | Hash mismatch, schema mismatch, constraints MAJOR mismatch | 503 (startup refuses `real` mode) |
| `FeatureSchemaMismatchError` / `FEATURE_SCHEMA_MISMATCH` | Built vector does not match the bundle schema | 500 |
| `CapabilityUnavailableError` / `CAPABILITY_UNAVAILABLE` | Real facade lacks the capability (during development) | 501 |
| `RecommendationBudgetExceeded` (not an error) | Budget hit | 200 with partial results and `empty_reason`/notes |

**Factory and wiring (R2, `api/deps.py`).** `get_intelligence()` returns one process-wide instance chosen by `SMQI_INTELLIGENCE_BACKEND`:

| Value | Behaviour | Allowed when |
|---|---|---|
| `mock` | `MockQualityIntelligence` for everything | `SMQI_ENV` ∈ {dev, test} |
| `hybrid` | Real for every capability `RealQualityIntelligence.capabilities()` reports `true`; mock otherwise. Each output's `inference_backend` reflects its true origin | dev, test **[PROPOSED] UD-11** |
| `real` | `RealQualityIntelligence.from_settings(...)`. Startup fails if any P0 capability is unavailable | All. **Mandatory when `SMQI_ENV=demo`** |

### 9.2 Mock contract (R2, `app/intelligence_mock/`)

The mock MUST:
- implement the full Protocol;
- return contract-valid objects;
- be deterministic (values derived from a SHA-256 of the canonical input);
- set `inference_backend="mock"`, `is_mock=true` and `model_version="mock-0.0.0"`;
- add the caveat `MOCK_INFERENCE` to every prediction.

The mock MAY call `ConstraintRegistry.check_hard_constraints` so the BLOCKED path can be exercised. It calls the registry function rather than re-implementing rules.

The mock MUST NOT imitate real model behaviour (no hand-written "physics"). Its numbers are placeholders.

Everywhere a mock value can appear, **MOCK** must be visible:
- the UI shows a persistent red banner "MOCK INTELLIGENCE — outputs are placeholders, not model predictions";
- DB rows store `inference_backend='mock'`;
- analytics exclude mock rows by default.

### 9.3 API contract (R2 implements; JOINT review of shapes)

#### 9.3.1 Conventions

- Base path `/api/v1`. JSON only, except SSE.
- **Envelope (Plan §16.3):** `{"data": <payload|null>, "error": <ErrorBody|null>, "meta": {"request_id": "...", "latency_ms": 12, "api_version": "1", "contracts_version": "0.1.0"}}`.
- `ErrorBody = {code, message, field|null, details[]|null, constraint_version|null, hint|null}`. `details[]` lists per-field problems for 422 (`[{field, code, message, limit, value}]`).
- `X-Request-ID` is accepted or generated, and echoed in `meta.request_id` and the logs.
- CORS is restricted to `SMQI_CORS_ORIGINS`. Optional `X-API-Key` is required iff `SMQI_API_KEY` is set (Plan §16.6).
- Pagination uses `?limit=50&offset=0` and returns `meta.total`. Filters are query params.
- The OpenAPI document is served at `/api/v1/openapi.json`. The frontend generates types from it with `openapi-typescript` (`npm run gen:api`). **The frontend never hand-writes an API type** (Plan §21.2).

#### 9.3.2 Endpoint catalogue

Paths are from Plan §16.3 unless marked **[P]** (proposed addition, RC-18–20). Priority is shown in brackets.

**Simulation (R2):**

| Method | Path | Request | Response `data` | Errors |
|---|---|---|---|---|
| POST | `/simulation/runs` [P0] | `{machine_id, product_id, material_lot_id, parameters: ProcessRecipe, mode?: "auto", speed_factor?: "1x", halt_on_critical?: true, scenario_label?: str}` | `SimulationState` (status `INITIALIZED`) | 422 `PARAM_OUT_OF_RANGE`, `COUPLING_VIOLATION`, `VALIDATION_ERROR`; 404 `REFERENCE_NOT_FOUND` |
| POST | `/simulation/runs/{id}/start` [P0] | `{mode: "auto"\|"stepwise", speed_factor?}` | `SimulationState` | 404 `RUN_NOT_FOUND`; 409 `INVALID_STATE_TRANSITION` |
| POST | `/simulation/runs/{id}/advance` [P0] | — | `{stage_result \| prediction, state}` | 409 (not stepwise, or terminal) |
| POST | `/simulation/runs/{id}/pause` [P1] | — | `SimulationState` | 409 |
| POST | `/simulation/runs/{id}/resume` [P1] | — | `SimulationState` | 409 |
| POST | `/simulation/runs/{id}/reset` [P0] | — | `SimulationState` | 409 `RUN_IMMUTABLE` if FINAL_RESULT/ABORTED (UD-08) |
| POST | `/simulation/runs/{id}/abort` **[P]** [P0] | `{reason?}` | `SimulationState` | 409 |
| POST | `/simulation/runs/{id}/override` [P0] | `{stage, acknowledgement: str}` | `SimulationState` | 409 if not BLOCKED |
| GET | `/simulation/runs/{id}` [P0] | — | `SimulationState` | 404 |
| GET | `/simulation/runs/{id}/events` [P0] | header `Last-Event-ID?` | `text/event-stream` (9.5) | 404 |
| GET | `/simulation/runs/{id}/stages/{stage}` [P0] | — | `StageResult` (+ presentation timing) | 404 |
| GET | `/simulation/runs` [P0 basic, P1 filters] | `?machine_id&product_id&material_lot_id&label&risk_level&is_whatif&inference_backend&from&to&limit&offset` | `ScenarioSummary[]` | — |
| PATCH | `/simulation/runs/{id}/label` **[P]** [P0] | `{scenario_label}` | `ScenarioSummary` | 404 |
| GET | `/simulation/runs/{id}/lineage` **[P]** [P1] | — | tree `{run, children[]}` | 404 |

**Prediction, what-if, recommendation (R2 endpoints, R1 compute):**

| Method | Path | Request | Response `data` | Errors |
|---|---|---|---|---|
| POST | `/predict` [P0] | `{machine_id, product_id, material_lot_id, parameters, include_explanation?: true}` | `{prediction_id, stage_results, prediction}`. Persists a `predictions` row with `run_id=null`, so explanations stay retrievable | 422, 503 |
| POST | `/predict/batch` [P2] | CSV upload or JSON array (≤ 5,000 rows) | `{rows: [{index, prediction \| error}]}` | 413, 422 |
| GET | `/predict/{prediction_id}/explain` [P0] | — | `LocalExplanation` | 404 |
| POST | `/whatif` [P0] | `{base_run_id, overrides: {param: value}, persist?: true, label?: str}` | `WhatIfResult` (Plan §16.4) | 404, 422 (unknown parameter or out of range), 409 (base not FINAL_RESULT) |
| POST | `/whatif/sensitivity` [P1] | `{base_run_id, parameter, steps?: 40}` | `SensitivityResult` | 404, 422, 429 |
| POST | `/whatif/compare` [P1] | `{run_id_a, run_id_b}` | `diff` | 404 |
| POST | `/recommend` [P0] | `{run_id, locked?: [], max_changes?: 3, n_options?: 3, objective?: "min_p_fail", enable_refinement?: false}` | `{request_id, ...RecommendationResponse}` | 404, 409 (run not FINAL_RESULT), 422, 429 |

**Reference, meta, analytics (R2):**

| Method | Path | Response `data` |
|---|---|---|
| GET | `/machines`, `/products`, `/materials` [P0] | Lists of `MachineProfile` / `ProductContext` / `MaterialLot` |
| POST | `/materials` [P0] (F1 "create lot") | Creates a lot. Validated against the registry. Returns `MaterialLot` |
| GET | `/constraints` [P0] | `ConstraintRegistry.to_public_dict()` + `version` + `content_hash` |
| GET | `/models` [P1], `/models/active` [P0] | `model_versions` rows + `metrics.json` summary + `is_mock` |
| GET | `/models/active/global-explanation` **[P]** [P1] | `GlobalExplanation` |
| GET | `/analytics/summary` [P1] | Failure rate, run counts, stage risk frequency (excludes what-if, mock, non-final by default) |
| GET | `/analytics/by-machine`, `/analytics/by-parameter?parameter=&buckets=`, `/analytics/by-material` **[P]** [P1] | Aggregations |
| GET | `/analytics/spc?machine_id=&parameter=` **[P]** [P1] | `SpcAlert[]` + series |
| GET | `/health` [P0] | `{status: "ok"\|"degraded", db: bool, intelligence: IntelligenceVersionInfo, model_loaded: bool}` |

#### 9.3.3 Validation tiers (Plan §16.5)

1. **Schema:** types, required fields, numeric bounds generated from the registry → 422 `PARAM_OUT_OF_RANGE` / `VALIDATION_ERROR` with per-field `details`.
2. **Coupling:** `registry.check_couplings` → 422 `COUPLING_VIOLATION` with `rule_id` in `details`.
3. **Domain/safety:** hard constraints at runtime produce a BLOCKED stage or WARNING breaches **inside the simulation**, never an HTTP error.

#### 9.3.4 Stable error codes (enumerated in `app/api/errors.py`, mirrored as a TS union)

`VALIDATION_ERROR`, `PARAM_OUT_OF_RANGE`, `COUPLING_VIOLATION`, `UNKNOWN_PARAMETER`, `PARAMETER_NOT_ACTIONABLE`, `REFERENCE_NOT_FOUND`, `RUN_NOT_FOUND`, `PREDICTION_NOT_FOUND`, `INVALID_STATE_TRANSITION`, `RUN_IMMUTABLE`, `STAGE_RESULTS_INCOMPLETE`, `MODEL_NOT_LOADED`, `MODEL_ARTIFACT_INVALID`, `FEATURE_SCHEMA_MISMATCH`, `CAPABILITY_UNAVAILABLE`, `UPSTREAM_CONTEXT_MISSING`, `INVALID_INTELLIGENCE_INPUT`, `REGISTRY_INVALID`, `RATE_LIMITED`, `UNAUTHORIZED`, `PAYLOAD_TOO_LARGE`, `INTERNAL_ERROR`.

Adding a code is a MINOR contract change. Renaming or removing one is MAJOR.

### 9.4 Database contract (R2 owns; Plan §17)

**Engine:**
- SQLite file `var/smqi.db` for dev and test.
- PostgreSQL for demo (P2, via Docker Compose).
- Same SQLAlchemy 2.0 models. Alembic with `render_as_batch=True` for SQLite ALTERs.
- JSON columns use the SQLAlchemy `JSON` type (portable).

**Tables:** Plan §17.2 columns, plus **[P]** additions needed by the contracts.

| Table | Key columns | Additions **[P]** | Mutability |
|---|---|---|---|
| `machines` | `id` int PK, `code` unique, `tonnage`, `machine_type`, `max_inj_pressure`, `max_clamp_force`, `installed_on`, `last_maintenance_on`, `active` | `fleet_version` | Editable reference data. Runs snapshot what they used |
| `products` | `id`, `code` unique, `name`, `cavity_count`, `nominal_shot_weight_g`, `wall_thickness_mm`, `projected_area_cm2`, `active` | — | Editable reference |
| `materials` | `id`, `lot_code` unique, `resin_grade`, `mfi`, `moisture_pct`, `regrind_pct`, `received_on`, `notes` | `colourant_pct` (listed in Plan §8.2 inputs, missing from §17.2) | Insert-only after use in a run |
| `process_runs` | `id` UUID PK, `machine_id` FK, `product_id` FK, `material_lot_id` FK, `status`, `mode`, `is_whatif`, `parent_run_id` FK self, `scenario_label`, `started_at`, `completed_at`, `created_by` (nullable) | `speed_factor`, `halt_on_critical`, `blocked_stage`, `override_count`, `abort_reason`, `context_snapshot` JSON (machine/product/lot values used), `inference_backend`, `constraints_version`, `last_seq`, `created_at` | Status fields mutable until terminal. Only `scenario_label` mutable after |
| `run_parameters` | `id`, `run_id` FK unique (1:1), one typed column per `ProcessRecipe` field, `created_at` | — | **Immutable** after insert |
| `stage_results` | `id`, `run_id` FK, `stage_name`, `sequence_index`, `health_score`, `risk_level`, `anomaly_flag`, `anomaly_score`, `indicators` JSON, `constraint_breaches` JSON, `notes` JSON, `duration_ms`, `created_at` | `substate`, `anomaly` JSON (method, contributors), `upstream_in` JSON, `upstream_out` JSON, `inputs_used` JSON, `indicator_provenance` JSON, `blocked`, `block_reason`, `overridden`, `module_version`, `constraints_version`, `compute_ms`, `reused_from_stage_result_id` (what-if reuse trace) | Immutable once the run is terminal. Deleted only by RESET of a non-terminal run |
| `predictions` | `id` UUID, `run_id` FK **nullable** (null for `/predict`), `model_version_id` FK, `label`, `p_fail`, `threshold_used`, `risk_level`, `risk_drivers` JSON, `explanation` JSON, `stage_risk_mass` JSON, `caveats` JSON, `latency_ms`, `created_at` | `p_fail_raw`, `anomaly_global` JSON, `ood` JSON, `uncertainty` JSON, `constraint_override_applied`, `inference_backend`, `feature_schema_hash`, `constraints_version`, `input_snapshot` JSON (for `/predict` rows) | **Immutable** |
| `recommendations` | `id`, `run_id` FK, `option_rank`, `changes` JSON, `predicted_p_fail`, `predicted_label`, `delta_p_fail`, `constraint_status`, `stability_score`, `extrapolation_flag`, `cycle_time_delta_s`, `search_method`, `created_at` | `request_id` UUID (groups one `/recommend` call), `candidate` JSON (full `RecommendationCandidate`), `request` JSON, `model_version_id` FK, `constraints_version`, `evaluated_count` | Append-only |
| `model_versions` | `id`, `name` (`fusion`\|`anomaly`\|`stage_stats`\|`mock`), `semver`, `algorithm`, `trained_at`, `dataset_hash`, `git_sha`, `metrics` JSON, `artifact_path`, `is_active` | `feature_schema_hash`, `constraints_version`, `threshold`, `bundle_sha256`, unique(`name`, `semver`) | Upserted at startup from `models/registry.json` |
| `simulation_events` | `id`, `run_id` FK, `event_type`, `payload` JSON, `created_at` | `seq` int, unique(`run_id`, `seq`), `stage` nullable | Append-only |

**Indexes (Plan §17.4):** `process_runs(created_at)`, `process_runs(machine_id, created_at)`, `process_runs(parent_run_id)`, `stage_results(run_id, sequence_index)`, `predictions(run_id)`, `simulation_events(run_id, created_at)`. **[P]** also `simulation_events(run_id, seq)` unique, `recommendations(run_id, request_id)`.

**Identity and lineage rules:**
- Original runs have `is_whatif=false` and `parent_run_id=NULL`.
- What-if runs have `is_whatif=true` and `parent_run_id=<base>`.
- A what-if **never** updates its parent's rows. Reused stage results are **copied** into the child with `reused_from_stage_result_id` set, so each run is self-contained.
- A "scenario" is a run with a non-null `scenario_label` (Plan §17.3). No separate scenarios table.

**Model-version traceability:** every `predictions` and `recommendations` row references `model_versions.id` and stores `constraints_version` and `feature_schema_hash`. Mock outputs reference the `mock` row.

**Migrations:**
- Alembic from R2-P2: `0001_initial`, then one revision per change.
- **Never edit a migration that has been merged to `main`.**
- Every migration must pass `upgrade head` from an empty DB and `downgrade -1`/`upgrade` round-trip in tests.

**Persistence boundaries:**
- Role 1 code never touches the DB (B3).
- If Role 1 needs new persisted data, it proposes a CCR. Role 2 implements the schema change.

**Dataset separation:** training data lives in `data/`, never in the application DB (Plan §17.5).

**Seed:**
- `uv run python -m app.db.seed` is idempotent.
- It imports the demo subset of `fleet.yaml` (machines `MC-01…MC-0n`, product `PP-JBOX-42`, demo lots incl. `A-771`) and registers model versions.

### 9.5 Event and simulation contract (R2 implements; JOINT shapes)

#### 9.5.1 Stage order and state machine (Plan §7.2–7.3)

Order: `MATERIAL_CONDITIONING → PLASTICIZING → INJECTION → PACKING → COOLING → QUALITY_INSPECTION → FINAL_RESULT`.

| From | Command / event | Guard | To | Side effects (events in order) |
|---|---|---|---|---|
| INITIALIZED | START (auto/stepwise) | params valid (already validated at create) | MATERIAL_CONDITIONING (S1 `PENDING`) | `run.started`. Auto: spawn the asyncio task |
| S_k (k=1..5) RUNNING | STAGE_DONE | stage result persisted, not blocked | S_{k+1} PENDING (k<5) or QUALITY_INSPECTION (k=5) | `stage.completed`, then `stage.started` for the next stage |
| S_k RUNNING | BLOCK | `result.blocked` and `halt_on_critical=true` | BLOCKED (`blocked_stage=S_k`) | `constraint.breached`, `stage.blocked` |
| S_k RUNNING | critical breach and `halt_on_critical=false` | — | continue | `constraint.breached`. Stage COMPLETED with CRITICAL risk |
| BLOCKED | OVERRIDE | `stage == blocked_stage` | S_{k+1} (auto resumes; stepwise waits) | `stage.override_acknowledged` **[P]**, `stage.completed` (with `overridden=true`) |
| any RUNNING stage (auto) | PAUSE | mode = auto | PAUSED (remembers previous) | `run.paused` |
| PAUSED | RESUME | — | previous state | `run.resumed` **[P]** |
| any non-terminal | RESET | — | INITIALIZED | Delete this run's stage results and prediction; keep parameters; `run.reset` |
| FINAL_RESULT / ABORTED | RESET | — | **rejected** 409 `RUN_IMMUTABLE` **[P] UD-08** | UI offers "Re-run as new run" (clone parameters) |
| any non-terminal | ABORT | — | ABORTED | Persist the partial run; `run.aborted` |
| QUALITY_INSPECTION | PREDICTED | 5 stage results present | FINAL_RESULT | Persist prediction + explanation; `prediction.ready`, `run.completed` |
| any | internal error | — | ABORTED (`abort_reason=ERROR:<code>`) | `run.error` **[P]**, `run.aborted` |

- Stage substates: `PENDING → RUNNING → COMPLETED | BLOCKED`.
- Terminal statuses: `FINAL_RESULT`, `ABORTED`.
- **Startup recovery (Plan §18.5):** any run left in a non-terminal running status is set to `ABORTED` with `abort_reason="SERVER_RESTART"`. Completed stage rows survive.

#### 9.5.2 Execution model (Plan §18.5, §7.4)

- **Auto mode:** one `asyncio` task per active run, held in an in-process registry keyed by `run_id`. Presentation delay per stage is `await asyncio.sleep(stage_ms / speed)`, with `stage_ms` = `SMQI_STAGE_PRESENTATION_MS` (default 1500, allowed range 1200–2000). `instant` means no sleep.
- **Stepwise mode:** no task. Each `POST /advance` synchronously executes exactly one stage (or the quality stage) and returns its result.
- **Labelling:** the UI labels speed as **"presentation speed"**. Modelled process times (`cycle_time_s`, `cooling_time_s`, `hold_time_s`) are parameters and are never confused with animation duration.
- **Stage cache:** in-process LRU (`SMQI_STAGE_CACHE_SIZE`, default 5000). Key = SHA-256 of `(stage_name, canonical JSON of stage input slice, canonical JSON of upstream_in, module_version, constraints_version)`. Fusion results are cached on the full feature-vector hash + model version (Plan §13.3). No Redis.

#### 9.5.3 Event envelope and catalogue

Every event is persisted to `simulation_events` **before** it is published to the per-run `asyncio.Queue` (write-then-publish), so replay is always possible.

```json
{ "run_id": "9f2c...", "seq": 7, "ts": "2026-10-14T12:04:06.120Z",
  "type": "stage.completed", "stage": "PLASTICIZING", "payload": { ... } }
```

| `type` | `stage` | `payload` | UI effect |
|---|---|---|---|
| `run.started` | null | `{parameters, context, mode, speed_factor, inference_backend, model_version}` | Initialise the pipeline |
| `stage.started` | S | `{index, inputs_in_scope: {...}, upstream_in}` | Node → ACTIVE, populate the active-stage panel |
| `stage.progress` (optional) | S | `{pct}` | Progress ring |
| `stage.completed` | S | `StageResult` (+ `presentation_ms`, `cache_hit`) | Node → COMPLETED with colour + badge |
| `anomaly.flagged` | S or null | `AnomalyResult` | Purple "!" overlay + timeline row |
| `constraint.breached` | S | `ConstraintBreach` | Warning chip (critical ⇒ red) |
| `stage.blocked` | S | `{reason, breaches[]}` | Halt, show the override dialog |
| `stage.override_acknowledged` **[P]** | S | `{acknowledgement, breaches[]}` | Timeline row; badge "overridden" |
| `prediction.ready` | QUALITY_INSPECTION | `PredictionResult` | Reveal the result card |
| `run.completed` / `run.paused` / `run.resumed` **[P]** / `run.reset` / `run.aborted` | null | `{status, reason?}` | Control state |
| `run.error` **[P]** | null | `{code, message}` | Error toast; run aborted |

#### 9.5.4 SSE formatting (Plan §18.2–18.4)

- Media type `text/event-stream`, served via FastAPI `StreamingResponse`.
- Each event is written as:
  ```
  id: <seq>
  event: <type>
  data: <single-line JSON envelope>
  <blank line>
  ```
- A keepalive comment `: keepalive` is sent every 15 s.
- On connect with `Last-Event-ID: n`, the server first replays persisted events with `seq > n`, then streams live.
- The server closes the stream after `run.completed` or `run.aborted` has been delivered.
- **Client contract:** track `last_seq`. On a gap (`seq > last_seq + 1`) or a reconnect, call `GET /simulation/runs/{id}` once to re-sync. If SSE fails twice, fall back to polling `GET /simulation/runs/{id}` every 300 ms (Plan §18.2, R17).

### 9.6 Dependency and configuration contract

**Toolchain (verified on the dev machine, 2026-10-14):**

| Tool | Version |
|---|---|
| Python | 3.12 (pinned in `.python-version`; 3.14.x is the machine default and is **not** used, UD-01) |
| uv | 0.10.x |
| Node | 24.x (24.14.1 installed) |
| npm | 11.x |
| Docker | 29.x, Compose v5 (P2 only) |

- Library versions are resolved once by `uv lock` / `npm install` in R2-P1 and pinned in `uv.lock` / `package-lock.json`. Both members use `uv sync --frozen` and `npm ci`.
- Plan-mandated major versions: Pydantic v2, SQLAlchemy 2.0, React 18 (UD-13).
- **Lockfiles are committed. Any dependency change ships in the same PR as its lockfile change.**

**Environment variables** (prefix `SMQI_`; loaded by `pydantic-settings` from env and `.env`; `.env` is never committed; `.env.example` lists all):

| Variable | Default | Owner | Meaning |
|---|---|---|---|
| `SMQI_ENV` | `dev` | R2 | `dev` \| `test` \| `demo` |
| `SMQI_DATABASE_URL` | `sqlite:///./var/smqi.db` | R2 | SQLAlchemy URL |
| `SMQI_INTELLIGENCE_BACKEND` | `mock` (dev), `real` (demo) | R2 | `mock` \| `hybrid` \| `real` |
| `SMQI_MODEL_DIR` | `./models` | R1 | Model store root |
| `SMQI_FUSION_MODEL_VERSION` | `active` | R1 | `active` (from `models/registry.json`) or an explicit semver |
| `SMQI_ANOMALY_MODEL_VERSION` | `active` | R1 | |
| `SMQI_STAGE_STATS_VERSION` | `active` | R1 | |
| `SMQI_CONSTRAINTS_PATH` | `./backend/app/domain/constraints.yaml` | R1 | |
| `SMQI_CORS_ORIGINS` | `http://localhost:5173` | R2 | Comma-separated |
| `SMQI_API_KEY` | unset | R2 | Enables the `X-API-Key` check |
| `SMQI_LOG_LEVEL` / `SMQI_LOG_FORMAT` | `INFO` / `json` | R2 | |
| `SMQI_STAGE_PRESENTATION_MS` | `1500` | R2 | |
| `SMQI_STAGE_CACHE_SIZE` | `5000` | R2 | |
| `SMQI_RECOMMEND_TIME_BUDGET_S` | `5` | R1 | |
| `SMQI_RATE_LIMIT_PER_MIN` | `30` | R2 | For `/recommend`, `/whatif/sensitivity` |
| `SMQI_DATA_DIR` | `./data` | R1 | Offline only |
| `SMQI_SEED` | `42` | R1 | Global seed |
| `MLFLOW_TRACKING_URI` | `file:./mlruns` | R1 | Offline only |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | R2 | Frontend |

**Model artifact layout (Plan §9.10, extended):**

```
models/
  registry.json                 # committed: list of bundles {name, semver, sha256, path, active}
  MANIFEST.sha256               # committed: per-file hashes of every bundle
  fusion/1.0.0/
    preprocessor.joblib  model.joblib  calibrator.joblib
    shap_background.parquet  feature_schema.json  global_explanation.json
    metrics.json  metric_floors.json  metadata.json  constraints_version.txt
  anomaly/1.0.0/   isolation_forest.joblib  threshold.json  feature_schema.json  metadata.json
  stage_stats/1.0.0/   stats.json  metadata.json   # MFI tertiles, lot z-score params,
                                                   # percentile bands used by stage rules
```

- `metadata.json` MUST contain: `model_name`, `semver`, `algorithm`, `git_sha`, `dataset_hash`, `generator_version`, `train_date`, `split_spec`, `seed`, `threshold`, `threshold_policy` (e.g. "FAIL recall ≥ 0.85 on validation"), `calibration_method`, `constraints_version`, `contracts_version`, `is_fixture` (true only for the tiny test bundle).
- `feature_schema.json` MUST contain, per feature: `name`, `dtype`, `group` (`raw`\|`stage`\|`engineered`\|`context`), `owning_stage` (or a split map for cross-stage features), `p01`, `p99`, `display_name`, `provenance`. It also holds the `excluded_columns` list.

**Commands (cross-platform, run from the repo root):**

| Purpose | Command |
|---|---|
| Install (R2 / app) | `uv sync --frozen` |
| Install (R1 / training) | `uv sync --frozen --group ml` |
| DB migrate + seed | `uv run alembic -c backend/alembic.ini upgrade head` then `uv run python -m app.db.seed` |
| Run API | `uv run uvicorn app.main:app --reload --app-dir backend --port 8000` |
| Backend tests | `uv run pytest` |
| Lint / format / types | `uv run ruff check .`, `uv run black --check .`, `uv run mypy backend/app` |
| Generate data / train all | `uv run python -m ml_pipeline.cli generate` / `uv run python -m ml_pipeline.cli train-all` |
| Frontend | `cd frontend; npm ci; npm run dev` (port 5173); `npm run gen:api`; `npm run test`; `npm run lint`; `npm run typecheck` |

**Error-handling conventions:**
- Python: typed exceptions → central FastAPI handlers → envelope. No bare `except:`. Every log line carries `request_id` and, where relevant, `run_id`.
- Frontend: a single API client unwraps the envelope and maps `error.code` to UI messages. Unknown codes are shown generically with `request_id`.

---

## 10. Integration and contract-change procedures

### 10.1 Integration principles

1. **Contract-first.**
   - This roadmap's Sections 7–9 are implemented as code in W1: `contracts/` (R1), the API skeleton and mock (R2).
   - Contract versions: `CONTRACTS_VERSION` 0.x until M1, **1.0.0 at M1 approval**.
2. **Mocks from day one.** Role 2 never waits for Role 1. Role 1 never needs the API to test intelligence.
3. **A shared contract test suite** (`backend/tests/contract/`):
   - Role 1 authors JSON fixtures (inputs and expected **invariants**).
   - Role 2 authors the harness, parametrized over the `mock`, `hybrid` and `real` implementations.
   - Both implementations MUST pass the same suite.
4. **Weekly integration checkpoint** (Plan §21.2; every Friday from W2):
   1. merge both role branches to `main`;
   2. run the full test suite on a clean `uv sync --frozen` + `npm ci`;
   3. run the E2E smoke test;
   4. update `docs/integration_status.md` (capability matrix real/mock, open CCRs, blockers).
5. **Capability matrix.** `IntelligenceVersionInfo.capabilities` tells Role 2 exactly which real capabilities exist, so no undocumented assumption about Role 1 progress is possible.

### 10.2 Mock replacement procedure

For each capability, in the order run_stage → predict → explain → anomaly_global → recommend → sensitivity:

| Step | Who | Action |
|---|---|---|
| 1 | R1 | Delivers the capability with `capabilities()[name] = true`, contract fixtures updated with real outputs, bundle archive + SHA-256, and a note in `integration_status.md` |
| 2 | R2 | Runs the contract suite against `real` for that capability (tiny fixture bundle in CI; full bundle locally) |
| 3 | R2 | Switches dev to `hybrid`, runs E2E, and fixes any UI assumptions that only held for mock data |
| 4 | Both | Joint integration test for the capability (Section 13 milestone row) passes |
| 5 | R2 | Marks the capability "REAL" in the matrix |
| 6 | R2 | Before M14, deletes the hybrid default from demo config; `real` is mandatory in demo |

### 10.3 Contract artifacts and their versions

| Artifact | Version key | Who bumps |
|---|---|---|
| `app/contracts/*` | `CONTRACTS_VERSION` | Author of the CCR |
| `constraints.yaml` | `registry_version` | R1 |
| API (OpenAPI) | `api_version` (path `/api/v1`) | R2 |
| Event catalogue | `EVENTS_VERSION` in `engine/events.py` | R2 |
| DB schema | Alembic head revision | R2 |
| Model bundles | semver per bundle | R1 |

### 10.4 Contract-change procedure (CCR)

A change to any shared schema, endpoint, event, parameter name, error code, registry rule or inference signature MUST follow these steps. **Silent changes are forbidden.**

1. **Identify** the incompatibility or missing requirement. Open `docs/contract_changes/CCR-NNN-<slug>.md` using the template below.
2. **Propose** the smallest change that solves it.
3. **List** every affected module and consumer (both roles, frontend types, DB, fixtures, docs).
4. **Document** the new schema or interface in this roadmap (Sections 7–9) in the same PR.
5. **Update** tests, fixtures and examples (contract fixtures, OpenAPI snapshot, TS types).
6. **Approve.** Both members approve the PR (CODEOWNERS enforces JOINT paths).
7. **Re-plan.** Update the affected phase tasks in Sections 11/12 if work changes.
8. **Verify** compatibility before merge: the full suite plus the contract suite for mock and real pass on the merged branch.

```markdown
# CCR-NNN: <title>
- Requested by: Role X        - Date:            - Status: proposed|approved|rejected|merged
- Type: additive (MINOR) | breaking (MAJOR) | clarification (PATCH)
- Problem:
- Proposed change (exact fields/signatures):
- Affected: contracts | registry | API | events | DB | frontend | fixtures | bundles
- Migration / compatibility plan:
- Tests updated:
- Approvals: Role 1 [ ]  Role 2 [ ]
```

Additive changes (new optional field, new endpoint, new error code) are MINOR. Renames, removals or semantic changes are MAJOR. A MAJOR change requires both roles to schedule the update in the same weekly checkpoint.

---

## 11. Role 1: complete phase-wise development roadmap

**Role:** AI/ML, Manufacturing Intelligence & Recommendation Engineer. Every phase lists the 16 required fields.

**Sequence rationale (RC-11):**
- Stage modules (R1-P5) come **before** the fusion freeze (R1-P6) because "the fusion feature set cannot be frozen before [stage modules] complete" (Plan Phase 5 gate).
- An interim GBDT bundle (`fusion-0.1.0`, raw + engineered features) ships at the end of R1-P4, so Role 2 can integrate real inference early (Milestone M7).

| Phase | Title | Priority | Weeks |
|---|---|---|---|
| R1-P1 | Domain registry, contracts bootstrap, dataset discovery & feasibility | P0 | W1 |
| R1-P2 | Synthetic generator, data validation, EDA & preprocessing | P0 | W2–W3 |
| R1-P3 | Feature engineering & leakage-safe splitting | P0 | W3 |
| R1-P4 | Baselines & primary GBDT model selection (interim bundle 0.1.0) | P0 | W4 |
| R1-P5 | Five stage-intelligence modules | P0 (sub-models P1) | W5 |
| R1-P6 | Fusion v1, calibration, threshold & risk engine (+ MLP benchmark P2) | P0 (MLP P2) | W6 |
| R1-P7 | Explainability, OOD & anomaly detection | P0 SHAP/OOD; P1 IsoForest/SPC; P2 AE | W7 |
| R1-P8 | Constrained recommendation engine & sensitivity | P0 funnel + guard; P1 pairwise/DE/sweep | W8 |
| R1-P9 | Packaging & integration handoff | P0 | W9 |
| R1-P10 | Intelligence validation & final evaluation | P0 | W10–W12 |

---

### R1-P1: Domain Registry, Contracts Bootstrap, Dataset Discovery & Feasibility

1. **Phase:** R1-P1, Domain Registry, Contracts Bootstrap, Dataset Discovery & Feasibility (Plan Phase 0 + start of Phase 1).
2. **Objective:**
   - Fix the canonical vocabulary in code: contracts, parameter dictionary, constraint registry v1, remedy table, virtual fleet.
   - Decide, from evidence, which dataset tiers are feasible.
3. **Priority:** P0.
4. **Primary owner:** Role 1 (Role 2 reviews contracts and registry).
5. **Dependencies:**
   - None blocking.
   - Repo skeleton from R2-P1 task 1 (day 1). If it is late, work in the agreed paths and merge when the skeleton lands.
6. **Estimated duration:** 5–7 working days (W1, overlapping W2 for literature citations).
7. **Ordered tasks:**
   1. Implement `backend/app/contracts/` **v0.1.0** exactly as Sections 7 and 9.1 (enums, context, recipe, stage, anomaly, prediction, explanation, recommendation, sensitivity, errors, interface Protocol, version info). Day 1–2. Request Role 2 review within 24 h.
   2. Add `scripts/export_contract_schemas.py` (shared script; R1 writes the first version) to emit `docs/contracts/*.schema.json`.
   3. Write `docs/parameter_dictionary.md`. For every field in Sections 7.3–7.6: unit, kind, stage, actionable, physical role, related defect modes (Plan §3.2), provenance.
   4. Literature survey of PP injection-molding windows and defect mechanisms. Populate `constraints.yaml` **v1.0.0** with the Section 8.2 structure: every parameter with `min`, `max`, `nominal`, `step`, `unit`, `actionable`, `change_cost`, `max_step_change`, `tolerance`, `provenance`, `citation`. Mark any value without a citation `unvalidated` or `heuristic`.
   5. Define ≥ 2 resin grades (placeholder names until literature confirms) with melt window, degradation ceiling, moisture spec max and critical factor.
   6. Write coupling rules CPL-001…004, hard constraints HC-001…006, `stage_checks` weights per stage, `risk_bands` ([PROPOSED] values from Sections 7.10 and 7.13), and the `recommendation` block.
   7. Write `remedies.yaml` v1 from Plan §14.3: cooling_adequacy < 1 → ↑cooling_time / ↓mold_temp; degradation high → ↓melt_temp / ↓residence; sink/void high → ↑hold_pressure / ↑hold_time; flash high → ↓inj_pressure / ↓hold_pressure / ↑clamp_force; short-shot high → ↑melt_temp / ↑inj_pressure / ↑inj_velocity; moisture flag → ↑drying_time. Each rule gets a rationale.
   8. Write `fleet.yaml`: 6–10 virtual machines (type, tonnage, max pressure, max clamp, installed date, maintenance date, persistent bias description), product `PP-JBOX-42` (+ optional 1–2 products), resin grades, ~5 demo lots including `A-771` (MFI 12, moisture 0.04 %, regrind 15 %, per Plan §5.1). Tag all `synthetic`.
   9. Implement `constraint_loader.py` (Section 8.4 API) and `dependency_graph.py` (`stage_inputs`, `invalidated_stages`).
   10. **Tier-1 dataset search.**
       - Search Kaggle, Mendeley Data, UCI ML Repository, Zenodo and paper supplements for injection-molding (or nearest-equivalent) quality datasets.
       - For each candidate record in `docs/dataset_feasibility.md`: URL, licence (verbatim name), row count, **actual** column list, units, label definition, machines, time index, overlap with the canonical schema (column → canonical mapping), missing fields, verdict.
       - **Do not record a dataset as usable until its licence and columns have been verified from the source.**
   11. Download only licence-compatible candidates into `data/raw/<source>/` with `source_manifest.json` (URL, licence, retrieval date, SHA-256 per file).
   12. Write the **feasibility decision**:
       - (a) Tier-1 dataset X is used for real-data validation and distribution calibration, **or**
       - (b) no suitable Tier-1 exists, so the project proceeds Tier-2-only and the report states it.
       - Also list the synthetic assumptions required.
   13. Write `docs/synthetic_generator_spec.md` (Plan §19.4 steps 1–6): context sampling, recipe sampling with correlations, mechanism formulas (short-shot, flash, sink/void, warp, splay, degradation), coefficient table (to be fitted in R1-P2 so marginal defect rates match targets), label combination, realism (noise, missingness, drift, label noise), documentation outputs.
   14. ADRs: `ADR-001-domain-selection`, `ADR-002-synthetic-primary-dataset`, `ADR-003-no-autonomous-agents`, `ADR-004-two-role-ownership` (from Plan §2, §19, §8.1 and this roadmap).
8. **Files created/modified:**
   - `backend/app/contracts/*.py`
   - `backend/app/domain/{constraints.yaml, remedies.yaml, fleet.yaml, CHANGELOG.md, constraint_loader.py, dependency_graph.py}`
   - `backend/tests/domain/test_constraint_loader.py`, `test_dependency_graph.py`
   - `backend/tests/contract/fixtures/` (initial: `recipe_nominal.json`, `recipe_melt_ceiling_breach.json`, `recipe_short_cooling.json`, `recipe_clamp_insufficient.json`, `recipe_high_moisture.json`)
   - `docs/{parameter_dictionary.md, dataset_feasibility.md, synthetic_generator_spec.md}`, `docs/decisions/ADR-001..004.md`, `docs/contracts/*.schema.json`
   - `data/raw/<source>/source_manifest.json` (if any)
9. **Technical details:**
   - Contracts are frozen Pydantic v2 models (`model_config = ConfigDict(frozen=True, extra="forbid")`).
   - The registry loader validates YAML into Pydantic models, computes `content_hash` over canonical JSON (sorted keys), and exposes immutable views.
   - `invalidated_stages(changed)` is **derived from the `stage_inputs` slices (Section 7.10)**, never maintained as a separate list. It returns the earliest stage whose input slice contains any changed field, plus all downstream stages up to COOLING. S6 fusion always re-runs.
   - Fields used by no stage module (e.g. `machine_id`, `machine_age_days`) invalidate only fusion.
   - Consequences: `projected_area_cm2`/`cavity_count` start at INJECTION; `wall_thickness_mm`/`mold_temp_c` start at PACKING; lot attributes start at MATERIAL_CONDITIONING. This is consistent with Plan §13.2, except that `mold_temp_c` starts at S4 because the gate-freeze heuristic consumes it.
10. **Required tests:**
    - Loader: every parameter has all required keys; `min < nominal < max`; `step > 0`; units ∈ `units_allowed`; `max_step_change ≤ max − min`; every `ProcessRecipe`/context field has a registry entry and vice versa; the nominal recipe produces zero coupling and hard-constraint breaches; `melt_temp_c = ceiling + 1` ⇒ HC-001 CRITICAL; `hold_pressure_bar > inj_pressure_bar` ⇒ CPL-001; `content_hash` is stable across loads; invalid YAML raises `REGISTRY_INVALID`.
    - Dependency graph: `cooling_time_s → [COOLING]`; `melt_temp_c → [PLASTICIZING, INJECTION, PACKING, COOLING]`; `moisture_pct → all five`; `hold_pressure_bar → [PACKING, COOLING]`; `mold_temp_c → [PACKING, COOLING]`; `machine_id → []` (fusion only). A generated test asserts that, for every field, the result equals "earliest stage whose `stage_inputs` contains it + downstream".
    - Contracts: JSON round-trip; enum ordering; `RiskLevel` ordinal mapping; `extra="forbid"` rejects unknown fields.
11. **Deliverables:** contracts v0.1.0; registry v1.0.0; remedies v1; fleet v1; loader + dependency graph; parameter dictionary; feasibility report with decision; generator spec; ADR-001…004; initial contract fixtures.
12. **Handoff requirements (to Role 2):**
    - Merged contracts + loader + registry.
    - A note in `integration_status.md` listing the registry public payload shape (for `GET /constraints`), the five fixture recipes (for mock and BLOCKED demo), and the default nominal recipe (for UI defaults).
13. **Acceptance criteria:**
    - Every parameter has documented nominal, min, max, step, unit, actionable flag and change cost (Plan Phase 0 acceptance).
    - Every value has a citation or an explicit `unvalidated`/`heuristic` provenance.
    - The feasibility report states verified facts only.
    - Role 2 has approved contracts v0.1.0.
14. **Completion gate:** no generator implementation until registry v1.0.0 is merged (Plan Phase 0 gate). Contracts must be approved before M1 closes.
15. **Compatibility requirements for Role 2:**
    - Field names in contracts = registry keys = dataset canonical columns = DB column names.
    - `to_public_dict()` is stable and documented, because the frontend builds sliders from it.
16. **Risks & assumptions:**
    - No suitable Tier-1 dataset (likely, A-01): proceed Tier-2-only and state it.
    - Literature windows vary by grade: keep `unvalidated` flags instead of inventing precision.
    - Contracts may need early revision: allowed through CCRs while in 0.x.

---

### R1-P2: Synthetic Generator, Data Validation, EDA & Preprocessing

1. **Phase:** R1-P2, Synthetic Generator, Data Validation, EDA & Preprocessing (Plan Phases 1–2).
2. **Objective:** Produce a documented, deterministic, mechanism-based Tier-2 corpus (plus Tier-1 ingestion if feasible), validate it, understand it, and build the leak-free preprocessing object.
3. **Priority:** P0 (Tier-3 augmentation P1).
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P1 (registry v1, fleet, generator spec, feasibility decision).
6. **Estimated duration:** 8–10 working days (W2–W3).
7. **Ordered tasks:**
   1. Implement `ml_pipeline/synthetic/mechanisms.py`. Each defect mechanism is a pure, documented function (Plan §19.4 step 3) reusing `app/intelligence/derivations.py` formulas: `viscosity_proxy`, `fill_index`, `packing_integral`, `cooling_adequacy`, `thermal_exposure`, `cavity_pressure_estimate`. Also expose `true_p_defect(process_input) -> float`, used later for the recommendation ground-truth check (Plan §24.3).
   2. Implement `generator.py`:
      - context sampling: machine bias vectors and maintenance drift; product; resin grade → MFI ~ truncated Normal; moisture ~ LogNormal; regrind ~ Beta scaled to percent;
      - recipe = nominal(grade, product) + Normal noise + 5–12 % heavy-tailed excursions, with imposed correlations (velocity↔melt temp; rushed cycle shortens cooling and hold);
      - mechanism scores → `p_defect = 1 − Π(1 − p_m)` → `label ~ Bernoulli`; `defect_mode = argmax`;
      - realism: sensor noise (recorded ≠ setpoint); 1–3 % missingness, higher on older machines; temporal ordering with per-machine drift; 1–2 % label noise;
      - `batch_id` (consecutive shots sharing setpoints and lot), `shot_id`, `timestamp`.
   3. Fit the mechanism coefficients so marginal defect rates are plausible and the overall failure rate is 6–12 % (Plan §19.6). Record the coefficient table and fitting procedure.
   4. `generator_config.yaml`: 25,000–40,000 rows, 6–10 machines, 200+ lots, seed, `generator_version`. Output `data/synthetic/<generator_version>/shots.parquet` + `MANIFEST.sha256`. Tag every row `source_tier="synthetic"`, `generator_version`.
   5. If the feasibility decision allows: `ingest.py` maps Tier-1 columns to canonical names, harmonises units, tags `source_tier="real"`, and writes `data/interim/real_<source>.parquet`.
   6. `validate.py`: column presence (Plan §19.5), dtypes, registry ranges (flag, don't drop), nullity rates, duplicate `shot_id`, label ∈ {0, 1}, timestamp monotonic per machine, `p_defect_true` ∈ [0, 1]. Writes `data/reports/validation_<dataset>.json` + `.md`. **Hard-fails** on contract breach.
   7. `eda.py`: univariate, bivariate, target-conditioned distributions; correlation matrix and VIF; class balance; failure rate by machine, resin grade, lot and parameter bucket; defect-mode mix; non-monotone checks (fill_index vs failure). Outputs go to `data/reports/eda/` with a summary in `docs/eda_summary.md`.
   8. `clean.py`: de-duplication, impossible-value removal, unit harmonisation, outlier **flagging** (IQR + robust z), never blind deletion.
   9. `preprocess.py`: an sklearn `Pipeline`/`ColumnTransformer` containing:
      - group-median imputer by (`machine_id`, `resin_grade`) for setpoints and by `resin_grade` for lot attributes, plus `_was_missing` flags, all fitted on train only (Plan §9.2);
      - `UNKNOWN` category + one-hot for `machine_id`, `resin_grade`, `product_id` (Plan §9.4 MVP);
      - `StandardScaler` (kept for all models so one object serves all, Plan §9.1(8));
      - an **explicit allowlist**. Excluded: `shot_id`, `batch_id`, `timestamp`, `material_lot_id`, `p_defect_true`, `defect_mode`, `source_tier`, `generator_version`, `shift`, `operator_id`.
   10. Write `docs/dataset_card.md` (tiers, provenance, generator assumptions, coefficient table, limitations, the `STATEMENT_SYNTHETIC_DATA` sentence).
   11. Produce 20 generator rows as additional contract fixtures (`backend/tests/contract/fixtures/generated_rows.json`) so Role 2 has realistic recipes.
8. **Files:**
   - `ml_pipeline/synthetic/{generator.py, mechanisms.py, generator_config.yaml}`
   - `ml_pipeline/{ingest.py, validate.py, eda.py, clean.py, preprocess.py, cli.py}`
   - `backend/app/intelligence/derivations.py`
   - `ml_pipeline/tests/test_generator.py`, `test_validate.py`, `test_preprocess.py`
   - `docs/{dataset_card.md, eda_summary.md}`
   - `data/synthetic/<v>/MANIFEST.sha256` (committed); data files gitignored
9. **Technical details:**
   - All randomness comes from `numpy.random.Generator(PCG64(seed))`, passed explicitly (no global state).
   - Parquet is written with deterministic row order and column order so byte-identical regeneration is testable (D3).
   - `derivations.py` is pure numeric code with no sklearn, so the stage modules, the generator and the feature builder all share **one** implementation of each formula.
   - Heuristic formulas (gate freeze, required cooling) carry docstrings stating "heuristic, not a solved physical time".
10. **Required tests:**
    - Same seed ⇒ identical file SHA-256; different seed ⇒ different.
    - Row count, machine count, lot count and failure rate within targets.
    - Mechanism direction tests: low fill_index ⇒ higher short-shot probability; high cavity pressure vs clamp ⇒ higher flash; moisture × melt temp interaction ⇒ splay only at high temperature.
    - The validator detects injected faults (missing column, out-of-range, duplicate id, non-binary label).
    - The preprocessor fitted on train leaves test-set statistics unused (fit on train, assert medians equal train medians).
    - Excluded columns are absent from the transformer output.
11. **Deliverables:** generator + config + seed + corpus + manifest; Tier-1 interim data (if any); validation report; EDA report; cleaning and preprocessing modules; dataset card; generated fixture rows.
12. **Handoff requirements:**
    - The dataset card and EDA summary are shared with Role 2 (for analytics screen design and seed lots).
    - `generated_rows.json` fixtures.
    - The registry nominal recipe is confirmed against the generated distribution.
13. **Acceptance criteria:**
    - Marginal distributions and failure rate match the documented targets.
    - The validation suite passes.
    - The generator is deterministic given its seed (Plan Phase 1 acceptance).
    - The preprocessing pipeline is fitted inside training folds only.
14. **Completion gate:** no model training until validation passes **and** the split protocol (R1-P3) is written (Plan Phase 1 gate).
15. **Compatibility requirements for Role 2:** none at runtime. The fixture rows MUST validate against the API recipe schema (Role 2 runs them through `POST /simulation/runs` in tests).
16. **Risks & assumptions:**
    - Generator coefficients make the task trivially separable: tune toward realistic overlap, and report the generator-recovery caveat.
    - The Tier-1 schema overlap is small: use Tier-1 only for validation of overlapping features, and document it.

---

### R1-P3: Feature Engineering & Leakage-Safe Splitting

1. **Phase:** R1-P3, Feature Engineering & Leakage-Safe Splitting (Plan Phase 2, §9.3, §9.6).
2. **Objective:** Build the single shared feature builder and the split protocol that every later model uses.
3. **Priority:** P0.
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P2 (validated corpus, preprocessing).
6. **Estimated duration:** 5 working days (W3).
7. **Ordered tasks:**
   1. Implement `app/ml/features.py: FeatureBuilder.build(process_input, stage_results=None) -> FeatureVector`. It contains:
      - **raw** features;
      - **engineered** features from Plan §9.3, each via `derivations.py`: `viscosity_proxy`, `effective_melt_temp_c`, `thermal_exposure`, `fill_index`, `packing_integral`, `cooling_adequacy`, `pressure_headroom`, `temp_profile_slope`, `cycle_balance`, `moisture_temp_risk`, `machine_age_norm`, `days_since_maintenance`, `regrind_mfi_interaction`;
      - **context** features;
      - (from R1-P6) **stage** features.
   2. For each engineered feature record definition, justification, owning stage (`fill_index → INJECTION`, `thermal_exposure → PLASTICIZING`, `moisture_temp_risk` split 50/50 MATERIAL/PLASTICIZING, etc.), provenance, and whether it is available at serving time.
   3. **Rolling features:** implement only for offline SPC/analytics. Exclude them from the fusion feature set (RC-12) and document why.
   4. `feature_schema.json` writer: ordered names, dtypes, groups, owning stage or split map, train-set p01/p99, display names, provenance, `excluded_columns`.
   5. `split.py`:
      - temporal final holdout = last ~20 % of the time index (untouched test);
      - from the remaining training portion, **StratifiedGroupKFold(5) by `batch_id`** for model selection;
      - a **calibration split** = group-disjoint, time-later slice of the training portion (≈ 15 %), never from test;
      - a **leave-one-machine-out** diagnostic split generator;
      - persist indices to `data/processed/splits/<split_version>.json`.
   6. Write `docs/leakage_checklist.md`: batch, temporal, machine and target leakage; pre-split imputation; stage sub-model stacking; forbidden columns; how each is prevented and tested.
   7. Add a "shuffled-target" sanity experiment script.
8. **Files:** `backend/app/ml/features.py`; `ml_pipeline/{split.py, feature_report.py}`; `ml_pipeline/tests/test_split.py`; `backend/tests/ml/test_features.py`; `docs/leakage_checklist.md`; `docs/feature_catalogue.md`.
9. **Technical details:**
   - `FeatureBuilder` is pure and vectorised for batch training, with a single-record path for serving. **Both paths call the same column functions.**
   - Feature order at serving time is always read from `feature_schema.json` (Plan §9.10).
10. **Required tests:**
    - Group disjointness across folds and calibration/test splits.
    - `max(train.timestamp) < min(test.timestamp)`.
    - Calibration ∩ test = ∅.
    - Shuffled-target model PR-AUC within ±0.02 of prevalence (chance).
    - Forbidden columns are absent from the schema (unit test, Plan §19.5).
    - Batch vs single-record feature vectors are identical for the same rows (**skew test**, R18).
    - Builder determinism.
    - A missing optional value produces `None` → imputer (no crash).
11. **Deliverables:** feature builder, feature catalogue, `feature_schema.json` writer, split module + persisted indices, leakage checklist, shuffled-target report.
12. **Handoff requirements:** `docs/feature_catalogue.md` is shared with Role 2 for display names and stage ownership in the UI. The display names in `feature_schema.json` are the strings the UI shows.
13. **Acceptance criteria:**
    - Splits are verified group-disjoint and time-ordered.
    - The deliberate leakage test yields chance performance (Plan Phase 2 acceptance).
14. **Completion gate:** no model selection before the split protocol is fixed (Plan Phase 2 gate).
15. **Compatibility requirements for Role 2:** feature display names and stage ownership are the only strings the UI uses for attributions. Role 2 must not rename features.
16. **Risks & assumptions:**
    - Engineered features may be collinear (harmless for trees, distorts SHAP; handled in R1-P7 with grouped attribution).
    - Some features may be unavailable for Tier-1: document per dataset.

---

### R1-P4: Baselines & Primary GBDT Model Selection (interim bundle `fusion-0.1.0`)

1. **Phase:** R1-P4, Baselines & Primary GBDT Model Selection (Plan Phases 3–4).
2. **Objective:**
   - Establish honest baselines and a trusted metric harness.
   - Select and tune the GBDT on raw + engineered + context features.
   - Ship an interim, correctly packaged bundle for early integration.
3. **Priority:** P0.
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P3.
6. **Estimated duration:** 5–6 working days (W4).
7. **Ordered tasks:**
   1. `evaluate.py` metric harness:
      - PR-AUC (primary), FAIL recall (co-primary), FAIL precision, F1, F2, ROC-AUC (comparability only), accuracy (always next to the majority baseline);
      - confusion matrices at 0.5 and at the tuned threshold;
      - Brier score; per-machine and per-resin-grade breakdown; fold mean ± 95 % CI.
      - Writes `metrics.json` and a Markdown table. Reproducible with one command.
   2. Baselines: majority class; Logistic Regression (`class_weight="balanced"`); Decision Tree (plus extracted rules for the report); Random Forest.
   3. GBDT: XGBoost (primary), LightGBM (comparison), with `scale_pos_weight`/class weights and early stopping on the validation fold.
   4. Optuna TPE, 50–150 trials with an explicit time budget. Objective = mean PR-AUC across GroupKFold folds. Fixed seeds. Every trial is logged to MLflow (`file:./mlruns`) or a CSV fallback with parameters, metrics and git SHA.
   5. Imbalance escalation (Plan §9.7): class weights → threshold tuning → SMOTE/SMOTENC **only inside folds** as a reported ablation, if needed.
   6. Select the primary model on measured PR-AUC + FAIL-recall evidence (not accuracy). Write `docs/model_selection_v0.md`.
   7. Quick isotonic calibration on the calibration split and a provisional threshold, so the interim bundle has the full layout. These are formalised in R1-P6.
   8. `package_bundle.py`: write `models/fusion/0.1.0/` (Plan §9.10 layout + Section 9.6 metadata), update `models/registry.json` and `MANIFEST.sha256`.
   9. `app/ml/bundle.py` (load + verify hashes + constraints-version check) and `app/ml/predict.py`. Facade capability `predict=true`; `run_stage` is still `false` (the hybrid mock supplies stage results; the 0.1.0 feature schema has no stage features).
   10. Build the **tiny fixture bundle** `backend/tests/fixtures/model_bundle_tiny/` (≈ 2,000 rows, small trees, `is_fixture=true`, < 2 MB) for Role 2 CI.
8. **Files:** `ml_pipeline/{evaluate.py, train_baselines.py, train_fusion.py, tune.py, package_bundle.py, registry_update.py}`; `backend/app/ml/{bundle.py, predict.py}`; `backend/app/intelligence/facade.py` (initial); `backend/tests/ml/test_bundle.py`, `test_predict.py`; `docs/model_selection_v0.md`; `models/registry.json`.
9. **Technical details:**
   - The bundle is loaded **whole**. `bundle.py` verifies every file's SHA-256 against `MANIFEST.sha256` and raises `ArtifactInvalidError` on mismatch.
   - Inference uses the fitted preprocessor + model + calibrator in that order. The threshold comes from `metadata.json`.
   - No training code is imported at serving time.
10. **Required tests:**
    - Harness reproducibility (same seed ⇒ same metrics to 1e-9).
    - All baselines beat the majority class on PR-AUC.
    - The bundle loads and predicts on contract fixtures; `p_fail` ∈ [0, 1].
    - Feature order is taken from the schema (shuffle schema order in a test copy ⇒ mismatch error).
    - A corrupted file ⇒ `MODEL_ARTIFACT_INVALID`.
    - The tiny bundle loads in < 1 s.
11. **Deliverables:** baseline evaluation report; metric harness; tuned GBDT; `fusion-0.1.0` bundle (archive + SHA-256); tiny fixture bundle; model-selection note.
12. **Handoff requirements:** bundle archive placed per Section 14.5; `integration_status.md` updated (capability `predict` = REAL for 0.1.0); instructions for `SMQI_INTELLIGENCE_BACKEND=hybrid`.
13. **Acceptance criteria:**
    - Baselines beat the majority-class baseline on PR-AUC.
    - Metrics are reproducible from a single command (Plan Phase 3 acceptance).
    - The GBDT improves PR-AUC and FAIL-recall over the baselines, with fold-level CIs reported (Plan Phase 4 acceptance). **If it does not, report it honestly and keep the best baseline as the interim model.**
14. **Completion gate:** no advanced modelling until the harness is trusted (Plan Phase 3 gate). The fusion feature set is **not** frozen here (Plan Phase 4 gate).
15. **Compatibility requirements for Role 2:** `predict()` returns a full contract-valid `PredictionResult`. For 0.1.0, fields that depend on later phases (`explanation`, `anomaly_global`, `stage_risk_mass`) are `null` or empty, with caveat `STAGE_SUBMODEL_DISABLED` where relevant. Role 2 UI MUST handle nulls.
16. **Risks & assumptions:**
    - The synthetic task may be easy, giving inflated metrics: always report the generator-recovery caveat.
    - Optuna time budget: cap the trials.

---

### R1-P5: Five Stage-Intelligence Modules

1. **Phase:** R1-P5, Five Stage-Intelligence Modules (Plan Phase 5, §8).
2. **Objective:** Implement S1–S5 as pure, deterministic, tested modules that produce the Section 7.9–7.10 contract, plus the reference statistics they need.
3. **Priority:** P0 for rules + indicators + statistics. **P1** for supervised sub-models (RC-13).
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P1 (registry, contracts), R1-P2 (`derivations.py`, corpus), R1-P3 (training split, used for reference stats).
6. **Estimated duration:** 6–7 working days (W5). **Material module first (days 1–2) for M5.**
7. **Ordered tasks:**
   1. `base.py`:
      - `StageModule` protocol (`stage_name`, `module_version`, `input_fields`, `upstream_fields`, `evaluate(inputs, upstream, refs, registry) -> StageResult`);
      - shared helpers: severity functions, health aggregation (Section 7.10), risk banding, breach construction, L1 anomaly helpers (robust z, percentile band, spec limit), notes builder.
   2. `ml_pipeline/stage_reference_stats.py` → `models/stage_stats/1.0.0/stats.json`, computed on the **training split only**:
      - MFI tertiles (viscosity class);
      - per-grade lot-history mean/sd for `mfi` and `moisture_pct`;
      - p01/p99 bands for `fill_index`, `packing_integral`, `cooling_adequacy`;
      - per-machine `mold_temp_c` norms;
      - cycle-consistency tolerance.
      `references.py` loads them.
   3. `material.py` (S1): spec rules (moisture ≤ grade spec; regrind ≤ policy), `dryness_margin`, `viscosity_class`, z-scores, `moisture_risk`. Anomaly if |z| > 3 or a hard spec breach. BLOCK per HC-006. Publishes `viscosity_class`, `moisture_flag`. **Integrate via the facade immediately (M5).**
   4. `thermal.py` (S2): melt window rule; monotonic barrel profile rule; `temp_profile_slope`; `thermal_exposure`; `shear_heat_offset_c = f(screw_rpm, back_pressure)`; `effective_melt_temp_c`; `degradation_exposure`; `splay_risk` (moisture_flag × melt excess). Anomaly on profile inversion. BLOCK per HC-001. Publishes `effective_melt_temp_c`, `viscosity_proxy`.
   5. `injection.py` (S3): `fill_index` normalised (~1.0 = expected clean fill); headroom rule; clamp guard via `cavity_pressure_estimate_bar` and `required_clamp_force_ton`; `shear_rate_proxy`; heuristic `short_shot_risk`/`flash_risk` (logistic of fill-index deviation and clamp margin). Anomaly when `fill_index` is outside p01–p99. BLOCK per HC-002. Publishes `fill_completion_proxy`, `cavity_pressure_estimate_bar`.
   6. `packing.py` (S4): `packing_integral`; `gate_freeze_estimate_s` (labelled heuristic); `hold_vs_freeze_ratio`; `sink_void_risk` / `over_pack_risk` as a **signed** distance from the band (never averaged, Plan §8.3 S4.6); cushion rule. Anomaly: cushion ≈ 0 or integral outside the band. No block. Publishes `residual_stress_proxy`.
   7. `cooling.py` (S5): `required_cooling_estimate_s` (thickness² family heuristic); `cooling_adequacy`; `warp_risk`; `ejection_risk`; `dimensional_stability_index`; `cycle_consistency`; `cycle_balance`. Anomaly: cycle inconsistency, or mold temp far from the machine norm. No block.
   8. `pipeline.py`: `run_stage` / `run_all_stages` (deterministic chaining of upstream context). Facade capability `run_stage=true`.
   9. Stage-level evaluation (Plan §24.2), computed on the generated corpus:
      - failure rate per stage risk band (monotonicity, with CIs);
      - rule coverage (fraction of rows firing each rule; flag dead or always-on rules).
      Write `docs/stage_specs/S1..S5.md`. Each documents the ten Plan fields (purpose, inputs, logic, method, output, risk score, anomaly, state transition, effect on next stage, failure modes) and marks every value as specification-derived, heuristic, dataset-derived or learned.
   10. (P1, after P0 integration) OOF-trained sub-models: S3 short-shot/flash classifier, S5 warp classifier, S2 ridge melt-consistency, S4 sink classifier. Each sits behind `submodels.enabled` with its own `module_version` bump. Trained with stacking discipline (Plan §10.3): out-of-fold predictions for fusion training rows; the target is a defect-mode indicator (never used as a fusion input).
8. **Files:** `backend/app/intelligence/{base.py, material.py, thermal.py, injection.py, packing.py, cooling.py, references.py, pipeline.py, facade.py}`; `ml_pipeline/stage_reference_stats.py`; `models/stage_stats/1.0.0/`; `backend/tests/intelligence/test_{base,material,thermal,injection,packing,cooling,pipeline,purity}.py`; `docs/stage_specs/*.md`; `docs/stage_evaluation.md`.
9. **Technical details:**
   - Modules receive plain dicts and immutable reference objects. They never read files themselves (the facade loads references once).
   - `module_version` is a constant per module. **Any behaviour change bumps it**, because the R2 cache key includes it.
   - Notes are deterministic templates (e.g. "melt temp 268 °C with residence 41 s → thermal degradation exposure").
10. **Required tests:**
    - **Golden defect-mechanism cases** (Plan Phase 5 acceptance): high moisture + high melt ⇒ S1 `moisture_flag` and S2 `splay_risk` high; melt > ceiling ⇒ S2 `blocked`; low pressure × velocity with high viscosity ⇒ S3 `short_shot_risk` high; insufficient clamp ⇒ S3 `blocked`; low hold ⇒ S4 `sink_void_risk` high; over-pack ⇒ `over_pack_risk` high and `residual_stress_proxy` raised; zero cushion ⇒ S4 anomaly; short cooling ⇒ `cooling_adequacy` < 1 and S5 risk ≥ HIGH; inverted barrel profile ⇒ S2 anomaly.
    - **Purity:** calling twice gives equal objects. No randomness or clock (monkeypatch `time` and `random` to raise).
    - **Import boundary:** no `sqlalchemy`, `fastapi`, `app.db`, `app.api`, `app.services`, `app.engine`.
    - `health_score` ∈ [0, 1]; `risk_ordinal` consistent with `risk_level`; every indicator key has provenance; exact key set per stage.
    - `upstream_out` contains exactly the Section 7.8 keys owned so far.
    - Contract fixtures validate.
    - p95 `run_stage` < 5 ms.
11. **Deliverables:** five modules + pipeline + references; stage stats bundle; stage specification documents; stage evaluation report; updated contract fixtures with **real** stage outputs.
12. **Handoff requirements:** capability `run_stage` = REAL; fixtures `stage_results_<recipe>.json`; `module_version` list in `integration_status.md`; notice that cache keys change whenever module versions change.
13. **Acceptance criteria:**
    - Every module is deterministic, side-effect-free and produces the documented output contract.
    - Golden cases produce the expected risk direction (Plan Phase 5 acceptance).
    - The stage-risk-vs-outcome monotonicity report exists, and is discussed honestly if not monotone.
14. **Completion gate:** the fusion feature set cannot be frozen before this phase completes (Plan Phase 5 gate).
15. **Compatibility requirements for Role 2:**
    - `StageResult` exactly per Section 7.9.
    - `blocked` is the only signal Role 2 uses to halt.
    - `upstream_out` is passed unchanged to the next `run_stage`.
    - Role 2 must not interpret indicator values beyond display.
16. **Risks & assumptions:**
    - Heuristic constants may produce dead rules: the rule coverage report drives tuning.
    - Weights are assumptions (Plan §8.4): document them, do not claim they are learned.

---

### R1-P6: Fusion v1, Calibration, Threshold & Risk Engine (+ MLP Benchmark, P2)

1. **Phase:** R1-P6, Fusion v1, Calibration, Threshold & Risk Engine (Plan Phase 6, §9.9, §10, §24.1; MLP Plan §9.5).
2. **Objective:**
   - Freeze the fusion feature set (raw + stage + engineered + context) and retrain.
   - Prove there is no leakage. Calibrate probabilities and set a documented threshold.
   - Implement the risk engine and OOD caveats.
   - Ship `fusion-1.0.0`.
3. **Priority:** P0. MLP benchmark **P2** (only after M8).
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P4 (harness, tuned GBDT), R1-P5 (stage modules).
6. **Estimated duration:** 6–7 working days (W6). MLP +3 days later, if P2 is authorised.
7. **Ordered tasks:**
   1. Compute stage outputs for every training row with the **same** `run_all_stages`. Rule-only modules are deterministic, so no OOF is needed; any enabled P1 sub-model MUST use OOF predictions (Plan §10.3).
   2. Freeze the fusion feature groups A (≈ 18–23 raw), B (5 × {health, risk_ordinal, anomaly_score} + 2–3 indicators each ≈ 25), C (≈ 13 engineered), D (machine one-hot, age, maintenance gap, cavity count, thickness, shot weight). Write `feature_schema.json` v1.
   3. Retune the GBDT (Optuna, same protocol). Train the final model on the training portion.
   4. **Ablation** (Plan Phase 6): raw-only vs stage-only vs fusion, same split. Report honestly, including the case where fusion does not beat raw-only.
   5. **Calibration:** isotonic (Platt if the calibration split is small) on the calibration split. Reliability diagram + Brier before and after. Persist the calibrator inside the bundle.
   6. **Threshold:** tune on the validation PR curve to the documented operating point (A-07: FAIL-recall ≥ 0.85 [PROPOSED], UD-05). Record `threshold` and `threshold_policy` in metadata. State the precision cost explicitly.
   7. **Risk bands:** derive `p_fail` bands from empirical failure rates per probability decile (Plan R13). If they differ from the Section 7.13 placeholders, submit a registry MINOR CCR.
   8. `risk_engine.py`: operational risk = max(band(p_fail), constraint band); critical breach ⇒ CRITICAL + caveat `CRITICAL_CONSTRAINT_OVERRIDDEN`; anomalies ⇒ caveats only; `risk_drivers` list with weights.
   9. `ood.py`: per-feature p01/p99 bounds from the schema → `ood` field + `OUT_OF_DISTRIBUTION` caveat.
   10. Final evaluation **once** on the temporal holdout. Leave-one-machine-out diagnostic (expect lower numbers; report them). Learning curve. Per-machine and per-grade breakdown.
   11. **Generator ground-truth calibration check:** compare calibrated `p_fail` to `p_defect_true` on the test set (synthetic only; diagnostic).
   12. Tier-1 real-data evaluation section (if Tier-1 exists), reported **separately and prominently**.
   13. Write `metric_floors.json` (recorded floors for ML regression tests) and `docs/model_card.md` v1.
   14. Package **`fusion-1.0.0`**; update `registry.json`; set it active.
   15. (P2) PyTorch MLP (1–3 hidden layers, embedding for `machine_id`, focal loss) under the identical split and preprocessing. Report both with fold CIs and the Plan §9.5 rationale. The MLP is **not** promoted unless it wins on evidence (expected: it does not).
8. **Files:** `ml_pipeline/{train_fusion.py, calibrate.py, ablation.py, evaluate.py}`; `backend/app/intelligence/risk_engine.py`; `backend/app/ml/{ood.py, predict.py}`; `models/fusion/1.0.0/*`; `docs/{model_card.md, ml_evaluation_report.md (draft)}`; tests under `backend/tests/{ml,intelligence}/`; (P2) `ml_pipeline/train_mlp.py`.
9. **Technical details:** fusion inference is `run_all_stages` → `FeatureBuilder` (schema order) → preprocessor → XGBoost margin → calibrator → threshold → risk engine → OOD → (R1-P7) SHAP. One code path serves `/predict`, simulation, what-if and recommendation.
10. **Required tests:**
    - Calibrator is monotone; Brier(after) ≤ Brier(before) on the calibration set (report the test-set value).
    - Threshold read from metadata (change metadata ⇒ label changes).
    - Critical breach in stage results ⇒ `risk_level=CRITICAL` and caveat present (**never an ordinary PASS presentation**).
    - OOD caveat fires for a fixture with an out-of-band value.
    - Skew test: training-time vector equals serving-time vector for identical input.
    - `p_defect_true` and `defect_mode` absent from the schema.
    - ML regression: retrained metrics ≥ floors.
    - p95 `evaluate` < 150 ms.
11. **Deliverables:** `fusion-1.0.0` bundle; ablation report; calibration report; threshold policy; risk engine; OOD; model card v1; evaluation report draft; (P2) MLP comparison section.
12. **Handoff requirements:** capability `predict` = REAL with stage features; updated fixtures `prediction_<recipe>.json`; release note listing new caveat codes and the threshold; any registry CCR for risk bands.
13. **Acceptance criteria:**
    - The ablation table exists and is discussed honestly (Plan Phase 6).
    - PR-AUC and FAIL-recall reported with fold CIs; Brier improved by calibration (Plan Phase 4 acceptance).
    - Every claim is reproducible.
    - Synthetic metrics are labelled as generator-recovery.
14. **Completion gate:** no explainability work before the feature set is frozen (Plan Phase 6 gate).
15. **Compatibility requirements for Role 2:**
    - `PredictionResult` fields per Section 7.12.
    - Role 2 displays `p_fail` and `risk_level` as different concepts.
    - When `constraint_override_applied` is true, the UI uses the NOT-RELEASABLE presentation.
16. **Risks & assumptions:**
    - Small calibration set ⇒ use Platt.
    - Stage features add little: acceptable and publishable (Plan Phase 6).
    - The threshold operating point is a product decision (UD-05).

---

### R1-P7: Explainability, OOD & Anomaly Detection

1. **Phase:** R1-P7, Explainability, OOD & Anomaly Detection (Plan Phase 7, §11, §12).
2. **Objective:**
   - Local and global SHAP explanations with stage risk mass and caveat gating.
   - Global unsupervised anomaly detection (Isolation Forest) and SPC rules.
   - All kept distinct from prediction and operational risk.
3. **Priority:**
   - SHAP local/global + stage risk mass + caveat gating: **P0** (F7).
   - Isolation Forest global detector: **P1** (F15).
   - SPC: **P1**.
   - Autoencoder: **P2**.
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P6 (frozen feature set, `fusion-1.0.0`).
6. **Estimated duration:** 5–6 working days (W7).
7. **Ordered tasks:**
   1. Sample and version `shap_background.parquet` (200–500 training rows, stratified by label and machine). Rebuild the bundle as `fusion-1.0.1` if needed.
   2. `app/ml/explain.py`: TreeExplainer on the XGBoost model in **log-odds** space. Output:
      - signed top-k attributions with display names and current values;
      - direction labels;
      - `grouped_attributions` (temperature, pressure, time, material, context);
      - `stage_risk_mass` per Plan §11.2 (ownership from the schema; cross-stage features split 50/50);
      - `show_caveat_banner` when OOD/anomaly caveats exist.
   3. Precompute `global_explanation.json` (mean |SHAP| over a held-out sample) into the bundle.
   4. Offline report material (`explain_offline.py`): SHAP dependence plots; SHAP interaction values (sampled); permutation-importance cross-check; partial dependence / ICE; decision-tree surrogate ("the model in 12 rules").
   5. (P1) `ml_pipeline/anomaly_train.py`: Isolation Forest on the PASS-dominant training process vector (numeric features). Threshold = training-set percentile (e.g. top 2 %). Normalised score [0, 1]. Contributors by robust-z deviation. Package `models/anomaly/1.0.0/`. Add capability `anomaly_global`. Fill `PredictionResult.anomaly_global` plus the `ANOMALY_DETECTED` caveat.
   6. (P1) Add the Isolation Forest score to recommendation guard check 4 (RC-16).
   7. (P1) `spc.py`: X-bar / moving-range limits from a stable reference window; Western-Electric subset (1 point > 3σ; 8 consecutive on one side; 2 of 3 > 2σ). Pure functions `spc_check(series)`. Capability `spc`.
   8. (P1) Optional ensemble-spread uncertainty from the fold models (`uncertainty.method="ensemble_spread"`).
   9. (P2) PyTorch autoencoder on scaled numeric features, with per-feature reconstruction error, as an alternative `AnomalyMethod.autoencoder`.
   10. Report the One-Class SVM comparison as a baseline only (Plan §12.2).
8. **Files:** `backend/app/ml/explain.py`; `backend/app/intelligence/{anomaly.py, spc.py}`; `ml_pipeline/{explain_offline.py, anomaly_train.py}`; `models/anomaly/1.0.0/`; `backend/tests/{ml/test_explain.py, intelligence/test_anomaly.py, intelligence/test_spc.py}`; `docs/explainability_report.md`.
9. **Technical details:**
   - SHAP is computed on the transformed feature matrix and mapped back to canonical feature names via the schema. One-hot columns aggregate to their parent feature (e.g. `machine_id`).
   - `stage_risk_mass` uses |SHAP| shares, so shares are non-negative and sum to 1.
   - The **association, not causation** footnote key is always attached.
10. **Required tests:**
    - Additivity: `base_value + Σ shap ≈ model margin` (|err| < 1e-3).
    - Stage risk mass sums to 1 ± 1e-6 and is non-negative.
    - Deterministic given the background.
    - Top-5 SHAP features overlap ≥ 3 with permutation-importance top-5 on the test set [PROPOSED sanity bar; report if not met].
    - p95 explanation latency < 300 ms (Plan §24.4) and < 200 ms target (Plan Phase 7).
    - Isolation Forest: detection rate on injected synthetic anomalies (combinations outside the generator's normal region) and false-alarm rate on normal test data, reported vs the target percentile.
    - SPC rules fire on constructed sequences.
    - Anomaly outputs never change `p_fail` or `label`.
11. **Deliverables:** explain service; global explanation; explainability report (incl. limitations from Plan §11.4); (P1) anomaly bundle, SPC module, detection-rate report; (P2) autoencoder.
12. **Handoff requirements:** capabilities `explain`, `global_explanation` (P0); `anomaly_global`, `spc` (P1) set REAL; fixtures `explanation_<recipe>.json`; a UI copy note for limitations (Plan §11.4) and the grouped-attribution recommendation.
13. **Acceptance criteria:**
    - Local explanation within latency.
    - Attribution sanity-checked against permutation importance.
    - Anomaly detector flags injected anomalies at the target rate (Plan Phase 7).
    - Statistical prediction, operational risk and anomaly scores stay distinct fields.
14. **Completion gate:** the recommendation engine MUST NOT be finalised before the feasibility signals exist (Plan Phase 7 gate). For P0 that means **OOD percentile bounds**; Isolation Forest joins in P1.
15. **Compatibility requirements for Role 2:**
    - The UI shows the `DISCLAIMER_SHAP` footnote permanently and the caveat banner when `show_caveat_banner`.
    - Charts use `display_name`.
    - Global importance comes from `GET /models/active/global-explanation`.
16. **Risks & assumptions:**
    - Correlated features split credit (R8): headline claims use grouped attribution.
    - The background set changes values: it is versioned with the model.

---

### R1-P8: Constrained Recommendation Engine & Sensitivity

1. **Phase:** R1-P8, Constrained Recommendation Engine & Sensitivity (Plan Phase 8, §13.5, §14).
2. **Objective:** Answer "what should I change to make it pass?" with ranked, guarded, model-relative options. Provide local sensitivity analysis.
3. **Priority:**
   - **P0** (F11): Stage 1 rule-guided proposals; Stage 2 single-parameter coordinate search; the full six-check feasibility guard (check 4 via percentile bounds); ranking with change cost and cycle-time impact.
   - **P1**: pairwise moves on the top-3 sensitive parameters, differential-evolution refinement, Isolation Forest in check 4, sensitivity sweep endpoint (F14).
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P6 (`evaluate` pipeline, risk bands), R1-P7 (OOD bounds; Isolation Forest for P1), registry `recommendation` block + `remedies.yaml`.
6. **Estimated duration:** 7–8 working days (W8).
7. **Ordered tasks:**
   1. `proposals.py`: for each stage with risk ≥ MEDIUM and each `constraint_breaches` entry, consult `remedies.yaml` and generate 10–40 directed candidates (direction × step fractions), all inside windows by construction.
   2. `search.py`: coordinate-wise search over actionable, unlocked parameters. k = 7 levels each within `[x − max_step_change, x + max_step_change] ∩ [min, max]`, snapped to `step`. (P1) A second pass of pairwise moves on the top-3 most sensitive parameters (from `sensitivity.py` local gradients).
   3. `guard.py`, in this order, recording the per-check result (Plan §14.4):
      1. box;
      2. hard constraints (HC-*, including the derived clamp requirement and the thickness-based minimum cooling time);
      3. couplings (CPL-*);
      4. distribution: every feature within p01–p99 bounds (P0), plus Isolation Forest score (P1). Failure ⇒ reject, or flag `EXTRAPOLATED` and rank last if within a relaxed band [PROPOSED: p00.5–p99.5];
      5. step size;
      6. stability: 20 perturbations of ± `stability_noise_fraction_of_step` × step; label flips > 20 % ⇒ `UNSTABLE` and demoted. Run on finalists only.
   4. `ranking.py`: `score = w1·Δp_fail − w2·change_cost − w3·instability − w4·extrapolation − w5·cycle_time_increase_norm` (weights from the registry). `change_cost = Σ change_cost_j · |Δx_j| / (max_j − min_j)`. Enforce `max_changes`. Select `n_options` **diverse** options labelled Minimal change / Balanced / Aggressive.
   5. **Cycle-time rule (UD-09):** when `cycle_time_follows_stage_times` is true, candidate `cycle_time_s = base + Δfill_time + Δhold_time + Δcooling_time`. Report `cycle_time_delta_s` and `cycle_time_delta_pct`.
   6. (P1) `refine.py`: SciPy `differential_evolution`, seeded from the top-5 Stage-2 candidates. Same bounds. The guard is a rejection filter. Budget-capped at 2,000 evaluations or 5 s.
   7. `funnel.py`: orchestration, time/eval budgets, `rejected_counts` per check, `empty_reason` when nothing survives. Deterministic given `seed`. In-process memoisation of `evaluate` keyed by the canonical input hash.
   8. `sensitivity.py` (P1, F14): 40-point sweep across the admissible window; `local_gradient` (central finite difference at the current value); `range_swing`; `flip_point` (nearest label flip, linear interpolation between grid points).
   9. `ml_pipeline/recommend_eval.py`: on ~500 held-out failing recipes, report flip rate, Δp_fail distribution, constraint satisfaction (**must be 100 %**), extrapolation rate, stability rate (target > 90 % for the top option), minimality, cycle-time cost, and **generator ground-truth check** (does `true_p_defect` drop, not just the model estimate). Write `docs/recommendation_evaluation_report.md`. This is the headline honesty result (Plan §24.3).
8. **Files:** `backend/app/recommendation/{proposals.py, search.py, guard.py, ranking.py, refine.py, funnel.py, sensitivity.py}`; `ml_pipeline/recommend_eval.py`; `backend/tests/recommendation/test_{guard,search,funnel,ranking,sensitivity,properties}.py`; `docs/recommendation_evaluation_report.md`.
9. **Technical details:**
   - Search only over **actionable raw** parameters, never derived features (Plan §14.2 A).
   - Every candidate is scored through `evaluate()` (same transformations as normal predictions).
   - Non-actionable fields and `locked` fields are copied verbatim.
   - The engine never proposes outside the window, even if `p_fail` would be lower (Plan §14.7).
10. **Required tests:**
    - **Property tests (hypothesis)** over random failing inputs: every returned candidate passes box, hard constraints, couplings, step-size and lock checks. Non-actionable fields are unchanged. `len(changes) ≤ max_changes`. `constraint_status == "ALL_SATISFIED"`. `cycle_time_delta_s` is present.
    - Deterministic for a fixed seed.
    - Budget respected (≤ 5 s).
    - Empty result returns `empty_reason`, never an exception.
    - Unknown or locked parameter in a sensitivity request ⇒ typed error.
    - The sensitivity curve covers exactly the admissible window.
    - The flip point lies between grid points with different labels.
11. **Deliverables:** recommendation package; sensitivity; evaluation harness and report; updated fixtures `recommendation_<recipe>.json`, `sensitivity_cooling_time.json`.
12. **Handoff requirements:** capabilities `recommend` (P0) and `sensitivity` (P1) set REAL; documentation of request defaults and `rejected_counts` semantics for the UI "stability / extrapolation" display; the guard-tested statement in `integration_status.md` (**UI MUST NOT expose recommendations until this is recorded**, Plan Phase 8 gate).
13. **Acceptance criteria:**
    - 100 % of returned options satisfy hard constraints (asserted by test).
    - Reported success, stability and extrapolation-rejection rates (Plan Phase 8).
    - Ground-truth check reported with the generator-assumption caveat.
14. **Completion gate:** recommendations are not exposed in the UI until the guard tests pass (Plan Phase 8 gate).
15. **Compatibility requirements for Role 2:**
    - The UI must show the constraint stamp, stability, in-distribution/EXTRAPOLATED flags, cycle-time impact and `DISCLAIMER_RECOMMENDATION` on every option.
    - "Send to what-if" uses `changes[].to_value` as overrides.
16. **Risks & assumptions:**
    - The optimiser exploits the model (R9): mitigated by checks 4 and 6, the ground-truth check, and reporting how often the guard triggers.
    - Weights are assumptions.

---

### R1-P9: Packaging & Integration Handoff

1. **Phase:** R1-P9, Packaging & Integration Handoff (Plan §9.10, Phase 9 handoff).
2. **Objective:** Deliver a reproducible, verified, documented intelligence package that Role 2 can run in any environment, with consistent transformations across simulation, `/predict`, what-if and recommendation.
3. **Priority:** P0.
4. **Primary owner:** Role 1.
5. **Dependencies:** R1-P5…P8.
6. **Estimated duration:** 4–5 working days (W9). Earlier handoffs happened incrementally.
7. **Ordered tasks:**
   1. Finalise `RealQualityIntelligence.from_settings(settings)`. It loads the registry, fusion bundle, anomaly bundle and stage stats once; verifies hashes, `constraints_version` and `contracts_version`; and reports `capabilities()` (all P0 true).
   2. `ml_pipeline.cli train-all`: generate → validate → split → stage stats → train → calibrate → explain artifacts → anomaly → package → registry update, from a clean clone, with a recorded seed (D2, D3; replaces `make train`, RC-08).
   3. Finalise `models/registry.json` (active versions) and `MANIFEST.sha256`. Produce bundle archives `smqi-models-<date>.zip` + `.sha256` (Section 14.5).
   4. Refresh the tiny fixture bundle against the final schema.
   5. Update **all** contract fixtures with real outputs for the 5 canonical recipes + 20 generated rows.
   6. Write `docs/intelligence_interface.md`: every method, inputs and outputs, errors, performance, examples (JSON), capability matrix, configuration variables, troubleshooting (hash mismatch, version mismatch).
   7. **What-if consistency check:** for 200 random single and multi-parameter overrides, reusing upstream stage results + recomputing invalidated ones equals the full `evaluate` exactly (Role 1 side of the equivalence property).
   8. Update the model card, dataset card and `README` ML quickstart.
8. **Files:** `backend/app/intelligence/facade.py`; `ml_pipeline/cli.py`; `models/registry.json`; `MANIFEST.sha256`; `backend/tests/contract/fixtures/*`; `backend/tests/fixtures/model_bundle_tiny/`; `docs/intelligence_interface.md`; `README.md` (ML section).
9. **Technical details:**
   - Loading is fail-fast with typed errors.
   - No absolute or machine-specific paths: everything resolves relative to `SMQI_MODEL_DIR`.
   - Bundles are joblib-pickled. Document that pickles must be loaded with the same library versions (pinned by `uv.lock`) and are trusted local artifacts only.
10. **Required tests:**
    - Contract suite passes for `real` with the full bundle and with the tiny bundle.
    - Clean-clone reproduction gives byte-identical data and metrics equal to recorded values within tolerance (≤ 1e-6 for deterministic steps; documented tolerance for tree-training nondeterminism, if any).
    - Load failures (missing file, hash mismatch, schema mismatch, constraints MAJOR mismatch) give the correct error codes.
    - The equivalence property holds (200 cases).
11. **Deliverables:** final integration package (facade + bundles + archives + manifests + fixtures + interface doc).
12. **Handoff requirements:** bundle archive transfer per Section 14.5; `integration_status.md` capability matrix all REAL; joint session with Role 2 to run the contract suite on Role 2's machine (**the "separate environment" test**).
13. **Acceptance criteria:**
    - Role 2 runs the full real pipeline on their machine from the archive and README alone.
    - The contract suite is green for `real`.
14. **Completion gate:** M8–M11 cannot close without this phase's package (Section 13).
15. **Compatibility requirements for Role 2:** env variable names and the artifact layout are exactly per Section 9.6. No new required settings without a CCR.
16. **Risks & assumptions:**
    - Library version drift breaks pickles: lockfile discipline.
    - Large archives: keep them < 100 MB by limiting the SHAP background and tree count if needed.

---

### R1-P10: Intelligence Validation & Final Evaluation

1. **Phase:** R1-P10, Intelligence Validation & Final Evaluation (Plan Phases 13, 15; §24).
2. **Objective:** Complete testing, the evaluation evidence and the limitations documentation for the intelligence layer, and support system-level E2E testing.
3. **Priority:** P0.
4. **Primary owner:** Role 1 (supports Role 2's E2E).
5. **Dependencies:** R1-P9; Role 2 integration (M8–M11).
6. **Estimated duration:** W10–W12 (≈ 8–10 working days, shared with report and demo work).
7. **Ordered tasks:**
   1. Close test gaps: unit tests for every module; property tests (purity, equivalence, recommendation constraints); leakage tests; ML regression floors; artifact loading.
   2. Invalid-input tests across all interface methods (types, ranges, unknown or locked parameters, incomplete stage results).
   3. Explanation consistency over the 5 canonical recipes (stable top features across reloads; additivity).
   4. Finalise `docs/ml_evaluation_report.md`:
      - every metric from Plan §24.1;
      - baselines vs GBDT vs (P2) MLP with CIs;
      - ablation; calibration (reliability, Brier); threshold policy;
      - per-machine/grade; leave-one-machine-out; learning curve;
      - Tier-1 real-data section (or its documented absence);
      - stage-level evaluation (Plan §24.2); anomaly detection rates.
   5. Finalise `docs/recommendation_evaluation_report.md` (Plan §24.3 table, including the ground-truth check).
   6. Write the limitations chapter input: the four claims; Plan §25.3 fundamental limitations; data provenance table (dataset-derived / specification-derived / heuristic / learned / synthetic / unvalidated for every threshold and weight).
   7. Support the joint E2E journey (Section 15.4): triage and fix intelligence-side defects found by Role 2.
   8. Benchmarks for Plan §24.4 intelligence rows (prediction, SHAP, sweep, recommendation, instant run compute).
   9. Co-prepare the ML part of the demo script and slides.
8. **Files:** tests across `backend/tests/{domain,intelligence,ml,recommendation}/`, `ml_pipeline/tests/`; `docs/{ml_evaluation_report.md, recommendation_evaluation_report.md, model_card.md, dataset_card.md, limitations_intelligence.md}`.
9. **Technical details:** all reports are regenerated by `ml_pipeline.cli report` from recorded artifacts. **No hand-typed numbers.**
10. **Required tests:** the full R1 suite. `uv run pytest backend/tests/{domain,intelligence,ml,recommendation,contract} ml_pipeline/tests` is green on a clean clone.
11. **Deliverables:** D2–D10, D18, D19 final; limitations input for D20.
12. **Handoff requirements:** final reports and numbers delivered to Role 2 for the demo, Model Info screen and report; frozen bundle versions recorded.
13. **Acceptance criteria:**
    - All Role 1 tests pass.
    - Every reported number is reproducible from the CLI.
    - No unsupported performance or physical-validation claim appears anywhere.
14. **Completion gate:** contributes to M13 and M14. Role 1's Definition of Done (Section 20.2).
15. **Compatibility requirements for Role 2:** no interface changes after **M12** except bug fixes. Any fix that changes outputs bumps the bundle or module version.
16. **Risks & assumptions:**
    - Late discovery of leakage ⇒ must re-run P6+. Mitigated by early leakage tests.
    - Time pressure: P1/P2 items are dropped before P0 quality is compromised.

---

## 12. Role 2: complete phase-wise development roadmap

**Role:** Backend, Simulation, Database & Frontend Engineer. Every phase lists the 16 required fields.

Role 2 has the larger surface (backend + frontend), so phases overlap in time. The weekly checkpoint (Section 10.1) keeps the system runnable end-to-end from W4 onward.

| Phase | Title | Priority | Weeks |
|---|---|---|---|
| R2-P1 | Repository setup, contracts integration & mock intelligence | P0 | W1–W2 |
| R2-P2 | Database & persistence | P0 | W2–W3 |
| R2-P3 | Backend schemas, validation & services | P0 | W3 |
| R2-P4 | Simulation state machine, event flow & SSE | P0 (pause/resume/speed P1) | W4–W5 |
| R2-P5 | Intelligence integration, what-if & scenario backend | P0 (compare/sensitivity P1) | W5–W9 (incremental) |
| R2-P6 | Frontend process-control workspace | P0 | W4–W8 |
| R2-P7 | What-if, recommendation & explainability UI | P0 (A/B compare, sensitivity curves P1) | W8–W9 |
| R2-P8 | History & analytics | P0 history; P1 analytics/compare/SPC; P2 batch CSV | W9–W10 |
| R2-P9 | Deployment & system integration | P0 (Docker Compose/PG/CI P2) | W10–W11 |
| R2-P10 | System testing & demonstration | P0 | W11–W12 |

---

### R2-P1: Repository Setup, Contracts Integration & Mock Intelligence

1. **Phase:** R2-P1, Repository Setup, Contracts Integration & Mock Intelligence.
2. **Objective:** A runnable skeleton for backend and frontend with shared conventions, the registry served by the API, registry-driven validation, and a contract-compliant mock intelligence, so all Role 2 work can proceed in parallel with Role 1.
3. **Priority:** P0.
4. **Primary owner:** Role 2.
5. **Dependencies:**
   - None for tasks 1–6.
   - R1-P1 task 1 (contracts v0.1.0, day 2–3) for tasks 8–10.
   - R1-P1 task 9 (loader) for task 9. Until it lands, use a stub loader that reads the same YAML, and delete it on merge.
6. **Estimated duration:** 6–8 working days (W1–W2).
7. **Ordered tasks:**
   1. **Day 1:**
      - `git init`; first commit containing the Plan PDF and this roadmap.
      - `.gitignore`: `data/**` except manifests and README; `models/**` except `registry.json` and `MANIFEST.sha256`; `var/`, `mlruns/`, `.env`, `node_modules/`, `dist/`, `__pycache__/`, `.venv/`.
      - `.gitattributes` (LF normalisation; `*.parquet`/`*.joblib` binary).
      - `CODEOWNERS` from Section 4.
      - Branches `role-1-ai-ml` and `role-2-application` (Section 14).
   2. Root `pyproject.toml` (Section 4.1: packages `app` from `backend/app` and `ml_pipeline`; dependency groups) plus `.python-version` = 3.12. Run `uv lock` and commit `uv.lock`. Configure ruff, black, mypy (partial: `app/contracts`, `app/api`, `app/services`, `app/engine`), and pytest (`testpaths`, `pythonpath`, asyncio mode).
   3. Backend skeleton:
      - `main.py` app factory with startup: load settings → load registry → build intelligence → DB check;
      - `core/config.py` (pydantic-settings, `SMQI_` prefix, Section 9.6 variables);
      - `core/logging.py` (JSON via structlog; `request_id` middleware; `run_id` binding);
      - `api/errors.py` (error-code enum, exception handlers, envelope, Pydantic 422 → `VALIDATION_ERROR`/`PARAM_OUT_OF_RANGE` with `details`);
      - `schemas/envelope.py`; `GET /api/v1/health`.
   4. Frontend scaffold:
      - `npm create vite@latest` (React + TS), pinned to React 18 (UD-13);
      - Tailwind; shadcn/ui init; TanStack Query; Zustand; Recharts; Framer Motion; React Router;
      - ESLint + Prettier; Vitest + React Testing Library + MSW (UD-12);
      - `scripts/gen_api_types.(ps1|sh)` → `openapi-typescript http://localhost:8000/api/v1/openapi.json -o src/api/generated/schema.d.ts`;
      - `src/api/client.ts` (envelope unwrap, error-code mapping, `X-Request-ID`).
   5. `.env.example` with all Section 9.6 variables. Write `README.md` (setup for PowerShell and bash).
   6. Write `docs/architecture.md` (Section 3 condensed), `docs/api.md` (Section 9.3), `docs/events.md` (Section 9.5) and `docs/integration_status.md` (capability matrix, all MOCK).
   7. Review contracts v0.1.0 (R1-P1) within 24 h. Raise CCRs, not private edits.
   8. `intelligence_mock/mock.py`: `MockQualityIntelligence` implements the full Protocol per Section 9.2 (deterministic hash-derived values, `is_mock=true`, `MOCK_INFERENCE` caveat). BLOCKED is driven by the `registry.check_hard_constraints` call. `hybrid.py` routes per capability.
   9. Wire the registry: load at startup; `GET /api/v1/constraints` returns `to_public_dict()`; validation helpers that generate Pydantic field bounds dynamically from the registry and run `check_couplings`.
   10. `api/deps.py: get_intelligence()` per `SMQI_INTELLIGENCE_BACKEND`. Startup refuses `mock`/`hybrid` when `SMQI_ENV=demo`.
   11. `backend/tests/contract/test_interface_contract.py`: harness parametrized over the implementations that are available (mock now; real later), loading R1 fixtures and asserting schema validity and invariants (ranges, enum consistency, stage order, `upstream_out` keys, shares sum to 1, candidate constraint status).
   12. `backend/tests/test_import_boundaries.py` (B1, B2, B7; R1 adds B3).
8. **Files:** repo root files; `backend/app/{main.py, core/*, api/{errors.py, deps.py, routes_meta.py}, schemas/envelope.py, intelligence_mock/*}`; `backend/tests/{contract/test_interface_contract.py, test_import_boundaries.py, api/test_health.py, api/test_constraints.py}`; `frontend/*` scaffold; `scripts/gen_api_types.*`; `docs/{architecture.md, api.md, events.md, integration_status.md}`.
9. **Technical details:**
   - Pydantic models for the recipe are built at import time from the registry via `pydantic.create_model`, using `Field(ge=min, le=max)`. This keeps a **single source** of limits with no duplication.
   - Mock outputs are generated through the **contracts constructors**, so a schema drift fails the mock immediately.
10. **Required tests:**
    - The app starts with `mock`. `/health` reports `intelligence.is_mock=true`.
    - `/constraints` returns `registry_version` and `content_hash`.
    - Envelope shape on success and error.
    - A 422 carries per-field `details`.
    - Demo profile + mock ⇒ startup error.
    - Mock passes the contract suite and is deterministic.
    - Import-boundary test passes.
    - The frontend builds, lints, type-checks, and the Vitest smoke test passes.
11. **Deliverables:** runnable skeletons; locked dependencies; mock + hybrid intelligence; registry endpoint; contract harness; docs skeleton; integration status file.
12. **Handoff requirements:** an OpenAPI snapshot `docs/openapi.json` for Role 1 review; mock behaviour notes; confirmation that contract fixtures from R1 run in the harness.
13. **Acceptance criteria:** a fresh clone runs `uv sync --frozen`, `uv run pytest` and `npm ci && npm run build` successfully on both members' machines. Contracts v1.0.0 approved (M1).
14. **Completion gate:** M1 (contracts approved) and M3 (mock inference operational) are recorded in `integration_status.md`.
15. **Compatibility requirements for Role 1:**
    - The harness MUST accept the real facade without modification.
    - The mock MUST NOT import from `app.intelligence`, `app.ml` or `app.recommendation` (it may import `app.contracts` and `app.domain`).
16. **Risks & assumptions:**
    - Library resolution issues on Python 3.12/Windows: resolve in this phase, before others depend on them.
    - shadcn/ui CLI changes: pin the generated components in the repo.

---

### R2-P2: Database & Persistence

1. **Phase:** R2-P2, Database & Persistence (Plan §17).
2. **Objective:** Implement the Section 9.4 schema with migrations, repositories, immutability rules, lineage and seed data.
3. **Priority:** P0 (PostgreSQL compatibility P2).
4. **Primary owner:** Role 2.
5. **Dependencies:** R2-P1; R1-P1 (`fleet.yaml` for the seed; contracts for JSON column shapes).
6. **Estimated duration:** 5 working days (W2–W3).
7. **Ordered tasks:**
   1. `db/base.py` and `db/session.py`: SQLAlchemy 2.0 typed declarative models; engine from `SMQI_DATABASE_URL`; SQLite pragmas (foreign keys ON, WAL); a session dependency for FastAPI.
   2. `db/models.py`: all tables and **[P]** additions from Section 9.4, with FKs, unique constraints and indexes. `run_parameters` gets one typed column per `ProcessRecipe` field, generated from the registry parameter list at **development time** (a script emits the model code; no runtime magic) and checked by a test.
   3. Alembic: `alembic.ini` + `env.py` (`render_as_batch=True`). Generate `0001_initial`.
   4. `db/repositories.py`:
      - `RunRepository` (create, get, list with filters, update status, set label, lineage);
      - `StageResultRepository`; `PredictionRepository`; `RecommendationRepository`; `EventRepository` (append with next `seq`); `ModelVersionRepository` (upsert from registry); reference repositories.
   5. Immutability guards: repository methods refuse to mutate `run_parameters`, `predictions`, `recommendations` and events. They also refuse to modify stage results of terminal runs (raise `RUN_IMMUTABLE`).
   6. `db/seed.py`: idempotent import of the `fleet.yaml` demo subset; upsert `model_versions` from `models/registry.json` if present, plus a `mock` row.
   7. Context snapshot: at run creation, store machine/product/lot values in `process_runs.context_snapshot` so later reference edits do not alter history.
8. **Files:** `backend/app/db/*`, `backend/alembic.ini`, `backend/alembic/{env.py, versions/0001_initial.py}`, `scripts/gen_run_parameters_model.py`, `backend/tests/db/test_{models,migrations,repositories,immutability,seed,lineage}.py`, `docs/database.md`.
9. **Technical details:**
   - UUIDs are stored as `String(36)` for portability.
   - JSON columns use `sqlalchemy.JSON`.
   - Timestamps are UTC with `timezone=True`.
   - `seq` is allocated per run inside the same transaction as the event insert.
10. **Required tests:**
    - `alembic upgrade head` on an empty SQLite DB; `downgrade -1` / `upgrade` round-trip.
    - (P2) the same on PostgreSQL via Docker.
    - FK integrity.
    - `run_parameters` columns equal the registry setpoint list.
    - JSON round-trip of contract objects.
    - Immutability violations raise.
    - Lineage query returns the parent/children tree.
    - Seed is idempotent (running twice gives the same row counts).
    - Event `seq` is strictly increasing under concurrent appends (asyncio test).
11. **Deliverables:** models, migrations, repositories, seed, DB docs.
12. **Handoff requirements:** `docs/database.md` (tables, immutability, lineage); a note to Role 1 that intelligence never writes to the DB; any requested persisted intelligence field must arrive via a CCR.
13. **Acceptance criteria:** migrations run clean from empty (D14); integrity and retrieval tests pass; the seed provides machines, product `PP-JBOX-42` and lot `A-771`.
14. **Completion gate:** M4 needs this phase plus the R2-P4 skeleton.
15. **Compatibility requirements for Role 1:** JSON columns store contract objects via `.model_dump(mode="json")` unchanged. Role 2 does not reshape intelligence payloads.
16. **Risks & assumptions:**
    - SQLite ALTER limitations: batch mode.
    - Schema churn: never edit merged migrations.

---

### R2-P3: Backend Schemas, Validation & Services

1. **Phase:** R2-P3, Backend Schemas, Validation & Services (Plan §16).
2. **Objective:** Implement the API schemas, the three validation tiers, thin routers over service classes, structured errors, logging and limits, and the stateless prediction and reference endpoints.
3. **Priority:** P0 (`/predict/batch` P2).
4. **Primary owner:** Role 2.
5. **Dependencies:** R2-P1, R2-P2, R1-P1 (loader `check_box`/`check_couplings`).
6. **Estimated duration:** 5 working days (W3).
7. **Ordered tasks:**
   1. `schemas/`: request/response models for every Section 9.3 endpoint, **embedding contract types** (no re-declaration of contract fields).
   2. Validation:
      - Tier 1: registry-derived bounds → `PARAM_OUT_OF_RANGE` with `limit`, `value`, `constraint_version`, `hint`.
      - Tier 2: `check_couplings` → `COUPLING_VIOLATION` with `rule_id`.
      - Tier 3: runtime only (R2-P4).
      - Unknown fields → `UNKNOWN_PARAMETER`.
   3. Services (business logic out of routers):
      - `reference_service` (machines/products/materials; create lot with registry validation);
      - `inference_service` (builds `ProcessInput` from codes + snapshot, calls `intelligence.evaluate`, persists `predictions` with `inference_backend`, maps `IntelligenceError` → HTTP);
      - `explain_service`;
      - skeletons of `simulation_service`, `whatif_service`, `recommendation_service`, `analytics_service`.
   4. Routers: `routes_reference.py`, `routes_prediction.py` (`POST /predict`, `GET /predict/{id}/explain`), `routes_meta.py` (`/health`, `/constraints`, `/models`, `/models/active`).
   5. Middleware:
      - CORS from settings;
      - optional `X-API-Key`;
      - in-process token-bucket rate limiter for `/recommend` and `/whatif/sensitivity` → 429 `RATE_LIMITED`;
      - request timing into `meta.latency_ms`.
   6. Generate the OpenAPI snapshot. Run `npm run gen:api`. Commit the generated types. Add a CI/local check that fails if the generated types are stale.
8. **Files:** `backend/app/schemas/*`, `backend/app/services/{reference_service.py, inference_service.py, explain_service.py, *_service.py skeletons}`, `backend/app/api/routes_{reference,prediction,meta}.py`, `backend/tests/{api,services,schemas}/*`, `frontend/src/api/generated/schema.d.ts`, `docs/openapi.json`.
9. **Technical details:**
   - Synchronous intelligence calls run in the threadpool (`run_in_threadpool`) so the event loop (SSE) is never blocked.
   - Every `IntelligenceError.code` maps through one table (Section 9.1).
10. **Required tests:**
    - Each endpoint: 200 path, 404, 422 (exact min/max accepted; min − step and max + step rejected with the correct code and `details`), coupling 422 with `rule_id`.
    - Envelope on every error, including unhandled ones (500 `INTERNAL_ERROR` with `request_id`, no stack trace leaked).
    - Rate limit returns 429.
    - CORS headers.
    - API key enforced only when set.
    - `/predict` persists a prediction row with `inference_backend="mock"`.
    - Generated TS types compile (`npm run typecheck`).
11. **Deliverables:** validated REST surface for reference, predict, explain and meta; OpenAPI + TS types; error-code table in `docs/api.md`.
12. **Handoff requirements:** `docs/openapi.json` shared; Role 1 confirms error-code mapping for intelligence errors.
13. **Acceptance criteria:** every Section 9.3 endpoint in this phase's scope is implemented and tested; validation boundaries are exact; no business logic in routers (review checklist).
14. **Completion gate:** frontend integration of these endpoints begins only after the schema is stable (Plan Phase 10 gate). MSW mocks are used before that.
15. **Compatibility requirements for Role 1:** Role 2 passes `ProcessInput` built strictly from the canonical names, so the real facade must accept it unchanged.
16. **Risks & assumptions:** dynamic Pydantic models complicate OpenAPI. Mitigation: generate a static recipe schema at startup with `create_model`, so OpenAPI shows explicit fields.

---

### R2-P4: Simulation State Machine, Event Flow & SSE

1. **Phase:** R2-P4, Simulation State Machine, Event Flow & SSE (Plan §7.3–7.6, §18).
2. **Objective:** A server-side FSM that runs the six-stage workflow through the intelligence interface, persists every stage and event, and streams state over SSE with replay. Supports auto and stepwise modes, blocking and override, pause/resume, reset/abort, and restart recovery.
3. **Priority:**
   - **P0:** FSM, stepwise + auto at fixed speed, BLOCKED/override, abort/reset, SSE, persistence, recovery.
   - **P1:** pause/resume/speed control (F17).
4. **Primary owner:** Role 2.
5. **Dependencies:** R2-P2, R2-P3; mock intelligence (R2-P1); R1 `stage_inputs()` from the loader.
6. **Estimated duration:** 7 working days (W4–W5).
7. **Ordered tasks:**
   1. `engine/state_machine.py`: a pure transition table (Section 9.5.1) with guards. `apply(state, command) -> (new_state, events_to_emit)` or raises `INVALID_STATE_TRANSITION`.
   2. `engine/events.py`: event types (`EVENTS_VERSION`), envelope builder, `EventBus` (persist-then-publish; per-run `asyncio.Queue` subscribers; replay from the DB by `seq`).
   3. `engine/cache.py`: LRU stage cache (Section 9.5.2 key), size from settings, hit/miss counters exposed in `/health`.
   4. `engine/stage_runner.py`: build the stage input slice with `registry.stage_inputs(stage)`, look up the cache, call `intelligence.run_stage` (threadpool), measure `compute_ms`, and return `StageResult` + `cache_hit`.
   5. `services/simulation_service.py`:
      - `create_run` (validate, snapshot context, persist run + parameters, status INITIALIZED);
      - `start` (auto: spawn a task in `engine/run_registry.py`; stepwise: set first stage PENDING);
      - `advance`; `pause`; `resume`; `reset`; `abort`; `override`;
      - quality stage: `intelligence.predict(..., include_explanation=True)` → persist prediction → `prediction.ready` → `run.completed`.
   6. Auto-mode loop per Plan §7.6 steps 1–10 with the presentation delay `SMQI_STAGE_PRESENTATION_MS / speed` (`instant` = 0). Pause uses an `asyncio.Event`. On BLOCK with `halt_on_critical`, the task stops and waits for override or abort.
   7. Emit `anomaly.flagged` when `StageResult.anomaly.flag` is set, and `constraint.breached` per breach.
   8. `api/sse.py` + `GET /simulation/runs/{id}/events`: `StreamingResponse`; `Last-Event-ID` replay; 15 s keepalive; close after a terminal event; client-disconnect cleanup.
   9. `api/routes_simulation.py`: all simulation endpoints from Section 9.3.2.
   10. Startup recovery: mark non-terminal running runs `ABORTED` (`SERVER_RESTART`).
   11. Polling fallback: `GET /simulation/runs/{id}` returns the full `SimulationState` including `last_seq` and the timeline.
8. **Files:** `backend/app/engine/{state_machine.py, events.py, cache.py, stage_runner.py, run_registry.py}`, `backend/app/services/simulation_service.py`, `backend/app/api/{routes_simulation.py, sse.py}`, `backend/tests/engine/test_{state_machine,cache,stage_runner,events}.py`, `backend/tests/api/test_simulation_{stepwise,auto,blocked,sse,recovery,concurrency}.py`, `docs/events.md` (final).
9. **Technical details:**
   - The FSM never computes intelligence. It only orders calls and records results.
   - Presentation timing is separate from `compute_ms`. Both are stored.
   - **Upstream context:** the stage runner passes `StageResult.upstream_out` of stage k as `upstream` for stage k+1, unchanged.
10. **Required tests:**
    - Exhaustive transition table: every (state, command) pair is either valid with the expected events or rejected with 409.
    - Stepwise run to FINAL_RESULT with 5 stage rows + 1 prediction.
    - Auto run at `instant` completes within the budget (< 300 ms compute, Plan §24.4).
    - Event order `run.started, (stage.started, [anomaly/constraint], stage.completed)×5, prediction.ready, run.completed`, with `seq` contiguous from 1.
    - SSE scripted client (httpx streaming) receives every event. Reconnect with `Last-Event-ID` replays only missing events.
    - BLOCK path with the `recipe_melt_ceiling_breach.json` fixture ⇒ `stage.blocked`; override ⇒ continues and the prediction carries `constraint_override_applied=true`.
    - Pause/resume (P1) keeps order.
    - Reset clears stage results of a non-terminal run. Reset of a terminal run ⇒ 409 `RUN_IMMUTABLE`.
    - Abort persists the partial run.
    - Simulated restart ⇒ ABORTED with stage rows intact.
    - 10 concurrent auto runs complete without interleaving errors (Plan §24.4).
11. **Deliverables:** working FSM + SSE with mock intelligence; event docs.
12. **Handoff requirements:**
    - Event catalogue v1 frozen in `docs/events.md`.
    - The frontend (R2-P6) builds against it.
    - Role 1 is notified that stage modules are called exactly as `run_stage(stage, ProcessInput, UpstreamContext)`.
13. **Acceptance criteria:**
    - A full run is watchable via a scripted SSE client.
    - Every transition is tested.
    - Blocked runs cannot reach FINAL_RESULT without an override record.
14. **Completion gate:** M4 (DB + simulation skeleton operational).
15. **Compatibility requirements for Role 1:**
    - The orchestrator relies only on `StageResult.blocked`, `upstream_out`, `anomaly.flag` and `constraint_breaches`.
    - Any new block semantics require a CCR.
16. **Risks & assumptions:**
    - asyncio tasks leak on client disconnect: the run registry owns tasks, not connections.
    - SSE buffering by proxies: send headers `Cache-Control: no-cache`, `X-Accel-Buffering: no`.

---

### R2-P5: Intelligence Integration, What-If & Scenario Backend

1. **Phase:** R2-P5, Intelligence Integration, What-If & Scenario Backend (Plan §13, Phase 9; Phase 12).
2. **Objective:**
   - Replace mocks with real intelligence capability by capability.
   - Persist explanations, anomalies and recommendations with model traceability.
   - Implement what-if branching with dependency-graph partial re-simulation, diffs, lineage and scenario saving, without overwriting originals.
3. **Priority:**
   - **P0:** real integration, `/whatif` (single and multi-parameter), `/recommend`, scenario label.
   - **P1:** `/whatif/compare`, `/whatif/sensitivity`, lineage endpoint.
4. **Primary owner:** Role 2.
5. **Dependencies:**
   - R2-P4.
   - Role 1 deliveries per capability: `fusion-0.1.0` (R1-P4), `run_stage` (R1-P5), `fusion-1.0.0` (R1-P6), `explain` (R1-P7), `recommend` (R1-P8), `sensitivity` (R1-P8 P1), final package (R1-P9).
6. **Estimated duration:** incremental across W5–W9. ≈ 8–10 working days total.
7. **Ordered tasks:**
   1. Startup registration: read `models/registry.json` + bundle metadata through `intelligence.version_info()` (never by loading joblib), and upsert `model_versions`. Expose `/models`, `/models/active`, `/models/active/global-explanation`.
   2. Integrate `fusion-0.1.0` in `hybrid` mode (`/predict` real; stages mock). Use the tiny bundle in CI.
   3. Integrate real `run_stage` (M5 with Material first, M6 with all five). Verify the cache key includes the real `module_version`s.
   4. Integrate `fusion-1.0.0` (M7/M8): full real simulation; persist `p_fail_raw`, `ood`, `caveats`, `feature_schema_hash`, `constraints_version`, `model_version_id`.
   5. Integrate explanations (M9): persist `explanation` + `stage_risk_mass` with the prediction; `GET /predict/{id}/explain`; global explanation endpoint.
   6. `whatif_service` (M11):
      - validate overrides (canonical names; registry box + couplings);
      - `changed = keys(overrides)`; `invalid = registry.invalidated_stages(changed)`;
      - reuse parent stage results upstream of the earliest invalidated stage (copy with `reused_from_stage_result_id`);
      - recompute invalidated stages through the stage runner (cache);
      - always re-run `predict`;
      - apply the UD-09 cycle-time rule when changed times are present and `cycle_time_s` is not explicitly overridden;
      - persist the child run (`is_whatif=true`, `parent_run_id`, `scenario_label=label`) when `persist=true`; return `run_id=null` when false;
      - assemble the `diff` per Section 7.16.
   7. `POST /whatif/compare` (P1): structured diff between any two runs.
   8. `POST /whatif/sensitivity` (P1): load the base run → `intelligence.sensitivity`.
   9. `recommendation_service` (M10, only after R1 records "guard tested"):
      - `POST /recommend`: base run must be FINAL_RESULT;
      - build the `RecommendationRequest` (`locked` = user list; registry non-actionables are enforced by R1);
      - call the interface in the threadpool with the time budget;
      - persist one row per candidate with `request_id`;
      - return the response. Rate limited.
   10. `PATCH /simulation/runs/{id}/label` (save scenario). `GET /simulation/runs/{id}/lineage` (P1).
   11. Switch dev default from `mock` → `hybrid` → `real`. Update the `integration_status.md` capability matrix at every step.
   12. Missing or invalid artifacts: `/health` → `degraded`; affected endpoints return 503 `MODEL_NOT_LOADED` / `MODEL_ARTIFACT_INVALID` with a hint. Simulation start is refused with a clear error. **Never silently fall back to mock in `real` mode.**
8. **Files:** `backend/app/services/{whatif_service.py, recommendation_service.py, inference_service.py, explain_service.py}`, `backend/app/api/routes_{whatif,recommend,prediction,meta,simulation}.py`, `backend/tests/{services,api}/test_whatif_*.py`, `test_recommend_*.py`, `test_real_integration_*.py`, `backend/tests/e2e/test_backend_journey.py`.
9. **Technical details:**
   - **What-if never mutates parent rows.**
   - The partial re-sim uses the same stage runner and cache as normal runs, so partial and full results are byte-identical by construction.
   - Fusion is always recomputed (Plan §13.2).
10. **Required tests:**
    - **Property test (hypothesis):** for random valid override sets on fixture parents, the partial re-sim result (stage results + prediction) equals a fresh full run with the merged parameters (JSON-canonical equality) (D11).
    - Parent rows unchanged after any what-if (row hashes before and after).
    - `persist=false` writes nothing.
    - Child has `is_whatif=true` and the correct `parent_run_id`.
    - The diff matches the hand-computed expected diff for `cooling_time_s` (only COOLING recomputed) and `melt_temp_c` (PLASTICIZING onward recomputed).
    - Recommendation rows persisted with `request_id` and `model_version_id`. A 409 when the base is not final.
    - Real integration tests against the tiny bundle: simulation, predict, explain, what-if, recommend.
    - Missing bundle ⇒ 503 and `/health` degraded.
    - Single what-if latency < 100 ms (Plan §24.4) with real intelligence.
11. **Deliverables:** fully real backend; what-if service + endpoints; recommendation endpoint; scenario save; lineage.
12. **Handoff requirements:** `integration_status.md` with all P0 capabilities REAL; a joint integration session per milestone M5–M11 (Section 13).
13. **Acceptance criteria:**
    - The full journey works via API with real intelligence (scripted).
    - What-if runs never overwrite originals.
    - Mock is disabled in demo config.
14. **Completion gate:** M8, M9, M10, M11.
15. **Compatibility requirements for Role 1:** Role 2 consumes only the interface. Any need for new data (e.g. extra diff fields) is solved from existing outputs or through a CCR, never by importing Role 1 internals.
16. **Risks & assumptions:**
    - Recommendation latency near 5 s blocks a worker: run it in the threadpool and show progress in the UI.
    - Cache memory: bounded LRU.

---

### R2-P6: Frontend Process-Control Workspace

1. **Phase:** R2-P6, Frontend Process-Control Workspace (Plan §15; Phase 11).
2. **Objective:** The centrepiece screen: a process control workstation (not an ML dashboard). Context selection, registry-driven validated parameter entry, an animated six-stage SVG pipeline, active-stage panel, live event timeline via SSE, run controls, BLOCKED override, and a result card that shows real backend outputs with correct risk semantics.
3. **Priority:** P0 (speed control and step button P1 where they depend on F17).
4. **Primary owner:** Role 2.
5. **Dependencies:** R2-P3 (stable schema; generated types), R2-P4 (events v1). Before those are stable, use MSW handlers built from contract fixtures.
6. **Estimated duration:** W4–W8 (≈ 10–12 working days, interleaved with R2-P5).
7. **Ordered tasks:**
   1. Design tokens in Tailwind config: dark industrial surface, high-contrast state colours (Plan §15.4), monospace numerics. The state language is **colour + glyph + text** for PENDING `[ ]`, ACTIVE `[*]`, COMPLETED risk colours `[X]`, ANOMALY `!`, BLOCKED `[/]`.
   2. App shell: header (machine | product | lot | run id), router for 7 screens (Process Control default; others stubbed), persistent `DISCLAIMER_SIMULATION` footer, **MOCK banner** whenever `/health` or any payload reports `is_mock`.
   3. Context selectors: machines, products, materials from the API; "Create lot" dialog (validated by the API).
   4. Parameter panel:
      - one control per registry setpoint (slider + numeric input) with min, max, step, unit and display name **from `/constraints`**;
      - grouped by stage;
      - client-side range validation mirroring the registry;
      - server 422 `details` mapped to fields; coupling errors shown with `rule_id` text;
      - "Load nominal recipe" from registry nominals.
   5. Zustand stores: `draftRecipe`, `context`, `runState` (reducer driven by SSE events), `uiPrefs`.
   6. Run controls: RUN (create + open SSE + start), STEP (stepwise advance), PAUSE/RESUME and speed selector labelled **"presentation speed"** (P1), RESET, ABORT, mode toggle.
   7. `useRunEvents(runId)` hook: EventSource; `seq` tracking; gap detection → `GET /simulation/runs/{id}` re-sync; reconnect; after two failures switch to 300 ms polling; cleanup on unmount.
   8. SVG stage pipeline: 6 nodes + 5 connectors. Node shows health, risk text, state glyph, anomaly badge, BLOCKED outline. Framer Motion pulse for ACTIVE. Connector fill animation. 60 fps target.
   9. Active-stage panel: inputs in scope (from `stage.started`), upstream values, derived indicators with provenance tooltips (e.g. "heuristic"), notes, breaches.
   10. Event timeline: ordered rows with timestamps, type, stage and key values; anomaly rows purple.
   11. BLOCKED override dialog: shows reason + breaches; requires a typed acknowledgement; calls `/override`.
   12. Result card (after `prediction.ready`):
       - **three separate blocks**: "Model-predicted failure probability" (`p_fail` calibrated + label + threshold + model version), "Operational risk" (`risk_level` + drivers), "Anomaly status";
       - risk origin bar from `stage_risk_mass`;
       - caveats list / OOD banner;
       - **NOT RELEASABLE** presentation when `constraint_override_applied`;
       - buttons WHY THIS PREDICTION? / WHAT SHOULD I CHANGE? / SAVE SCENARIO (the latter two enabled in R2-P7).
   13. Loading, empty, error (error code + hint + request_id), blocked and completed states for every panel.
8. **Files:** `frontend/src/{app/, stores/, api/sse.ts, features/process-control/*, components/pipeline/*, components/result/*, components/params/*, components/common/{MockBanner,Disclaimer,ErrorState}.tsx}`, `frontend/src/test/*`.
9. **Technical details:**
   - The SSE reducer is a pure function `(state, event) -> state`, unit-tested with fixture event streams.
   - **Nothing displayed as a prediction comes from anywhere but API payloads.** MSW is test-only and excluded from production builds (assert in the build test).
10. **Required tests (Vitest + RTL + MSW):**
    - Pipeline renders every state with glyph + text (not colour only).
    - Parameter panel bounds equal the `/constraints` fixture (change the fixture ⇒ bounds change).
    - The 422 mapping shows field errors.
    - SSE reducer: in-order, duplicate, gap ⇒ resync call, terminal events.
    - Polling fallback activates.
    - Override dialog requires an acknowledgement.
    - Result card shows the three distinct blocks, and NOT RELEASABLE for the overridden fixture.
    - Mock banner appears for `is_mock` payloads.
    - `npm run typecheck` and `npm run lint` are clean.
11. **Deliverables:** the functional Process Control screen against the real backend (mock or real intelligence).
12. **Handoff requirements:** screenshots (stepwise deterministic) for the report; a list of UI copy needing Role 1 confirmation (indicator explanations, provenance labels).
13. **Acceptance criteria:**
    - A full run is watchable end-to-end without page refresh.
    - Every backend state is visually represented.
    - The UI degrades gracefully to polling (Plan Phase 11).
    - No parameter limit literals in the frontend source (B6 grep test).
14. **Completion gate:** part of M8 (end-to-end prediction visible in the UI). No animation polish before all screens are functional (Plan Phase 11 gate).
15. **Compatibility requirements for Role 1:** the UI uses `display_name`/units from the registry and schema. Indicator keys are displayed verbatim with provenance; the UI never re-computes them.
16. **Risks & assumptions:**
    - Animation jank: CSS transforms only.
    - Projector colour distortion: glyph + text redundancy.

---

### R2-P7: What-If, Recommendation & Explainability UI

1. **Phase:** R2-P7, What-If, Recommendation & Explainability UI (Plan §11.3, §13.4–13.6, §14.6, §15.3).
2. **Objective:**
   - Interactive what-if workbench with diffs.
   - Recommendation cards with full guard information and disclaimers.
   - SHAP explainability panel.
   - All using real backend outputs, with prediction, risk and anomaly visibly distinct.
3. **Priority:**
   - **P0:** what-if single/multi edit + diff; recommendations UI; SHAP local panel + stage risk donut.
   - **P1:** live slider (debounced), A/B scenario compare, sensitivity strip with flip points, dependence plot, global importance.
   - **P2:** 2-D response surface.
4. **Primary owner:** Role 2.
5. **Dependencies:** R2-P5 endpoints; R1-P7 (explain), R1-P8 (recommend; **guard-tested statement**).
6. **Estimated duration:** 7–8 working days (W8–W9).
7. **Ordered tasks:**
   1. What-If Workbench:
      - draft recipe forked from a base run (Zustand; nothing persisted until Evaluate or Save, Plan §13.7);
      - edit one or many parameters; Evaluate → `POST /whatif`;
      - (P1) live slider with 150 ms debounce and `persist=false`;
      - Reset restores parent parameters exactly.
   2. Diff view per Plan §13.6: parameter rows (A, B, Δ); stage rows (health/risk A → B, improved/worsened/unchanged); prediction flip; p_fail Δ; operational risk band change; constraint-compliance change; **cycle-time impact**. Pipeline nodes animate risk colour changes.
   3. (P1) Scenario A/B compare page from two saved runs (`/whatif/compare`).
   4. (P1) Sensitivity strip: per-parameter p_fail curve across the admissible window, current point marker, flip-point marker; ranked "which knob matters most here" from `local_gradient`/`range_swing`, with a note that sensitivity ≠ SHAP (Plan §13.5).
   5. Recommendations screen:
      - request form: locked parameters multi-select from actionable params; `max_changes`;
      - progress indicator after 1 s;
      - option cards showing label, changes from→to with units, predicted p_fail from→to, rationale, **constraint stamp** (guard checks list), stability (flips/20), in-distribution / **EXTRAPOLATED** badge with "hypothesis for trial" text, cycle-time impact;
      - "Send to What-If" sets overrides from `changes`;
      - permanent `DISCLAIMER_RECOMMENDATION`;
      - empty result shows `empty_reason`.
   6. Explainability panel:
      - signed horizontal SHAP bar chart (Recharts) toward FAIL / toward PASS with values and display names;
      - grouped attribution toggle;
      - stage risk donut;
      - caveat banner when `show_caveat_banner`;
      - permanent `DISCLAIMER_SHAP` footnote;
      - a note that SHAP explains the model margin (log-odds).
   7. (P1) Model Info screen: active model version, training date, dataset hash, generator version, metrics, calibration/reliability data, threshold policy, global importance, the `STATEMENT_SYNTHETIC_DATA` text.
   8. UI separation audit: every screen that shows numbers labels them as **predicted probability**, **operational risk** or **anomaly**. A test asserts the labels.
8. **Files:** `frontend/src/features/{whatif, recommendations, explainability, model-info}/*`, `frontend/src/components/charts/*`, tests.
9. **Technical details:** what-if live mode cancels in-flight requests (AbortController) to keep the latest result authoritative.
10. **Required tests:**
    - The diff renders the fixture diff exactly.
    - Debounce triggers one request per pause.
    - Reset restores the parent.
    - Option cards render every guard field. The disclaimer is always present.
    - EXTRAPOLATED badge text.
    - Send-to-what-if builds the correct overrides.
    - SHAP chart sign/direction mapping.
    - Caveat banner gating.
    - No numeric prediction literal in components (lint rule or review checklist + test that components render only fixture-supplied numbers).
11. **Deliverables:** What-If Workbench, Recommendations, Explainability and (P1) Model Info screens.
12. **Handoff requirements:** Role 1 reviews explanation and recommendation copy for claim discipline (Section 1.7).
13. **Acceptance criteria:**
    - The user can go result → why → what should I change → send to what-if → evaluate → save scenario, with real outputs.
    - The three risk concepts are visually distinct.
    - The disclaimers are permanent.
14. **Completion gate:** M9, M10, M11 (UI side).
15. **Compatibility requirements for Role 1:** the UI depends only on `LocalExplanation`, `RecommendationResponse`, `SensitivityResult` and the diff contract.
16. **Risks & assumptions:** recommendation latency up to 5 s, handled with progress UI and disabled double-submit.

---

### R2-P8: History & Analytics

1. **Phase:** R2-P8, History & Analytics (Plan F12–F14, F16, §15.3).
2. **Objective:** Browse, filter and compare persisted runs and scenarios with lineage, plus analytics supported only by stored data, with model-version traceability.
3. **Priority:**
   - **P0:** run history list + run detail + scenario labels (MVP "run history persisted").
   - **P1:** lineage tree, analytics dashboard, SPC drift view, Model Info metrics.
   - **P2:** batch CSV upload + bulk scoring (F19).
4. **Primary owner:** Role 2.
5. **Dependencies:** R2-P5 (persisted runs with predictions); R1-P7 `spc_check` (P1).
6. **Estimated duration:** 5–6 working days (W9–W10).
7. **Ordered tasks:**
   1. History screen:
      - filterable, paginated table (machine, product, lot, label, risk, date range, what-if toggle, backend toggle);
      - run detail view reusing pipeline + result components in read-only mode;
      - scenario label edit;
      - model version column.
   2. (P1) Lineage tree for a parent run and its what-if children (`/lineage`).
   3. (P1) `analytics_service` SQL aggregations:
      - failure rate by machine, by lot/resin grade, by parameter bucket (registry-defined buckets);
      - stage risk frequency;
      - runs over time.
      - **Default exclusions:** `is_whatif=true`, `inference_backend='mock'`, non-FINAL_RESULT runs. All are togglable and stated on screen (Plan §13.7).
   4. (P1) Analytics screen: Recharts bars, lines and heat table; empty states when data is insufficient. **No synthetic filler data.**
   5. (P1) SPC drift view: series from the DB → `/analytics/spc` → `intelligence.spc_check` → alerts; chart with control limits.
   6. (P1) Model metrics panel from `/models` (`metrics.json` summary).
   7. (P2) `/predict/batch`: CSV upload (≤ 5,000 rows), registry validation per row, bulk scoring, downloadable results. Results are not stored as runs.
8. **Files:** `backend/app/services/analytics_service.py`, `backend/app/api/routes_analytics.py`, `frontend/src/features/{history, analytics}/*`, tests.
9. **Technical details:** aggregations run in SQL via SQLAlchemy Core with indexed filters. Bucket edges come from the registry (no hardcoded limits).
10. **Required tests:**
    - Aggregations on a seeded DB match hand-computed expectations.
    - Exclusion defaults verified (what-if and mock rows excluded unless toggled).
    - Pagination and filter correctness.
    - Lineage tree shape.
    - SPC endpoint returns alerts for a constructed series.
11. **Deliverables:** History (P0), Analytics/Lineage/SPC/Model metrics (P1), batch scoring (P2).
12. **Handoff requirements:** analytics definitions documented in `docs/api.md` for the report.
13. **Acceptance criteria:**
    - Analytics show only stored-data-backed numbers with their exclusion rules visible.
    - Every displayed prediction row shows its model version.
14. **Completion gate:** M12.
15. **Compatibility requirements for Role 1:** SPC uses `spc_check(SpcSeries)`. Role 2 does not implement SPC rules.
16. **Risks & assumptions:** few runs early on make analytics sparse. A seeded demo history may be generated **by running real simulations** through the API (scripted), never by inserting fabricated predictions.

---

### R2-P9: Deployment & System Integration

1. **Phase:** R2-P9, Deployment & System Integration (Plan Phases 12, 14).
2. **Objective:** One coherent system that runs from a clean clone with real artifacts, verified configuration, clean migrations and documented setup. Docker Compose if P2 is authorised.
3. **Priority:** **P0** clean local setup with real artifacts. **P2** Docker Compose (api + PostgreSQL + static frontend), GitHub Actions CI.
4. **Primary owner:** Role 2 (Role 1 provides artifacts and the ML README section).
5. **Dependencies:** R1-P9 package; R2-P5…P8.
6. **Estimated duration:** 4–6 working days (W10–W11).
7. **Ordered tasks:**
   1. Integrate the final model archive (Section 14.5): unpack to `models/`, verify `MANIFEST.sha256`, start with `SMQI_ENV=demo`, `SMQI_INTELLIGENCE_BACKEND=real`.
   2. Configuration audit: every Section 9.6 variable is documented in `.env.example`; there are no absolute paths; startup logs list resolved versions (contracts, registry, bundles, DB revision).
   3. Clean-environment test: on the **other member's machine** (or a fresh folder/VM), follow the README only: `uv sync --frozen` → migrate → seed → run API → `npm ci` → `npm run build`/`dev` → run the journey. Record the duration (target < 10 min, Plan Phase 14) and every friction point; fix the docs.
   4. Production frontend build served by FastAPI `StaticFiles` (simple single-process demo) **or** by the Compose web container (P2) (UD-16).
   5. Performance pass on Plan §24.4 targets; fix hot spots (cache, threadpool, payload sizes).
   6. (P2) `docker/Dockerfile.api`, `docker/Dockerfile.web`, `docker/compose.yaml`: api + postgres + web; model directory mounted read-only; seed on first run; healthchecks. Run migrations on PostgreSQL.
   7. (P2) `.github/workflows/ci.yml`: ruff, black --check, mypy, pytest (with the tiny bundle), npm lint, typecheck, test, build.
   8. `docs/troubleshooting.md`: port conflicts, SSE behind proxies, hash mismatch, constraints version mismatch, Windows path issues, Python version mismatch.
8. **Files:** `README.md`, `.env.example`, `backend/app/main.py` (static serving), `docker/*` (P2), `.github/workflows/ci.yml` (P2), `docs/{troubleshooting.md, deployment.md}`.
9. **Technical details:** demo profile settings: `real` intelligence mandatory, the API key optional, CORS locked to the served origin, `speed_factor` default 1x, a deterministic seeded demo dataset of runs created via the API script.
10. **Required tests:**
    - Clean-clone checklist executed and recorded.
    - Migrations clean on SQLite (and PostgreSQL for P2).
    - `/health` = ok with real intelligence.
    - Startup fails loudly with a missing bundle.
    - (P2) `docker compose up` brings the system live.
11. **Deliverables:** reproducible setup; integration build; deployment docs; (P2) Compose + CI.
12. **Handoff requirements:** the setup log in `integration_status.md`; known-issues list.
13. **Acceptance criteria:** a clean machine runs the system from the README in < 10 minutes (Plan Phase 14). The full journey runs without console errors (Plan Phase 12).
14. **Completion gate:** prerequisite for M13.
15. **Compatibility requirements for Role 1:** artifacts are consumed exactly as published. No local edits to bundles or registry.
16. **Risks & assumptions:**
    - Windows/Unix path differences.
    - Library wheels for Python 3.12 (UD-01).
    - Docker availability on presentation day: local mode is the primary, Compose is the bonus.

---

### R2-P10: System Testing & Demonstration

1. **Phase:** R2-P10, System Testing & Demonstration (Plan Phases 13, 15; §24.4–24.5).
2. **Objective:** Prove the whole application works, with tests and benchmarks, and prepare a reproducible 8-minute demonstration with a recorded backup.
3. **Priority:** P0.
4. **Primary owner:** Role 2 (Role 1 co-owns the ML parts of the demo and report).
5. **Dependencies:** R2-P9; R1-P10.
6. **Estimated duration:** W11–W12 (≈ 8 working days).
7. **Ordered tasks:**
   1. Playwright E2E (UD-12) of the full journey (Section 15.4): select context → enter recipe → validate (including a rejected out-of-range value) → run (auto, instant and 1x) → watch 5 stages → PASS/FAIL + calibrated p_fail → explanation → recommendations → send to what-if → evaluate → save scenario → history → analytics.
   2. Special-path E2E:
      - BLOCKED (melt above ceiling) → override → NOT RELEASABLE result;
      - abort mid-run;
      - reset;
      - SSE drop → polling fallback;
      - server kill mid-run → ABORTED with inspectable partial state.
   3. Fault injection: missing artifacts (503 + degraded health), invalid params (422 codes), unknown run (404), rate limit (429), intelligence error mapping.
   4. Scenario immutability check across the whole journey (row hashes of original runs unchanged).
   5. Analytics check: what-if and mock excluded by default.
   6. Benchmarks vs Plan §24.4: prediction p95 < 150 ms, SHAP p95 < 300 ms, what-if < 100 ms, sweep < 1.5 s, recommendation < 5 s, instant run < 300 ms, SSE jitter < 100 ms, 10 concurrent runs, 60 fps animation (DevTools). Record results honestly in `docs/system_test_report.md`.
   7. `docs/demo_script.md` (8 minutes, deterministic seeded runs):
      1. context;
      2. live run with anomaly;
      3. FAIL result with risk separation;
      4. why (SHAP + stage risk mass);
      5. what should I change (guard, stability, cycle-time);
      6. what-if flip with stage diff;
      7. BLOCKED demonstration;
      8. history/analytics;
      9. limitations slide (four claims).
      Include a failure-recovery path (stepwise mode, polling, recorded video).
   8. Record the backup demo video before demo day. Rehearse.
   9. Final integration report: capability matrix, versions, test results, known limitations.
8. **Files:** `frontend/e2e/*.spec.ts`, `backend/tests/e2e/*`, `scripts/benchmark.py`, `scripts/seed_demo_runs.py` (creates runs via the API), `docs/{system_test_report.md, demo_script.md, final_integration_report.md}`.
9. **Technical details:** E2E runs against `SMQI_ENV=test` with `real` intelligence using the **full** bundle locally and the tiny bundle in CI. Seeds are fixed for deterministic screenshots.
10. **Required tests:** all of the above. The joint E2E journey is green. Every P0 acceptance item in Section 19 is checked.
11. **Deliverables:** D1, D12–D16 final; D22 demo script + video; system test report.
12. **Handoff requirements:** shared final checklist sign-off with Role 1.
13. **Acceptance criteria:**
    - Full journey executes without manual intervention or console errors.
    - The demo runs in < 8 minutes with a rehearsed recovery path (Plan Phase 15).
    - Benchmarks are reported, including any missed targets.
14. **Completion gate:** M13 and M14.
15. **Compatibility requirements for Role 1:** E2E uses only published versions. Failures in intelligence are reported to Role 1 with reproduction inputs (canonical JSON).
16. **Risks & assumptions:** demo-day failure (R20), mitigated by the seeded deterministic run, instant mode, offline build, recorded video and rehearsed script.

---

## 13. Cross-role dependencies and milestone table

### 13.1 Milestones

**Dependency direction legend:**
- **R1→R2:** Role 2 consumes a Role 1 artifact.
- **R2→R1:** Role 1 consumes a Role 2 artifact.
- **⇄:** joint.

| # | Milestone (target week) | Role 1 deliverable | Role 2 deliverable | Shared interface / artifact | Direction | Integration test | Completion criteria (proof) |
|---|---|---|---|---|---|---|---|
| M1 | Shared architecture & contracts approved (W1) | `app/contracts` v0.1→1.0.0, registry v1.0.0, loader | Repo skeleton, OpenAPI skeleton, review | `contracts/`, `constraints.yaml`, this roadmap | ⇄ | `test_interface_contract.py` imports all contracts; registry loads in the API | Both approvals on the PR; `CONTRACTS_VERSION=1.0.0`; `integration_status.md` entry |
| M2 | Dataset feasibility & canonical input schema established (W1–W2) | `dataset_feasibility.md` decision; parameter dictionary; generator spec | Recipe API schema generated from the registry | Canonical field list (Section 7.6) | R1→R2 | API accepts `recipe_nominal.json`; rejects out-of-range fixtures with correct codes | Decision recorded; the field list is identical in registry, contracts and API (test) |
| M3 | Mock inference interface operational (W2) | Contract fixtures (5 recipes) | `MockQualityIntelligence`, hybrid router | `QualityIntelligence` Protocol | ⇄ | Contract suite green for mock | `/health` shows mock; MOCK banner visible in the UI |
| M4 | Database & simulation skeleton operational (W4) | — (registry `stage_inputs`, `invalidated_stages` already delivered) | DB + migrations + FSM + SSE with mock | Event catalogue v1, DB schema | R1→R2 (loader) | Scripted SSE client watches a mock run to FINAL_RESULT; BLOCKED fixture blocks | Recorded test run; `docs/events.md` frozen |
| M5 | First stage-intelligence module integrated (W5) | S1 Material module, capability `run_stage` (S1 real) | Hybrid routing per stage | `run_stage()`, `StageResult` | R1→R2 | Simulation with S1 real + S2–S5 mock; the S1 golden case shows the moisture flag in the UI | Capability matrix: S1 REAL; contract suite green for S1 |
| M6 | All five stage modules integrated (W6) | S2–S5, stage stats bundle | Stage runner with real module versions in cache keys | `run_stage()`, `upstream_out` chain | R1→R2 | Full real stage chain; golden cases visible; partial == full for stage-only reruns | Capability `run_stage` REAL for all; purity tests green |
| M7 | Initial fusion model available (W4–W5) | `fusion-0.1.0` bundle + tiny fixture bundle | `/predict` real in hybrid; `model_versions` registration | Bundle layout, `predict()`, `registry.json` | R1→R2 | `/predict` returns a real calibrated `p_fail` for fixtures; `/models/active` shows 0.1.0 | Archive SHA-256 verified on Role 2's machine |
| M8 | End-to-end quality prediction operational (W7) | `fusion-1.0.0` (raw + stage + engineered + context), risk engine, OOD | Full real simulation; result card | `PredictionResult` | R1→R2 | UI run → real PASS/FAIL + calibrated p_fail + operational risk; critical-override fixture shows NOT RELEASABLE | E2E smoke green in `real` (mock off) |
| M9 | Explainability integrated (W8) | `explain`, `global_explanation` | Explainability panel, persisted explanation | `LocalExplanation`, `GlobalExplanation` | R1→R2 | SHAP chart and stage risk donut for a FAIL run; caveat banner on the OOD fixture | Latency within budget; disclaimer present |
| M10 | Recommendation engine integrated (W9) | `recommend`, guard tests, evaluation report | `/recommend`, cards, send-to-what-if | `RecommendationResponse` | R1→R2 | FAIL run → 3 options, all `ALL_SATISFIED`, stamps visible; property test re-run in the integration env | "Guard tested" recorded **before** the UI is enabled; 100 % compliance |
| M11 | What-if simulation operational (W9) | `invalidated_stages`, `sensitivity` (P1), equivalence check | `/whatif`, diff UI, lineage, scenario save | Diff contract, dependency graph | ⇄ | Partial == full property test; cooling-time change recomputes only COOLING + fusion; parent unchanged | Property test green; latency < 100 ms |
| M12 | History & analytics integrated (W10) | SPC functions (P1); final metrics files | History, lineage, analytics, Model Info | `/analytics/*`, `metrics.json` | R1→R2 | Analytics on seeded real runs; exclusions verified | Screens functional with stored data only; **interface freeze** after M12 |
| M13 | End-to-end testing completed (W11) | R1 test suite + evaluation reports final | Playwright journey + fault injection + benchmarks | Whole system | ⇄ | Section 15.4 joint journey | `system_test_report.md` and R1 reports complete; all P0 checklist items ticked |
| M14 | Final demonstration ready (W12) | ML demo segments, model card, dataset card | Demo script, seeded runs, video | Demo build | ⇄ | Full rehearsal in < 8 min with failure recovery | Video recorded; rehearsal signed off by both |

### 13.2 Parallel work and blocking dependencies

| Week | Role 1 (can proceed independently) | Role 2 (can proceed independently) | Hard blocking dependencies |
|---|---|---|---|
| W1 | Contracts, registry, fleet, dataset search | Repo, tooling, backend/frontend skeleton | R2 mock waits for contracts (day 2–3). R1 waits for the repo skeleton (day 1) |
| W2 | Generator, validation | Mock, registry endpoint, DB models | R2 seed waits for `fleet.yaml` |
| W3 | EDA, preprocessing, features, splits | Schemas, services, `/predict` (mock) | — |
| W4 | Baselines, GBDT, `fusion-0.1.0` | FSM, SSE, frontend shell | — |
| W5 | Stage modules (S1 first) | Process Control UI; `fusion-0.1.0` hybrid | M5 needs S1 |
| W6 | Fusion v1, calibration, risk engine | UI + real stage integration | M6 needs S2–S5 |
| W7 | SHAP, OOD, (P1) Isolation Forest | Real fusion integration; result card | M8 needs `fusion-1.0.0` |
| W8 | Recommendation engine | Explainability UI; what-if backend | M9 needs `explain` |
| W9 | Packaging & handoff | Recommendation + what-if UI | M10 needs the "guard tested" statement |
| W10 | Validation & reports | History/analytics; deployment | M12 needs persisted real runs |
| W11 | Reports, E2E support | E2E, benchmarks | M13 joint |
| W12 | Demo, report | Demo, video | M14 joint |

**Rule:** neither role may assume a capability exists unless `capabilities()` reports it **and** `integration_status.md` marks it REAL. Until then Role 2 uses the mock or hybrid, and Role 1 uses contract fixtures.

---

## 14. Parallel development and Git workflow

### 14.1 Repository and branches

| Branch | Purpose | Merges into | Rules |
|---|---|---|---|
| `main` | Canonical **integration branch** (always runnable) | — | Only via PR. All tests green. No direct pushes |
| `role-1-ai-ml` | Role 1 long-lived branch | `main` (at least weekly) | Rebase or merge `main` in at least weekly |
| `role-2-application` | Role 2 long-lived branch | `main` (at least weekly) | Same |
| `r1/<phase>-<topic>`, `r2/<phase>-<topic>` | Short feature branches | Role branch | Small, reviewable |
| `ccr/<NNN>-<slug>` | Contract changes | `main` directly (both approve) | Then both role branches merge `main` |

- **Hosting:** the folder is not yet a git repository. R2-P1 initialises it. A shared remote (e.g. a private GitHub repo) is **recommended** for PRs and CODEOWNERS (UD-02).
- **Commits:** Conventional Commits with role scope, e.g. `feat(r1-stage): add packing module`, `fix(r2-sse): replay from Last-Event-ID`, `ccr(contracts): add run.resumed event`.

### 14.2 Merge requirements (quality gate for every PR to `main`)

1. `uv sync --frozen` and `npm ci` succeed. Lockfiles are updated in the same PR as dependency changes.
2. `uv run ruff check .`, `uv run black --check .` and the scoped mypy are clean. `npm run lint` and `npm run typecheck` are clean.
3. `uv run pytest` is green, including the contract suite (mock **and** the available real capabilities via the tiny bundle) and the import-boundary tests.
4. `npm run test` is green. Generated API types are up to date.
5. JOINT paths need approval from both members (CODEOWNERS).
6. No secrets, `.env`, absolute machine paths, data files or full model bundles are committed.

### 14.3 Keeping separate environments compatible

- Both members use Python 3.12 via uv (`.python-version`) and Node 24 via npm. Versions come **only** from the lockfiles.
- `.env.example` is the template. Each member keeps a private `.env`.
- Never hardcode `C:\Users\...` or `/home/...`. All paths are relative to the repo root or come from env variables.
- `integration_status.md` records each member's OS, Python, uv, Node and npm versions and the last clean-setup date.

### 14.4 Artifact versioning

- Models follow semver per bundle. `models/registry.json` and `models/MANIFEST.sha256` are committed. Bundles are not (Plan §21.1).
- Datasets: generator config + seed are committed (regenerable). Data files are not. `data/**/MANIFEST.sha256` and `source_manifest.json` are committed.
- The tiny fixture bundle (< 2 MB, `is_fixture=true`) **is committed** so CI and Role 2 can run real-path tests.

### 14.5 Artifact transfer between environments

1. Role 1 runs `uv run python -m ml_pipeline.cli package-archive`, producing `smqi-models-<YYYYMMDD>-<fusion semver>.zip` + `.sha256`.
2. Role 1 uploads it to the agreed shared location (UD-02: GitHub Release asset on the private repo, or a shared drive) and commits the updated `models/registry.json` + `MANIFEST.sha256`.
3. Role 2 downloads it, verifies SHA-256, unzips to `models/`, and runs `uv run pytest backend/tests/contract -k real`.
4. Both record the transfer in `integration_status.md`.

**Do not assume code works together because each member can run it alone.** Compatibility is proven only by the merged-branch tests and the weekly clean-environment checkpoint.

---

## 15. Testing strategy and quality gates

### 15.1 Test pyramid and locations

| Level | Tooling | Location | Owner |
|---|---|---|---|
| Unit | pytest | `backend/tests/{domain,intelligence,ml,recommendation}`, `ml_pipeline/tests` | R1 |
| Unit | pytest | `backend/tests/{engine,db,services,schemas}` | R2 |
| Property | hypothesis | R1: purity, recommendation constraints, equivalence (intelligence side). R2: partial == full re-sim, FSM | Both |
| Contract | pytest | `backend/tests/contract` (fixtures R1, harness R2) | JOINT |
| API integration | pytest + httpx (ASGI transport) | `backend/tests/api` | R2 |
| Frontend unit/component | Vitest + RTL + MSW | `frontend/src/**/*.test.tsx` | R2 |
| E2E | Playwright | `frontend/e2e` | R2 (R1 contributes scenarios) |
| ML regression | pytest on `metric_floors.json` | `backend/tests/ml` | R1 |
| Leakage | pytest | `ml_pipeline/tests` | R1 |
| Benchmarks | `scripts/benchmark.py` | — | R2 (R1 for intelligence rows) |

### 15.2 Role 1 test coverage (required)

- Dataset and schema validation; generator determinism.
- Leakage-safe preprocessing (train-only fit); split disjointness and temporal order; shuffled-target chance test; forbidden columns absent.
- Feature transformation consistency (batch == single; training == serving; schema order).
- Model evaluation reproducibility; calibration monotone with improved Brier; threshold from metadata.
- Stage-rule boundaries (exact min/max/tolerance edges); health aggregation; risk banding; block conditions; golden defect cases.
- Anomaly thresholds (L1 rules; Isolation Forest percentile; injected-anomaly detection).
- SHAP additivity, stage-risk-mass normalisation, determinism, latency.
- Recommendation feasibility (100 %), locked-parameter behaviour, step limits, stability, budget, empty results.
- Reproducibility and artifact loading (hash mismatch, version mismatch).
- Coverage target **[PROPOSED] ≥ 85 % lines** for `app/{domain,intelligence,ml,recommendation}` (UD-18).

### 15.3 Role 2 test coverage (required)

- API request/response validation and envelopes; error codes.
- DB models, migrations (empty → head, round-trip), immutability, lineage, seed idempotency.
- FSM transitions (exhaustive), stage-result persistence, event ordering and `seq`, SSE delivery and replay, polling fallback.
- Constraint validation (tiers 1–2) and critical blocking/override (tier 3).
- Frontend form validation driven by `/constraints`; SSE reducer; risk-concept separation; mock banner; disclaimers.
- Real backend integration with the tiny bundle; scenario immutability; history and analytics exclusions; clean deployment.
- Coverage target **[PROPOSED] ≥ 75 % lines** for `app/{api,services,engine,db}` (UD-18).

### 15.4 Joint integration test (the acceptance journey)

**Select machine/product/material → Enter recipe → Validate parameters → Run simulation → Execute five stage-intelligence modules → Run fusion prediction → Display PASS/FAIL and calibrated failure probability → Display explainability → Generate constrained recommendations → Run what-if comparison → Save scenario → Retrieve history and analytics.**

It MUST verify that:

- [ ] Critical constraint breaches cannot silently produce an ordinary confident PASS (BLOCKED → override → NOT RELEASABLE + CRITICAL risk + caveat).
- [ ] Invalid recommendation candidates are rejected (no returned option fails any guard check; rejected counts > 0 on the stress fixture).
- [ ] What-if runs do not overwrite original runs (row hashes unchanged; child has `parent_run_id`).
- [ ] Predictions and operational risk are presented as different concepts (separate UI blocks, labels asserted).
- [ ] The frontend uses actual backend outputs (E2E asserts UI values equal API payload values for the same run).
- [ ] Model artifacts and versions are traceable (prediction → `model_versions` row → bundle SHA-256 → git SHA, dataset hash).
- [ ] Mock implementations are not mistaken for genuine inference (demo profile refuses mock; any mock output shows the banner and `is_mock=true`).
- [ ] The software workflow is not described as a physically validated digital twin (disclaimer present; text audit of the UI and docs for forbidden phrases).

### 15.5 Quality gates

| Gate | When | Requirement |
|---|---|---|
| G-PR | Every PR to `main` | Section 14.2 |
| G-Phase | End of each phase | Phase acceptance criteria met; tests run and reported; Appendix B report; next phase only after confirmation |
| G-Milestone | M1–M14 | The milestone's integration test passes on the merged `main` in a clean environment |
| G-Freeze | After M12 | Interface freeze: only bug fixes. Any output change bumps module or bundle versions |
| G-Demo | M14 | Section 19 checklist complete; both members sign off |

### 15.6 Pre-coding dependency checklist (for the coding agent, every phase)

- [ ] Required schemas exist in `app/contracts` at the needed version.
- [ ] The other role's interfaces needed by this phase are documented (and REAL or mockable).
- [ ] Existing implementations have been inspected (no duplicate modules).
- [ ] The lockfile is in sync. No new dependency without updating `pyproject.toml`/`package.json` + lockfile (and an ADR for stack additions, Plan R15).
- [ ] Naming follows Section 7.1. Configuration follows Section 9.6.
- [ ] The planned change does not violate boundary rules B1–B8.

---

## 16. Deployment and final demonstration plan

### 16.1 Local development (both roles)

```bash
# Python (repo root)
uv sync --frozen                 # Role 1 adds: --group ml
uv run alembic -c backend/alembic.ini upgrade head
uv run python -m app.db.seed
uv run uvicorn app.main:app --reload --app-dir backend --port 8000
# Frontend
cd frontend && npm ci && npm run dev    # http://localhost:5173
```

PowerShell users run the same commands. Set environment variables with `$env:SMQI_INTELLIGENCE_BACKEND = "real"`, or put them in `.env`.

### 16.2 Demo profile

- `SMQI_ENV=demo`, `SMQI_INTELLIGENCE_BACKEND=real`, active bundles verified.
- The frontend production build is served by FastAPI static files (single process) or by the P2 Compose web container.
- **Seeded demo history** is created by `scripts/seed_demo_runs.py`, which calls the **API** to run real simulations with fixed seeds and recipes. It never inserts predictions directly.
- **Deterministic demo recipes** (from contract fixtures):
  1. a FAIL recipe dominated by cooling (short cooling, high melt), giving a recommendation flip;
  2. a melt-above-ceiling recipe for the BLOCKED demonstration;
  3. a nominal PASS recipe.

### 16.3 Docker Compose (P2, only after all P0 integration)

`docker/compose.yaml` with:
- `api`: Python 3.12 image, `uv sync --frozen`, migrations on start, models mounted read-only;
- `db`: PostgreSQL;
- `web`: static build.

`docker compose up` brings the system live (Plan Phase 14). Local mode remains the primary demo path.

### 16.4 Demonstration (8 minutes, Plan §23.3, Phase 15)

| Min | Segment | Owner |
|---|---|---|
| 0:00 | Problem, domain, four-claim statement | R1 |
| 0:45 | Process Control: select MC-03 / PP-JBOX-42 / A-771, registry-driven sliders, validation | R2 |
| 1:30 | Live run: stages animate, anomaly badge on Thermal, timeline | R2 |
| 2:30 | Result: FAIL, calibrated P(fail), operational risk vs anomaly, risk origin | R2 |
| 3:00 | Why: SHAP bars, stage risk mass, association-not-causation note | R1 |
| 3:45 | What should I change: 3 options, guard stamp, stability, extrapolation, cycle-time cost, disclaimer | R1 |
| 4:45 | Send to what-if: stage-by-stage diff, verdict flip; slider tweak recomputes only COOLING | R2 |
| 5:45 | BLOCKED demonstration: melt above ceiling, refusal, override → NOT RELEASABLE | R2 |
| 6:30 | History lineage + analytics (what-if excluded) + Model Info (synthetic statement, metrics) | R2 / R1 |
| 7:15 | Evaluation highlights incl. recommendation ground-truth check, limitations | R1 |

**Failure recovery path:** stepwise mode (no SSE), instant mode, polling fallback, recorded video.

---

## 17. Scope priorities and exclusions

### 17.1 P0: Mandatory MVP (target: integrated by W9, Plan §23.1)

| Plan ID | Feature | Owner(s) |
|---|---|---|
| F1 | Machine, product and material context (selection + lot creation) | R2 (fleet content R1) |
| F2 | Validated process-parameter entry (registry-driven) | R2 (registry R1) |
| F3 | Six-stage simulation state machine (stepwise + auto, BLOCKED) | R2 |
| F4 | Five stage-intelligence modules (+ fusion at S6) | R1 |
| F5 | Fusion quality prediction (calibrated) | R1 |
| F6 | Stage-level risk and anomaly indicators (L1) | R1 compute, R2 display |
| F7 | SHAP explainability (local + global, stage risk mass) | R1 compute, R2 display |
| F8 | Process-flow visualization (SVG pipeline) | R2 |
| F9 | Live event log (SSE timeline) | R2 |
| F10 | What-if simulation (mutation + delta panel) | R2 (dependency graph R1) |
| F11 | Constrained recommendations (rule proposals + coordinate search + six-check guard) | R1 algorithm, R2 UI |
| — | Run history persisted (MVP) | R2 |

### 17.2 P1: Enhancements (only after the P0 workflow is integrated and green)

| Plan ID | Feature | Owner(s) |
|---|---|---|
| F12 | Scenario comparison (A vs B) | R2 |
| F13 | Simulation history analytics dashboard | R2 |
| F14 | Parameter-sensitivity curves (1-D sweeps, flip points) | R1 compute, R2 UI |
| F15 | Dedicated Isolation Forest anomaly detection (+ guard check 4 IF component) | R1 |
| F16 | Model registry / version metadata surface (Model Info) | R2 (metadata R1) |
| F17 | Pause/resume/step-through/speed controls | R2 |
| — | SPC drift alerts; stage sub-models (OOF); pairwise search + DE refinement; ensemble-spread uncertainty; Tier-3 augmentation | R1 (UI R2) |

### 17.3 P2: Showcase (conditional; only with explicit authorisation after P0 + P1 are stable)

| Plan ID | Feature | Owner(s) |
|---|---|---|
| F18 | MLP deep-learning benchmark (and autoencoder anomaly detector) | R1 |
| F19 | CSV batch upload and bulk scoring | R2 (R1 inference) |
| F20 | Docker Compose deployment (+ PostgreSQL, CI) | R2 |
| — | 2-D response-surface heatmap; run-lineage tree polish; recommendation stability panel | R2 (R1 compute) |

### 17.4 Explicitly excluded (Plan F21–F26, §23.4); not to be built without explicit user authorisation

Multi-user authentication or RBAC · real-time PLC/OPC-UA/MQTT ingestion · 3D mold/part rendering (Three.js) · reinforcement-learning process control · microservices or Kubernetes · CFD/FEA/mold-flow solver · message brokers (Celery/Redis/Kafka) · Airflow · GraphQL · Next.js · Redis cache · mobile app · multi-tenancy · LLM chatbot layer · agent frameworks (LangChain etc.).

**Scope rules:**
- Neither role starts P1 work while any P0 integration milestone (M1–M11) is open.
- Any new feature must displace an existing one and needs an ADR (Plan R15).

---

## 18. Technical risks and mitigation

The Plan's register (§25.1–25.2), with owners, plus team-specific risks.

| # | Risk | Impact | Likelihood | Mitigation | Owner |
|---|---|---|---|---|---|
| R1 | Synthetic-data bias: the model learns the generator | High | Certain | State it prominently; Tier-1 validation if available; generator coefficients grounded in literature; report separately | R1 |
| R2 | Insufficient real data | Medium | High | Tier-1 used for validation and distribution calibration only; scope claims | R1 |
| R3 | Class imbalance distorts metrics | Medium | Certain | PR-AUC + FAIL-recall selection; tuned threshold; class weights; ablation | R1 |
| R4 | Data leakage (random splits, pre-split preprocessing, in-fold stage sub-models) | Critical | Medium | GroupKFold by batch + temporal holdout; pipeline-internal preprocessing; OOF stacking; automated leakage tests | R1 |
| R5 | Overfitting the synthetic structure | Medium | Medium | CV tuning, early stopping, learning curves, temporal test, fold variance | R1 |
| R6 | Target leakage from `p_defect_true`/`defect_mode` | Critical | Low | Feature allowlist + unit test | R1 |
| R7 | Miscalibrated probabilities driving risk bands and deltas | High | Medium | Mandatory calibration; reliability diagram; Brier before/after | R1 |
| R8 | Correlated features distort SHAP | Medium | High | Grouped attribution; permutation cross-check; UI limitation note | R1 / R2 |
| R9 | Recommendation engine exploits the model | Critical | High | Six-check guard; in-distribution; stability; ground-truth check; never surface unguarded options | R1 |
| R10 | Unrealistic or unsafe suggestions | High | Medium | Hard filters, step limits, locked parameters, BLOCKED state | R1 / R2 |
| R11 | Simulation mistaken for physical simulation | High | High | Permanent disclaimer; vocabulary discipline; text audit test | R2 / R1 |
| R12 | SHAP presented as causal proof | High | High | Permanent footnote; limitations section | R2 / R1 |
| R13 | Arbitrary risk thresholds | Medium | High | Derive bands from decile failure rates; provenance in the registry | R1 |
| R14 | Frontend/backend integration complexity | High | High | Contract-first OpenAPI + generated types; MSW and mock from W1; weekly checkpoints | R2 |
| R15 | Scope creep | High | Very high | Exclusion list binding; ADR for additions; P1/P2 gating | Both |
| R16 | Over-engineering | High | Medium | Rejection list (Plan §20); "simplest robust option" | Both |
| R17 | SSE instability during the demo | Medium | Medium | `seq` gap detection + re-sync; polling fallback; stepwise backup; video | R2 |
| R18 | Model-serving skew | High | Medium | One feature builder; schema order; skew test | R1 |
| R19 | Team bottleneck on one member | Medium | Medium | Interface-first; mocks; capability matrix | Both |
| R20 | Demo failure | High | Low | Seeded deterministic runs; instant mode; offline build; video; rehearsal | R2 |
| T1 | **Role 2 workload** (backend + frontend) exceeds capacity | High | High | Strict P0 focus; P1/P2 deferrable; Role 1 may be **explicitly assigned** E2E scenarios or report writing (never competing implementations) | Both |
| T2 | Python 3.14 default on the machine causes wheel or compat issues | Medium | Medium | Pin 3.12 via `.python-version` + uv (UD-01) | R2 |
| T3 | Model archive transfer or version drift between machines | Medium | Medium | SHA-256 manifests, lockfiles, the contract suite on the receiving machine | Both |
| T4 | Mock outputs leak into demo or analytics | High | Low | Demo profile refuses mock; `is_mock` flags; analytics exclusion; banner | R2 |
| T5 | Contract churn breaks the other role | High | Medium | CCR procedure; versioning; JOINT CODEOWNERS; freeze after M12 | Both |
| T6 | No Tier-1 dataset found | Medium | High | Planned for (A-01); honest reporting | R1 |
| T7 | Windows-specific path/encoding issues | Low | Medium | `pathlib`, UTF-8 everywhere, `.gitattributes` | Both |

**Fundamental limitations (stated, not mitigated, Plan §25.3):**
1. No physical validation.
2. Correlation, not causation.
3. No physics (heuristics are labelled).
4. Distribution-bound.
5. Static models.
6. Single-process scope.
7. Binary label granularity.

---

## 19. Final acceptance checklist

**Architecture and contracts**
- [ ] One modular monolith; no extra services; boundary rules B1–B8 enforced by tests.
- [ ] `app/contracts` v1.x used by both roles. The registry is the single source of limits (no duplicates anywhere).
- [ ] Field names identical across dataset, feature schema, registry, contracts, DB, API and TS types.
- [ ] All CCRs merged and documented. No silent contract changes.

**Intelligence (Role 1)**
- [ ] Feasibility report, dataset card and generator spec are complete and honest; Tier-1 status stated.
- [ ] Generator reproducible byte-identically from config + seed.
- [ ] Leakage tests green; split protocol documented.
- [ ] Baselines, GBDT and ablation reported with CIs. Calibration with reliability diagram and Brier. Documented threshold policy.
- [ ] Five stage modules are pure and deterministic, with golden tests and stage specs (provenance per value).
- [ ] SHAP local/global + stage risk mass within latency. Limitations documented.
- [ ] Recommendation guard: 100 % compliance; stability, extrapolation and ground-truth results reported.
- [ ] Reproducible `train-all`; verified bundles; model card.

**Application (Role 2)**
- [ ] FSM with all transitions tested; BLOCKED/override; reset/abort; restart recovery.
- [ ] SSE with replay and polling fallback; event catalogue documented.
- [ ] DB migrations clean from empty; immutability and lineage enforced.
- [ ] What-if partial == full property test; originals never overwritten.
- [ ] Seven screens functional (Process Control, Explainability, What-If, Recommendations, History, Analytics, Model Info). P1 screens are marked as such if deferred.
- [ ] UI shows predicted probability, operational risk and anomaly as distinct concepts. Disclaimers are permanent. The MOCK banner works.
- [ ] Clean-machine setup < 10 min from the README.

**Joint**
- [ ] Section 15.4 journey green in `real` mode on a clean environment.
- [ ] Benchmarks recorded (met or honestly missed).
- [ ] No unsupported claims: performance numbers only from reports; no physical-validation, digital-twin or causal claims.
- [ ] Demo < 8 min rehearsed; backup video recorded.
- [ ] D1–D22 delivered or explicitly descoped with reason.

---

## 20. Definition of done

### 20.1 Any phase (both roles)

A phase is **done** only when:
1. all ordered tasks are implemented;
2. the required tests exist and pass, with the commands and results recorded;
3. the acceptance criteria are met;
4. the deliverables and handoff artifacts are published and `integration_status.md` is updated;
5. compatibility with the other role is verified (contract suite and import boundaries green);
6. documentation is updated;
7. an Appendix B report has been delivered;
8. the user has confirmed before the next phase starts.

**Code written but untested is not done.**

### 20.2 Role 1 done

- Phases R1-P1…R1-P10 done.
- The capability matrix shows every P0 capability REAL.
- The contract suite is green for `real` on Role 2's machine.
- D2–D10, D18 and D19 are delivered.
- The four-claim discipline holds in every Role 1 document.
- No interface changes are pending.

### 20.3 Role 2 done

- Phases R2-P1…R2-P10 done.
- Mock is disabled in demo.
- The full journey runs in real mode on a clean machine.
- D1 and D11–D17 (Role 2 parts) and D22 are delivered.
- All UI disclaimers and risk separations are present.
- Benchmarks are recorded.

### 20.4 Project done

- Roles 1 and 2 are done.
- Milestones M1–M14 are closed with proof.
- The Section 19 checklist is complete.
- The final report (D20) includes the limitations chapter with the four-claim distinction (Plan Phase 15 acceptance).
- The deck (D21) has been rehearsed.

---

## Appendix A: Decisions (approved)

> **Status: APPROVED on 2026-10-15.** The user approved all recommendations UD-01 to UD-20 as written. They are now binding decisions, and every **[PROPOSED]** item they cover (Sections 2–9, incl. the UD-17 contract additions and the UD-06 placeholder bands) is part of the agreed baseline.
>
> Approval does not settle the *outcome* of UD-03, UD-04 and UD-05. Role 1 still determines the cited values, the dataset choice and the final threshold in R1-P1/R1-P6, following the approved procedure. Any further change to these decisions goes through a CCR (Section 10.4).

| ID | Decision | Recommendation | Needed by |
|---|---|---|---|
| UD-01 | Python version: the machine default is 3.14.x; the Plan says 3.11+ | Pin **3.12** via `.python-version` and uv for wheel availability across xgboost/shap/scipy/torch | Before R2-P1 task 2 |
| UD-02 | Repo root and hosting; artifact transfer location | Repo root = current folder. Private GitHub repo with CODEOWNERS. Model archives as release assets (or a shared drive) | W1 |
| UD-03 | Numeric registry values (Section 8.3) are placeholders | Role 1 replaces them with cited values or keeps them flagged `unvalidated` | End of R1-P1 |
| UD-04 | Tier-1 dataset selection | Decided by the R1-P1 feasibility report | End of R1-P1 |
| UD-05 | Decision-threshold operating point | FAIL-recall ≥ 0.85 on validation; precision cost reported | R1-P6 |
| UD-06 | Initial stage-health and p_fail risk bands | Use the Sections 7.10/7.13 placeholders; re-derive p_fail bands in R1-P6 | M1 (placeholders), R1-P6 (final) |
| UD-07 | Display of a run that passed an overridden critical breach | "NOT RELEASABLE" headline, `risk_level=CRITICAL`, model label secondary | M1 |
| UD-08 | RESET of FINAL_RESULT/ABORTED runs | Reject (409 `RUN_IMMUTABLE`); offer "Re-run as new run" | M1 |
| UD-09 | `cycle_time_s` behaviour in what-if and recommendation | Adjust by Δ(fill + hold + cooling) unless explicitly overridden; always report cycle-time impact | M1 |
| UD-10 | API identifiers for reference entities | Codes (`MC-03`, `PP-JBOX-42`, `A-771`) in API and contracts; integer PKs internal | M1 |
| UD-11 | `hybrid` intelligence mode during development | Allow in dev/test only; per-output `inference_backend`; forbidden in demo | M1 |
| UD-12 | Frontend test tooling (not specified by the Plan) | Vitest + React Testing Library + MSW + Playwright | R2-P1 |
| UD-13 | React major version (Plan says React 18) | Keep **React 18** as specified unless both approve an upgrade | R2-P1 |
| UD-14 | Formatter (Plan says ruff + black) | Keep ruff (lint) + black (format) | R2-P1 |
| UD-15 | LightGBM as runtime dependency if it beats XGBoost | Only via CCR; XGBoost remains the default primary | R1-P4 |
| UD-16 | Frontend serving for the demo; PostgreSQL/Compose scope | FastAPI static serving + SQLite for the primary demo; Compose + PG only as P2 | R2-P9 |
| UD-17 | Proposed additions to Plan contracts: events `run.resumed`, `stage.override_acknowledged`, `run.error`; endpoints `/abort`, `/label`, `/lineage`, `/analytics/by-material`, `/analytics/spc`, `/models/active/global-explanation`; DB columns marked [P] | Approve as listed | M1 |
| UD-18 | Coverage targets | ≥ 85 % (intelligence), ≥ 75 % (backend app) | M1 |
| UD-19 | Ownership of `app/contracts/` | JOINT, with Role 1 as primary author and Role 2 approval mandatory | M1 |
| UD-20 | Stage supervised sub-models | Deferred to P1 (MVP rule + statistics, per Plan §23.1) | M1 |

---

## Appendix B: Phase completion report template

```markdown
## Phase report: <R1|R2>-P<n> <title>
- Role: <Role 1|Role 2>          - Date:            - Branch / commit:
### Tasks completed
### Files created / modified
### Tests executed (exact commands) and results
### Acceptance criteria satisfied (each criterion: met / not met + evidence)
### Known limitations / unresolved issues
### Integration impact on the other role (contracts touched, CCRs, capability matrix changes)
### Handoff artifacts (paths, versions, SHA-256)
### Unverified items (what could not be run and why)
### Remaining tasks in this role's roadmap
### Request: confirm before starting <next phase>
```

---

## Appendix C: Glossary

| Term | Meaning in this project (Plan §8.1, §19.3) |
|---|---|
| AI/ML model | A fitted statistical artifact producing a numeric output from features (fusion model, sub-models, anomaly detector, calibrator) |
| Intelligence module | A stateless, deterministic, non-autonomous component evaluating one stage with rules, indicators, statistics and optionally a small model |
| Service | An application-layer component exposing an interface (simulation, inference, analytics …) |
| Autonomous agent | Deliberately **not used** in this project |
| Real data | Recorded from physical equipment by a third party under a stated licence |
| Synthetic data | Generated by the documented mechanism-based generator; encodes beliefs, not measurements |
| Simulated data | Output of a physics solver. **This project produces none** |
| Augmented data | Real or synthetic rows transformed by noise, jitter or drift |
| Operational risk | Risk-engine band combining calibrated P(fail) and constraint breaches; distinct from model probability and anomaly status |
| Stage risk mass | Share of total \|SHAP\| attribution owned by each stage's features |
| What-if | A child run derived from a parent with mutated parameters, re-simulated from the earliest invalidated stage |
| Feasibility guard | The six checks every recommendation candidate must pass before its probability is shown |
| CCR | Contract Change Request (Section 10.4) |
| Capability matrix | `QualityIntelligence.capabilities()` + `integration_status.md` record of which features are REAL vs MOCK |

---

*End of PROJECT_DEVELOPMENT_ROADMAP.md. This document is the single source of truth for role allocation, phase-wise development and integration compatibility. Changes to it follow the CCR procedure (Section 10.4).*
