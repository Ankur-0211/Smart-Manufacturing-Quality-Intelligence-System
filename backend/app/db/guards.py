"""Immutability rules enforced as ORM events (roadmap 9.4 "Mutability" column).

| Table             | Rule                                                                  |
|-------------------|-----------------------------------------------------------------------|
| run_parameters    | never updated; never deleted                                          |
| predictions       | never updated; deleted only by RESET of a non-terminal run            |
| recommendations   | append-only                                                           |
| simulation_events | append-only                                                           |
| stage_results     | never updated; deleted only by RESET of a non-terminal run            |
| process_runs      | once terminal, only ``scenario_label`` (and ``updated_at``) may change |

Bulk ``session.execute(update(...))`` bypasses ORM events; repositories never use it for
these tables (the single exception, the ``last_seq`` counter, is not a guarded column).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Mapper, object_session

from app.db.errors import ImmutableRowError, RunImmutableError
from app.db.models import (
    Prediction,
    ProcessRun,
    Recommendation,
    RunParameters,
    SimulationEvent,
    StageResultRow,
)
from app.db.vocab import TERMINAL_STATUSES

_NEVER_UPDATED = (RunParameters, Prediction, Recommendation, SimulationEvent, StageResultRow)
_NEVER_DELETED = (RunParameters, Recommendation, SimulationEvent)
_TERMINAL_MUTABLE_COLUMNS = {"scenario_label", "updated_at"}


def _forbid_update(_: Mapper[Any], __: Any, target: Any) -> None:
    raise ImmutableRowError(f"{type(target).__name__} rows are immutable")


def _forbid_delete(_: Mapper[Any], __: Any, target: Any) -> None:
    raise ImmutableRowError(f"{type(target).__name__} rows are append-only")


def _run_is_terminal(target: StageResultRow | Prediction) -> bool:
    run = getattr(target, "run", None)
    if run is None and target.run_id is not None:
        session = object_session(target)
        run = session.get(ProcessRun, target.run_id) if session is not None else None
    return run is not None and run.status in TERMINAL_STATUSES


def _guard_result_delete(_: Mapper[Any], __: Any, target: Any) -> None:
    if _run_is_terminal(target):
        raise RunImmutableError(
            f"Cannot delete {type(target).__name__} of a terminal run (run {target.run_id})"
        )


def _guard_terminal_run_update(_: Mapper[Any], __: Any, target: ProcessRun) -> None:
    state = inspect(target)
    status_hist = state.attrs.status.history
    previous = status_hist.deleted[0] if status_hist.deleted else target.status
    if previous not in TERMINAL_STATUSES:
        return
    changed = {
        attr.key
        for attr in state.attrs
        if attr.history.has_changes() and attr.key not in ("stage_results", "children", "parent")
    }
    illegal = changed - _TERMINAL_MUTABLE_COLUMNS
    if illegal:
        raise RunImmutableError(f"Run {target.id} is {previous}; cannot change {sorted(illegal)}")


def _install() -> None:
    for model in _NEVER_UPDATED:
        if not event.contains(model, "before_update", _forbid_update):
            event.listen(model, "before_update", _forbid_update)
    for model in _NEVER_DELETED:
        if not event.contains(model, "before_delete", _forbid_delete):
            event.listen(model, "before_delete", _forbid_delete)
    for model in (StageResultRow, Prediction):
        if not event.contains(model, "before_delete", _guard_result_delete):
            event.listen(model, "before_delete", _guard_result_delete)
    if not event.contains(ProcessRun, "before_update", _guard_terminal_run_update):
        event.listen(ProcessRun, "before_update", _guard_terminal_run_update)


_install()
