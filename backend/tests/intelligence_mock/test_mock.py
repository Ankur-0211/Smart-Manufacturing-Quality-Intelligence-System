"""MockQualityIntelligence behaviour beyond the shared contract harness (roadmap 9.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.anomaly import SpcSeries
from app.contracts.context import ProcessInput
from app.contracts.enums import INTELLIGENCE_STAGES, ConstraintSeverity, RiskLevel, StageName
from app.contracts.errors import (
    CapabilityUnavailableError,
    InvalidInputError,
    LockedParameterError,
    StageResultsIncompleteError,
    UnknownParameterError,
    UpstreamMissingError,
)
from app.contracts.interface import QualityIntelligence
from app.contracts.recommendation import RecommendationRequest
from app.contracts.stage import UpstreamContext
from app.intelligence_mock.mock import MOCK_VERSION, MockQualityIntelligence

FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures"


@pytest.fixture(scope="module")
def mock() -> MockQualityIntelligence:
    return MockQualityIntelligence.for_tests()


def load(name: str) -> ProcessInput:
    return ProcessInput.model_validate_json((FIXTURES / f"{name}.json").read_text("utf-8"))


def test_satisfies_the_protocol(mock: MockQualityIntelligence) -> None:
    assert isinstance(mock, QualityIntelligence)
    info = mock.version_info()
    assert info.is_mock and info.fusion_model_version == MOCK_VERSION
    assert set(info.module_versions) == set(INTELLIGENCE_STAGES)


def test_every_prediction_is_labelled_mock(mock: MockQualityIntelligence) -> None:
    prediction = mock.evaluate(load("recipe_nominal")).prediction
    assert prediction.is_mock and prediction.inference_backend == "mock"
    assert prediction.model_version == MOCK_VERSION
    assert "MOCK_INFERENCE" in {c.code for c in prediction.caveats}


def test_outputs_depend_on_inputs(mock: MockQualityIntelligence) -> None:
    a = mock.evaluate(load("recipe_nominal"))
    b = mock.evaluate(load("recipe_short_cooling"))
    # S1-S4 read the same slice; COOLING reads cooling_time_s, so only it changes.
    for x, y in zip(a.stage_results[:4], b.stage_results[:4], strict=True):
        assert x.health_score == y.health_score
    assert a.stage_results[4].health_score != b.stage_results[4].health_score


@pytest.mark.parametrize(
    ("fixture", "stage", "rule"),
    [
        ("recipe_high_moisture", StageName.MATERIAL_CONDITIONING, "HC-006"),
        ("recipe_melt_ceiling_breach", StageName.PLASTICIZING, "HC-001"),
    ],
)
def test_blocked_path_comes_from_the_registry(
    mock: MockQualityIntelligence, fixture: str, stage: StageName, rule: str
) -> None:
    result = mock.evaluate(load(fixture))
    blocked = [r for r in result.stage_results if r.blocked]
    assert [r.stage_name for r in blocked] == [stage]
    assert blocked[0].risk_level is RiskLevel.CRITICAL
    assert [b.rule_id for b in blocked[0].constraint_breaches] == [rule]
    prediction = result.prediction
    # Critical-breach rule (7.12): never an ordinary confident result.
    assert prediction.constraint_override_applied
    assert prediction.risk_level is RiskLevel.CRITICAL
    assert "CRITICAL_CONSTRAINT_OVERRIDDEN" in {c.code for c in prediction.caveats}


def test_warning_breach_does_not_block(mock: MockQualityIntelligence) -> None:
    inp = load("recipe_nominal")
    recipe = inp.recipe.model_copy(update={"cushion_mm": 13.0})  # HC-005 band is 1-12
    result = mock.evaluate(ProcessInput(context=inp.context, recipe=recipe))
    packing = result.stage_results[3]
    assert not packing.blocked
    assert [(b.rule_id, b.severity) for b in packing.constraint_breaches] == [
        ("HC-005", ConstraintSeverity.WARNING)
    ]


def test_upstream_is_cumulative_and_required(mock: MockQualityIntelligence) -> None:
    stages = mock.run_all_stages(load("recipe_nominal"))
    out = stages[-1].upstream_out.model_dump(exclude_none=True)
    assert set(out) == {
        "viscosity_class",
        "moisture_flag",
        "effective_melt_temp_c",
        "viscosity_proxy",
        "fill_completion_proxy",
        "cavity_pressure_estimate_bar",
        "residual_stress_proxy",
    }
    with pytest.raises(UpstreamMissingError):
        mock.run_stage(StageName.INJECTION, load("recipe_nominal"), UpstreamContext())
    with pytest.raises(InvalidInputError):
        mock.run_stage(StageName.QUALITY_INSPECTION, load("recipe_nominal"), UpstreamContext())


def test_predict_needs_all_five_stages(mock: MockQualityIntelligence) -> None:
    inp = load("recipe_nominal")
    stages = mock.run_all_stages(inp)
    with pytest.raises(StageResultsIncompleteError):
        mock.predict(inp, stages[:4])
    with pytest.raises(StageResultsIncompleteError):
        mock.predict(inp, list(reversed(stages)))


def test_explanation_is_top_k_sorted(mock: MockQualityIntelligence) -> None:
    inp = load("recipe_nominal")
    explanation = mock.explain(inp, mock.run_all_stages(inp), top_k=5)
    shap = [abs(a.shap_value) for a in explanation.attributions]
    assert len(shap) == 5 and shap == sorted(shap, reverse=True)


def test_recommendations_respect_the_registry(mock: MockQualityIntelligence) -> None:
    inp = load("recipe_nominal")
    base = mock.evaluate(inp)
    request = RecommendationRequest(locked=["melt_temp_c"], max_changes=2)
    response = mock.recommend(inp, base.stage_results, base.prediction, request)
    assert response.base_p_fail == base.prediction.p_fail
    assert response.candidates or response.empty_reason
    registry = mock.registry
    for c in response.candidates:
        assert 1 <= len(c.changes) <= 2
        assert c.predicted_p_fail < base.prediction.p_fail
        for ch in c.changes:
            spec = registry.parameter(ch.parameter)
            assert spec.actionable and ch.parameter != "melt_temp_c"
            assert spec.max_step_change is not None and abs(ch.delta) <= spec.max_step_change
        # Scored through the same pipeline: re-evaluating the candidate gives its p_fail.
        updated = inp.recipe.model_copy(update={ch.parameter: ch.to_value for ch in c.changes})
        recipe = updated.model_dump()
        recipe["cycle_time_s"] = inp.recipe.cycle_time_s + c.cycle_time_delta_s
        again = mock.evaluate(
            ProcessInput.model_validate({"context": inp.context, "recipe": recipe})
        )
        assert again.prediction.p_fail == c.predicted_p_fail
    assert [c.option_rank for c in response.candidates] == list(
        range(1, len(response.candidates) + 1)
    )
    if response.candidates:
        aggressive = min(response.candidates, key=lambda c: c.predicted_p_fail)
        assert aggressive.option_label == "Aggressive"
    with pytest.raises(InvalidInputError):
        mock.recommend(
            inp, base.stage_results, base.prediction, RecommendationRequest(locked=["ghost"])
        )


def test_sensitivity(mock: MockQualityIntelligence) -> None:
    inp = load("recipe_nominal")
    result = mock.sensitivity(inp, "melt_temp_c", steps=12)
    spec = mock.registry.parameter("melt_temp_c")
    assert (result.points[0].value, result.points[-1].value) == (spec.min, spec.max)
    assert len(result.points) == 12
    with pytest.raises(UnknownParameterError):
        mock.sensitivity(inp, "ghost")
    with pytest.raises(LockedParameterError):
        mock.sensitivity(inp, "moisture_pct")


def test_spc_is_not_offered(mock: MockQualityIntelligence) -> None:
    assert mock.capabilities()["spc"] is False
    with pytest.raises(CapabilityUnavailableError):
        mock.spc_check(SpcSeries(parameter="melt_temp_c", values=[230.0]))
