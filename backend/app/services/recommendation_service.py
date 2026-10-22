"""Recommendations for a finished run (roadmap 7.15, R2-P5 task 9; Plan §14).

The search, guard and ranking are Role 1's (``QualityIntelligence.recommend``). Role 2 rebuilds the
contract inputs from the stored run, applies the time budget, persists one row per candidate with
the request id and model version, and returns the response unchanged.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.contracts.context import ProcessInput
from app.contracts.interface import QualityIntelligence
from app.contracts.prediction import PredictionResult
from app.contracts.recommendation import RecommendationRequest
from app.core.ids import new_id
from app.db.repositories import (
    ModelVersionRepository,
    PredictionRepository,
    RecommendationRepository,
    RunRepository,
    StageResultRepository,
)
from app.db.session import Database
from app.services.intelligence_executor import stage_result_from_json
from app.services.predictions import prediction_row_to_json, split_model_version
from app.services.simulation_service import stage_row_to_json
from app.services.whatif_service import BaseNotFinalError

_PREDICTION_FIELDS = frozenset(PredictionResult.model_fields)


def prediction_from_json(stored: Mapping[str, Any]) -> PredictionResult:
    """Rebuild the contract object from a stored row; absent values fall back to defaults."""
    data = {k: v for k, v in stored.items() if k in _PREDICTION_FIELDS and v is not None}
    return PredictionResult.model_validate(data)


class RecommendationService:
    def __init__(self, db: Database, intelligence: QualityIntelligence) -> None:
        self.db = db
        self.intelligence = intelligence

    def recommend(
        self,
        run_id: str,
        *,
        locked: Sequence[str] = (),
        max_changes: int = 3,
        n_options: int = 3,
        objective: str = "min_p_fail",
        enable_refinement: bool = False,
        time_budget_s: float = 5.0,
    ) -> dict[str, Any]:
        with self.db.session() as s:
            run = RunRepository(s).get(run_id)
            row = PredictionRepository(s).for_run(run_id)
            if run.status != "FINAL_RESULT" or row is None:
                raise BaseNotFinalError(
                    f"run {run_id} is {run.status}; recommendations need a final result"
                )
            inp = ProcessInput.model_validate(
                {"context": run.context_snapshot, "recipe": run.parameters.as_dict()}
            )
            stages = [
                stage_result_from_json(stage_row_to_json(r))
                for r in StageResultRepository(s).for_run(run_id)
            ]
            prediction = prediction_from_json(prediction_row_to_json(row))

        request = RecommendationRequest.model_validate(
            {
                "locked": list(locked),
                "max_changes": max_changes,
                "n_options": n_options,
                "objective": objective,
                "enable_refinement": enable_refinement,
                "time_budget_s": time_budget_s,
            }
        )
        response = self.intelligence.recommend(inp, stages, prediction, request)
        data = response.model_dump(mode="json")
        request_id = new_id()

        with self.db.session() as s:
            run = RunRepository(s).get(run_id)
            name, semver = split_model_version(response.model_version)
            versions = ModelVersionRepository(s)
            version = versions.find(name, semver) or versions.upsert(
                name, semver, algorithm="unregistered"
            )
            RecommendationRepository(s).add_batch(
                run,
                request_id,
                [self._row(c) for c in data["candidates"]],
                request=request.model_dump(mode="json"),
                model_version_id=version.id,
                constraints_version=response.constraints_version,
                evaluated_count=response.evaluated_count,
            )
        return {"request_id": request_id, **data}

    @staticmethod
    def _row(candidate: Mapping[str, Any]) -> dict[str, Any]:
        stability = candidate.get("stability") or {}
        trials = stability.get("trials") or 0
        return {
            "option_rank": candidate["option_rank"],
            "changes": candidate["changes"],
            "predicted_p_fail": candidate["predicted_p_fail"],
            "predicted_label": candidate["predicted_label"],
            "delta_p_fail": candidate["delta_p_fail"],
            "constraint_status": candidate["constraint_status"],
            # Share of stability trials whose label did not flip (Plan §14.4).
            "stability_score": 1.0 - stability.get("flips", 0) / trials if trials else None,
            "extrapolation_flag": "EXTRAPOLATED" in (candidate.get("flags") or []),
            "cycle_time_delta_s": candidate.get("cycle_time_delta_s"),
            "search_method": candidate.get("search_method"),
            "candidate": candidate,
        }
