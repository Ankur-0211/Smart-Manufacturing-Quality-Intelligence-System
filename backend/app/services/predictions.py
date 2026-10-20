"""Prediction persistence shared by simulation runs and stateless ``POST /predict`` (roadmap 9.4).

``PredictionResult`` JSON in, ``predictions`` row out, and back again. Role 2 never reshapes the
intelligence payload: the stored columns are the contract fields, and the model version is
resolved to a ``model_versions`` row for traceability.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import Prediction, ProcessRun
from app.db.repositories import ModelVersionRepository, PredictionRepository
from app.db.vocab import MODEL_NAMES

PREDICTION_JSON_COLUMNS = (
    "label",
    "p_fail",
    "p_fail_raw",
    "threshold_used",
    "risk_level",
    "risk_drivers",
    "explanation",
    "stage_risk_mass",
    "caveats",
    "anomaly_global",
    "ood",
    "uncertainty",
    "constraint_override_applied",
    "inference_backend",
    "feature_schema_hash",
    "constraints_version",
)


def split_model_version(value: str) -> tuple[str, str]:
    """``"fusion-1.0.0"`` -> ``("fusion", "1.0.0")``; rejects names outside the registry table."""
    name, _, semver = value.partition("-")
    if name not in MODEL_NAMES or not semver:
        raise ValueError(f"unrecognised model_version {value!r} (expected '<name>-<semver>')")
    return name, semver


def persist_prediction(
    session: Session,
    run: ProcessRun | None,
    prediction: Mapping[str, Any],
    *,
    compute_ms: float,
    input_snapshot: Mapping[str, Any] | None = None,
) -> Prediction:
    """Insert one ``predictions`` row (``run=None`` for stateless predictions)."""
    name, semver = split_model_version(str(prediction["model_version"]))
    mv = ModelVersionRepository(session)
    # Registered at startup; an unknown version is recorded, never overwritten.
    version = mv.find(name, semver) or mv.upsert(name, semver, algorithm="unregistered")
    values = {k: prediction.get(k) for k in PREDICTION_JSON_COLUMNS}
    values = {k: v for k, v in values.items() if v is not None}
    values.update(
        model_version_id=version.id,
        latency_ms=prediction.get("compute_ms", compute_ms),
        input_snapshot=dict(input_snapshot) if input_snapshot is not None else None,
    )
    return PredictionRepository(session).add(run, **values)


def prediction_row_to_json(row: Prediction) -> dict[str, Any]:
    out: dict[str, Any] = {k: getattr(row, k) for k in PREDICTION_JSON_COLUMNS}
    mv = row.model_version
    out["model_version"] = f"{mv.name}-{mv.semver}"
    out["is_mock"] = row.inference_backend == "mock"
    out["prediction_id"] = row.id
    out["compute_ms"] = row.latency_ms
    return out
