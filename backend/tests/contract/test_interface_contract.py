"""Shared contract-test harness (roadmap 10.1, R2-P1 task 11).

- Fixtures: authored by Role 1 in ``backend/tests/contract/fixtures/*.json``.
- Harness: owned by Role 2. It is parametrized over every available implementation of
  ``QualityIntelligence`` (mock, hybrid, real).

Every test skips with an explicit reason until its prerequisites exist, so a green run never
hides missing work. The skip reasons are part of the R2-P1 phase report.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Canonical stage order (roadmap 7.2). QUALITY_INSPECTION is produced by predict().
STAGE_ORDER = ["MATERIAL_CONDITIONING", "PLASTICIZING", "INJECTION", "PACKING", "COOLING"]
RISK_ORDINAL = {"NORMAL": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
UPSTREAM_KEYS_BY_STAGE = {  # roadmap 7.8, cumulative keys each stage may publish
    "MATERIAL_CONDITIONING": {"viscosity_class", "moisture_flag"},
    "PLASTICIZING": {"effective_melt_temp_c", "viscosity_proxy"},
    "INJECTION": {"fill_completion_proxy", "cavity_pressure_estimate_bar"},
    "PACKING": {"residual_stress_proxy"},
    "COOLING": set(),
}


def _contracts_available() -> bool:
    try:
        importlib.import_module("app.contracts.interface")
    except ModuleNotFoundError:
        return False
    return True


def _recipe_fixtures() -> list[Path]:
    return sorted(FIXTURES_DIR.glob("recipe_*.json"))


def _implementations() -> list[Any]:
    """Instantiate each implementation that exists. Later phases add hybrid and real here."""
    impls: list[Any] = []
    try:
        mock_mod = importlib.import_module("app.intelligence_mock.mock")
    except ModuleNotFoundError:
        mock_mod = None
    if mock_mod is not None:
        impls.append(pytest.param(mock_mod.MockQualityIntelligence.for_tests(), id="mock"))
    return impls


requires_contracts = pytest.mark.skipif(
    not _contracts_available(),
    reason="app.contracts v0.1.0 not delivered yet (R1-P1 task 1); blocks M1/M3",
)


def _dump(obj: Any) -> dict[str, Any]:
    dumped: dict[str, Any] = obj.model_dump(mode="json")
    return dumped


def _comparable(obj: Any) -> dict[str, Any]:
    """Dump without wall-clock timing, which is the only field allowed to differ between calls."""
    dumped: dict[str, Any] = obj.model_dump(mode="json", exclude={"compute_ms"})
    return dumped


def _assert_stage_results(stage_results: list[Any]) -> None:
    dumped = [_dump(r) for r in stage_results]
    assert [r["stage_name"] for r in dumped] == STAGE_ORDER
    published: set[str] = set()
    for index, r in enumerate(dumped, start=1):
        assert r["sequence_index"] == index
        assert 0.0 <= r["health_score"] <= 1.0
        assert RISK_ORDINAL[r["risk_level"]] == r["risk_ordinal"]
        assert 0.0 <= r["anomaly"]["score"] <= 1.0
        assert set(r["indicators"]) == set(r["indicator_provenance"])
        published |= UPSTREAM_KEYS_BY_STAGE[r["stage_name"]]
        out_keys = {k for k, v in r["upstream_out"].items() if v is not None}
        assert out_keys <= published, f"{r['stage_name']} published keys it does not own"
        if r["blocked"]:
            assert r["block_reason"]
            assert any(b["severity"] == "CRITICAL" for b in r["constraint_breaches"])


def _assert_prediction(prediction: Any) -> None:
    p = _dump(prediction)
    assert p["label"] in {"PASS", "FAIL"}
    assert 0.0 <= p["p_fail"] <= 1.0
    assert (p["label"] == "FAIL") == (p["p_fail"] >= p["threshold_used"])
    assert p["is_mock"] == (p["inference_backend"] == "mock")
    if p["is_mock"]:
        assert any(c["code"] == "MOCK_INFERENCE" for c in p["caveats"])
    if p["stage_risk_mass"]:
        assert abs(sum(s["share"] for s in p["stage_risk_mass"]) - 1.0) < 1e-6
    if p["constraint_override_applied"]:
        assert p["risk_level"] == "CRITICAL"
        assert any(c["code"] == "CRITICAL_CONSTRAINT_OVERRIDDEN" for c in p["caveats"])


@requires_contracts
def test_fixtures_present() -> None:
    if not _recipe_fixtures():
        pytest.skip("No recipe_*.json contract fixtures yet (Role 1, R1-P1)")
    for path in _recipe_fixtures():
        json.loads(path.read_text(encoding="utf-8"))


@requires_contracts
@pytest.mark.parametrize(
    "fixture", _recipe_fixtures() or [None], ids=lambda p: p.stem if p else "none"
)
@pytest.mark.parametrize("impl", _implementations() or [None])
def test_evaluate_satisfies_contract(impl: Any, fixture: Path | None) -> None:
    if impl is None:
        pytest.skip("No QualityIntelligence implementation available yet (mock pending)")
    if fixture is None:
        pytest.skip("No contract fixtures yet")
    from app.contracts.context import ProcessInput

    process_input = ProcessInput.model_validate_json(fixture.read_text(encoding="utf-8"))
    result = impl.evaluate(process_input, include_explanation=True)
    _assert_stage_results(result.stage_results)
    _assert_prediction(result.prediction)

    # Equivalence guarantee (roadmap 9.1 #4): evaluate == run_all_stages + predict.
    stages = impl.run_all_stages(process_input)
    assert [_comparable(s) for s in stages] == [_comparable(s) for s in result.stage_results]
    prediction = impl.predict(process_input, stages, include_explanation=True)
    assert _comparable(prediction) == _comparable(result.prediction)

    # Determinism guarantee (roadmap 9.1 #1): identical inputs give identical outputs.
    again = impl.evaluate(process_input, include_explanation=True)
    assert [_comparable(s) for s in again.stage_results] == [
        _comparable(s) for s in result.stage_results
    ]
    assert _comparable(again.prediction) == _comparable(result.prediction)


@requires_contracts
@pytest.mark.parametrize("impl", _implementations() or [None])
def test_capabilities_and_version_info(impl: Any) -> None:
    if impl is None:
        pytest.skip("No QualityIntelligence implementation available yet (mock pending)")
    info = _dump(impl.version_info())
    assert info["is_mock"] == (info["inference_backend"] == "mock")
    assert set(impl.capabilities()) >= {"run_stage", "predict", "explain", "recommend"}
