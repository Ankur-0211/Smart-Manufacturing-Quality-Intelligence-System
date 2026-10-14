from __future__ import annotations

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

import app.db.models  # noqa: F401
from app.db.base import Base
from app.db.session import Database, alembic_head
from tests.db.conftest import alembic_config, migrate

EXPECTED_TABLES = {
    "machines",
    "products",
    "materials",
    "process_runs",
    "run_parameters",
    "stage_results",
    "predictions",
    "recommendations",
    "model_versions",
    "simulation_events",
}


def test_upgrade_from_empty_creates_all_tables(db_url: str) -> None:
    migrate(db_url)
    db = Database(db_url)
    tables = set(inspect(db.engine).get_table_names()) - {"alembic_version"}
    assert tables == EXPECTED_TABLES
    status = db.status()
    assert status.reachable and status.migrated and status.revision == alembic_head()
    db.dispose()


def test_migrations_match_models(db_url: str) -> None:
    """No drift between the ORM models and the migration history."""
    migrate(db_url)
    db = Database(db_url)
    with db.engine.connect() as conn:
        ctx = MigrationContext.configure(conn, opts={"compare_type": True})
        diffs = compare_metadata(ctx, Base.metadata)
    db.dispose()
    assert diffs == [], f"models differ from migrations; autogenerate a revision: {diffs}"


def test_downgrade_and_upgrade_round_trip(db_url: str) -> None:
    migrate(db_url)
    cfg = alembic_config(db_url)
    command.downgrade(cfg, "base")
    db = Database(db_url)
    assert set(inspect(db.engine).get_table_names()) <= {"alembic_version"}
    db.dispose()
    command.upgrade(cfg, "head")
    db = Database(db_url)
    assert db.status().migrated
    db.dispose()


def test_status_reports_unmigrated_database(db_url: str) -> None:
    db = Database(db_url)
    status = db.status()
    assert status.reachable and not status.migrated
    assert "alembic upgrade head" in status.detail
    db.dispose()


def test_indexes_from_plan_exist(db_url: str) -> None:
    migrate(db_url)
    db = Database(db_url)
    insp = inspect(db.engine)
    names = {i["name"] for t in EXPECTED_TABLES for i in insp.get_indexes(t)}
    db.dispose()
    assert {
        "ix_process_runs_created_at",
        "ix_process_runs_machine_id_created_at",
        "ix_process_runs_parent_run_id",
        "ix_stage_results_run_id_sequence_index",
        "ix_predictions_run_id",
        "ix_simulation_events_run_id_created_at",
        "ix_recommendations_run_id_request_id",
    } <= names
