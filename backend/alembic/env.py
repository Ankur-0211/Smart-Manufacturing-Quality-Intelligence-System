"""Alembic environment (roadmap R2-P2). Batch mode is on for SQLite ALTER support."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import Engine

import app.db.models  # noqa: F401  (registers tables on Base.metadata)
from app.db.base import Base
from app.db.session import create_db_engine

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    # Priority: programmatic override (tests) > `alembic -x db_url=...` > application settings.
    override = config.attributes.get("db_url") or context.get_x_argument(as_dictionary=True).get(
        "db_url"
    )
    if override:
        return str(override)
    from app.core.config import get_settings

    return get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _run(connection)
        return
    engine: Engine = create_db_engine(_database_url())
    with engine.connect() as conn:
        _run(conn)
    engine.dispose()


def _run(connection: object) -> None:
    context.configure(
        connection=connection,  # type: ignore[arg-type]
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
