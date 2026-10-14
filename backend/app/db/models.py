"""ORM models for the application DB (roadmap 9.4; Plan 17.2 plus the [P] additions).

Conventions:
- Column names use the canonical unit-suffixed field names of roadmap 7.3-7.6, so DB, contracts,
  API and dataset agree (e.g. ``tonnage_ton`` rather than the Plan's ``tonnage``).
- Reference entities have internal integer PKs and a unique ``code``. The API and contracts
  expose only the codes (UD-10 / A-09).
- Runs and predictions use UUIDv4 string PKs (String(36) for SQLite/PostgreSQL portability).
- Immutability is enforced in ``app.db.guards`` (ORM events), not by convention.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.ids import new_id
from app.db.base import Base, utcnow
from app.db.vocab import (
    INFERENCE_BACKENDS,
    MACHINE_TYPES,
    MODEL_NAMES,
    PREDICTION_LABELS,
    RISK_LEVELS,
    RUN_MODES,
    RUN_STATUSES,
    SPEED_FACTORS,
    STAGE_NAMES,
    STAGE_SUBSTATES,
    sql_in,
)

UUID_LEN = 36
CODE_LEN = 32
SHORT = 64


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


class Machine(Base):
    __tablename__ = "machines"
    __table_args__ = (CheckConstraint(sql_in("machine_type", MACHINE_TYPES), name="machine_type"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(CODE_LEN), unique=True)
    machine_type: Mapped[str] = mapped_column(String(16))
    tonnage_ton: Mapped[float] = mapped_column(Float)
    max_inj_pressure_bar: Mapped[float] = mapped_column(Float)
    max_clamp_force_ton: Mapped[float] = mapped_column(Float)
    installed_on: Mapped[date] = mapped_column(Date)
    last_maintenance_on: Mapped[date] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    fleet_version: Mapped[str | None] = mapped_column(String(SHORT))


class Product(Base):
    """Product and mold are one entity in the Plan (``products(molds)``): mold_id == code."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(CODE_LEN), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    cavity_count: Mapped[int] = mapped_column(Integer)
    nominal_shot_weight_g: Mapped[float] = mapped_column(Float)
    wall_thickness_mm: Mapped[float] = mapped_column(Float)
    projected_area_cm2: Mapped[float] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    fleet_version: Mapped[str | None] = mapped_column(String(SHORT))


class MaterialLot(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lot_code: Mapped[str] = mapped_column(String(CODE_LEN), unique=True)
    resin_grade: Mapped[str] = mapped_column(String(CODE_LEN))
    mfi: Mapped[float] = mapped_column(Float)
    moisture_pct: Mapped[float] = mapped_column(Float)
    regrind_pct: Mapped[float] = mapped_column(Float)
    colourant_pct: Mapped[float] = mapped_column(Float)
    received_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    fleet_version: Mapped[str | None] = mapped_column(String(SHORT))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


class ProcessRun(Base):
    __tablename__ = "process_runs"
    __table_args__ = (
        CheckConstraint(sql_in("status", RUN_STATUSES), name="status"),
        CheckConstraint(sql_in("mode", RUN_MODES), name="mode"),
        CheckConstraint(sql_in("speed_factor", SPEED_FACTORS), name="speed_factor"),
        CheckConstraint(
            "inference_backend IS NULL OR " + sql_in("inference_backend", INFERENCE_BACKENDS),
            name="inference_backend",
        ),
        CheckConstraint(
            "(NOT is_whatif AND parent_run_id IS NULL) "
            "OR (is_whatif AND parent_run_id IS NOT NULL)",
            name="whatif_lineage",
        ),
        Index("ix_process_runs_created_at", "created_at"),
        Index("ix_process_runs_machine_id_created_at", "machine_id", "created_at"),
        Index("ix_process_runs_parent_run_id", "parent_run_id"),
    )

    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=new_id)
    machine_id: Mapped[int] = mapped_column(ForeignKey("machines.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    material_lot_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))

    status: Mapped[str] = mapped_column(String(32), default="INITIALIZED")
    mode: Mapped[str] = mapped_column(String(16), default="auto")
    speed_factor: Mapped[str] = mapped_column(String(16), default="1x")
    halt_on_critical: Mapped[bool] = mapped_column(Boolean, default=True)
    current_stage: Mapped[str | None] = mapped_column(String(32))
    blocked_stage: Mapped[str | None] = mapped_column(String(32))
    override_count: Mapped[int] = mapped_column(Integer, default=0)
    abort_reason: Mapped[str | None] = mapped_column(String(256))

    is_whatif: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("process_runs.id"))
    scenario_label: Mapped[str | None] = mapped_column(String(200))

    # Values of machine/product/lot at run creation, so later reference edits never alter history.
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON)
    inference_backend: Mapped[str | None] = mapped_column(String(8))
    constraints_version: Mapped[str | None] = mapped_column(String(SHORT))
    last_seq: Mapped[int] = mapped_column(Integer, default=0)

    created_by: Mapped[str | None] = mapped_column(String(SHORT))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
    started_at: Mapped[datetime | None] = mapped_column()
    completed_at: Mapped[datetime | None] = mapped_column()

    machine: Mapped[Machine] = relationship()
    product: Mapped[Product] = relationship()
    material_lot: Mapped[MaterialLot] = relationship()
    parameters: Mapped[RunParameters] = relationship(back_populates="run", uselist=False)
    stage_results: Mapped[list[StageResultRow]] = relationship(
        back_populates="run",
        order_by="StageResultRow.sequence_index",
        foreign_keys="StageResultRow.run_id",
    )
    parent: Mapped[ProcessRun | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[ProcessRun]] = relationship(back_populates="parent")

    @property
    def is_terminal(self) -> bool:
        from app.db.vocab import TERMINAL_STATUSES

        return self.status in TERMINAL_STATUSES


