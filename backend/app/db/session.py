"""Engine and session management (SQLAlchemy 2.0, synchronous).

FastAPI handlers call the DB via sync sessions; long work runs in the threadpool, so the event
loop (SSE) is never blocked.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import Engine, create_engine, event, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

import app.db.guards  # noqa: F401  (installs immutability guards)

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def _sqlite_pragmas(dbapi_connection: Any, _: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


def create_db_engine(database_url: str, *, echo: bool = False) -> Engine:
    url = make_url(database_url)
    connect_args: dict[str, Any] = {}
    if url.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        if url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(database_url, echo=echo, connect_args=connect_args, future=True)
    if url.get_backend_name() == "sqlite":
        event.listen(engine, "connect", _sqlite_pragmas)
        if url.database and url.database != ":memory:":

            def _wal(dbapi_connection: Any, _: Any) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.close()

            event.listen(engine, "connect", _wal)
    return engine


@dataclass(frozen=True)
class DbStatus:
    reachable: bool
    migrated: bool
    revision: str | None
    head: str | None
    detail: str


def alembic_head() -> str | None:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    return script.get_current_head()


class Database:
    """Owns the engine and session factory for one application instance."""

    def __init__(self, database_url: str) -> None:
        self.url = database_url
        self.engine = create_db_engine(database_url)
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False, future=True)

    @contextmanager
    def session(self) -> Iterator[Session]:
        """Transactional scope: commit on success, rollback on error."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def status(self) -> DbStatus:
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                has_version = inspect(conn).has_table("alembic_version")
                revision = (
                    conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                    if has_version
                    else None
                )
        except Exception as exc:
            return DbStatus(False, False, None, None, f"unreachable: {type(exc).__name__}")
        head = alembic_head()
        migrated = revision is not None and revision == head
        detail = (
            f"at head {head}"
            if migrated
            else f"migration needed (db={revision}, head={head}); run alembic upgrade head"
        )
        return DbStatus(True, migrated, revision, head, detail)

    def dispose(self) -> None:
        self.engine.dispose()
