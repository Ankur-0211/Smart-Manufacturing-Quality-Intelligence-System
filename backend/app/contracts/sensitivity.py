"""Sensitivity sweep contracts (roadmap Section 7.16)."""
from pydantic import BaseModel, ConfigDict, Field

from .enums import PredictionLabel


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SensitivityPoint(_Frozen):
    value: float
    p_fail: float = Field(ge=0.0, le=1.0)
    label: PredictionLabel


class SensitivityResult(_Frozen):
    parameter: str
    unit: str
    current_value: float
    points: list[SensitivityPoint] = Field(default_factory=list)
    local_gradient: float = 0.0
    range_swing: float = 0.0
    flip_point: float | None = None