class RunParameters(Base):
    """Wide, typed recipe table (Plan 17.3 rejects key-value). Columns == vocab.RECIPE_FIELDS."""

    __tablename__ = "run_parameters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("process_runs.id"), unique=True)

    drying_time_h: Mapped[float] = mapped_column(Float)
    dryer_temp_c: Mapped[float] = mapped_column(Float)
    barrel_temp_rear_c: Mapped[float] = mapped_column(Float)
    barrel_temp_mid_c: Mapped[float] = mapped_column(Float)
    barrel_temp_front_c: Mapped[float] = mapped_column(Float)
    nozzle_temp_c: Mapped[float] = mapped_column(Float)
    melt_temp_c: Mapped[float] = mapped_column(Float)
    screw_rpm: Mapped[float] = mapped_column(Float)
    back_pressure_bar: Mapped[float] = mapped_column(Float)
    residence_time_s: Mapped[float] = mapped_column(Float)
    inj_velocity_mm_s: Mapped[float] = mapped_column(Float)
    inj_pressure_bar: Mapped[float] = mapped_column(Float)
    fill_time_s: Mapped[float] = mapped_column(Float)
    shot_size_mm: Mapped[float] = mapped_column(Float)
    switchover_position_mm: Mapped[float] = mapped_column(Float)
    clamp_force_ton: Mapped[float] = mapped_column(Float)
    hold_pressure_bar: Mapped[float] = mapped_column(Float)
    hold_time_s: Mapped[float] = mapped_column(Float)
    cushion_mm: Mapped[float] = mapped_column(Float)
    mold_temp_c: Mapped[float] = mapped_column(Float)
    cooling_time_s: Mapped[float] = mapped_column(Float)
    cycle_time_s: Mapped[float] = mapped_column(Float)
    ejection_force_proxy: Mapped[float] = mapped_column(Float)

    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    run: Mapped[ProcessRun] = relationship(back_populates="parameters")

    def as_dict(self) -> dict[str, float]:
        from app.db.vocab import RECIPE_FIELDS

        return {name: getattr(self, name) for name in RECIPE_FIELDS}


