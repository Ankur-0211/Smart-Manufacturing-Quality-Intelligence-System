"""Stateless prediction and explanation (roadmap R2-P3 task 3; ``POST /predict``).

Builds ``ProcessInput`` from reference codes plus a fresh context snapshot, runs the full pure
pipeline through ``QualityIntelligence.evaluate`` and persists a ``predictions`` row with
``run_id=NULL`` so its explanation stays retrievable.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import date
from typing import Any

from app.contracts.context import ProcessInput
from app.contracts.explanation import LocalExplanation
from app.contracts.interface import PipelineResult, QualityIntelligence
from app.db.base import utcnow
from app.db.errors import NotFoundError
from app.db.repositories import PredictionRepository, ReferenceRepository, context_snapshot
from app.db.session import Database
from app.services.predictions import persist_prediction

#: (recipe, RunContext JSON snapshot) -> validated recipe; raises on violation.
ParameterValidator = Callable[[Mapping[str, float], Mapping[str, Any]], Mapping[str, float]]


class ExplanationUnavailableError(Exception):
    """No stored explanation, and the model that made the prediction is no longer loaded."""


class InferenceService:
    def __init__(self, db: Database, intelligence: QualityIntelligence) -> None:
        self.db = db
        self.intelligence = intelligence

    def build_input(
        self,
        *,
        machine_id: str,
        product_id: str,
        material_lot_id: str,
        parameters: Mapping[str, float],
        validate_parameters: ParameterValidator,
        today: date | None = None,
    ) -> ProcessInput:
        """Resolve references (``NotFoundError``), snapshot context, validate the recipe."""
        with self.db.session() as s:
            refs = ReferenceRepository(s)
            machine, product = refs.machine(machine_id), refs.product(product_id)
            lot = refs.material(material_lot_id)
            if not machine.active:
                raise NotFoundError("machine", machine_id)
            if not product.active:
                raise NotFoundError("product", product_id)
            snapshot = context_snapshot(machine, product, lot, today=today or utcnow().date())
        recipe = validate_parameters(parameters, snapshot)
        return ProcessInput.model_validate({"context": snapshot, "recipe": recipe})

    def predict(self, inp: ProcessInput, *, include_explanation: bool) -> dict[str, Any]:
        """Evaluate and persist. Returns ``{prediction_id, stage_results, prediction}`` JSON."""
        t0 = time.perf_counter()
        result: PipelineResult = self.intelligence.evaluate(
            inp, include_explanation=include_explanation
        )
        compute_ms = round((time.perf_counter() - t0) * 1000, 3)
        prediction = result.prediction.model_dump(mode="json")
        with self.db.session() as s:
            row = persist_prediction(
                s,
                None,
                prediction,
                compute_ms=compute_ms,
                input_snapshot=inp.model_dump(mode="json"),
            )
            prediction_id = row.id
        return {
            "prediction_id": prediction_id,
            "stage_results": [r.model_dump(mode="json") for r in result.stage_results],
            "prediction": prediction,
        }

    def explanation(self, prediction_id: str) -> LocalExplanation:
        """Stored explanation, or a recomputation when the same model is still loaded.

        Raises ``NotFoundError`` (unknown id) or ``ExplanationUnavailableError``.
        """
        with self.db.session() as s:
            row = PredictionRepository(s).get(prediction_id)
            stored = row.explanation
            snapshot = row.input_snapshot
            model_version = f"{row.model_version.name}-{row.model_version.semver}"
        # Run predictions always store their explanation (the engine predicts with it on).
        if stored is not None:
            return LocalExplanation.model_validate(stored)
        info = self.intelligence.version_info()
        if snapshot is None or info.model_version != model_version:
            raise ExplanationUnavailableError(
                f"prediction {prediction_id} has no stored explanation and model {model_version} "
                f"is not loaded (current: {info.model_version})"
            )
        # Deterministic pipeline (roadmap 9.1 #1): re-evaluating the stored input reproduces the
        # stage results and prediction the explanation refers to.
        inp = ProcessInput.model_validate(snapshot)
        result = self.intelligence.evaluate(inp, include_explanation=False)
        return self.intelligence.explain(inp, result.stage_results, result.prediction)
