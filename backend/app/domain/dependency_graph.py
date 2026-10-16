"""BOOTSTRAP v0.1.0 by Role 2 (CCR-002) — owner: Role 1.

Stage dependency graph (roadmap 8.4, 13.2 what-if invalidation). Pure; built only from the
registry's ``stage_inputs`` block, so no field-to-stage mapping is hand-written anywhere else.

Changing a field invalidates the EARLIEST stage whose raw slice reads it, plus every downstream
stage (upstream context propagates forward). A field read by no stage module (e.g. machine_id,
tonnage_ton) feeds only the fusion model: it invalidates no stage, only the prediction.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from app.contracts.enums import INTELLIGENCE_STAGES, StageName


class StageDependencyGraph:
    def __init__(self, stage_inputs: Mapping[StageName, Sequence[str]]) -> None:
        missing = [s for s in INTELLIGENCE_STAGES if s not in stage_inputs]
        if missing:
            raise ValueError(f"stage_inputs missing stages: {', '.join(missing)}")
        self._inputs: dict[StageName, tuple[str, ...]] = {
            s: tuple(stage_inputs[s]) for s in INTELLIGENCE_STAGES
        }
        first: dict[str, StageName] = {}
        for stage in INTELLIGENCE_STAGES:  # canonical order, so the first hit is the earliest
            for field in self._inputs[stage]:
                first.setdefault(field, stage)
        self._first_stage = first

    def stage_inputs(self, stage: StageName) -> list[str]:
        if stage not in self._inputs:
            raise ValueError(f"{stage} has no raw input slice (S1-S5 only)")
        return list(self._inputs[stage])

    def first_stage(self, field: str) -> StageName | None:
        """Earliest stage reading ``field``; None if only the fusion model uses it."""
        return self._first_stage.get(field)

    def fields(self) -> frozenset[str]:
        return frozenset(self._first_stage)

    def invalidated_stages(self, changed: Iterable[str]) -> list[StageName]:
        """Earliest affected stage and everything downstream, in canonical order."""
        indices = [
            INTELLIGENCE_STAGES.index(stage)
            for field in changed
            if (stage := self._first_stage.get(field)) is not None
        ]
        if not indices:
            return []
        return list(INTELLIGENCE_STAGES[min(indices) :])
