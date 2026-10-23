# System test report — roadmap R2-P10

**Date:** 2026-10-23
**Branch:** `role-2-application` (commit after `f85dde6`). Read with [`final_integration_report.md`](final_integration_report.md): CCR-004 A0 affects the meaning of several results below
**Intelligence:** Role 1's `fusion-1.0.0` (pure-Python facade, no model bundle), `constraints-1.0.0`, contracts 0.1.0
**Machine:** Windows 11, 12 CPUs, Python 3.12.10, Node 24.14.1, Chromium (Playwright 1.64.1)

The report states results as measured, including the targets that were missed or could not be measured.

## 1. Test inventory

| Layer | Command | Result |
|---|---|---|
| Backend unit, API, contract and integration | `uv run pytest` | **544 passed**, 5 xfailed. The xfails are strict and tied to CCR-004 #3–#4 (Role 1 invariants) |
| … of which fault injection (task 3) | `backend/tests/e2e/test_fault_injection.py` | 28 passed |
| … of which journey integrity (tasks 4–5) | `backend/tests/e2e/test_journey_integrity.py` | 2 passed |
| Frontend unit and screen tests | `npm test` (Vitest) | **109 passed** (22 files) |
| End-to-end, real intelligence | `npm run test:e2e` (Playwright, `scripts/e2e_server.py`) | **9 passed** |
| Static checks | ruff, `ruff format`, mypy (strict), ESLint, Prettier, `tsc -b`, `npm run check:api` | clean |

**Playwright specs:**
- `journey.spec.ts`: the §15.4 journey and an instant run.
- `special-paths.spec.ts`: BLOCKED → override, abort, reset, SSE drop → polling.
- `demo.spec.ts`: replays `docs/demo_script.md`.
- `perf.spec.ts`: animation guard.

## 2. Acceptance journey checklist (roadmap §15.4)

