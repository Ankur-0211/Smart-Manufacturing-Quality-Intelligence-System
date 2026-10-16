"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

RecommendationRequest, RecommendationCandidate and RecommendationResponse (roadmap 7.15).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import ContractModel, Probability
from .enums import CandidateFlag, PredictionLabel, RiskLevel, StageName

GuardCheckName = Literal[
    "box", "hard_constraints", "couplings", "distribution", "step_size", "stability"
]


class RecommendationRequest(ContractModel):
    locked: list[str] = Field(default_factory=list)  # on top of registry non-actionable fields
    max_changes: int = Field(default=3, ge=1, le=6)
    n_options: int = Field(default=3, ge=1)
    objective: Literal["min_p_fail"] = "min_p_fail"
    enable_refinement: bool = False  # P1 differential evolution
    time_budget_s: float = Field(default=5.0, gt=0.0)
    seed: int = 0


class ParameterChange(ContractModel):
    parameter: str
    from_value: float
    to_value: float
    delta: float
    unit: str | None


class StageHealthAfter(ContractModel):
    stage: StageName
    health_score: Probability
    risk_level: RiskLevel


class GuardCheck(ContractModel):
    check: GuardCheckName
    passed: bool
    detail: str = ""


class Stability(ContractModel):
    trials: int = Field(default=20, ge=1)
    flips: int = Field(ge=0)
    stable: bool


class RecommendationCandidate(ContractModel):
    option_rank: int = Field(ge=1)
    option_label: Literal["Minimal change", "Balanced", "Aggressive"]
    changes: list[ParameterChange] = Field(min_length=1)
    predicted_p_fail: Probability
    predicted_label: PredictionLabel
    delta_p_fail: float
    stage_health_after: list[StageHealthAfter]
    # Returned candidates always satisfy every constraint; anything else is never returned.
    constraint_status: Literal["ALL_SATISFIED"] = "ALL_SATISFIED"
    guard_checks: list[GuardCheck]
    stability: Stability
    in_distribution: bool
    flags: list[CandidateFlag] = Field(default_factory=list)
    cycle_time_delta_s: float
    cycle_time_delta_pct: float
    change_cost: float
    score: float
    rationale: list[str] = Field(default_factory=list)
    search_method: Literal["rule_proposal", "coordinate", "pairwise", "differential_evolution"]


class RecommendationResponse(ContractModel):
    base_p_fail: Probability
    base_label: PredictionLabel
    candidates: list[RecommendationCandidate]
    evaluated_count: int = Field(ge=0)
    rejected_counts: dict[GuardCheckName, int] = Field(default_factory=dict)
    empty_reason: str | None = None
    model_version: str
    constraints_version: str
    disclaimer_key: Literal["DISCLAIMER_RECOMMENDATION"] = "DISCLAIMER_RECOMMENDATION"
    compute_ms: float = Field(ge=0.0)
