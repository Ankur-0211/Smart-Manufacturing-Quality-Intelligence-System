"""HybridQualityIntelligence (roadmap 9.1 factory, UD-11; R2-P1 task 8).

Routes each call to the real facade when ``real.capabilities()`` reports that capability, and to
the mock otherwise. Every output keeps the ``inference_backend`` of the implementation that made
it, so a mock value can never be presented as real.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contracts.context import ProcessInput
from app.contracts.enums import INTELLIGENCE_STAGES, InferenceBackend, StageName
from app.contracts.explanation import GlobalExplanation, LocalExplanation
from app.contracts.interface import IntelligenceVersionInfo, PipelineResult, QualityIntelligence
from app.contracts.prediction import PredictionResult
from app.contracts.recommendation import RecommendationRequest, RecommendationResponse
from app.contracts.sensitivity import SensitivityResult
from app.contracts.stage import StageResult, UpstreamContext

ROUTED_CAPABILITIES = (
    "run_stage",
    "predict",
    "explain",
    "global_explanation",
    "recommend",
    "sensitivity",
)


class HybridQualityIntelligence:
    def __init__(self, real: QualityIntelligence, mock: QualityIntelligence) -> None:
        self.real = real
        self.mock = mock
        self._real_caps = {k: bool(v) for k, v in real.capabilities().items()}

    def _for(self, capability: str) -> QualityIntelligence:
        return self.real if self._real_caps.get(capability, False) else self.mock

    def routing(self) -> dict[str, InferenceBackend]:
        """Which backend serves each capability (for /health and logs)."""
        return {
            c: InferenceBackend.REAL if self._for(c) is self.real else InferenceBackend.MOCK
            for c in ROUTED_CAPABILITIES
        }

    def capabilities(self) -> dict[str, bool]:
        mock_caps = self.mock.capabilities()
        names = set(self._real_caps) | set(mock_caps)
        return {c: self._real_caps.get(c, False) or bool(mock_caps.get(c, False)) for c in names}

    def version_info(self) -> IntelligenceVersionInfo:
        any_mock = any(b is InferenceBackend.MOCK for b in self.routing().values())
        fusion = self._for("predict").version_info()
        return fusion.model_copy(update={"is_mock": any_mock, "capabilities": self.capabilities()})

    def run_stage(
        self, stage: StageName, inp: ProcessInput, upstream: UpstreamContext
    ) -> StageResult:
        return self._for("run_stage").run_stage(stage, inp, upstream)

    def predict(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        include_explanation: bool = True,
    ) -> PredictionResult:
        prediction = self._for("predict").predict(inp, stage_results, include_explanation=False)
        if include_explanation:
            prediction = prediction.model_copy(
                update={"explanation": self.explain(inp, stage_results, prediction)}
            )
        return prediction

    def explain(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        prediction: PredictionResult,
    ) -> LocalExplanation:
        return self._for("explain").explain(inp, stage_results, prediction)

    def global_explanation(self) -> GlobalExplanation:
        return self._for("global_explanation").global_explanation()

    def evaluate(self, inp: ProcessInput, include_explanation: bool = False) -> PipelineResult:
        # Composed from the routed parts so evaluate == run_stage x5 + predict (9.1 #4).
        stages: list[StageResult] = []
        upstream = UpstreamContext()
        for stage in INTELLIGENCE_STAGES:
            result = self.run_stage(stage, inp, upstream)
            stages.append(result)
            upstream = result.upstream_out
        return PipelineResult(
            stage_results=stages,
            prediction=self.predict(inp, stages, include_explanation=include_explanation),
        )

    def recommend(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        prediction: PredictionResult,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        return self._for("recommend").recommend(inp, stage_results, prediction, request)

    def sensitivity(self, inp: ProcessInput, parameter: str, steps: int = 40) -> SensitivityResult:
        return self._for("sensitivity").sensitivity(inp, parameter, steps)
