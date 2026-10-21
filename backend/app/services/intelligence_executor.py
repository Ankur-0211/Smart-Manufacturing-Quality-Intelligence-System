"""StageExecutor adapter over ``QualityIntelligence`` (roadmap 9.1, R2-P5 port binding).

The engine speaks JSON; this adapter converts at the boundary using the contract models, so a
payload that drifts from the contracts fails here, never deeper in the engine or the DB.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.contracts.context import ProcessInput
from app.contracts.enums import StageName, StageSubstate
from app.contracts.interface import QualityIntelligence
from app.contracts.stage import StageResult, UpstreamContext
from app.domain.constraint_loader import ConstraintRegistry

_STAGE_FIELDS = frozenset(StageResult.model_fields)


def stage_result_from_json(payload: Mapping[str, Any]) -> StageResult:
    """Rebuild a StageResult from a stored/streamed row.

    The DB stores an overridden stage as COMPLETED with ``blocked=true``; for the intelligence it
    is still a stage that passed through BLOCKED, so the contract substate is restored.
    """
    data = {k: v for k, v in payload.items() if k in _STAGE_FIELDS}
    if data.get("blocked"):
        data["substate"] = StageSubstate.BLOCKED.value
    return StageResult.model_validate(data)


def inference_backend_of(intelligence: QualityIntelligence) -> str:
    """ "mock" whenever any mock output may be produced (mock or hybrid), else "real"."""
    return "mock" if intelligence.version_info().is_mock else "real"


class IntelligenceStageExecutor:
    """Implements ``app.engine.ports.StageExecutor`` by delegating to the intelligence layer."""

    def __init__(self, intelligence: QualityIntelligence, registry: ConstraintRegistry) -> None:
        self.intelligence = intelligence
        self.registry = registry
        info = intelligence.version_info()
        self.inference_backend: str = inference_backend_of(intelligence)
        self.constraints_version: str = registry.version
        # Role 1's version info carries one model_version, no per-stage module versions
        # (CCR-004); it versions every stage's cache entries.
        self._module_version = info.model_version

    def module_version(self, stage: str) -> str:
        return self._module_version

    def stage_inputs(self, stage: str) -> Sequence[str]:
        """Parameters first consumed by ``stage`` (Role 1's ``stage_inputs``), for display."""
        return self.registry.stage_inputs(StageName(stage))

    def run_stage(
        self, stage: str, process_input: Mapping[str, Any], upstream: Mapping[str, Any]
    ) -> dict[str, Any]:
        result = self.intelligence.run_stage(
            StageName(stage),
            ProcessInput.model_validate(process_input),
            UpstreamContext.model_validate(upstream),
        )
        return result.model_dump(mode="json")

    def predict(
        self, process_input: Mapping[str, Any], stage_results: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        prediction = self.intelligence.predict(
            ProcessInput.model_validate(process_input),
            [stage_result_from_json(r) for r in stage_results],
            include_explanation=True,
        )
        return prediction.model_dump(mode="json")
