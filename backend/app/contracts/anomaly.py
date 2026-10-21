"""Anomaly detection contracts (roadmap Section 7.11)."""
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from .enums import AnomalyMethod


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AnomalyContributor(_Frozen):
    feature: str
    deviation: float


class AnomalyResult(_Frozen):
    scope: str
    method: AnomalyMethod
    score: float = Field(ge=0.0, le=1.0)
    is_anomaly: bool
    threshold: float
    top_contributors: list[AnomalyContributor] = Field(default_factory=list)
    note: str = ""
    model_version: str | None = None
