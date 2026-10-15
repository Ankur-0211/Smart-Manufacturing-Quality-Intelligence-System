# Domain registry changelog

Every change to `constraints.yaml`, `remedies.yaml` or `fleet.yaml` gets an entry and a version bump
(roadmap §8.1, §8.6). Owner: Role 1. Changes go through a CCR with both roles' approval.

## constraints-0.1.0 · remedies-0.1.0 · fleet-0.1.0 (2026-10-15): bootstrap (CCR-002)

- Written by Role 2 under CCR-002 (approved by Role 1 for the items Role 1 had not written yet).
- **Pure transcription** of roadmap §7.10, §8.2, §8.3 and §14.3. Every numeric value is a
  PROPOSED placeholder (`provenance: unvalidated`, `citation: null`), except `cavity_count` and
  `nominal_shot_weight_g`, which cite the project plan §2.2.
- `stage_inputs` added as the single source for the stage slices. Each parameter's `stage` must be
  the earliest consuming stage. Consequence: `mold_temp_c` and `wall_thickness_mm` start at PACKING
  (as roadmap §7.6 / R1-P1 tech details state).
- Rule `kind` vocabulary documented in the file header, for the loader to interpret.
- Demo fleet: MC-01…MC-04, PP-JBOX-42, lots A-771, A-772, B-310, A-790 (wet lot for the
  high-moisture fixture). All synthetic.
- **Role 1 to do on adoption:** review against the roadmap; replace placeholders with cited values or
  keep them flagged; remove the BOOTSTRAP headers; bump versions; extend the fleet for the generator.
