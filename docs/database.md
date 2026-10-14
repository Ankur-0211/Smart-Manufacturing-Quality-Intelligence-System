# Database (Role 2, R2-P2)

The contract is roadmap §9.4. This file records the implementation.

## Engine and sessions

| Item | Value |
|---|---|
| ORM | SQLAlchemy 2.0, synchronous sessions (`app/db/session.py: Database`) |
| Dev/test DB | SQLite file `var/smqi.db` (`SMQI_DATABASE_URL`). Pragmas: `foreign_keys=ON`, `busy_timeout=5000`, WAL for file DBs |
| Demo DB (P2) | PostgreSQL, same models (install the `postgres` dependency group) |
| Transactions | Services own them via `with db.session() as s:` (commit on success, rollback on error). Repositories never commit |
| Health | `/api/v1/health` reports `database.available = true` only when reachable **and** at the Alembic head |

## Migrations

```bash
uv run alembic -c backend/alembic.ini upgrade head          # create / update the dev DB
uv run alembic -c backend/alembic.ini revision --autogenerate -m "<change>"   # after a model change
uv run alembic -c backend/alembic.ini -x db_url=sqlite:///./var/other.db upgrade head
```

- History: `0001_initial_schema` creates all 10 tables.
- **Never edit a migration after it is merged to `main`.** Add a new revision instead.
- Batch mode (`render_as_batch=True`) is enabled for SQLite ALTERs. Every constraint has a
  deterministic name (`app/db/base.py: NAMING_CONVENTION`).
- `tests/db/test_migrations.py` checks: upgrade from empty, **no drift** between models and
  migrations (`compare_metadata`), and the downgrade → upgrade round trip.

## Tables

All 10 tables of roadmap §9.4 exist, including every [P] addition. Two naming decisions:

1. **Canonical unit-suffixed column names** follow roadmap §7.1/§7.3–7.6, e.g.
   `machines.tonnage_ton`, `max_inj_pressure_bar`, `max_clamp_force_ton`. The Plan's §17.2 sketch
   (`tonnage`, `max_inj_pressure`) is overridden by the roadmap rule that DB, contracts, API and
   dataset names agree.
2. **Reference entities** have an internal integer `id` and a unique `code` / `lot_code`. The API
   and contracts expose only the codes (`MC-03`, `PP-JBOX-42`, `A-771`), per UD-10.
   `process_runs.machine_id` etc. are the internal integer FKs.

| Table | PK | Notes |
|---|---|---|
| `machines`, `products`, `materials` | int + unique code | `fleet_version` records the seed source |
| `process_runs` | UUID string | `context_snapshot` JSON freezes machine/product/lot values at creation. CHECK: `is_whatif ⇔ parent_run_id IS NOT NULL` |
| `run_parameters` | int, `run_id` unique (1:1) | One typed column per recipe field. Columns == `app/db/vocab.py: RECIPE_FIELDS` (tested) |
| `stage_results` | int | Unique (`run_id`, `stage_name`). `reused_from_stage_result_id` traces what-if reuse |
| `predictions` | UUID string | `run_id` is NULL for stateless `POST /predict` rows |
| `recommendations` | int | Unique (`request_id`, `option_rank`). `request_id` groups one `/recommend` call |
| `model_versions` | int | Unique (`name`, `semver`). The `mock` row is ensured by the seed |
| `simulation_events` | int | Unique (`run_id`, `seq`) |

CHECK constraints restrict enum-like columns (status, stage, risk level, label, mode, speed,
backend, machine type, model name) to the roadmap §7.2 vocabulary.

> `app/db/vocab.py` is a **temporary transcription** of roadmap §7.2/§7.6, because `app.contracts`
> has not been delivered yet. When it lands, the constants are replaced by imports.
> `tests/db/test_vocab_matches_contracts.py` (skipped today) then enforces equality.

## Immutability (`app/db/guards.py`, ORM events)

| Table | Rule | Error |
|---|---|---|
| `run_parameters` | never updated or deleted | `ImmutableRowError` |
| `predictions`, `stage_results` | never updated; deleted only by RESET of a **non-terminal** run | `ImmutableRowError` / `RunImmutableError` |
| `recommendations`, `simulation_events` | append-only | `ImmutableRowError` |
| `process_runs` | once `FINAL_RESULT`/`ABORTED`, only `scenario_label` may change | `RunImmutableError` (→ API `RUN_IMMUTABLE`) |

Repositories also refuse to **add** stage results or predictions to a terminal run.

## Event sequence numbers

`EventRepository.append` allocates `seq` with
`UPDATE process_runs SET last_seq = last_seq + 1 … RETURNING last_seq` inside the caller's
transaction. This makes `seq` strictly increasing and gap-free per run, even with concurrent
writers (tested with 8 threads × 40 events). Events are written before they are published
(roadmap §9.5.3). `after(run_id, seq)` serves SSE `Last-Event-ID` replay.

## Lineage and ordering

- `RunRepository.lineage(run_id)` returns the what-if tree.
- `created_at` can tie within one clock tick, and run ids are random UUIDs. Ordering therefore
  breaks ties with the insertion-ordered `run_parameters.id`.
- What-if reuse **copies** parent stage results into the child (`copy_for_child`), so a run never
  depends on another run's rows, and parents are never modified.

## Seed (`app/db/seed.py`)

```bash
uv run python -m app.db.seed                 # uses SMQI_FLEET_PATH (default backend/app/domain/fleet.yaml)
uv run python -m app.db.seed --fleet path/to/fleet.yaml
```

- Exit codes: `0` ok · `2` fleet file missing or invalid · `3` DB not migrated.
- Idempotent: existing codes are left untouched. Entries with `demo: false` are skipped. The
  `mock` model-version row is always ensured.
- `fleet.yaml` is **authored by Role 1**. Expected format (canonical contract field names):

```yaml
fleet_version: fleet-0.1.0
machines:
  - {machine_id: MC-03, machine_type: ELECTRIC, tonnage_ton: 180, max_inj_pressure_bar: 2000,
     max_clamp_force_ton: 180, installed_on: 2020-01-01, last_maintenance_on: 2026-09-01}
products:
  - {product_id: PP-JBOX-42, name: "PP junction-box housing", cavity_count: 4,
     nominal_shot_weight_g: 42, wall_thickness_mm: 2.5, projected_area_cm2: 100}
material_lots:
  - {material_lot_id: A-771, resin_grade: PP-H, mfi: 12, moisture_pct: 0.04, regrind_pct: 15,
     colourant_pct: 2, received_on: 2026-09-01}
```

Extra keys are ignored, so Role 1 may add generator-only fields such as machine bias vectors.
Test fixture: `backend/tests/fixtures/fleet_demo.yaml`.

## Not yet implemented (by design)

- Startup recovery (`abort_interrupted`) exists in the repository but is wired into app startup in
  R2-P4.
- Model-version registration from `models/registry.json` waits for Role 1's registry format
  (R1-P4).
