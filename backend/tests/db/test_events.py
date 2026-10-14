from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.db.errors import NotFoundError
from app.db.models import Machine, MaterialLot, Product
from app.db.repositories import EventRepository, RunRepository
from app.db.session import Database

Refs = tuple[Machine, Product, MaterialLot]


def _new_run_id(session: Session, refs: Refs, recipe: dict[str, float]) -> str:
    m, p, lot = refs
    run = RunRepository(session).create(
        machine=m, product=p, material_lot=lot, parameters=recipe, today=date(2026, 10, 15)
    )
    session.commit()
    return run.id


def test_seq_is_contiguous_and_replayable(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run_id = _new_run_id(session, refs, recipe)
    repo = EventRepository(session)
    types = ["run.started", "stage.started", "stage.completed", "prediction.ready", "run.completed"]
    seqs = [repo.append(run_id, t, {"i": i}, stage=None).seq for i, t in enumerate(types)]
    assert seqs == [1, 2, 3, 4, 5]
    assert [e.event_type for e in repo.after(run_id, 2)] == types[2:]
    assert RunRepository(session).get(run_id).last_seq == 5


def test_seq_unique_under_concurrent_writers(
    database: Database, session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run_id = _new_run_id(session, refs, recipe)

    def write(i: int) -> int:
        with database.session() as s:
            return EventRepository(s).append(run_id, "stage.progress", {"i": i}).seq

    with ThreadPoolExecutor(max_workers=8) as pool:
        seqs = sorted(pool.map(write, range(40)))
    assert seqs == list(range(1, 41))


def test_append_to_unknown_run(session: Session) -> None:
    with pytest.raises(NotFoundError):
        EventRepository(session).append("00000000-0000-0000-0000-000000000000", "run.started", {})
