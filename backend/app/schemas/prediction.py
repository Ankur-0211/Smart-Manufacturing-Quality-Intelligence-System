"""``/predict`` and ``/models`` payloads (roadmap 9.3.2). Contract types embedded, not copied."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.contracts.interface import IntelligenceVersionInfo
from app.contracts.prediction import PredictionResult
from app.contracts.recipe import ProcessRecipe
from app.contracts.stage import StageResult


class PredictRequest(BaseModel):
    """Windows and couplings come from the registry and are enforced server-side (rule B6)."""

    model_config = ConfigDict(extra="forbid")

    machine_id: str
    product_id: str
    material_lot_id: str
    parameters: ProcessRecipe
    include_explanation: bool = True


class PredictResponse(BaseModel):
    prediction_id: str
    stage_results: list[StageResult]
    prediction: PredictionResult


class ModelVersionOut(BaseModel):
    version: str  # "<name>-<semver>", the form predictions carry in model_version
    name: str
    semver: str
    algorithm: str
    is_active: bool
    trained_at: datetime | None
    metrics: dict[str, Any]
    feature_schema_hash: str | None
    dataset_hash: str | None  # provenance for Model Info (roadmap R2-P7 task 7)
    git_sha: str | None
    bundle_sha256: str | None
    constraints_version: str | None
    threshold: float | None
    created_at: datetime


class ActiveModelsOut(BaseModel):
    is_mock: bool
    intelligence: IntelligenceVersionInfo
    models: list[ModelVersionOut]
