# CCR-004: Findings from integrating Role 1's deliverables (1a22d7b)

| Field | Value |
|---|---|
| Requested by | Role 2 |
| Date | 2026-10-22 |
| Status | proposed (for Role 1). Role 2 has **not** edited any Role 1 file |
| Type | mixed: bug reports, contract gaps (MINOR) and one process issue |

Role 1's commit `1a22d7b` (PR #1) was merged into `role-2-application` on 2026-10-21 (`ea53a34`):
- **Role 1's versions, kept as owner:** contracts, `constraints.yaml`, `remedies.yaml`, `fleet.yaml`, the loader, the dependency graph and the facade.
- **Role 2's versions, kept as authoritative:** `core/config.py`, `pyproject.toml`, `uv.lock`, `.python-version` and the roadmap.

Role 2's code now runs on Role 1's interface: the mock, the hybrid router, the factory, the stage executor, validation, `/constraints` and `/predict`. `RealQualityIntelligence` can serve `SMQI_INTELLIGENCE_BACKEND=real` today.

The shared contract harness (`backend/tests/contract/test_interface_contract.py`) now runs **both** the mock and the real facade:
- The real facade passes the equivalence, determinism and per-fixture rule tests.
- It fails the invariant checks listed below. Those tests are marked strict `xfail` with this CCR's numbers, so they start failing as soon as the gaps are fixed. Then the marker must be removed.

## A. Defects (please fix)

1. **The 4-cavity product can never pass.**
   - With the nominal recipe, `PP-JBOX-42-4C` needs about 207 t of clamp force (HC-002).
   - The largest machine in `fleet.yaml` is rated 175 t, and the clamp window allows at most 220 t.
   - So every run of that product is BLOCKED at INJECTION on every machine. Either the product data, the HC-002 heuristic or the fleet needs adjusting.
2. **The label is forced to FAIL on any critical breach.**
   - `facade.py` sets `label = FAIL if p_fail >= threshold or any_critical`. Example: FAIL at `p_fail=0.236` with threshold 0.35.
   - Roadmap §7.12 keeps `label` as the model's decision (`FAIL` iff `p_fail >= threshold_used`). A critical breach is shown separately:
     - `risk_level=CRITICAL`;
     - a `CRITICAL_CONSTRAINT_OVERRIDDEN` caveat;
     - and the UI's **NOT RELEASABLE** banner (UD-07).
   - The UI already does this, so a forced FAIL hides the model's actual decision.
3. **`stage_risk_mass` doesn't sum to 1** (± 1e-6, §7.12). This happens for the `recipe_high_moisture`, `recipe_melt_ceiling_breach` and `recipe_short_cooling` fixtures.
4. **`required_clamp_force_ton` has no `indicator_provenance` entry.** INJECTION reports it as an indicator, but §7.9 needs one provenance entry per indicator key. It is added by `check_hard_constraints` after the stage builds its provenance map.
5. **Limits are written into the Python code.**
   - `constraint_loader.py` hard-codes the CPL-002 delta (120 °C), the HC-005 cushion band (2–15 mm), the HC-003 headroom factor (0.90) and the HC-004 formula (2·s²).
   - `constraints.yaml` has a different HC-005 description, and the `constants` block of CPL-002 is not read.
   - §8.6 says there must be no other copy of any limit. Please read these from the registry.
6. **No windows for lot attributes.**
   - `constraints.yaml → parameters` has only the 23 setpoints. There are no entries for `mfi`, `moisture_pct`, `regrind_pct` or `colourant_pct` (§7.5, §8.3).
   - As a result, `POST /materials` can only type-check those values. Role 2's validation picks up their windows automatically once entries exist.
7. **`fleet.yaml`:** with the nominal recipe (120 t clamp), CPL-003 rejects MC-03 (110 t max). That is acceptable if intended, but the nominal recipe can't be used on that machine.

7a. **Recommendations without predicted benefit** (found 2026-10-22 through `POST /recommend`).
    - For the nominal run (MC-02 / PP-JBOX-42 / A-771, p_fail 0.236), all three candidates predict exactly 0.236. They are labelled Minimal change, Balanced and Aggressive, and change 1–3 parameters.
    - Roadmap §7.15 and Plan §14 rank candidates by improvement. An option with zero predicted improvement should either not be offered, or come with an `empty_reason` / note saying nothing better was found.

## B. Contract gaps against roadmap §9.1 (please add, or agree to drop)

8. **`QualityIntelligence` is missing four methods.**
   - `run_all_stages` and `build_features`: Role 2 now loops `run_stage` itself.
   - `detect_anomaly` and `spc_check` (P1).
   - Also, `explain` takes `(inp, stage_results, prediction)` instead of `(inp, stage_results, top_k)`.
9. **`IntelligenceVersionInfo` has only one `model_version`.**
   - §9.1 also lists `module_versions`, `fusion_model_version`, `anomaly_model_version`, `feature_schema_hash`, `inference_backend` and `capabilities`.
   - Role 2 now uses `model_version` as every stage's cache version and derives the backend from `is_mock`. Per-stage versions are needed so a changed stage module invalidates cached results correctly.
10. **`capabilities()` uses different keys.**
    - It returns `evaluate` and `spc_check`; §9.1 uses `spc` and has no `evaluate`.
    - `spc_check` is reported as `true`, but no such method exists.
11. **`stage_inputs(stage)` returns parameters *first* consumed by a stage.**
    - §8.4 / §7.10 define it as the stage's full input slice. For example, PLASTICIZING also reads `mfi` and `moisture_pct`.
    - Role 2 now keys its stage cache on the full input, which is safe either way, and uses `stage_inputs` for display only.
12. **The loader returns plain dicts and tuples** (`check_box` returns `(ok, min, max)`; parameters are dicts), where §8.4 specifies typed specs and `ConstraintBreach` lists.
    - Role 2 has adapted to this. Please confirm it is the intended API, and Role 2 will update §8.4 to match.
13. **`ConstraintRegistry` has no `invalidated_stages()`.**
    - It's a module function in `dependency_graph.py` with its own hard-coded field-to-stage map, which also includes `QUALITY_INSPECTION`.
    - What-if (R2-P7) will call that function. Please keep the map in sync with `constraints.yaml → parameters[*].stage`, or derive it from there.
14. **Contract models dropped the §7.9/§7.12 invariants** (risk ordinal = level, label vs threshold, `is_mock` vs backend and so on). They are checked by the harness instead, which is fine. Please run it with `uv run pytest backend/tests/contract`.

## C. Process

15. **`main` has the roadmap reverted to the 1.0.0 draft.** Role 1's commit replaced v1.0.1 (Appendix A approved 2026-10-15) with a stale copy. `role-2-application` keeps 1.0.1; please don't overwrite it again.
16. **Pushes to `main` should go through a PR that both roles review**, so changes like #15 get caught.
17. **Role 1 files don't follow the repo's ruff/format settings.** Role 2 excludes Role 1-owned paths from its lint and type gates (`pyproject.toml`); please run `uv run ruff format` / `ruff check` on them.

## Fixtures

Role 2 rebuilt the five `recipe_*.json` contract fixtures from Role 1's fleet and nominal recipe: MC-02, PP-JBOX-42, and lots A-771 or D-105. With Role 1's registry, each fixture triggers exactly the rule it is named after (none, HC-001, HC-004, HC-002, HC-006). Role 1 owns the fixtures from now on.
