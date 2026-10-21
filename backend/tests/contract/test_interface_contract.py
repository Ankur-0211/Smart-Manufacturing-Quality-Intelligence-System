"""Shared contract-test harness (roadmap 10.1, R2-P1 task 11).

- Fixtures: ``backend/tests/contract/fixtures/*.json`` (CCR-002 bootstrap; Role 1 may extend).
- Harness: owned by Role 2. It runs every available ``QualityIntelligence`` implementation (mock,
  and Role 1's real facade) through the same invariants, using only Role 1's Protocol methods.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.context import ProcessInput
from app.contracts.enums import INTELLIGENCE_STAGES
from app.contracts.interface import QualityIntelligence
from app.contracts.stage import UpstreamContext
from app.domain.constraint_loader import load_constraint_registry
from app.intelligence.facade import RealQualityIntelligence
from app.intelligence_mock.mock import MockQualityIntelligence

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FIXTURES = sorted(FIXTURES_DIR.glob("recipe_*.json"))

STAGE_ORDER = [s.value for s in INTELLIGENCE_STAGES]
RISK_ORDINAL = {"NORMAL": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
UPSTREAM_KEYS_BY_STAGE = {  # roadmap 7.8, keys each stage may publish
    "MATERIAL_CONDITIONING": {"viscosity_class", "moisture_flag"},
    "PLASTICIZING": {"effective_melt_temp_c", "viscosity_proxy"},
    "INJECTION": {"fill_completion_proxy", "cavity_pressure_estimate_bar"},
    "PACKING": {"residual_stress_proxy"},
    "COOLING": set(),
}

_REGISTRY = load_constraint_registry()
IMPLEMENTATIONS = [
    pytest.param(MockQualityIntelligence(_REGISTRY), id="mock"),
    pytest.param(RealQualityIntelligence(registry=_REGISTRY), id="real"),
]


def _dump(obj: Any) -> dict[str, Any]:
    dumped: dict[str, Any] = obj.model_dump(mode="json")
    return dumped


def _comparable(obj: Any) -> dict[str, Any]:
    """Dump without wall-clock timing, which is the only field allowed to differ between calls."""
    dumped: dict[str, Any] = obj.model_dump(mode="json", exclude={"compute_ms"})
    return dumped


def _load(path: Path) -> ProcessInput:
    return ProcessInput.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _run_stages(impl: QualityIntelligence, inp: ProcessInput) -> list[Any]:
    results, upstream = [], UpstreamContext()
    for stage in INTELLIGENCE_STAGES:
        result = impl.run_stage(stage, inp, upstream)
        results.append(result)
        upstream = result.upstream_out
    return results


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
        assert r["substate"] in {"COMPLETED", "BLOCKED"}
        assert (r["substate"] == "BLOCKED") == r["blocked"]
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


def test_fixtures_present() -> None:
    assert FIXTURES, "recipe_*.json contract fixtures are missing"


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda p: p.stem)
@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_evaluate_satisfies_contract(impl: QualityIntelligence, fixture: Path) -> None:
    inp = _load(fixture)
    result = impl.evaluate(inp, include_explanation=True)
    _assert_stage_results(result.stage_results)
    _assert_prediction(result.prediction)

    # Equivalence guarantee (roadmap 9.1 #4): evaluate == run_stage x5 + predict.
    stages = _run_stages(impl, inp)
    assert [_comparable(s) for s in stages] == [_comparable(s) for s in result.stage_results]
    prediction = impl.predict(inp, stages, include_explanation=True)
    assert _comparable(prediction) == _comparable(result.prediction)

    # Determinism guarantee (roadmap 9.1 #1): identical inputs give identical outputs.
    again = impl.evaluate(inp, include_explanation=True)
    assert [_comparable(s) for s in again.stage_results] == [
        _comparable(s) for s in result.stage_results
    ]
    assert _comparable(again.prediction) == _comparable(result.prediction)


@pytest.mark.parametrize("impl", IMPLEMENTATIONS)
def test_capabilities_and_version_info(impl: QualityIntelligence) -> None:
    assert isinstance(impl, QualityIntelligence)
    info = _dump(impl.version_info())
    assert info["constraints_version"] == _REGISTRY.version
    assert set(impl.capabilities()) >= {"run_stage", "predict", "explain", "recommend"}
    prediction = impl.evaluate(_load(FIXTURES[0])).prediction
    assert info["is_mock"] == prediction.is_mock
    assert info["model_version"] == prediction.model_version
