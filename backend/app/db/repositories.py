"""Repositories: the only code that issues queries (roadmap R2-P2 task 4).

Services own transactions (``Database.session()``); repositories never commit. Payloads for JSON
columns are plain dicts (``contract_obj.model_dump(mode="json")`` once contracts exist), stored
unchanged: Role 2 never reshapes intelligence payloads (roadmap R2-P2 #15).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import Select, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.orm.util import identity_key

from app.db.base import utcnow
from app.db.errors import DuplicateError, NotFoundError, RunImmutableError
from app.db.models import (
    Machine,
    MaterialLot,
    ModelVersion,
    Prediction,
    ProcessRun,
    Product,
    Recommendation,
    RunParameters,
    SimulationEvent,
    StageResultRow,
)
from app.db.vocab import RECIPE_FIELDS, TERMINAL_STATUSES

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


class ReferenceRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def list_machines(self, *, active_only: bool = True) -> Sequence[Machine]:
        stmt = select(Machine).order_by(Machine.code)
        if active_only:
            stmt = stmt.where(Machine.active.is_(True))
        return self.s.scalars(stmt).all()

    def list_products(self, *, active_only: bool = True) -> Sequence[Product]:
        stmt = select(Product).order_by(Product.code)
        if active_only:
            stmt = stmt.where(Product.active.is_(True))
        return self.s.scalars(stmt).all()

    def list_materials(self) -> Sequence[MaterialLot]:
        return self.s.scalars(select(MaterialLot).order_by(MaterialLot.lot_code)).all()

    def machine(self, code: str) -> Machine:
        row = self.s.scalar(select(Machine).where(Machine.code == code))
        if row is None:
            raise NotFoundError("machine", code)
        return row

    def product(self, code: str) -> Product:
        row = self.s.scalar(select(Product).where(Product.code == code))
        if row is None:
            raise NotFoundError("product", code)
        return row

    def material(self, lot_code: str) -> MaterialLot:
        row = self.s.scalar(select(MaterialLot).where(MaterialLot.lot_code == lot_code))
        if row is None:
            raise NotFoundError("material lot", lot_code)
        return row

    def create_material(self, **values: Any) -> MaterialLot:
        lot = MaterialLot(**values)
        try:
            with self.s.begin_nested():  # savepoint: a duplicate must not roll back the caller
                self.s.add(lot)
        except IntegrityError as exc:
            raise DuplicateError("material lot", str(values.get("lot_code"))) from exc
        return lot


def machine_snapshot(machine: Machine, *, today: date) -> dict[str, Any]:
    """MachineProfile values (roadmap 7.3); ages are derived for ``today``.

    Float columns are coerced to float so a freshly created entity and a reloaded one snapshot
    identically (12 vs 12.0 would otherwise change JSON and cache keys)."""
    return {
        "machine_id": machine.code,
        "machine_type": machine.machine_type,
        "tonnage_ton": float(machine.tonnage_ton),
        "max_inj_pressure_bar": float(machine.max_inj_pressure_bar),
        "max_clamp_force_ton": float(machine.max_clamp_force_ton),
        "machine_age_days": (today - machine.installed_on).days,
        "days_since_maintenance": (today - machine.last_maintenance_on).days,
    }


def product_snapshot(product: Product) -> dict[str, Any]:
    """ProductContext values (roadmap 7.4)."""
    return {
        "product_id": product.code,
        "name": product.name,
        "cavity_count": product.cavity_count,
        "nominal_shot_weight_g": float(product.nominal_shot_weight_g),
        "wall_thickness_mm": float(product.wall_thickness_mm),
        "projected_area_cm2": float(product.projected_area_cm2),
    }


def lot_snapshot(lot: MaterialLot) -> dict[str, Any]:
    """MaterialLot values (roadmap 7.5)."""
    return {
        "material_lot_id": lot.lot_code,
        "resin_grade": lot.resin_grade,
        "mfi": float(lot.mfi),
        "moisture_pct": float(lot.moisture_pct),
        "regrind_pct": float(lot.regrind_pct),
        "colourant_pct": float(lot.colourant_pct),
    }


def context_snapshot(
    machine: Machine, product: Product, lot: MaterialLot, *, today: date
) -> dict[str, Any]:
    """RunContext values as used by a run (contract field names, roadmap 7.3-7.5)."""
    return {
        "machine": machine_snapshot(machine, today=today),
        "product": product_snapshot(product),
        "material_lot": lot_snapshot(lot),
    }


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunFilters:
    machine_code: str | None = None
    product_code: str | None = None
    material_lot_code: str | None = None
    status: str | None = None
    is_whatif: bool | None = None
    inference_backend: str | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    label: str | None = None  # prediction label PASS/FAIL
    risk_level: str | None = None  # prediction risk level


@dataclass
class LineageNode:
    run: ProcessRun
    children: list[LineageNode] = field(default_factory=list)


class RunRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def create(
        self,
        *,
        machine: Machine,
        product: Product,
        material_lot: MaterialLot,
        parameters: Mapping[str, float],
        mode: str = "auto",
        speed_factor: str = "1x",
        halt_on_critical: bool = True,
        scenario_label: str | None = None,
        parent_run_id: str | None = None,
        inference_backend: str | None = None,
        constraints_version: str | None = None,
        today: date | None = None,
    ) -> ProcessRun:
        missing = [f for f in RECIPE_FIELDS if f not in parameters]
        unknown = [f for f in parameters if f not in RECIPE_FIELDS]
        if missing or unknown:
            raise ValueError(f"recipe mismatch: missing={missing} unknown={unknown}")
        if parent_run_id is not None:
            self.get(parent_run_id)  # must exist
        run = ProcessRun(
            machine=machine,
            product=product,
            material_lot=material_lot,
            mode=mode,
            speed_factor=speed_factor,
            halt_on_critical=halt_on_critical,
            scenario_label=scenario_label,
            is_whatif=parent_run_id is not None,
            parent_run_id=parent_run_id,
            inference_backend=inference_backend,
            constraints_version=constraints_version,
            context_snapshot=context_snapshot(
                machine, product, material_lot, today=today or utcnow().date()
            ),
        )
        run.parameters = RunParameters(**{f: float(parameters[f]) for f in RECIPE_FIELDS})
        self.s.add(run)
        self.s.flush()
        return run

    def get(self, run_id: str, *, with_children: bool = False) -> ProcessRun:
        opts = [selectinload(ProcessRun.parameters), selectinload(ProcessRun.stage_results)]
        if with_children:
            opts.append(selectinload(ProcessRun.children))
        run = self.s.get(ProcessRun, run_id, options=opts)
        if run is None:
            raise NotFoundError("run", run_id)
        return run

    def _filtered(self, f: RunFilters) -> Select[tuple[ProcessRun]]:
        stmt = select(ProcessRun)
        if f.machine_code:
            stmt = stmt.join(Machine, ProcessRun.machine_id == Machine.id).where(
                Machine.code == f.machine_code
            )
        if f.product_code:
            stmt = stmt.join(Product, ProcessRun.product_id == Product.id).where(
                Product.code == f.product_code
            )
        if f.material_lot_code:
            stmt = stmt.join(MaterialLot, ProcessRun.material_lot_id == MaterialLot.id).where(
                MaterialLot.lot_code == f.material_lot_code
            )
        if f.status:
            stmt = stmt.where(ProcessRun.status == f.status)
        if f.is_whatif is not None:
            stmt = stmt.where(ProcessRun.is_whatif.is_(f.is_whatif))
        if f.inference_backend:
            stmt = stmt.where(ProcessRun.inference_backend == f.inference_backend)
        if f.created_from:
            stmt = stmt.where(ProcessRun.created_at >= f.created_from)
        if f.created_to:
            stmt = stmt.where(ProcessRun.created_at <= f.created_to)
        if f.label or f.risk_level:
            stmt = stmt.join(Prediction, Prediction.run_id == ProcessRun.id)
            if f.label:
                stmt = stmt.where(Prediction.label == f.label)
            if f.risk_level:
                stmt = stmt.where(Prediction.risk_level == f.risk_level)
        return stmt

    def search(
        self, filters: RunFilters | None = None, *, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[ProcessRun], int]:
        stmt = self._filtered(filters or RunFilters())
        total = self.s.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = self.s.scalars(
            stmt.join(RunParameters, RunParameters.run_id == ProcessRun.id)
            .order_by(ProcessRun.created_at.desc(), RunParameters.id.desc())
            .limit(limit)
            .offset(offset)
        ).all()
        return rows, total

    def set_status(self, run: ProcessRun, status: str, **fields: Any) -> ProcessRun:
        """Change FSM status and related fields. Refused once the run is terminal."""
        if run.status in TERMINAL_STATUSES:
            raise RunImmutableError(f"Run {run.id} is {run.status}")
        run.status = status
        for key, value in fields.items():
            if not hasattr(ProcessRun, key):
                raise AttributeError(f"ProcessRun has no field {key}")
            setattr(run, key, value)
        if status in TERMINAL_STATUSES and run.completed_at is None:
            run.completed_at = utcnow()
        self.s.flush()
        return run

    def set_label(self, run: ProcessRun, label: str | None) -> ProcessRun:
        """Save scenario: the only mutation allowed on terminal runs (roadmap 9.4)."""
        run.scenario_label = label
        self.s.flush()
        return run

    def lineage(self, run_id: str) -> LineageNode:
        """Tree rooted at ``run_id`` with all what-if descendants."""
        root = self.get(run_id)

        def build(run: ProcessRun) -> LineageNode:
            kids = self.s.scalars(
                select(ProcessRun)
                .join(RunParameters, RunParameters.run_id == ProcessRun.id)
                .where(ProcessRun.parent_run_id == run.id)
                # created_at can tie within one clock tick; the 1:1 parameters row id is
                # an insertion-ordered tiebreaker (UUID run ids are random).
                .order_by(ProcessRun.created_at, RunParameters.id)
            ).all()
            return LineageNode(run=run, children=[build(k) for k in kids])

        return build(root)

    def abort_interrupted(self, reason: str = "SERVER_RESTART") -> list[str]:
        """Startup recovery (roadmap 9.5.1): runs whose in-process task died with the server.

        Only AUTO-mode runs that were executing a stage had a task. Runs that are waiting for the
        user survive a restart: stepwise runs (no task), BLOCKED runs (waiting for override) and
        PAUSED runs (resume starts a new task).
        """
        executing = [
            "MATERIAL_CONDITIONING",
            "PLASTICIZING",
            "INJECTION",
            "PACKING",
            "COOLING",
            "QUALITY_INSPECTION",
        ]
        rows = self.s.scalars(
            select(ProcessRun).where(ProcessRun.status.in_(executing), ProcessRun.mode == "auto")
        ).all()
        for run in rows:
            self.set_status(run, "ABORTED", abort_reason=reason)
        return [r.id for r in rows]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


def _require_open(run: ProcessRun) -> None:
    if run.status in TERMINAL_STATUSES:
        raise RunImmutableError(f"Run {run.id} is {run.status}; results are immutable")


class StageResultRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, run: ProcessRun, **values: Any) -> StageResultRow:
        _require_open(run)
        row = StageResultRow(run_id=run.id, **values)
        self.s.add(row)
        self.s.flush()
        return row

    def copy_for_child(self, source: StageResultRow, child: ProcessRun) -> StageResultRow:
        """What-if reuse: copy a parent's stage result into the child (roadmap 9.4 lineage)."""
        _require_open(child)
        skip = {"id", "run_id", "created_at", "reused_from_stage_result_id", "run"}
        values = {
            c.key: getattr(source, c.key)
            for c in StageResultRow.__table__.columns
            if c.key not in skip
        }
        return self.add(child, reused_from_stage_result_id=source.id, **values)

    def for_run(self, run_id: str) -> Sequence[StageResultRow]:
        return self.s.scalars(
            select(StageResultRow)
            .where(StageResultRow.run_id == run_id)
            .order_by(StageResultRow.sequence_index)
        ).all()

    def get(self, run_id: str, stage_name: str) -> StageResultRow:
        row = self.s.scalar(
            select(StageResultRow).where(
                StageResultRow.run_id == run_id, StageResultRow.stage_name == stage_name
            )
        )
        if row is None:
            raise NotFoundError("stage result", f"{run_id}/{stage_name}")
        return row


class PredictionRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add(self, run: ProcessRun | None, **values: Any) -> Prediction:
        if run is not None:
            _require_open(run)
        row = Prediction(run_id=run.id if run else None, **values)
        self.s.add(row)
        self.s.flush()
        return row

    def get(self, prediction_id: str) -> Prediction:
        row = self.s.get(Prediction, prediction_id)
        if row is None:
            raise NotFoundError("prediction", prediction_id)
        return row

    def for_run(self, run_id: str) -> Prediction | None:
        return self.s.scalar(
            select(Prediction)
            .where(Prediction.run_id == run_id)
            .order_by(Prediction.created_at.desc())
        )


def reset_run_results(session: Session, run: ProcessRun) -> None:
    """RESET (roadmap 9.5.1): drop stage results and prediction of a NON-terminal run."""
    _require_open(run)
    for row in StageResultRepository(session).for_run(run.id):
        session.delete(row)
    prediction = PredictionRepository(session).for_run(run.id)
    if prediction is not None:
        session.delete(prediction)
    session.flush()
    session.expire(run, ["stage_results"])


class RecommendationRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def add_batch(
        self,
        run: ProcessRun,
        request_id: str,
        candidates: Iterable[Mapping[str, Any]],
        **common: Any,
    ) -> list[Recommendation]:
        rows = [
            Recommendation(run_id=run.id, request_id=request_id, **common, **c) for c in candidates
        ]
        self.s.add_all(rows)
        self.s.flush()
        return rows

    def latest_for_run(self, run_id: str) -> Sequence[Recommendation]:
        latest = self.s.scalar(
            select(Recommendation.request_id)
            .where(Recommendation.run_id == run_id)
            .order_by(Recommendation.created_at.desc(), Recommendation.id.desc())
            .limit(1)
        )
        if latest is None:
            return []
        return self.s.scalars(
            select(Recommendation)
            .where(Recommendation.request_id == latest)
            .order_by(Recommendation.option_rank)
        ).all()


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def append(
        self, run_id: str, event_type: str, payload: Mapping[str, Any], stage: str | None = None
    ) -> SimulationEvent:
        """Allocate the next ``seq`` atomically (UPDATE ... RETURNING) and insert the event."""
        seq = self.s.execute(
            update(ProcessRun)
            .where(ProcessRun.id == run_id)
            .values(last_seq=ProcessRun.last_seq + 1)
            .returning(ProcessRun.last_seq)
            .execution_options(synchronize_session=False)
        ).scalar_one_or_none()
        if seq is None:
            raise NotFoundError("run", run_id)
        cached = self.s.identity_map.get(identity_key(ProcessRun, run_id))
        if cached is not None:
            self.s.expire(cached, ["last_seq"])  # the bulk UPDATE bypassed the ORM copy
        row = SimulationEvent(
            run_id=run_id, seq=seq, event_type=event_type, stage=stage, payload=dict(payload)
        )
        self.s.add(row)
        self.s.flush()
        return row

    def after(self, run_id: str, after_seq: int = 0) -> Sequence[SimulationEvent]:
        """Events with ``seq > after_seq`` in order (SSE ``Last-Event-ID`` replay)."""
        return self.s.scalars(
            select(SimulationEvent)
            .where(SimulationEvent.run_id == run_id, SimulationEvent.seq > after_seq)
            .order_by(SimulationEvent.seq)
        ).all()


