# Final integration report — roadmap R2-P10 task 9

**Date:** 2026-10-23 · **Author:** Role 2 · **Branch:** `role-2-application` · **Status:** draft for joint sign-off with Role 1

This report covers:
- the capability matrix;
- the versions in the integrated build;
- test results;
- known limitations.

Test detail is in [`system_test_report.md`](system_test_report.md); open findings for Role 1 are in [CCR-004](contract_changes/CCR-004-role1-integration-findings.md).

## Summary

- **The application side is integrated and tested end to end.** Simulation engine, persistence, API, SSE, every screen, what-if with partial re-simulation, analytics and single-process deployment all work on Role 1's real facade. Results: 544 backend tests, 109 frontend tests and 9 Playwright E2E tests pass, with fault injection and immutability checks.
- **The intelligence layer is not yet what it is labelled as (CCR-004 A0, #18–#21).** `fusion-1.0.0` has no trained model, no calibrator, no SHAP, and no stability or distribution checks. Its payloads say "calibrated", `tree_shap`, "2500 rows", "0/20 flips" and "in distribution", and the UI shows those labels as received.
  - The prediction is a hand-weighted logistic formula over stage health scores.
  - The attributions and global importance are fixed rules or constants.
  - The recommendation options are three fixed recipe edits, and three of the six guard checks are hard-coded passes.
- **Consequence:** the system can't yet honestly be demonstrated as ML-backed explanation and guarded recommendation. Section 5 lists the options. Choosing one is a joint decision with Role 1 and must be made before the demo.

## 1. Versions

**Source:**

| Item | Value |
|---|---|
| Role 2 branch | `role-2-application`, this report's commit (after `60c5c65`) |
| Role 1 delivery | `1a22d7b` (PR #1 to `main`), merged into `role-2-application` at `ea53a34` |
| Roadmap | `PROJECT_DEVELOPMENT_ROADMAP.md` v1.0.1 (Appendix A approved 2026-10-15). `main` still carries the reverted 1.0.0 draft (CCR-004 #15) |

**Contracts and artifacts:**

| Artifact | Version |
|---|---|
| Contracts | `0.1.0` |
| Constraint registry | `constraints-1.0.0`, sha256 `109ea30cf382…` |
| Fleet | `fleet-1.0.0` (4 machines, 2 products, 4 lots) |
| Remedies | `remedies-1.0.0` |
| Intelligence | `fusion-1.0.0` (`RealQualityIntelligence`, pure Python; no model bundle, no `models/`, no MANIFEST) |
| DB schema | Alembic `0001` (10 tables), SQLite in WAL mode |
| API | `/api/v1`, 32 paths and 34 operations (`docs/openapi.json`); `{data, error, meta}` envelope |

**Toolchain and main libraries** (versions pinned in `uv.lock` and `package-lock.json`):

| Layer | Versions |
|---|---|
| Toolchain | Python 3.12.10 (uv 0.10.7), Node 24.14.1, npm 11 |
| Backend | FastAPI 0.143.1, Pydantic 2.14.1, pydantic-settings 2.16.0, SQLAlchemy 2.0.54, Alembic 1.20.0, uvicorn 0.54.0, structlog 26.1.0 |
| Frontend | React 18.3.1, React Router 7.18.4, TanStack Query 5.104.2, Zustand 5.0.15, Recharts 3.10.1, Framer Motion 14.2.0, Tailwind 4.3.3, Vite 8.3.4, TypeScript 5.9.3 |
| Tests and quality | pytest 9.1.1, Hypothesis 6.169.1, ruff 0.17.0, mypy 2.4.0, Vitest 5.0.4, MSW 3.0.3, Playwright 1.64.1, openapi-typescript 7.13.0 |

## 2. Capability matrix

**Status legend:**
- **Integrated:** works end to end on the real backend and is covered by tests.
- **Integrated, placeholder intelligence:** Role 2's side is complete, but the values come from CCR-004 A0 placeholders.
- **Partial**, **Not built**, **Excluded**: as named.

### P0 (roadmap §17.1)

| ID | Capability | Owner | Status | Evidence / notes |
|---|---|---|---|---|
| F1 | Machine, product, material context; lot creation | R2 (fleet R1) | Integrated | Pickers, Create lot dialog with registry validation; E2E journey |
| F2 | Registry-driven parameter entry and validation | R2 (registry R1) | Integrated | Windows and units from `GET /constraints`; 422 codes per field; out-of-range refused in the UI (E2E) |
| F3 | Six-stage state machine (auto, stepwise, BLOCKED) | R2 | Integrated | Engine, override, abort, reset, restart recovery; E2E special paths |
| F4 | Five stage-intelligence modules | R1 | Integrated (rule-based) | `stages.py` rule evaluators with registry hard constraints. Rules are allowed by the plan; stage risk mass and provenance gaps in CCR-004 #3–#4 |
| F5 | Calibrated fusion prediction | R1 | **Integrated, placeholder intelligence** | A hand-weighted formula, not a trained or calibrated model (CCR-004 #18). Threshold 0.35. The label is forced to FAIL on critical breaches (#2) |
| F6 | Stage risk and anomaly indicators (L1) | R1 / R2 | Integrated | Per-stage risk and anomaly flags shown live. The global anomaly (`anomaly_global`) is not provided ("Not evaluated") |
| F7 | SHAP explainability, local and global, with stage risk mass | R1 / R2 | **Integrated, placeholder intelligence** | Panel, grouped view, donut, caveat banner and disclaimer all work. The values are fixed rules labelled `tree_shap`, and the global importance is a constant list labelled "2500 rows" (#19–#20) |
| F8 | Process-flow visualisation (SVG pipeline) | R2 | Integrated | Stage pipeline with health, risk, anomaly and override states |
| F9 | Live event log (SSE timeline) | R2 | Integrated | SSE with `Last-Event-ID` replay and polling fallback (E2E); jitter ~45 ms at 1x |
| F10 | What-if with partial re-simulation and diff | R2 (graph R1) | Integrated | Reuses unaffected stages (property-tested equal to full runs); §7.16 diff; scenarios saved as child runs; originals unchanged (row-hash test) |
| F11 | Constrained recommendations with the six-check guard | R1 / R2 | **Integrated, placeholder intelligence** | Cards, guard stamp, stability, cycle time, Send to What-If and the step-limit cross-check all work. The options are three fixed edits and three guard checks are hard-coded passes (#21, #7a, #7b) |
| — | Persisted run history | R2 | Integrated | History list, filters, run detail, scenario labels |

### P1 (roadmap §17.2)

| ID | Capability | Owner | Status | Evidence / notes |
|---|---|---|---|---|
| F12 | Scenario comparison A/B | R2 | Integrated | `/what-if/compare`, swap; Vitest and screenshots |
| F13 | History analytics dashboard | R2 | Integrated | `/analytics/*` SQL aggregations with stated and togglable exclusions (journey test) |
| F14 | Sensitivity curves and flip points | R1 / R2 | Integrated, with a defect | Sweeps are computed by re-evaluation. `flip_point` is the first crossing, not the nearest one (#7c) |
| F15 | Isolation Forest anomaly detection | R1 | Not delivered | `anomaly_global` is null |
| F16 | Model registry and Model Info | R2 (metadata R1) | Partial | Screen built. Role 1 reports no metrics, dataset hash, generator version, bundle SHA or threshold (#7d) |
| F17 | Pause, resume, step and speed controls | R2 | Integrated | Run controls; presentation speeds 0.5x / 1x / 2x / instant |
| — | SPC drift alerts | R1 (UI R2) | Partial | Stored series served and shown. `spc_check` is advertised but not implemented (#10), so there are no alerts or control limits |
| — | Lineage tree | R2 | Integrated | Run detail, climbing to the root |
| — | Live what-if slider | R2 | Integrated | 150 ms debounce; superseded requests aborted |

### P2 and exclusions (roadmap §17.3–17.4)

- **F18, MLP benchmark:** not started (Role 1).
- **F19, CSV batch scoring:** not built.
- **F20, Docker Compose, PostgreSQL and CI:** not built.
- **2-D response surface:** not built.
- **Dependence plot (P1):** not built; no API provides its data.
- **Excluded items (§17.4):** none built.

## 3. Interfaces and boundaries

- **Contracts:** Role 2 consumes Role 1's interface through `QualityIntelligence` only; the import-boundary test enforces B1, B2 and B7.
  - The mock and the real facade both run the contract harness. The real facade fails two invariant groups, marked strict `xfail` (CCR-004 #3–#4).
  - §9.1 gaps (per-stage module versions, `detect_anomaly`, `spc_check`, capability keys) are listed in CCR-004 #9–#13.
- **API:** OpenAPI is generated from the backend; the frontend types are generated from it, and `npm run check:api` fails when they are stale.
- **Deployment:** a single process serves the built SPA and the API (`docs/deployment.md`). A clean clone ran in 87 s with warm caches; the run on a clean second machine is still pending (R2-P9).

## 4. Test results

See [`system_test_report.md`](system_test_report.md).

**Suites:**

| Suite | Result |
|---|---|
| Backend (unit, API, contract, fault injection, journey integrity) | 544 passed, 5 strict xfail (CCR-004 #3–#4) |
| Frontend (Vitest) | 109 passed |
| End to end (Playwright, real intelligence) | 9 passed: journey, special paths, demo replay, animation guard |
| Static checks | ruff, mypy (strict), ESLint, Prettier and TypeScript clean |

**§15.4 checklist:** 6 of 8 met. Not met:
- recommendation-guard rejection is not demonstrated (#21);
- traceability to bundle, git SHA and dataset hash is not reported (#7d).

**Benchmarks (§24.4):**
- **Met:** prediction, explanation, what-if, sweep, recommendation, SSE jitter, and 10 concurrent runs.
- **Borderline:** instant-run p95, 219–340 ms against a 300 ms budget, varying with machine load.
- **Not met headless:** 60 fps (48–54 fps). The DevTools measurement on the demo machine is still to do.

**Defects found by system testing and fixed:**
- degraded `/health` when the model fails;
- typed error codes kept on aborted runs;
- stale run state after live runs;
- the aborted-run result card;
- two load-sensitive tests.

## 5. Known limitations and decisions needed

### Decision needed before the demo: CCR-004 A0

Role 2 shows payloads as received and has not altered Role 1's values. Today, the screens and the demo script call these values SHAP, calibrated and guard-checked.

| Option | What it means |
|---|---|
| **a. Role 1 delivers** | Trained fusion bundle, calibrator, SHAP and real guard checks (R1-P5…P10). Everything Role 2 built shows the real values with no change |
| **b. Role 1 relabels truthfully** | E.g. `method: heuristic_rules`, guard checks that are not run reported as not evaluated, no `n_rows`. The UI then shows the true labels with no Role 2 change |
| **c. Role 2 adds a visible notice meanwhile** | Explainability, Recommendations and Model Info say the intelligence layer reports rule-based placeholder values (CCR-004 A0). This needs Role 1's agreement because it describes their component |
| **d. Demo without those segments** | The demo script's 3:00 "Why" and 3:45 "What should I change" segments are presented only as UI capability, with the placeholder status stated aloud |

Until one is chosen, `docs/demo_script.md` must not present segments 3:00–4:45 as model explanation or verified recommendations.

### Other limitations

- **Role 1 (CCR-004):**
  - the 4-cavity product is always blocked and MC-03 can't run the nominal recipe (#1, #7);
  - the label is forced to FAIL on critical breaches (#2);
  - stage risk mass and provenance (#3–#4);
  - limits written into code (#5);
  - no lot-attribute windows (#6);
  - flip point (#7c);
  - no metrics or provenance (#7d);
  - no SPC (#10);
  - §9.1 gaps (#9–#13);
  - no global anomaly (F15).
- **Role 2:**
  - instant-run budget margin (three DB transactions per stage);
  - 60 fps on a real display not yet measured;
  - Docker Compose and CI not built (P2);
  - batch scoring not built (P2);
  - dependence plot not built;
  - backup video and rehearsal pending (task 8).
- **Process:**
  - `main` carries the reverted roadmap (#15);
  - CCR-001 and CCR-003 are unanswered;
  - milestone M1 (contracts approved) is still open.

## 6. Milestones

| Milestone | Status |
|---|---|
| M1 contracts approved | Open (CCR-003, CCR-004) |
| M2 dataset feasibility | Role 1; no deliverable seen |
| M3 mock operational | Reached 2026-10-16 |
| M4 DB and simulation skeleton | Reached |
| M5–M6 stage modules | Reached (rule-based modules) |
| M7–M8 fusion model, end-to-end prediction | Integrated end to end; **no trained model** (#18) |
| M9 explainability | UI integrated; **placeholder values** (#19–#20) |
| M10 recommendation engine | UI integrated; **placeholder search and guard** (#21) |
| M11 what-if | Reached |
| M12 history and analytics | Reached on the Role 2 side; SPC and metrics wait on Role 1 |
| M13 E2E testing | Role 2 suite done; Role 1 test suite and evaluation reports not seen |
| M14 demo ready | Not yet: needs the A0 decision, the rehearsal and the video |

## 7. Sign-off

| Item | Role 2 | Role 1 |
|---|---|---|
| Capability matrix agreed | ☐ | ☐ |
| CCR-004 A0 option chosen (a–d) | ☐ | ☐ |
| Versions frozen for the demo | ☐ | ☐ |
| Demo script rehearsed, video recorded | ☐ | ☐ |
