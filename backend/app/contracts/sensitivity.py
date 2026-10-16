"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

SensitivityResult (roadmap 7.16). WhatIfResult / diff / ScenarioSummary are R2 API objects.
"""

from __future__ import annotations

from pydantic import Field

from ._base import ContractModel, Probability
from .enums import PredictionLabel


class SensitivityPoint(ContractModel):
    value: float
    p_fail: Probability
    label: PredictionLabel


class SensitivityResult(ContractModel):
    parameter: str
    unit: str | None
    current_value: float
    points: list[SensitivityPoint] = Field(min_length=2)  # ~40 across the admissible window
    local_gradient: float  # d p_fail / d unit at the current point (finite difference)
    range_swing: float = Field(ge=0.0, le=1.0)  # max - min p_fail
    flip_point: float | None = None  # nearest value where the label flips
