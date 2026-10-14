# Instructions for the Role 1 coding agent

**From:** Role 2 (Backend, Simulation, Database & Frontend)
**To:** Role 1 (AI/ML, Manufacturing Intelligence & Recommendation) and the coding agent working for Role 1
**Date:** 2026-10-15
**Status:** read this **before** starting or continuing R1-P1

Give this whole file to your coding agent together with the instruction
"Follow ROLE 1 — AI/ML, Manufacturing Intelligence, and Recommendation Engineer."

---

## 0. Answer these two questions to Role 2 first (human to human)

1. **Have you already written any of `backend/app/contracts/`, `backend/app/domain/constraints.yaml`, the
   registry loader, or contract fixtures?**
   - **Yes:** push them to `role-1-ai-ml` now, even unfinished. Role 2 will build on your version and
     will **not** bootstrap anything. Skip Section 2 and go to Section 4.
   - **No:** reply "go ahead". Role 2 bootstraps them (Section 2) and you adopt them (Section 3).
2. **Do you approve CCR-002** (`docs/contract_changes/CCR-002-role2-bootstraps-contracts.md`)?
   It amends approved decision UD-19 for **v0.1.0 only**. Ownership stays with you afterwards.

Until both answers are given, **neither role edits** `backend/app/contracts/` or `backend/app/domain/`.
This prevents two competing versions of the shared contracts.

---

## 1. Project context (read in this order)

1. `PROJECT_DEVELOPMENT_ROADMAP.md`: the single source of truth. Read all of it. **Appendix A
   decisions UD-01 to UD-20 are all APPROVED.** Role 1's phases are in Section 11.
2. `docs/integration_status.md`: which shared artifacts exist, and what is real vs mock.
3. `docs/contract_changes/`: open change requests. CCR-001 and CCR-002 need your review.
4. `README.md`: setup commands.

**Repository:** `https://github.com/Ankur-0211/Smart-Manufacturing-Quality-Intelligence-System`. This is
the **only** remote. Do not create or use any other.

| Branch | Who | Rule |
|---|---|---|
| `main` | both | Integration only, via PR with all checks green |
| `role-1-ai-ml` | **you** | All Role 1 work goes here (or short `r1/<phase>-<topic>` branches merged into it) |
| `role-2-application` | Role 2 | Do not push here |

**Toolchain:**
- Windows-compatible commands.
- Python **3.12** via `uv` (`.python-version` is committed).
- Install with `uv sync --frozen --group ml`.
- Checks: `uv run pytest`, `uv run ruff check .`, `uv run black --check .`.
- Add dependencies only through `pyproject.toml` + `uv.lock` in the same commit. Role 1 owns the `ml` and `dl` groups.

**What Role 2 has already built** (branch `role-2-application`, phase R2-P1):

| Path | Content |
|---|---|
| `pyproject.toml`, `uv.lock` | Root project. Packages: `backend/app` (import name `app`). **Add `"ml_pipeline"` to `[tool.hatch.build.targets.wheel] packages` when you create that package** |
| `backend/app/{main,core,api,schemas}` | FastAPI skeleton, settings (`SMQI_*`), error envelope, `/api/v1/health` |
| `backend/tests/contract/test_interface_contract.py` | Shared contract-test harness. It loads `backend/tests/contract/fixtures/recipe_*.json` with `ProcessInput.model_validate_json(...)` and checks the roadmap §7 invariants |
| `backend/tests/test_import_boundaries.py` | Role 2 half of rules B1/B2/B7. **You add the B3 half for your packages** |
| `frontend/` | React 18 SPA scaffold |

To see Role 2's code from your branch: `git fetch origin && git merge origin/role-2-application`.
Do this once at the start, then at each weekly integration checkpoint (roadmap §10.1).

---

## 2. What Role 2 will bootstrap (only if you answered "go ahead")

Role 2 transcribes roadmap Sections 7, 8.2–8.4 and 9.1 into code **without inventing anything beyond
the roadmap**. It is tagged `CONTRACTS_VERSION = "0.1.0"` and `registry_version: constraints-0.1.0`.

| File | Content | Marked as |
|---|---|---|
| `backend/app/contracts/*.py` | Every enum and model in roadmap §7, errors and the `QualityIntelligence` Protocol in §9.1 | `# BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1` |
| `backend/app/domain/constraints.yaml` | Section 8.2 structure with **Section 8.3 placeholder values**. Every entry is `provenance: unvalidated`, `citation: null` | Header comment says the same |
| `backend/app/domain/remedies.yaml` | The remedy rules listed in roadmap R1-P1 task 7 | `unvalidated` |
| `backend/app/domain/fleet.yaml` | Minimal **demo** fleet: machines `MC-01..MC-04`, product `PP-JBOX-42`, lot `A-771` and 2–3 more lots. Values come from roadmap §5 examples / §8.3 nominals | `synthetic`, demo only |
| `backend/app/domain/constraint_loader.py`, `dependency_graph.py` | The Section 8.4 API, with `invalidated_stages` derived from `stage_inputs` | — |
| `backend/tests/contract/fixtures/recipe_*.json` | The 5 named recipes from roadmap R1-P1 task 8 | — |
| `backend/tests/domain/test_constraint_loader.py`, `test_dependency_graph.py` | The tests listed in roadmap R1-P1 task 10 | — |

