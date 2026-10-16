"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

AnomalyResult (roadmap 7.11) and the P1 SPC shapes used by ``spc_check`` (9.1).
SpcSeries / SpcAlert are not specified field-by-field in the roadmap: PROVISIONAL (Role 1 confirms).
"""

from __future__ import annotations

from pydantic import Field

from ._base import ContractModel, Probability
from .enums import AnomalyMethod
from .stage import AnomalyContributor


class AnomalyResult(ContractModel):
    scope: str  # "global" or "stage:<StageName>"
    method: AnomalyMethod
    score: Probability
    is_anomaly: bool
    threshold: float
    top_contributors: list[AnomalyContributor] = Field(default_factory=list)
    note: str = ""
    model_version: str | None = None  # null for rule-based L1


class SpcSeries(ContractModel):
    """PROVISIONAL (P1)."""

    parameter: str
    values: list[float] = Field(min_length=1)
    machine_id: str | None = None


class SpcAlert(ContractModel):
    """PROVISIONAL (P1)."""

    rule: str
    parameter: str
    index: int = Field(ge=0)
    message: str
