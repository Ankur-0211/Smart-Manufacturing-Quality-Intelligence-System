"""Simulation engine driven by MockQualityIntelligence through the StageExecutor adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.contracts.enums import StageSubstate
from app.db.session import Database
from app.domain.constraint_loader import load_constraint_registry
from app.engine.cache import StageCache
from app.engine.events import EventBus
from app.intelligence_mock.mock import MockQualityIntelligence
from app.services.intelligence_executor import IntelligenceStageExecutor, stage_result_from_json
from app.services.simulation_service import SimulationService
from tests.services.conftest import create_test_run
from tests.services.test_simulation_service import HAPPY_EVENTS, _types, _wait_done

NOMINAL = json.loads(
    (
        Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "recipe_nominal.json"
    ).read_text("utf-8")
)["recipe"]


@pytest.fixture
def mock_service(database: Database) -> SimulationService:
    intelligence = MockQualityIntelligence.for_tests()
    executor = IntelligenceStageExecutor(intelligence, intelligence.registry)
    return SimulationService(
        database, EventBus(), StageCache(100), executor=executor, stage_presentation_ms=0
    )


async def test_mock_run_reaches_final_result(
    mock_service: SimulationService, database: Database
) -> None:
    run_id = create_test_run(database, recipe=NOMINAL, speed_factor="instant")
    await mock_service.start(run_id, mode="auto")
    state = await _wait_done(mock_service, run_id)
    assert state["status"] == "FINAL_RESULT"
    assert _types(state) == HAPPY_EVENTS
    prediction = state["prediction"]
    assert prediction["inference_backend"] == "mock" and prediction["is_mock"] is True
    assert prediction["model_version"] == "mock-0.0.0"
    assert any(c["code"] == "MOCK_INFERENCE" for c in prediction["caveats"])
    assert prediction["explanation"]["attributions"]
    assert state["inference_backend"] == "mock"
    assert state["constraints_version"] == load_constraint_registry().version
    assert [r["module_version"] for r in state["stage_results"]] == ["mock-0.0.0"] * 5


async def test_wet_lot_blocks_and_override_is_reported(
    mock_service: SimulationService, database: Database
) -> None:
    # D-105-like lot: 0.22 % moisture > 2 x the PP-H spec (HC-006).
    run_id = create_test_run(
        database, recipe=NOMINAL, lot_code="D-105", moisture_pct=0.22, speed_factor="instant"
    )
    await mock_service.start(run_id, mode="auto")
    state = await _wait_done(mock_service, run_id)
    assert state["status"] == "BLOCKED"
    assert state["blocked_stage"] == "MATERIAL_CONDITIONING"
    blocked = next(e for e in state["timeline"] if e["type"] == "stage.blocked")
    assert [b["rule_id"] for b in blocked["payload"]["breaches"]] == ["HC-006"]

    await mock_service.override(
        run_id, stage="MATERIAL_CONDITIONING", acknowledgement="operator accepts wet lot"
    )
    state = await _wait_done(mock_service, run_id)
    assert state["status"] == "FINAL_RESULT"
    prediction = state["prediction"]
    assert prediction["constraint_override_applied"] is True
    assert prediction["risk_level"] == "CRITICAL"
    assert any(c["code"] == "CRITICAL_CONSTRAINT_OVERRIDDEN" for c in prediction["caveats"])


def test_stored_overridden_stage_is_rebuilt_as_blocked() -> None:
    mock = MockQualityIntelligence.for_tests()
    from app.contracts.context import ProcessInput

    inp = ProcessInput.model_validate(
        {
            **json.loads(
                (
                    Path(__file__).resolve().parents[1]
                    / "contract"
                    / "fixtures"
                    / "recipe_high_moisture.json"
                ).read_text("utf-8")
            )
        }
    )
    result = mock.evaluate(inp).stage_results[0]
    stored: dict[str, Any] = {
        **result.model_dump(mode="json"),
        "substate": "COMPLETED",  # how the DB keeps an overridden stage
        "overridden": True,
        "presentation_ms": 0.0,
    }
    rebuilt = stage_result_from_json(stored)
    assert rebuilt.substate is StageSubstate.BLOCKED and rebuilt.blocked
