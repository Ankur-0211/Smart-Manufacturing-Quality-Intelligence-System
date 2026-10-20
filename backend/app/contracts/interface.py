"""In-process Python protocol for QualityIntelligence (roadmap Section 9.1)."""
from collections.abc import Sequence
from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel, ConfigDict

from .context import ProcessInput
from .enums import StageName
from .explanation import GlobalExplanation, LocalExplanation
from .prediction import PredictionResult
from .recommendation import RecommendationRequest, RecommendationResponse
from .sensitivity import SensitivityResult
from .stage import StageResult, UpstreamContext


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IntelligenceVersionInfo(_Frozen):
    contracts_version: str
    constraints_version: str
    model_version: str
    is_mock: bool
    capabilities: dict[str, bool]


class PipelineResult(_Frozen):
    stage_results: list[StageResult]
    prediction: PredictionResult


@runtime_checkable
class QualityIntelligence(Protocol):
    """The single interface between application and intelligence layers."""

    def capabilities(self) -> dict[str, bool]:
        """Return dict of available capabilities e.g. {'run_stage': True, 'predict': True, ...}."""
        ...

    def version_info(self) -> IntelligenceVersionInfo:
        """Return version metadata."""
        ...

    def run_stage(
        self, stage: StageName, inp: ProcessInput, upstream: UpstreamContext
    ) -> StageResult:
        """Run single stage intelligence (S1-S5)."""
        ...

    def predict(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        include_explanation: bool = True,
    ) -> PredictionResult:
        """Execute fusion quality prediction (S6)."""
        ...

    def explain(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        prediction: PredictionResult,
    ) -> LocalExplanation:
        """Compute local SHAP explanation and stage risk mass."""
        ...

    def global_explanation(self) -> GlobalExplanation:
        """Return global feature importance."""
        ...

    def evaluate(
        self, inp: ProcessInput, include_explanation: bool = False
    ) -> PipelineResult:
        """Convenience full pipeline: run all S1-S5 stages + S6 predict."""
        ...

    def recommend(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        prediction: PredictionResult,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        """Search constrained parameter space for lower p_fail candidates."""
        ...

    def sensitivity(
        self, inp: ProcessInput, parameter: str, steps: int = 40
    ) -> SensitivityResult:
        """Perform 1D parameter sweep across admissible window."""
        ...