| Requirement | Status | Evidence |
|---|---|---|
| Critical breaches cannot silently produce an ordinary confident PASS | ✓ | `special-paths.spec.ts`: melt 290 °C gives BLOCKED at Thermal, then override, then **NOT RELEASABLE**, risk CRITICAL, caveat `CRITICAL_CONSTRAINT_OVERRIDDEN` (UI and API); `demo.spec.ts` covers the same flow from History |
| Invalid recommendation candidates are rejected | **Not met** | Box, couplings and hard constraints are really checked. But `distribution`, `step_size` and `stability` are hard-coded passes in Role 1's facade (CCR-004 #21, #7b), and the options are three fixed edits, so no rejection by those checks can occur. The UI cross-checks `max_step_change` |
| What-if runs do not overwrite original runs | ✓ | `test_journey_integrity.py` hashes every row of the original runs (run, parameters, stage results, prediction, events); the hashes are identical after what-ifs, saved scenarios two levels deep, compare, sensitivity, recommend, lineage and analytics. Finished runs refuse reset, start and abort (409). Children carry `parent_run_id`. `journey.spec.ts` also checks the base run's API state byte for byte |
| Prediction and operational risk are different concepts | ✓ | Separate result-card blocks asserted in `journey.spec.ts` and the ResultCard tests; analytics labels shares as "model-predicted FAIL" |
| The frontend uses actual backend outputs | ✓ | `journey.spec.ts` compares the result card and quality-stage label with `GET /simulation/runs/{id}` for the same run; `demo.spec.ts` checks the demo numbers end to end |
| Model artifacts and versions are traceable | **Partial** | Each prediction references a `model_versions` row, and Model Info shows the version. Bundle SHA-256, git SHA, dataset hash and metrics are **not reported** by Role 1's facade (CCR-004 #7d); Model Info shows "not reported" |
| Mock is never mistaken for inference | ✓ for the mock; **✗ for `fusion-1.0.0`** | The real facade returns placeholder attributions, calibration and guard results labelled as computed (CCR-004 A0, #18–#21); the UI shows them as received. For the mock itself: | `SMQI_ENV=demo` refuses mock (`test_fault_injection.py`, config tests). The MOCK banner and `is_mock` are tested in Vitest. Analytics excludes MOCK-scored runs by default (`test_journey_integrity.py`) |
| Not described as a physically validated digital twin | ✓ | The software-simulation disclaimer is on every screen (App test). A text audit of `frontend/src` for "digital twin", "physically validated", "guarantee", "root cause", "proven" or "validated process" found only the mandatory recommendation disclaimer, which uses the phrase in the negative |

## 3. Special paths (task 2)

| Path | Status | Evidence |
|---|---|---|
| BLOCKED → override → NOT RELEASABLE | ✓ | `special-paths.spec.ts`, `demo.spec.ts` |
| Abort mid-run | ✓ | ABORTED with `Operator abort`; the completed stages stay inspectable in run detail, and the result card says there is no prediction |
| Reset | ✓ | A stepwise run returns to INITIALIZED with no stage results |
| SSE drop → polling fallback | ✓ | Every events request is aborted at the network layer; the view shows `live (polling)` and finishes with the API's numbers |
| Server killed mid-run → ABORTED, partial state inspectable | ✓ (API level) | `test_simulation_api.py` restarts the app mid-run and gets ABORTED with `SERVER_RESTART`. Playwright cannot restart its own web server, so this is not a browser test |

## 4. Fault injection (task 3)

The faults are injected into the live intelligence instance the app serves (`test_fault_injection.py`).

| Fault | Expected | Result |
|---|---|---|
| Model not loaded (`predict`, `evaluate`, `version_info` raise `MODEL_NOT_LOADED`) | 503 with code, message and hint; `/health` answers 200 with `status: degraded`, intelligence component unavailable, `model_loaded: false` | ✓ (after fix F1 below) |
| Each of the 10 typed intelligence errors | HTTP status from roadmap §9.3.4, stable code, `field` passed through | ✓ (10 cases) |
| Unexpected exception inside intelligence | 500 `INTERNAL_ERROR`, no internals (paths, file names) in the body | ✓ |
| Stage fails mid-run | Run ABORTED with `abort_reason ERROR:<code>`; the `run.error` event carries the code; earlier stages kept; further commands get 409 | ✓ (after fix F2 below) |
| Invalid parameters | `PARAM_OUT_OF_RANGE` with the field, `COUPLING_VIOLATION`, `UNKNOWN_PARAMETER`, `REFERENCE_NOT_FOUND`, on both `/simulation/runs` and `/predict` | ✓ |
| Unknown ids | 404 `RUN_NOT_FOUND` on run, lineage, start, what-if, recommend and compare; `PREDICTION_NOT_FOUND` on explain | ✓ |
| Rate limit (`/recommend`, limit 2/min) | Third call gets 429 `RATE_LIMITED` with a retry hint | ✓ |
| Missing or invalid registry; demo with mock | The app refuses to start (`RegistryInvalidError`, settings validation) | ✓ |

**Not testable yet:** a missing or corrupted **model bundle** and a MANIFEST hash mismatch. Role 1's facade loads no artifacts (R2-P9). The injected `MODEL_NOT_LOADED` above exercises the same handling path.

## 5. Analytics exclusions (task 5)

`test_journey_integrity.py` builds one database with 2 MOCK-scored runs (from a mock-backend app), 2 real runs and 1 real what-if child.

- **Defaults:** `runs = 2`, `excluded = {whatif: 1, mock: 2, unfinished: 0}`, predicted FAIL share 0.5.
- **Toggles:** `include_whatif` gives 3 runs, `include_mock` gives 4, both give 5.
- **Breakdowns:** they follow the same defaults.
- **History:** keeps every run.

The Analytics screen states the active exclusions (`journey.spec.ts`).

## 6. Benchmarks (task 6, Plan §24.4)

Command: `uv run python scripts/benchmark.py --n 60`.
- The intelligence and API rows run in-process.
- SSE and concurrency use a real uvicorn server on a socket.

This is the last of five runs on 2026-10-23; times in ms.

| Operation | p50 | p95 | max | Budget | Result |
|---|---|---|---|---|---|
| intelligence `run_stage` (per stage) | 0.0 | 0.1 | 0.1 | p95 < 5 | ✓ |
| intelligence `evaluate` (no explanation) | 0.3 | 0.7 | 0.9 | p95 < 150 | ✓ |
| intelligence `explain` | 0.1 | 0.1 | 0.2 | p95 < 300 | ✓ |
| API `POST /predict` (prediction) | 13.0 | 14.0 | 15.4 | p95 < 150 | ✓ |
| API `GET /predict/{id}/explain` (SHAP) | 7.2 | 8.0 | 8.4 | p95 < 300 | ✓ |
| API `POST /whatif` (persist=false) | 14.0 | 15.7 | 16.3 | < 100 | ✓ |
| API `POST /whatif/sensitivity` (40 points) | 28.0 | 29.4 | 29.4 | < 1 500 | ✓ |
| API `POST /recommend` | 23.0 | 24.4 | 24.4 | < 5 000 | ✓ |
| Instant auto run, server-side started → completed | 250.8 | **339.6** | 365.9 | p95 < 300 | **✗ in this run** (see below) |
| SSE jitter at 1x, \|stage-start interval − 1 500\| | 46.6 | 57.7 | 61.1 | < 100 | ✓ |
| 10 concurrent auto runs (instant), wall time | 2 513 | 2 730 | 2 730 | all complete, no interleaving errors | ✓ every run FINAL_RESULT, contiguous `seq`, stage events in order |
| API full run over HTTP (create, start, 6 advances) | 262.0 | 281.9 | 328.9 | — | (context for the row above) |
| `GET /analytics/summary` | 13.9 | 16.0 | 24.0 | — | |

**The instant-run budget is borderline.** Over today's three runs with this row, its p95 was 219 ms, then 250 ms (the `synchronous=NORMAL` experiment below), then 340 ms. On 2026-10-22 the comparable HTTP run was 111 ms, so the machine's load clearly moves this number.

The intelligence takes under 1 ms per stage; the rest is persistence and scheduling. Each stage does three separate DB transactions (load, `stage.started`, result plus `stage.completed`) and four thread hops, about 33 ms per stage here. SSE jitter shows the same ~40 ms offset.

What we ruled out: switching SQLite to `synchronous=NORMAL` made no measurable difference, so it is not fsync, and the change was not kept. Merging the per-stage transactions is the candidate fix. It must keep `stage.started` persisted before the compute, because that ordering is the event contract.

**60 fps animation: not met in headless, and not measured on a real display.**
- `perf.spec.ts` counts `requestAnimationFrame` during a 1x run. Headless Chromium (software rendering, no GPU) delivers 60.0 fps idle and **48–54 fps** during the run, with no frame over ~50 ms and no long tasks.
- A CPU profile of the run shows the main thread about 93 % idle. The app's own JavaScript costs a few ms over the 10 s run; the remaining samples are mostly Playwright's selector engine. So the frames are lost in paint and compositing, not in application code.
- The roadmap's 60 fps check is with DevTools on a real display. It could not be done here: Playwright can't launch a headed browser in this environment, and the in-app browser stopped rendering frames while hidden.
- **To do on the demo machine:** DevTools → Performance during a 1x run, then record the result here.
- `perf.spec.ts` is kept as a regression guard: ≥ 40 fps and no frame ≥ 100 ms, headless.

## 7. Defects found and fixed during R2-P10

| # | Defect | Found by | Fix |
|---|---|---|---|
| F1 | `/health` called `version_info()` unguarded, so a model that stops loading made health a 500 instead of "degraded" | fault injection | Health catches typed intelligence errors, marks the intelligence component unavailable with the code, and reports the version info resolved at startup |
| F2 | A stage failing with a typed intelligence error was recorded as `INTERNAL_ERROR`, losing the stable code | fault injection | `run.error` and `abort_reason` keep the intelligence error's code (`ERROR:MODEL_NOT_LOADED`) |
| F3 | Explainability right after a live instant run said "no prediction yet": it was served the run state cached at start (5 s freshness) | `demo.spec.ts` | When a live run ends, Process Control refreshes the run, history, lineage and analytics queries |
| F4 | An aborted run's result card said "Awaiting the quality inspection stage" | `special-paths.spec.ts` | It now says the run was aborted before quality inspection |
| F5 | Two Vitest tests were timing-sensitive under load (lazy chart import; typing speed) | full-suite runs during builds | Chart modules preloaded in the test setup; the debounce test uses synchronous edits |

## 8. Open items

- **Role 1** (CCR-004):
  - recommendations predict no gain and ignore the main driver (#7a);
  - the step-size guard passes oversized steps (#7b);
  - `flip_point` is not the nearest crossing (#7c);
  - no metrics or provenance (#7d);
  - no `spc_check` (#10);
  - stage risk mass doesn't always sum to 1 (#3–#4);
  - the model bundle and MANIFEST (R2-P9).
- **Role 2:**
  - instant-run budget margin (merge the per-stage transactions);
  - the 60 fps DevTools measurement on the demo machine;
  - backup video and rehearsal (task 8, needs the presenters);
  - final integration report (task 9);
  - joint sign-off with Role 1.
