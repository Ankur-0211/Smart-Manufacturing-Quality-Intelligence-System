"""``GET /api/v1/constraints`` payload (roadmap 8.4, 9.3.2).

Built from the loader's own spec models, so the API shape cannot drift from the registry schema;
the frontend generates its types from this and builds every slider, bound, step and unit from it
(rule B6).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from app.contracts.enums import StageName
from app.domain.constraint_loader import (
    CouplingRule,
    HardConstraint,
    ParameterSpec,
    RecommendationSettings,
    ResinGradeSpec,
    RiskBands,
    StageCheck,
    Submodels,
)


class ConstraintsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    content_hash: str
    units_allowed: list[str]
    resin_grades: dict[str, ResinGradeSpec]
    stage_inputs: dict[StageName, list[str]]
    parameters: list[ParameterSpec]  # registry order: setpoints first, in ProcessRecipe order
    coupling_rules: list[CouplingRule]
    hard_constraints: list[HardConstraint]
    stage_checks: dict[StageName, list[StageCheck]]
    risk_bands: RiskBands
    recommendation: RecommendationSettings
    submodels: Submodels
