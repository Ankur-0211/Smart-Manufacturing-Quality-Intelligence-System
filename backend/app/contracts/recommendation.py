"""Recommendation engine contracts (roadmap Section 7.15)."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from .enums import CandidateFlag, PredictionLabel, RiskLevel, StageName


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RecommendationRequest(_Frozen):
    locked: list[str] = Field(default_factory=list)
    max_changes: int = Field(default=3, ge=1, le=6)
    n_options: int = Field(default=3, ge=1, le=10)
    objective: Literal["min_p_fail"] = "min_p_fail"
    enable_refinement: bool = False
    time_budget_s: float = 5.0
    seed: int = 0


class ParameterChange(_Frozen):
    parameter: str
    from_value: float
    to_value: float
    delta: float
    unit: str


class GuardCheck(_Frozen):
    check: Literal["box", "hard_constraints", "couplings", "distribution", "step_size", "stability"]
    passed: bool
    detail: str


class StabilityReport(_Frozen):
    trials: int = 20
    flips: int = 0
    stable: bool = True


class StageHealthAfter(_Frozen):
    stage: StageName
    health_score: float = Field(ge=0.0, le=1.0)
    risk_level: RiskLevel


class RecommendationCandidate(_Frozen):
    option_rank: int = Field(ge=1)
    option_label: Literal["Minimal change", "Balanced", "Aggressive"]
    changes: list[ParameterChange] = Field(default_factory=list)
    predicted_p_fail: float = Field(ge=0.0, le=1.0)
    predicted_label: PredictionLabel
    delta_p_fail: float
    stage_health_after: list[StageHealthAfter] = Field(default_factory=list)
    constraint_status: Literal["ALL_SATISFIED"] = "ALL_SATISFIED"
    guard_checks: list[GuardCheck] = Field(default_factory=list)
    stability: StabilityReport = Field(default_factory=StabilityReport)
    in_distribution: bool = True
    flags: list[CandidateFlag] = Field(default_factory=list)
    cycle_time_delta_s: float = 0.0
    cycle_time_delta_pct: float = 0.0
    change_cost: float = 0.0
    score: float = 0.0
    rationale: list[str] = Field(default_factory=list)
    search_method: Literal["rule_proposal", "coordinate", "pairwise", "differential_evolution"] = "coordinate"


class RecommendationResponse(_Frozen):
    base_p_fail: float
    base_label: PredictionLabel
    candidates: list[RecommendationCandidate] = Field(default_factory=list)
    evaluated_count: int = 0
    rejected_counts: dict[str, int] = Field(default_factory=dict)
    empty_reason: str | None = None
    model_version: str = "fusion-1.0.0"
    constraints_version: str = "constraints-1.0.0"
    disclaimer_key: str = "DISCLAIMER_RECOMMENDATION"
    compute_ms: float = 0.0
