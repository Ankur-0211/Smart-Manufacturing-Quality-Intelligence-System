"""Prediction result contracts for the fusion quality engine (roadmap Section 7.12)."""
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from .anomaly import AnomalyResult
from .enums import InferenceBackend, PredictionLabel, RiskLevel
from .explanation import LocalExplanation, StageRiskShare


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RiskDriver(_Frozen):
    source: Literal["model", "anomaly", "constraint"]
    detail: str
    weight: float


class CaveatItem(_Frozen):
    code: str
    message: str
    features: list[str] = Field(default_factory=list)


class OodFeature(_Frozen):
    feature: str
    value: float | None
    p01: float
    p99: float


class OodReport(_Frozen):
    is_out_of_distribution: bool
    features_outside: list[OodFeature] = Field(default_factory=list)


class UncertaintyEstimate(_Frozen):
    method: Literal["none", "ensemble_spread"] = "none"
    value: float | None = None


class PredictionResult(_Frozen):
    label: PredictionLabel
    p_fail: float = Field(ge=0.0, le=1.0)
    p_fail_raw: float = Field(ge=0.0, le=1.0)
    threshold_used: float = Field(ge=0.0, le=1.0)
    model_version: str = "fusion-1.0.0"
    risk_level: RiskLevel
    risk_drivers: list[RiskDriver] = Field(default_factory=list)
    stage_risk_mass: list[StageRiskShare] = Field(default_factory=list)
    explanation: LocalExplanation | None = None
    uncertainty: UncertaintyEstimate = Field(default_factory=UncertaintyEstimate)
    anomaly_global: AnomalyResult | None = None
    ood: OodReport = Field(default_factory=lambda: OodReport(is_out_of_distribution=False))
    caveats: list[CaveatItem] = Field(default_factory=list)
    constraint_override_applied: bool = False
    inference_backend: InferenceBackend = InferenceBackend.REAL
    is_mock: bool = False
    feature_schema_hash: str = "sha256-default"
    constraints_version: str = "constraints-1.0.0"
    compute_ms: float = 0.0
