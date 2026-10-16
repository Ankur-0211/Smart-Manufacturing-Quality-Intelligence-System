"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

UpstreamContext, StageAnomaly, ConstraintBreach and StageResult (roadmap 7.8-7.10).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ._base import ContractModel, Ordinal, Probability
from .enums import (
    INTELLIGENCE_STAGES,
    AnomalyMethod,
    ConstraintSeverity,
    DataProvenance,
    RiskLevel,
    StageName,
    StageSubstate,
)

ViscosityClass = Literal["LOW", "NOMINAL", "HIGH"]


class UpstreamContext(ContractModel):
    """Every key is optional; each stage may only add the keys it owns (7.8)."""

    viscosity_class: ViscosityClass | None = None  # S1
    moisture_flag: bool | None = None  # S1
    effective_melt_temp_c: float | None = None  # S2
    viscosity_proxy: float | None = None  # S2
    fill_completion_proxy: Probability | None = None  # S3
    cavity_pressure_estimate_bar: float | None = None  # S3
    residual_stress_proxy: float | None = None  # S4


class AnomalyContributor(ContractModel):
    feature: str
    deviation: float


class StageAnomaly(ContractModel):
    """L1 per-stage anomaly (Plan 12.2)."""

    flag: bool
    score: Probability
    method: AnomalyMethod
    contributors: list[AnomalyContributor] = Field(default_factory=list)
    note: str = ""


class ConstraintBreach(ContractModel):
    rule_id: str
    severity: ConstraintSeverity
    parameters: list[str]
    value: float | None = None
    limit: float | None = None
    message: str
    hint: str | None = None
    provenance: DataProvenance
    constraints_version: str


class StageResult(ContractModel):
    """Output of ``run_stage()`` for S1-S5 (7.9)."""

    stage_name: StageName
    sequence_index: int = Field(ge=1, le=5)
    substate: StageSubstate
    inputs_used: dict[str, float | str | None]
    upstream_in: UpstreamContext
    upstream_out: UpstreamContext
    health_score: Probability
    risk_level: RiskLevel
    risk_ordinal: Ordinal
    anomaly: StageAnomaly
    indicators: dict[str, float | str | bool | None]
    indicator_provenance: dict[str, DataProvenance]
    notes: list[str] = Field(default_factory=list)
    constraint_breaches: list[ConstraintBreach] = Field(default_factory=list)
    blocked: bool = False
    block_reason: str | None = None
    module_version: str
    constraints_version: str
    compute_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _invariants(self) -> StageResult:
        if self.stage_name not in INTELLIGENCE_STAGES:
            raise ValueError("StageResult covers S1-S5 only; QUALITY_INSPECTION is predict()")
        if self.sequence_index != self.stage_name.sequence_index:
            raise ValueError("sequence_index does not match stage_name")
        if self.risk_ordinal != self.risk_level.ordinal:
            raise ValueError("risk_ordinal does not match risk_level")
        if set(self.indicators) != set(self.indicator_provenance):
            raise ValueError("indicator_provenance must have one entry per indicator key")
        if self.substate not in (StageSubstate.COMPLETED, StageSubstate.BLOCKED):
            raise ValueError("run_stage() returns COMPLETED or BLOCKED")
        if self.blocked != (self.substate is StageSubstate.BLOCKED):
            raise ValueError("blocked must agree with substate")
        if self.blocked and not self.block_reason:
            raise ValueError("a blocked stage needs block_reason")
        if any(len(n) > 160 for n in self.notes):
            raise ValueError("notes are at most 160 characters each")
        return self
