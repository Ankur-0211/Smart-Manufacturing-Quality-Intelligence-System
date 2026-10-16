"""HybridQualityIntelligence (roadmap 9.1 factory, UD-11; R2-P1 task 8).

Routes each call to the real facade when ``real.capabilities()`` reports that capability, and to
the mock otherwise. Every output keeps the ``inference_backend`` of the implementation that made
it, so a mock value can never be presented as real.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.contracts.anomaly import AnomalyResult, SpcAlert, SpcSeries
from app.contracts.context import ProcessInput
from app.contracts.enums import InferenceBackend, StageName
from app.contracts.explanation import GlobalExplanation, LocalExplanation
from app.contracts.interface import CAPABILITY_NAMES, IntelligenceVersionInfo, QualityIntelligence
from app.contracts.prediction import FeatureVector, PipelineResult, PredictionResult
from app.contracts.recommendation import RecommendationRequest, RecommendationResponse
from app.contracts.sensitivity import SensitivityResult
from app.contracts.stage import StageResult, UpstreamContext


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
            for c in CAPABILITY_NAMES
        }

    def capabilities(self) -> dict[str, bool]:
        mock_caps = self.mock.capabilities()
        return {
            c: self._real_caps.get(c, False) or mock_caps.get(c, False) for c in CAPABILITY_NAMES
        }

    def version_info(self) -> IntelligenceVersionInfo:
        stages = self._for("run_stage").version_info()
        fusion = self._for("predict").version_info()
        any_mock = any(b is InferenceBackend.MOCK for b in self.routing().values())
        return fusion.model_copy(
            update={
                "module_versions": stages.module_versions,
                "inference_backend": InferenceBackend.MOCK if any_mock else InferenceBackend.REAL,
                "is_mock": any_mock,
                "capabilities": self.capabilities(),
            }
        )

    def run_stage(
        self, stage: StageName, inp: ProcessInput, upstream: UpstreamContext
    ) -> StageResult:
        return self._for("run_stage").run_stage(stage, inp, upstream)

    def run_all_stages(self, inp: ProcessInput) -> list[StageResult]:
        return self._for("run_stage").run_all_stages(inp)

    def build_features(
        self, inp: ProcessInput, stage_results: Sequence[StageResult]
    ) -> FeatureVector:
        return self._for("predict").build_features(inp, stage_results)

    def predict(
        self,
        inp: ProcessInput,
        stage_results: Sequence[StageResult],
        include_explanation: bool = True,
    ) -> PredictionResult:
        prediction = self._for("predict").predict(inp, stage_results, include_explanation=False)
        if include_explanation:
            prediction = prediction.model_copy(
                update={"explanation": self.explain(inp, stage_results)}
            )
        return prediction

    def explain(
        self, inp: ProcessInput, stage_results: Sequence[StageResult], top_k: int = 10
    ) -> LocalExplanation:
        return self._for("explain").explain(inp, stage_results, top_k)

    def global_explanation(self) -> GlobalExplanation:
        return self._for("global_explanation").global_explanation()

    def detect_anomaly(
        self, inp: ProcessInput, stage_results: Sequence[StageResult]
    ) -> AnomalyResult:
        return self._for("anomaly_global").detect_anomaly(inp, stage_results)

    def evaluate(self, inp: ProcessInput, include_explanation: bool = False) -> PipelineResult:
        # Composed from the routed parts so evaluate == run_all_stages + predict (9.1 #4).
        stages = self.run_all_stages(inp)
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

    def spc_check(self, series: SpcSeries) -> list[SpcAlert]:
        return self._for("spc").spc_check(series)
