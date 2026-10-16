"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

PredictionResult (roadmap 7.12, 7.13), FeatureVector and PipelineResult (9.1).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from ._base import ContractModel, Probability
from .anomaly import AnomalyResult
from .enums import InferenceBackend, PredictionLabel, RiskLevel
from .explanation import LocalExplanation, StageShare
from .stage import StageResult

CaveatCode = Literal[
    "OUT_OF_DISTRIBUTION",
    "ANOMALY_DETECTED",
    "CRITICAL_CONSTRAINT_OVERRIDDEN",
    "MOCK_INFERENCE",
    "CONSTRAINTS_VERSION_MISMATCH",
    "STAGE_SUBMODEL_DISABLED",
]

STAGE_SHARE_TOLERANCE = 1e-6


class RiskDriver(ContractModel):
    source: Literal["model", "anomaly", "constraint"]
    detail: str
    weight: float


class Uncertainty(ContractModel):
    method: Literal["none", "ensemble_spread"] = "none"
    value: float | None = None


class OodFeature(ContractModel):
    feature: str
    value: float
    p01: float
    p99: float


class OodInfo(ContractModel):
    is_out_of_distribution: bool = False
    features_outside: list[OodFeature] = Field(default_factory=list)


class Caveat(ContractModel):
    code: CaveatCode
    message: str
    features: list[str] = Field(default_factory=list)


class PredictionResult(ContractModel):
    label: PredictionLabel
    p_fail: Probability  # calibrated
    p_fail_raw: Probability
    threshold_used: Probability
    model_version: str
    risk_level: RiskLevel  # operational risk (7.13)
    risk_drivers: list[RiskDriver] = Field(default_factory=list)
    stage_risk_mass: list[StageShare] = Field(default_factory=list)
    explanation: LocalExplanation | None = None
    uncertainty: Uncertainty = Field(default_factory=Uncertainty)
    anomaly_global: AnomalyResult | None = None
    ood: OodInfo = Field(default_factory=OodInfo)
    caveats: list[Caveat] = Field(default_factory=list)
    constraint_override_applied: bool = False
    inference_backend: InferenceBackend
    is_mock: bool
    feature_schema_hash: str
    constraints_version: str
    compute_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def _invariants(self) -> PredictionResult:
        codes = {c.code for c in self.caveats}
        if (self.label is PredictionLabel.FAIL) != (self.p_fail >= self.threshold_used):
            raise ValueError("label must be FAIL iff p_fail >= threshold_used")
        if self.is_mock != (self.inference_backend is InferenceBackend.MOCK):
            raise ValueError('is_mock must equal inference_backend == "mock"')
        if self.is_mock and "MOCK_INFERENCE" not in codes:
            raise ValueError("mock predictions carry the MOCK_INFERENCE caveat")
        if self.stage_risk_mass:
            total = sum(s.share for s in self.stage_risk_mass)
            if abs(total - 1.0) > STAGE_SHARE_TOLERANCE:
                raise ValueError("stage_risk_mass shares must sum to 1")
        if self.constraint_override_applied:
            # Critical-breach rule (7.12): never an ordinary confident PASS.
            if self.risk_level is not RiskLevel.CRITICAL:
                raise ValueError("an overridden critical breach forces risk_level CRITICAL")
            if "CRITICAL_CONSTRAINT_OVERRIDDEN" not in codes:
                raise ValueError("an overridden critical breach needs its caveat")
        return self


class FeatureVector(ContractModel):
    names: list[str]  # schema order
    values: list[float | None]
    feature_schema_hash: str

    @model_validator(mode="after")
    def _aligned(self) -> FeatureVector:
        if len(self.names) != len(self.values):
            raise ValueError("names and values must have the same length")
        return self


class PipelineResult(ContractModel):
    stage_results: list[StageResult]
    prediction: PredictionResult
