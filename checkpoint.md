# checkpoint.md

Running record of work done so far. Updated by the Role 1 agent.

| Item | Value |
|---|---|
| Last updated | 2026-10-15 |
| Role | Role 1: AI/ML, Manufacturing Intelligence & Recommendation |
| Source of truth | `PROJECT_DEVELOPMENT_ROADMAP.md` (the roadmap), the Plan it references, and user overrides (which win) |
| Current phase | R1-P1: Domain Registry, Contracts Bootstrap, Dataset Discovery & Feasibility |
| Phases completed | 0 of 10 (R1-P1 is in progress) |
| Delivery mode | The agent supplies code and file paths. The user creates the files, runs them and reports results |

## 1. Working agreements (user instructions)

1. The roadmap is the only source of truth. User changes override it.
2. Work in phases and stop after each for confirmation.
3. Ask permission before sensitive actions: installs, git, downloads, deletions, web searches.
4. The agent gives code with file references. It does not implement on its own.
5. Python 3.12 inside a venv.
6. Write `checkpoint.md` after at least 3 phases. The user asked for this early draft.
7. **User override:** git setup and pushing are skipped for now.

## 2. Coordination with Role 2

- Role 2 sent `ROLE1_AGENT_INSTRUCTIONS.md` and asked two questions.
  - **Q1, existing contracts:** answered "partly". Contracts part 1 exists locally.
  - **Q2, CCR-002 (Role 2 bootstraps contracts):** **approved for the remainder only (Option A).**
- Role 2 is to bootstrap the remaining contracts, the registry files, the loader, the dependency graph and the 5 fixtures. They were asked not to touch the part 1 files.
- **Not yet done by Role 1:**
  - Reviewing Role 2's bootstrap against roadmap §7/§9.1.
  - Ticking approval in CCR-001 and CCR-002.
  - Removing the BOOTSTRAP headers and bumping versions.
- Role 2's `pyproject.toml`, `uv.lock` and `.python-version` are authoritative. The local `pyproject.toml` was a throwaway and is not to be pushed.

## 3. Completed so far

### 3.1 Contracts v0.1.0, part 1 (`backend/app/contracts/`)

| File | Content |
|---|---|
| `version.py` | `CONTRACTS_VERSION = "0.1.0"` |
| `enums.py` | Every enum from roadmap §7.2: `StageName` (plus `STAGE_ORDER`, `INTELLIGENCE_STAGES`, `sequence_index`), `RunStatus`, `StageSubstate`, `RiskLevel` (with `ordinal` 0–4), `PredictionLabel`, `ConstraintSeverity`, `AnomalyMethod`, `RunMode`, `SpeedFactor`, `InferenceBackend`, `SourceTier`, `DataProvenance`, `ParameterKind`, `CandidateFlag`, and `MachineType` (needed by `MachineProfile`) |
| `recipe.py` | `ProcessRecipe` with 23 canonical setpoint fields (frozen, `extra="forbid"`) and `RECIPE_FIELDS` |
| `context.py` | `MachineProfile`, `ProductContext`, `MaterialLot`, `RunContext`, `ProcessInput` with `.flat()` |
| `errors.py` | `IntelligenceError` and its typed subclasses with the roadmap §9.1 codes. Also `RegistryInvalidError` (`REGISTRY_INVALID`), which §8.4 uses |
| `__init__.py` | Exports `CONTRACTS_VERSION` only |
| `backend/tests/contract/test_contracts_part1.py` | 5 tests |

Design notes:
- `context.py` does only structural checks (types, `gt`/`ge`). Parameter limits are not hardcoded, per rule B6. They will live in `constraints.yaml`.
- `RiskLevel.ordinal` is a property. The `risk_ordinal` field belongs to `StageResult` and `PredictionResult` in the not-yet-written contracts.

### 3.2 Parameter dictionary (R1-P1 task 3)

- `docs/parameter_dictionary.md` covers setpoints, lot attributes, product context and machine context. Each row has unit, first stage, actionable flag, physical role and related defect modes. It states no numeric windows.
- `backend/tests/domain/test_parameter_dictionary.py` has 2 tests. They check that every recipe and context field is documented.

### 3.3 Reported test results

| Command | Reported result |
|---|---|
| `uv run pytest backend/tests/contract -v` (part 1) | All passed (5 tests) |
| `uv run pytest backend/tests/domain/test_parameter_dictionary.py -v` | All passed (2 tests) |

## 4. Not done yet (R1-P1 remainder)

| Task | Status | Notes |
|---|---|---|
| Contracts: `stage`, `anomaly`, `prediction`, `explanation`, `recommendation`, `sensitivity`, `interface` (`QualityIntelligence` Protocol) | Delegated to Role 2's bootstrap, pending my review | |
| `scripts/export_contract_schemas.py` and `docs/contracts/*.schema.json` | Not started | |
| `constraints.yaml` v1.0.0, `remedies.yaml`, `fleet.yaml` | Role 2 is bootstrapping placeholders. Literature values and citations are still mine | Every value stays `unvalidated` until cited |
| `constraint_loader.py`, `dependency_graph.py` and their tests | Role 2 is bootstrapping | |
| Five `recipe_*.json` fixtures | Role 2 is bootstrapping | |
| Literature survey and cited windows (task 4) | Not started | |
| Tier-1 dataset search and `docs/dataset_feasibility.md` | Not started. Needs web access, so **user approval is required first** | Record only what is verified from source |
| `docs/synthetic_generator_spec.md` | Not started | |
| ADR-001 to ADR-004 | Not started | |
| B3 import-boundary test (intelligence, ml, recommendation, domain) | Not started | |
| `docs/integration_status.md` entry for Role 1 | Not started | |
| Appendix B report for R1-P1 | Not started. The phase is not complete | |

## 5. Unverified or open items

- **Test environment:** it is not confirmed whether the passing tests ran in the throwaway venv or in Role 2's `uv sync` environment.
- **Lint and format:** `ruff check` and `black --check` have not been run on the part 1 files.
- **Not on the repository:** part 1 is not committed or pushed to `role-1-ai-ml`. This is deliberate, per the git skip. A local backup may exist at `..\r1_part1_backup`.
- **The Plan PDF** has not been seen by the agent. Defect-mode links in the dictionary come from the roadmap's quoted couplings and need ticking against the Plan.
- **Role 2's bootstrap** has not been seen. Compatibility with part 1 is unchecked.
- **No Tier-1 dataset** has been searched for or verified.
- **The 5 roadmap Appendix A items to watch:** UD-07 (overridden-breach display), UD-08 (RESET after FINAL_RESULT), UD-09 (cycle-time coupling), UD-11 (hybrid mode) and UD-19 (contracts ownership, amended for v0.1.0 by CCR-002). Role 2's file says UD-01 to UD-20 are all approved, but I have not seen that record.

## 6. Next steps (in order)

1. Send Role 2 the "final" reply, if not sent yet.
2. Step 1C: ADR-001 to ADR-004 and `docs/synthetic_generator_spec.md`.
3. Ask permission, then run the Tier-1 dataset search and write `docs/dataset_feasibility.md`.
4. Review Role 2's bootstrap against roadmap §7/§9.1, then adopt it and approve the CCRs.
5. Cited literature values, then the B3 test and the Appendix B report for R1-P1.
6. Wait for user confirmation before R1-P2.

## 7. Claim discipline (roadmap §1.7)

No model, dataset or physical-validation result exists yet. Nothing here claims performance, physical validity or causal effect.