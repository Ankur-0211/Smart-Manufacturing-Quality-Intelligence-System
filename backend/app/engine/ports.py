"""The engine's single outbound port to the intelligence layer (Role 2 internal).

The engine works on JSON payloads (``model_dump(mode="json")`` of the contract objects) and reads
only the fields roadmap R2-P4 allows it to rely on: ``StageResult.blocked``, ``block_reason``,
``upstream_out``, ``anomaly.flag`` and ``constraint_breaches``; everything else is stored and
streamed unchanged.

This is NOT a second definition of the contracts. Once ``app.contracts`` is available, an adapter
(R2-P5) implements this port by delegating to ``QualityIntelligence.run_stage`` / ``predict`` and to
``ConstraintRegistry.stage_inputs``; until then no executor is bound and simulation commands answer
501 ``CAPABILITY_UNAVAILABLE``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol


class StageExecutor(Protocol):
    #: "real" | "mock" — persisted on runs and predictions for traceability.
    inference_backend: str
    constraints_version: str

    def module_version(self, stage: str) -> str:
        """Version of the stage module (part of the cache key)."""
        ...

    def stage_inputs(self, stage: str) -> Sequence[str]:
        """Field names of the raw input slice for ``stage`` (registry ``stage_inputs``)."""
        ...

    def run_stage(
        self, stage: str, process_input: Mapping[str, Any], upstream: Mapping[str, Any]
    ) -> dict[str, Any]:
        """StageResult JSON for S1-S5 (roadmap §7.9)."""
        ...

    def predict(
        self, process_input: Mapping[str, Any], stage_results: Sequence[Mapping[str, Any]]
    ) -> dict[str, Any]:
        """PredictionResult JSON incl. explanation (roadmap §7.12)."""
        ...
