"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

LocalExplanation and GlobalExplanation (roadmap 7.14).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ._base import ContractModel
from .enums import StageName


class Attribution(ContractModel):
    feature: str
    display_name: str
    value: float | str | None
    shap_value: float
    direction: Literal["toward_fail", "toward_pass"]
    stage: StageName | Literal["CONTEXT"]
    group: str


class GroupedAttribution(ContractModel):
    group: str
    shap_sum: float


class StageShare(ContractModel):
    stage: StageName
    share: float = Field(ge=0.0, le=1.0)


class LocalExplanation(ContractModel):
    method: Literal["tree_shap"] = "tree_shap"
    output_space: Literal["log_odds"] = "log_odds"  # explains the uncalibrated margin
    base_value: float
    attributions: list[Attribution]  # top-k, sorted by |shap_value|
    grouped_attributions: list[GroupedAttribution] = Field(default_factory=list)
    stage_risk_mass: list[StageShare] = Field(default_factory=list)
    background_version: str
    show_caveat_banner: bool = False


class GlobalImportance(ContractModel):
    feature: str
    value: float = Field(ge=0.0)
    stage: StageName | Literal["CONTEXT"]


class GlobalExplanation(ContractModel):
    model_version: str
    mean_abs_shap: list[GlobalImportance]
    computed_on: str
    n_rows: int = Field(ge=0)
