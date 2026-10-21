"""Stage execution and result contracts (roadmap Sections 7.8-7.10)."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from .enums import AnomalyMethod, ConstraintSeverity, DataProvenance, RiskLevel, StageName, StageSubstate


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class UpstreamContext(_Frozen):
    """Cumulative state passed forward from earlier stages."""
    viscosity_class: str | None = None
    moisture_flag: bool | None = None
    effective_melt_temp_c: float | None = None
    viscosity_proxy: float | None = None
    fill_completion_proxy: float | None = None
    cavity_pressure_estimate_bar: float | None = None
    residual_stress_proxy: float | None = None


class StageAnomaly(_Frozen):
    """L1 per-stage anomaly output."""
    flag: bool
    score: float = Field(ge=0.0, le=1.0)
    method: AnomalyMethod
    contributors: list[dict[str, Any]] = Field(default_factory=list)
    note: str = ""


class ConstraintBreach(_Frozen):
    """Record of a single breached parameter range, coupling rule or hard constraint."""
    rule_id: str
    severity: ConstraintSeverity
    parameters: list[str]
    value: float | None = None
    limit: float | None = None
    message: str
    hint: str | None = None
    provenance: DataProvenance = DataProvenance.UNVALIDATED
    constraints_version: str = "constraints-1.0.0"


class StageResult(_Frozen):
    """Execution output from a single stage intelligence module (S1-S5)."""
    stage_name: StageName
    sequence_index: int = Field(ge=1, le=6)
    substate: StageSubstate
    inputs_used: dict[str, Any]
    upstream_in: UpstreamContext
    upstream_out: UpstreamContext
    health_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel
    risk_ordinal: int = Field(ge=0, le=4)
    anomaly: StageAnomaly
    indicators: dict[str, Any]
    indicator_provenance: dict[str, DataProvenance] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    constraint_breaches: list[ConstraintBreach] = Field(default_factory=list)
    blocked: bool = False
    block_reason: str | None = None
    module_version: str = "1.0.0"
    constraints_version: str = "constraints-1.0.0"
    compute_ms: float = 0.0
