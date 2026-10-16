"""Invariants of the bootstrapped contract models (roadmap 7.8-7.16, 9.1). BOOTSTRAP by Role 2."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from app.contracts.enums import StageName
from app.contracts.interface import IntelligenceVersionInfo, QualityIntelligence
from app.contracts.prediction import FeatureVector, PredictionResult
from app.contracts.recommendation import RecommendationRequest
from app.contracts.stage import StageResult, UpstreamContext


def stage_result(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "stage_name": "PLASTICIZING",
        "sequence_index": 2,
        "substate": "COMPLETED",
        "inputs_used": {"melt_temp_c": 230.0, "resin_grade": "PP-H"},
        "upstream_in": {"viscosity_class": "NOMINAL", "moisture_flag": False},
        "upstream_out": {"effective_melt_temp_c": 232.5, "viscosity_proxy": 0.5},
        "health_score": 0.82,
        "risk_level": "LOW",
        "risk_ordinal": 1,
        "anomaly": {"flag": False, "score": 0.1, "method": "zscore"},
        "indicators": {"splay_risk": 0.1},
        "indicator_provenance": {"splay_risk": "heuristic"},
        "module_version": "plasticizing-0.1.0",
        "constraints_version": "constraints-0.1.0",
        "compute_ms": 0.4,
    }
    return {**base, **over}


def prediction(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "label": "FAIL",
        "p_fail": 0.71,
        "p_fail_raw": 0.66,
        "threshold_used": 0.5,
        "model_version": "mock-0.0.0",
        "risk_level": "HIGH",
        "inference_backend": "mock",
        "is_mock": True,
        "caveats": [{"code": "MOCK_INFERENCE", "message": "placeholder"}],
        "feature_schema_hash": "0" * 64,
        "constraints_version": "constraints-0.1.0",
        "compute_ms": 1.0,
    }
    return {**base, **over}


def test_valid_stage_result_round_trips() -> None:
    result = StageResult.model_validate(stage_result())
    assert StageResult.model_validate_json(result.model_dump_json()) == result


@pytest.mark.parametrize(
    "over",
    [
        pytest.param({"stage_name": "QUALITY_INSPECTION", "sequence_index": 6}, id="s6"),
        pytest.param({"sequence_index": 3}, id="sequence-index"),
        pytest.param({"risk_ordinal": 3}, id="ordinal"),
        pytest.param({"health_score": 1.2}, id="health-range"),
        pytest.param({"health_score": float("nan")}, id="nan"),
        pytest.param({"indicator_provenance": {}}, id="provenance-keys"),
        pytest.param({"substate": "RUNNING"}, id="substate"),
        pytest.param({"blocked": True}, id="blocked-but-completed"),
        pytest.param({"substate": "BLOCKED", "blocked": True}, id="blocked-no-reason"),
        pytest.param({"notes": ["x" * 161]}, id="long-note"),
        pytest.param({"surprise": 1}, id="extra-field"),
    ],
)
def test_stage_result_invariants(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        StageResult.model_validate(stage_result(**over))


def test_stage_result_is_frozen() -> None:
    result = StageResult.model_validate(stage_result())
    with pytest.raises(ValidationError):
        result.health_score = 0.1  # type: ignore[misc]


def test_upstream_context_is_all_optional() -> None:
    assert UpstreamContext().model_dump(exclude_none=True) == {}


def test_valid_prediction() -> None:
    PredictionResult.model_validate(prediction())
    PredictionResult.model_validate(
        prediction(
            stage_risk_mass=[{"stage": s, "share": 0.2} for s in list(StageName)[:5]],
            constraint_override_applied=True,
            risk_level="CRITICAL",
            caveats=[
                {"code": "MOCK_INFERENCE", "message": "placeholder"},
                {"code": "CRITICAL_CONSTRAINT_OVERRIDDEN", "message": "overridden"},
            ],
        )
    )


@pytest.mark.parametrize(
    "over",
    [
        pytest.param({"label": "PASS"}, id="label-vs-threshold"),
        pytest.param({"is_mock": False}, id="is-mock-vs-backend"),
        pytest.param({"caveats": []}, id="mock-caveat"),
        pytest.param({"stage_risk_mass": [{"stage": "COOLING", "share": 0.5}]}, id="shares-sum"),
        pytest.param({"constraint_override_applied": True}, id="override-not-critical"),
        pytest.param(
            {"constraint_override_applied": True, "risk_level": "CRITICAL"}, id="override-caveat"
        ),
    ],
)
def test_prediction_invariants(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PredictionResult.model_validate(prediction(**over))


def test_feature_vector_alignment() -> None:
    with pytest.raises(ValidationError):
        FeatureVector(names=["a", "b"], values=[1.0], feature_schema_hash="h")


def test_recommendation_request_defaults_and_bounds() -> None:
    req = RecommendationRequest()
    assert (req.max_changes, req.n_options, req.objective, req.seed) == (3, 3, "min_p_fail", 0)
    with pytest.raises(ValidationError):
        RecommendationRequest(max_changes=7)


def test_protocol_is_runtime_checkable() -> None:
    assert not isinstance(object(), QualityIntelligence)
    info = IntelligenceVersionInfo(
        contracts_version="0.1.0",
        constraints_version="constraints-0.1.0",
        module_versions={StageName.COOLING: "cooling-0.1.0"},
        fusion_model_version=None,
        feature_schema_hash=None,
        inference_backend="mock",
        is_mock=True,
    )
    assert info.model_dump(mode="json")["module_versions"] == {"COOLING": "cooling-0.1.0"}
