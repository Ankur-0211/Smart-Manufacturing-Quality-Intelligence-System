# CCR-002: Role 2 bootstraps contracts v0.1.0, registry and fixtures (amends UD-19 once)

| Field | Value |
|---|---|
| Requested by | Role 2 |
| Date | 2026-10-15 |
| Status | **approved by Role 1 for the remainder only** (2026-10-15, relayed by the project owner); partially delivered |
| Type | process / ownership (no field, endpoint or semantic change) |

## Problem

Role 2's R2-P1 tasks 8–11 are blocked on three R1-P1 outputs:
- `backend/app/contracts/` v0.1.0;
- `backend/app/domain/` registry + loader + demo fleet;
- contract fixtures.

R2-P2…R2-P4 also need these types for DB JSON columns, the state machine and API schemas. Role 1's
delivery date is unknown. All three items are already fully specified in roadmap §7, §8.2–8.4 and
§9.1, so producing them is transcription, not design.

## Proposed change

1. **One-time exception to UD-19 for v0.1.0 only.** Role 2 transcribes the roadmap into:
   - `app/contracts` (`CONTRACTS_VERSION = "0.1.0"`);
   - `constraints.yaml` (`constraints-0.1.0`, every value `provenance: unvalidated`);
   - `remedies.yaml`;
   - a minimal demo `fleet.yaml`;
   - `constraint_loader.py` and `dependency_graph.py`;
   - the 5 named recipe fixtures and the loader/graph tests from roadmap R1-P1 task 10.

   Nothing beyond the roadmap is invented. Every file carries a `BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1` header.
2. **Ownership does not change.** Role 1 adopts the files as primary owner, reviews them against the
   roadmap, removes the headers, and from then on owns all values, citations and further versions.
3. **Role 1 must not re-create these files.** Edits happen in place. MAJOR changes (renames,
   removals) need a CCR, because Role 2 code will depend on v0.1.0.
4. **Precondition:** Role 1 confirms it has **not** already written any of these files. If it has,
   this CCR is withdrawn and Role 1's version is used instead.

## Affected

- Process only. Files: `backend/app/contracts/**`, `backend/app/domain/**`, `backend/tests/contract/fixtures/**`, `backend/tests/domain/**`.
- R1-P1 tasks 1, 4–9 (partial) become "review and adopt" for Role 1. Literature values, dataset
  search, feasibility, generator spec and ADRs stay entirely with Role 1.

## Compatibility

No contract content differs from the approved roadmap. Contract tests will run for the mock as soon
as it lands.

## Role 1 answer (2026-10-15)

1. Role 1 has already written **contracts part 1**: `version`, `enums`, `recipe` (23 fields),
   `context` (MachineProfile, ProductContext, MaterialLot, RunContext, ProcessInput), `errors`,
   plus `tests/contract/test_contracts_part1.py`. It will push them to `role-1-ai-ml`.
   **Role 2 must not touch these files.** Mistakes found in them go to a CCR or a direct message.
2. CCR-002 is approved **for the remainder only**, using the exact names of roadmap §7 and §9.1.
   Role 1 will review, adopt, remove the BOOTSTRAP headers and bump versions.
3. Role 2's `pyproject.toml`, `.python-version` and `uv.lock` are authoritative. Role 1 adds
   `ml_pipeline` and the `ml` group when it creates that package.

## Delivery status

| Item | Status |
|---|---|
| `constraints.yaml`, `remedies.yaml`, `fleet.yaml`, `CHANGELOG.md` | **Delivered** (`constraints-0.1.0`, `remedies-0.1.0`, `fleet-0.1.0`) |
| 5 recipe fixtures (`recipe_*.json`) | **Delivered** (ProcessInput JSON shape per §7.3–7.7) |
| Data-level tests (`backend/tests/domain/test_registry_data.py`) | **Delivered** (24 tests) |
| Remaining contracts: stage, anomaly, prediction, explanation, recommendation, sensitivity, `interface.py` (Protocol) | **Waiting.** They import part-1 enums and types, so they are written after Role 1's part 1 is pushed and merged, against the real files |
| `constraint_loader.py`, `dependency_graph.py` + loader tests (R1-P1 task 10) | **Waiting**, same reason (they use `StageName`, `ConstraintSeverity`, …) |

## Approvals

- Role 1 [ ] (approved verbally for the remainder; box to be ticked by Role 1 after merge)
- Role 2 [x]
- Project owner (user) [x]
