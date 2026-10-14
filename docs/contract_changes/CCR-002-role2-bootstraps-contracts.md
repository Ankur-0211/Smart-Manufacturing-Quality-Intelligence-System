# CCR-002: Role 2 bootstraps contracts v0.1.0, registry and fixtures (amends UD-19 once)

| Field | Value |
|---|---|
| Requested by | Role 2 |
| Date | 2026-10-15 |
| Status | proposed (waiting for Role 1) |
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

## Approvals

- Role 1 [ ] (also confirm: "no prior contracts/registry work exists")
- Role 2 [x]
- Project owner (user) [ ]