class StageResultRow(Base):
    __tablename__ = "stage_results"
    __table_args__ = (
        UniqueConstraint("run_id", "stage_name"),
        CheckConstraint(sql_in("stage_name", STAGE_NAMES), name="stage_name"),
        CheckConstraint(sql_in("substate", STAGE_SUBSTATES), name="substate"),
        CheckConstraint(sql_in("risk_level", RISK_LEVELS), name="risk_level"),
        CheckConstraint("health_score >= 0 AND health_score <= 1", name="health_range"),
        CheckConstraint("sequence_index BETWEEN 1 AND 5", name="sequence_index"),
        Index("ix_stage_results_run_id_sequence_index", "run_id", "sequence_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("process_runs.id"))
    stage_name: Mapped[str] = mapped_column(String(32))
    sequence_index: Mapped[int] = mapped_column(Integer)
    substate: Mapped[str] = mapped_column(String(16))
    health_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(16))
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    anomaly_score: Mapped[float] = mapped_column(Float, default=0.0)
    anomaly: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    indicators: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    indicator_provenance: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    constraint_breaches: Mapped[list[Any]] = mapped_column(JSON, default=list)
    notes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    inputs_used: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    upstream_in: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    upstream_out: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    block_reason: Mapped[str | None] = mapped_column(Text)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    module_version: Mapped[str | None] = mapped_column(String(SHORT))
    constraints_version: Mapped[str | None] = mapped_column(String(SHORT))
    compute_ms: Mapped[float | None] = mapped_column(Float)
    duration_ms: Mapped[float | None] = mapped_column(Float)
    reused_from_stage_result_id: Mapped[int | None] = mapped_column(ForeignKey("stage_results.id"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    run: Mapped[ProcessRun] = relationship(back_populates="stage_results", foreign_keys=[run_id])


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("name", "semver"),
        CheckConstraint(sql_in("name", MODEL_NAMES), name="name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    semver: Mapped[str] = mapped_column(String(32))
    algorithm: Mapped[str] = mapped_column(String(64))
    trained_at: Mapped[datetime | None] = mapped_column()
    dataset_hash: Mapped[str | None] = mapped_column(String(SHORT))
    git_sha: Mapped[str | None] = mapped_column(String(SHORT))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    artifact_path: Mapped[str | None] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    feature_schema_hash: Mapped[str | None] = mapped_column(String(SHORT))
    constraints_version: Mapped[str | None] = mapped_column(String(SHORT))
    threshold: Mapped[float | None] = mapped_column(Float)
    bundle_sha256: Mapped[str | None] = mapped_column(String(SHORT))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        CheckConstraint(sql_in("label", PREDICTION_LABELS), name="label"),
        CheckConstraint(sql_in("risk_level", RISK_LEVELS), name="risk_level"),
        CheckConstraint(sql_in("inference_backend", INFERENCE_BACKENDS), name="inference_backend"),
        CheckConstraint("p_fail >= 0 AND p_fail <= 1", name="p_fail_range"),
        Index("ix_predictions_run_id", "run_id"),
    )

    id: Mapped[str] = mapped_column(String(UUID_LEN), primary_key=True, default=new_id)
    # NULL for stateless POST /predict rows (roadmap 9.3.2).
    run_id: Mapped[str | None] = mapped_column(ForeignKey("process_runs.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    label: Mapped[str] = mapped_column(String(8))
    p_fail: Mapped[float] = mapped_column(Float)
    p_fail_raw: Mapped[float | None] = mapped_column(Float)
    threshold_used: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(16))
    risk_drivers: Mapped[list[Any]] = mapped_column(JSON, default=list)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    stage_risk_mass: Mapped[list[Any]] = mapped_column(JSON, default=list)
    caveats: Mapped[list[Any]] = mapped_column(JSON, default=list)
    anomaly_global: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ood: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    uncertainty: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    constraint_override_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    inference_backend: Mapped[str] = mapped_column(String(8))
    feature_schema_hash: Mapped[str | None] = mapped_column(String(SHORT))
    constraints_version: Mapped[str | None] = mapped_column(String(SHORT))
    input_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    model_version: Mapped[ModelVersion] = relationship()


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        UniqueConstraint("request_id", "option_rank"),
        Index("ix_recommendations_run_id_request_id", "run_id", "request_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("process_runs.id"))
    request_id: Mapped[str] = mapped_column(String(UUID_LEN))
    option_rank: Mapped[int] = mapped_column(Integer)
    changes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    predicted_p_fail: Mapped[float] = mapped_column(Float)
    predicted_label: Mapped[str] = mapped_column(String(8))
    delta_p_fail: Mapped[float] = mapped_column(Float)
    constraint_status: Mapped[str] = mapped_column(String(32))
    stability_score: Mapped[float | None] = mapped_column(Float)
    extrapolation_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    cycle_time_delta_s: Mapped[float | None] = mapped_column(Float)
    search_method: Mapped[str | None] = mapped_column(String(32))
    candidate: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    request: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    model_version_id: Mapped[int | None] = mapped_column(ForeignKey("model_versions.id"))
    constraints_version: Mapped[str | None] = mapped_column(String(SHORT))
    evaluated_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class SimulationEvent(Base):
    __tablename__ = "simulation_events"
    __table_args__ = (
        UniqueConstraint("run_id", "seq"),
        Index("ix_simulation_events_run_id_created_at", "run_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("process_runs.id"))
    seq: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(48))
    stage: Mapped[str | None] = mapped_column(String(32))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
