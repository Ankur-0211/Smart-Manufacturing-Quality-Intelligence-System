"""Analytics over stored runs (roadmap R2-P8 tasks 3 and 5; Plan §13.7).

Every number is an SQL aggregation over persisted runs and their predictions; nothing is
synthesised. Default exclusions: what-if children, runs scored by the MOCK backend, and runs that
did not reach FINAL_RESULT. Each is togglable, and the response states which ones applied and how
many runs each removed.

"Failure rate" here is always the **model-predicted** FAIL share among runs with a prediction,
never an observed defect rate.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.db.models import (
    Machine,
    MaterialLot,
    Prediction,
    ProcessRun,
    RunParameters,
    StageResultRow,
)
from app.db.session import Database
from app.db.vocab import RECIPE_FIELDS

FINAL = "FINAL_RESULT"
MOCK = "mock"


@dataclass(frozen=True)
class AnalyticsFilters:
    include_whatif: bool = False
    include_mock: bool = False
    include_unfinished: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None


class UnknownParameterError(ValueError):
    """The parameter is not a recipe field with a registry window."""


def _backend() -> ColumnElement[Any]:
    # The prediction records the backend that actually scored the run; runs without one fall
    # back to the backend recorded on the run.
    return func.coalesce(Prediction.inference_backend, ProcessRun.inference_backend)


def _scoped(
    stmt: Select[Any], f: AnalyticsFilters, *, apply_exclusions: bool = True
) -> Select[Any]:
    stmt = stmt.outerjoin(Prediction, Prediction.run_id == ProcessRun.id)
    if f.created_from:
        stmt = stmt.where(ProcessRun.created_at >= f.created_from)
    if f.created_to:
        stmt = stmt.where(ProcessRun.created_at <= f.created_to)
    if apply_exclusions:
        if not f.include_whatif:
            stmt = stmt.where(ProcessRun.is_whatif.is_(False))
        if not f.include_mock:
            stmt = stmt.where(func.coalesce(_backend(), "") != MOCK)
        if not f.include_unfinished:
            stmt = stmt.where(ProcessRun.status == FINAL)
    return stmt


def _outcome_columns() -> list[ColumnElement[Any]]:
    fail = case((Prediction.label == "FAIL", 1), else_=0)
    return [
        func.count(ProcessRun.id).label("runs"),
        func.count(Prediction.id).label("with_prediction"),
        func.coalesce(func.sum(fail), 0).label("predicted_fail"),
        func.avg(Prediction.p_fail).label("mean_p_fail"),
    ]


def _outcome(row: Any) -> dict[str, Any]:
    scored = int(row.with_prediction or 0)
    fails = int(row.predicted_fail or 0)
    return {
        "runs": int(row.runs or 0),
        "with_prediction": scored,
        "predicted_fail": fails,
        "predicted_fail_rate": fails / scored if scored else None,
        "mean_p_fail": float(row.mean_p_fail) if row.mean_p_fail is not None else None,
    }


class AnalyticsService:
    def __init__(self, db: Database) -> None:
        self.db = db

    # -- summary ------------------------------------------------------------------------

    def summary(self, f: AnalyticsFilters) -> dict[str, Any]:
        with self.db.session() as s:
            base = _scoped(select(*_outcome_columns()).select_from(ProcessRun), f)
            totals = _outcome(s.execute(base).one())
            risk = s.execute(
                _scoped(select(Prediction.risk_level, func.count()).select_from(ProcessRun), f)
                .where(Prediction.id.is_not(None))
                .group_by(Prediction.risk_level)
            ).all()
            not_releasable = s.scalar(
                _scoped(select(func.count()).select_from(ProcessRun), f).where(
                    Prediction.constraint_override_applied.is_(True)
                )
            )
            return {
                "filters": self._filters(f),
                "excluded": self._excluded(s, f),
                **totals,
                "risk_levels": {level: int(n) for level, n in risk},
                "not_releasable": int(not_releasable or 0),
                "stage_risk_frequency": self._stage_risk(s, f),
                "runs_over_time": self._over_time(s, f),
            }

    def _filters(self, f: AnalyticsFilters) -> dict[str, Any]:
        return asdict(f)

    def _excluded(self, s: Session, f: AnalyticsFilters) -> dict[str, int]:
        """How many runs (in the date range) each active exclusion removes, counted separately."""
        everything = _scoped(
            select(func.count()).select_from(ProcessRun), f, apply_exclusions=False
        )
        out: dict[str, int] = {}
        if not f.include_whatif:
            out["whatif"] = int(s.scalar(everything.where(ProcessRun.is_whatif.is_(True))) or 0)
        if not f.include_mock:
            out["mock"] = int(s.scalar(everything.where(_backend() == MOCK)) or 0)
        if not f.include_unfinished:
            out["unfinished"] = int(s.scalar(everything.where(ProcessRun.status != FINAL)) or 0)
        return out

    def _stage_risk(self, s: Session, f: AnalyticsFilters) -> list[dict[str, Any]]:
        rows = s.execute(
            _scoped(
                select(StageResultRow.stage_name, StageResultRow.risk_level, func.count())
                .select_from(ProcessRun)
                .join(StageResultRow, StageResultRow.run_id == ProcessRun.id),
                f,
            ).group_by(StageResultRow.stage_name, StageResultRow.risk_level)
        ).all()
        by_stage: dict[str, dict[str, int]] = {}
        for stage, level, n in rows:
            by_stage.setdefault(stage, {})[level] = int(n)
        return [
            {"stage": stage, "counts": counts, "total": sum(counts.values())}
            for stage, counts in by_stage.items()
        ]

    def _over_time(self, s: Session, f: AnalyticsFilters) -> list[dict[str, Any]]:
        day = func.date(ProcessRun.created_at).label("day")
        rows = s.execute(
            _scoped(select(day, *_outcome_columns()).select_from(ProcessRun), f)
            .group_by(day)
            .order_by(day)
        ).all()
        return [{"day": str(r.day), **_outcome(r)} for r in rows]

    # -- breakdowns -----------------------------------------------------------------------

    def _grouped(
        self, f: AnalyticsFilters, key: Any, join: Callable[[Select[Any]], Select[Any]]
    ) -> list[dict[str, Any]]:
        with self.db.session() as s:
            stmt = _scoped(
                join(select(key.label("key"), *_outcome_columns()).select_from(ProcessRun)), f
            )
            rows = s.execute(stmt.group_by(key).order_by(key)).all()
            return [{"key": r.key, **_outcome(r)} for r in rows]

    def by_machine(self, f: AnalyticsFilters) -> dict[str, Any]:
        rows = self._grouped(
            f, Machine.code, lambda q: q.join(Machine, ProcessRun.machine_id == Machine.id)
        )
        return {"filters": self._filters(f), "rows": rows}

    def by_material(self, f: AnalyticsFilters, group: str) -> dict[str, Any]:
        """``group``: ``lot`` (lot code) or ``resin_grade``."""
        column = MaterialLot.resin_grade if group == "resin_grade" else MaterialLot.lot_code
        rows = self._grouped(
            f, column, lambda q: q.join(MaterialLot, ProcessRun.material_lot_id == MaterialLot.id)
        )
        return {"filters": self._filters(f), "group": group, "rows": rows}

    def by_parameter(
        self, f: AnalyticsFilters, parameter: str, buckets: int, spec: Mapping[str, Any] | None
    ) -> dict[str, Any]:
        """Equal-width buckets over the parameter's **registry window** (no hard-coded edges).
        The top bucket is closed so the window maximum is counted."""
        if parameter not in RECIPE_FIELDS or not spec:
            raise UnknownParameterError(parameter)
        lo, hi = float(spec["min"]), float(spec["max"])
        width = (hi - lo) / buckets
        column = getattr(RunParameters, parameter)
        # An explicit CASE over the edges is portable (SQLite and PostgreSQL cast differently).
        index = case(
            *[(column < lo + (i + 1) * width, i) for i in range(buckets - 1)], else_=buckets - 1
        )
        with self.db.session() as s:
            stmt = _scoped(
                select(index.label("bucket"), *_outcome_columns())
                .select_from(ProcessRun)
                .join(RunParameters, RunParameters.run_id == ProcessRun.id),
                f,
            )
            found = {r.bucket: _outcome(r) for r in s.execute(stmt.group_by(index)).all()}
        empty = {"runs": 0, "with_prediction": 0, "predicted_fail": 0}
        rows = [
            {
                "lo": round(lo + i * width, 10),
                "hi": round(lo + (i + 1) * width, 10),
                **(found.get(i) or {**empty, "predicted_fail_rate": None, "mean_p_fail": None}),
            }
            for i in range(buckets)
        ]
        return {
            "filters": self._filters(f),
            "parameter": parameter,
            "unit": spec.get("unit"),
            "window": {"min": lo, "max": hi},
            "rows": rows,
        }

    # -- SPC ----------------------------------------------------------------------------------

    def spc_series(
        self, f: AnalyticsFilters, machine_code: str, parameter: str, limit: int
    ) -> list[dict[str, Any]]:
        """The parameter's stored values for one machine, oldest first (the last ``limit``)."""
        if parameter not in RECIPE_FIELDS:
            raise UnknownParameterError(parameter)
        column = getattr(RunParameters, parameter)
        with self.db.session() as s:
            stmt = (
                _scoped(
                    select(ProcessRun.id, ProcessRun.created_at, column.label("value"))
                    .select_from(ProcessRun)
                    .join(RunParameters, RunParameters.run_id == ProcessRun.id)
                    .join(Machine, ProcessRun.machine_id == Machine.id),
                    f,
                )
                .where(Machine.code == machine_code)
                .order_by(ProcessRun.created_at.desc(), RunParameters.id.desc())
                .limit(limit)
            )
            rows: Sequence[Any] = s.execute(stmt).all()
        return [
            {"run_id": r.id, "created_at": r.created_at, "value": float(r.value)}
            for r in reversed(rows)
        ]