# ---------------------------------------------------------------------------
# Model versions
# ---------------------------------------------------------------------------

MOCK_MODEL = {"name": "mock", "semver": "0.0.0", "algorithm": "mock"}


class ModelVersionRepository:
    def __init__(self, session: Session) -> None:
        self.s = session

    def upsert(self, name: str, semver: str, **fields: Any) -> ModelVersion:
        row = self.find(name, semver)
        if row is None:
            try:
                # Savepoint: concurrent runs may register the same version at once; the loser
                # re-reads the winner's row instead of failing its run (IntegrityError).
                with self.s.begin_nested():
                    row = ModelVersion(name=name, semver=semver, **fields)
                    self.s.add(row)
            except IntegrityError:
                row = self.find(name, semver)
                if row is None:
                    raise
        for key, value in fields.items():
            setattr(row, key, value)
        if fields.get("is_active"):
            for other in self.s.scalars(
                select(ModelVersion).where(ModelVersion.name == name, ModelVersion.semver != semver)
            ):
                other.is_active = False
        self.s.flush()
        return row

    def find(self, name: str, semver: str) -> ModelVersion | None:
        return self.s.scalar(
            select(ModelVersion).where(ModelVersion.name == name, ModelVersion.semver == semver)
        )

    def ensure_mock(self) -> ModelVersion:
        """The row mock predictions reference (roadmap 9.4 traceability)."""
        return self.upsert(
            MOCK_MODEL["name"], MOCK_MODEL["semver"], algorithm="mock", is_active=True
        )

    def active(self, name: str) -> ModelVersion | None:
        return self.s.scalar(
            select(ModelVersion).where(ModelVersion.name == name, ModelVersion.is_active.is_(True))
        )

    def all_versions(self) -> Sequence[ModelVersion]:
        return self.s.scalars(
            select(ModelVersion).order_by(ModelVersion.name, ModelVersion.semver)
        ).all()