Role 2 pushes these to `role-2-application`, records them in `docs/integration_status.md`, and tells you.

---

## 3. Your job after the bootstrap lands (adopt, do not re-create)

1. **Merge, don't rewrite.** Run `git fetch origin && git merge origin/role-2-application` into
   `role-1-ai-ml`. **Do not delete and re-create** the bootstrapped files; edit them in place.
2. **Review the contracts against roadmap §7/§9.1.** Fix any mistakes directly. Then:
   - remove the `BOOTSTRAP` header comments (you now own the files);
   - bump `CONTRACTS_VERSION` to `0.1.1` if anything changed;
   - note each change in `backend/app/domain/CHANGELOG.md`.
   - Changes that **add** something (MINOR) are fine. Changes that **rename or remove** a field, enum
     value or method (MAJOR) need a new CCR and Role 2's approval, because Role 2 code will already
     depend on them.
3. **Own the registry values.** Do your literature work (roadmap R1-P1 tasks 3–6) and replace
   placeholder numbers with cited values, or keep them `unvalidated`/`heuristic`.
   - Each value change is a registry **MINOR** bump (`constraints-0.2.0`, …) plus a CHANGELOG entry.
   - **Do not rename parameters.** Names are canonical across the DB, API and UI.
4. **Own `fleet.yaml`.** Extend it to the 6–10 machines your generator needs. Keep `MC-01..MC-04`,
   `PP-JBOX-42` and `A-771`, because the Role 2 seed and demo use them.
   - Keep the format documented in `docs/database.md` → "Seed": top-level `fleet_version`,
     `machines`, `products`, `material_lots`, with canonical field names.
   - Extra keys are ignored, so generator-only fields are fine.
   - Mark entries the app should not seed with `demo: false`.
   - Check your file with `uv run python -m app.db.seed --fleet backend/app/domain/fleet.yaml` against a migrated dev DB.
5. **Own the fixtures.** Keep the 5 `recipe_*.json` file names and their intent:

   | Fixture | Intent |
   |---|---|
   | `recipe_nominal` | nominal recipe |
   | `recipe_melt_ceiling_breach` | melt above the degradation ceiling → BLOCK |
   | `recipe_short_cooling` | short cooling time |
   | `recipe_clamp_insufficient` | clamp force too low → BLOCK |
   | `recipe_high_moisture` | high moisture → BLOCK |

   Later phases add real-output fixtures next to them (roadmap §10.2).
6. **Review CCR-001** (two new API error codes, additive) and CCR-002. Tick your approval box in each
   file and set the status.
7. Continue the **rest of R1-P1**, which Role 2 does **not** touch:
   - parameter dictionary;
   - Tier-1 dataset search: verify licence and real columns from the source; never claim a dataset you did not verify;
   - feasibility decision;
   - synthetic generator spec;
   - ADR-001…004.
8. Add the **B3 import-boundary test**: `app/intelligence`, `app/ml`, `app/recommendation` and `app/domain`
   must not import `app.db`, `app.api`, `app.services`, `app.engine`, `sqlalchemy` or `fastapi`.
9. Update `docs/integration_status.md` (shared-artifact versions, your environment row).

**Acceptance for this adoption step:**
- `uv run pytest` is green on `role-1-ai-ml` after merging `role-2-application`.
- The contract harness runs, so the tests are no longer skipped for the "contracts missing" reason.

---

## 4. If you already started the contracts yourself

- Push your work to `role-1-ai-ml` immediately and tell Role 2. Role 2 will merge it and build on it.
- Make sure the field names match roadmap §7 **exactly**. The fixtures must be loadable with
  `ProcessInput.model_validate_json`.
- Then continue with Section 3, items 3–9.

---

## 5. Standing rules for your agent

- Implement **only Role 1** files (roadmap §6.3). Never edit `backend/app/{api,schemas,services,engine,db,core,intelligence_mock}`,
  `frontend/`, `docker/` or `scripts/` (except your own ML scripts).
- Any change to a shared contract follows the CCR procedure (roadmap §10.4). **No silent changes.**
- Run the phase's tests before calling a phase done. Report with the Appendix B template, then stop
  and ask before the next phase.
- After **every 3 completed phases** (R1-P3, R1-P6, R1-P9), create or update `checkpoint.md` in the
  repo root listing all tasks done so far.
- Never claim model performance, physical validation or causal effects that were not measured
  (roadmap §1.7 four-claim rule).
