"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

The intelligence interface (roadmap 9.1): the ONLY surface through which Role 2 reaches Role 1.
Guarantees: deterministic, stateless (beyond immutable artifacts and pure caches), thread safe;
``evaluate(inp) == run_all_stages(inp) + predict(...)``; recommendations are scored through the
identical run_stage/predict path. Domain breaches are data; failures raise IntelligenceError.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import Field

from ._base import ContractModel
from .anomaly import AnomalyResult, SpcAlert, SpcSeries
from .context import ProcessInput
from .enums import InferenceBackend, StageName
from .explanation import GlobalExplanation, LocalExplanation
from .prediction import FeatureVector, PipelineResult, PredictionResult
from .recommendation import RecommendationRequest, RecommendationResponse
from .sensitivity import SensitivityResult
from .stage import StageResult, UpstreamContext

CAPABILITY_NAMES: tuple[str, ...] = (
    "run_stage",
    "predict",
    "explain",
    "global_explanation",
    "anomaly_global",
    "recommend",
    "sensitivity",
    "spc",
)
# Capabilities that `real` mode must provide at startup (9.1 factory).
P0_CAPABILITIES: tuple[str, ...] = ("run_stage", "predict", "explain", "recommend")


class IntelligenceVersionInfo(ContractModel):
    contracts_version: str
    constraints_version: str
    module_versions: dict[StageName, str]
    fusion_model_version: str | None
    anomaly_model_version: str | None = None
    stage_stats_version: str | None = None
    feature_schema_hash: str | None
    inference_backend: InferenceBackend
    is_mock: bool
    capabilities: dict[str, bool] = Field(default_factory=dict)


@runtime_checkable
class QualityIntelligence(Protocol):
    def version_info(self) -> IntelligenceVersionInfo: ...

    def capabilities(self) -> dict[str, bool]: ...

    # ---- stage intelligence (S1-S5), pure ----
    def run_stage(
        self, stage: StageName, inp: ProcessInput, upstream: UpstreamContext
    ) -> StageResult: ...

    def run_all_stages(self, inp: ProcessInput) -> list[StageResult]: ...

    # ---- fusion (S6) ----
    def build_features(
        self, inp: ProcessInput, stage_results: Sequence[StageResult]
    ) -> FeatureVector: ...

    def predict(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        include_explanation: bool = True,
    ) -> PredictionResult: ...

    def explain(
        self, inp: ProcessInput, stage_results: Sequence[StageResult], top_k: int = 10
    ) -> LocalExplanation: ...

    def global_explanation(self) -> GlobalExplanation: ...

    def detect_anomaly(
        self, inp: ProcessInput, stage_results: Sequence[StageResult]
    ) -> AnomalyResult: ...

    # ---- convenience: full pure pipeline ----
    def evaluate(self, inp: ProcessInput, include_explanation: bool = False) -> PipelineResult: ...

    # ---- decision support ----
    def recommend(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        prediction: PredictionResult,
        request: RecommendationRequest,
    ) -> RecommendationResponse: ...

    def sensitivity(
        self, inp: ProcessInput, parameter: str, steps: int = 40
    ) -> SensitivityResult: ...

    def spc_check(self, series: SpcSeries) -> list[SpcAlert]: ...  # P1
