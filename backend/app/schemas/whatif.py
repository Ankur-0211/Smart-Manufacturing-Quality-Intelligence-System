"""``/whatif`` and ``/recommend`` payloads (roadmap 7.15, 7.16, 9.3.2). Contract types embedded."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.prediction import PredictionResult
from app.contracts.recommendation import RecommendationResponse
from app.contracts.stage import StageResult
from app.schemas.simulation import ScenarioSummary


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WhatIfRequest(_Strict):
    """Overrides use canonical recipe names; registry windows and couplings are enforced."""

    base_run_id: str
    overrides: dict[str, float] = Field(min_length=1)
    persist: bool = True
    label: str | None = Field(default=None, max_length=200)


class ParameterDiff(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str
    from_: float = Field(alias="from")
    to: float
    delta: float


class StageDiff(BaseModel):
    stage: str
    health_from: float
    health_to: float
    risk_from: str
    risk_to: str
    change: Literal["improved", "worsened", "unchanged"]


class PredictionDiff(BaseModel):
    label_from: str
    label_to: str
    p_fail_from: float
    p_fail_to: float
    p_fail_delta: float
    flipped: bool


class RiskDiff(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: str = Field(alias="from")
    to: str
    band_delta: int


class ComplianceDiff(BaseModel):
    warnings_from: int
    warnings_to: int
    critical_from: int
    critical_to: int


class CycleTimeDiff(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_: float = Field(alias="from")
    to: float
    delta_s: float
    delta_pct: float


class RunDiff(BaseModel):
    """Roadmap 7.16 ``diff`` (Plan §16.4 example, §13.6 table)."""

    parameters: list[ParameterDiff]
    stages: list[StageDiff]
    prediction: PredictionDiff
    operational_risk: RiskDiff
    constraint_compliance: ComplianceDiff
    cycle_time: CycleTimeDiff


class WhatIfResult(BaseModel):
    run_id: str | None  # null when persist=false
    parent_run_id: str
    recomputed_stages: list[str]
    reused_stages: list[str]
    stage_results: list[StageResult]
    prediction: PredictionResult
    diff: RunDiff


class CompareRequest(_Strict):
    run_id_a: str
    run_id_b: str


class SensitivityRequest(_Strict):
    base_run_id: str
    parameter: str
    steps: int = Field(default=40, ge=2, le=200)


class RecommendRequest(_Strict):
    run_id: str
    locked: list[str] = Field(default_factory=list)
    max_changes: int = Field(default=3, ge=1, le=6)
    n_options: int = Field(default=3, ge=1, le=10)
    objective: Literal["min_p_fail"] = "min_p_fail"
    enable_refinement: bool = False


class RecommendOut(RecommendationResponse):
    request_id: str


class LineageOut(BaseModel):
    run: ScenarioSummary
    children: list[LineageOut]
