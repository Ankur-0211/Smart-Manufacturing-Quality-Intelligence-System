"""Explanation contracts for SHAP attribution and stage risk mass (roadmap Section 7.14)."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from .enums import StageName


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FeatureAttribution(_Frozen):
    feature: str
    display_name: str
    value: float | str | None
    shap_value: float
    direction: Literal["toward_fail", "toward_pass"]
    stage: str
    group: str


class GroupedAttribution(_Frozen):
    group: str
    shap_sum: float


class StageRiskShare(_Frozen):
    stage: StageName
    share: float = Field(ge=0.0, le=1.0)


class LocalExplanation(_Frozen):
    method: str = "tree_shap"
    output_space: str = "log_odds"
    base_value: float
    attributions: list[FeatureAttribution] = Field(default_factory=list)
    grouped_attributions: list[GroupedAttribution] = Field(default_factory=list)
    stage_risk_mass: list[StageRiskShare] = Field(default_factory=list)
    background_version: str = "bg-1.0.0"
    show_caveat_banner: bool = False


class GlobalAttributionItem(_Frozen):
    feature: str
    value: float
    stage: str


class GlobalExplanation(_Frozen):
    model_version: str
    mean_abs_shap: list[GlobalAttributionItem] = Field(default_factory=list)
    computed_on: str
    n_rows: int
