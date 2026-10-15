"""Orchestrator behaviour (roadmap §9.5, R2-P4 required tests)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models import Prediction, StageResultRow
from app.db.session import Database
from app.db.vocab import STAGE_NAMES
from app.engine.cache import StageCache
from app.engine.events import EventBus
from app.engine.state_machine import InvalidTransitionError, RunImmutableTransitionError
from app.services.simulation_service import ExecutorUnavailableError, SimulationService
from tests.services.conftest import FakeExecutor

HAPPY_EVENTS = [
    "run.started",
    *[e for _ in STAGE_NAMES for e in ("stage.started", "stage.completed")],
    "stage.started",
    "prediction.ready",
    "run.completed",
]


async def _wait_done(
    service: SimulationService, run_id: str, timeout: float = 5.0
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = await asyncio.to_thread(service.state, run_id)
        if state["status"] == "PAUSED":
            return state  # the run task stays parked on the resume gate by design
        if state["status"] in ("FINAL_RESULT", "ABORTED", "BLOCKED"):
            handle = service._handles.get(run_id)
            if handle is None or handle.task is None or handle.task.done():
                return state
        await asyncio.sleep(0.01)
    raise AssertionError(f"run did not settle: {state['status']}")


def _types(state: dict[str, Any]) -> list[str]:
    return [e["type"] for e in state["timeline"]]


def _assert_contiguous(state: dict[str, Any]) -> None:
    assert [e["seq"] for e in state["timeline"]] == list(range(1, len(state["timeline"]) + 1))
    assert state["last_seq"] == len(state["timeline"])


async def test_stepwise_run_executes_one_stage_per_advance(
    service: SimulationService, make_run: Callable[..., str], database: Database
) -> None:
    run_id = make_run()
    await service.start(run_id, mode="stepwise")
    statuses = [await service.advance(run_id) for _ in range(6)]
    assert statuses == [*STAGE_NAMES[1:], "QUALITY_INSPECTION", "FINAL_RESULT"]
    state = service.state(run_id)
    assert state["status"] == "FINAL_RESULT" and state["current_stage"] is None
    assert [r["stage_name"] for r in state["stage_results"]] == list(STAGE_NAMES)
    assert (
        state["prediction"]["label"] == "FAIL"
        and state["prediction"]["model_version"] == "mock-0.0.0"
    )
    assert state["inference_backend"] == "mock" and state["completed_at"] is not None
    assert _types(state) == HAPPY_EVENTS
    _assert_contiguous(state)
    with pytest.raises(InvalidTransitionError):
        await service.advance(run_id)


async def test_auto_instant_run_completes(
    service: SimulationService, make_run: Callable[..., str]
) -> None:
    run_id = make_run(speed_factor="instant")
    await service.start(run_id, mode="auto")
    state = await _wait_done(service, run_id)
    assert state["status"] == "FINAL_RESULT"
    assert _types(state) == HAPPY_EVENTS
    _assert_contiguous(state)


async def test_upstream_context_is_chained_unchanged(
    service: SimulationService, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    run_id = make_run()
    await service.start(run_id, mode="stepwise")
    for _ in range(6):
        await service.advance(run_id)
    received = dict(executor.stage_calls)
    assert received["MATERIAL_CONDITIONING"] == {}
    assert set(received["PLASTICIZING"]) == {"viscosity_class", "moisture_flag"}
    assert set(received["COOLING"]) == {
        "viscosity_class",
        "moisture_flag",
        "effective_melt_temp_c",
        "viscosity_proxy",
        "fill_completion_proxy",
        "cavity_pressure_estimate_bar",
        "residual_stress_proxy",
    }
    assert [r["stage_name"] for r in executor.predict_calls[0]] == list(STAGE_NAMES)


async def test_anomaly_and_breach_events_precede_completion(
    service: SimulationService, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    executor.anomaly.add("PLASTICIZING")
    run_id = make_run()
    await service.start(run_id, mode="stepwise")
    await service.advance(run_id)
    await service.advance(run_id)
    types = _types(service.state(run_id))
    i = types.index("anomaly.flagged")
    assert types[i - 1] == "stage.started" and types[i + 1] == "stage.completed"


async def test_blocked_stage_halts_until_override(
    service: SimulationService,
    executor: FakeExecutor,
    make_run: Callable[..., str],
    database: Database,
) -> None:
    executor.block.add("PLASTICIZING")
    run_id = make_run(speed_factor="instant")
    await service.start(run_id, mode="auto")
    state = await _wait_done(service, run_id)
    assert state["status"] == "BLOCKED" and state["blocked_stage"] == "PLASTICIZING"
    assert [r["stage_name"] for r in state["stage_results"]] == ["MATERIAL_CONDITIONING"]
    assert _types(state)[-3:] == ["stage.started", "constraint.breached", "stage.blocked"]
    blocked_event = state["timeline"][-1]
    assert blocked_event["payload"]["reason"] == "test critical breach"
    assert blocked_event["payload"]["breaches"][0]["rule_id"] == "HC-TEST"

    with pytest.raises(InvalidTransitionError):
        await service.override(run_id, stage="INJECTION", acknowledgement="wrong stage")

    executor.block.clear()
    await service.override(run_id, stage="PLASTICIZING", acknowledgement="operator accepts risk")
    state = await _wait_done(service, run_id)
    assert state["status"] == "FINAL_RESULT" and state["override_count"] == 1
    plast = next(r for r in state["stage_results"] if r["stage_name"] == "PLASTICIZING")
    assert plast["blocked"] is True and plast["overridden"] is True
    assert state["prediction"]["constraint_override_applied"] is True
    assert state["prediction"]["risk_level"] == "CRITICAL"
    types = _types(state)
    i = types.index("stage.override_acknowledged")
    assert types[i + 1] == "stage.completed"
    _assert_contiguous(state)


async def test_halt_on_critical_false_records_blocked_result(
    service: SimulationService, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    executor.block.add("INJECTION")
    run_id = make_run(halt_on_critical=False, speed_factor="instant")
    await service.start(run_id, mode="auto")
    state = await _wait_done(service, run_id)
    assert state["status"] == "FINAL_RESULT"
    inj = next(r for r in state["stage_results"] if r["stage_name"] == "INJECTION")
    assert inj["blocked"] is True and inj["overridden"] is False
    assert "stage.blocked" not in _types(state) and "constraint.breached" in _types(state)


async def test_pause_and_resume(
    database: Database, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    service = SimulationService(
        database, EventBus(), StageCache(100), executor=executor, stage_presentation_ms=40
    )
    run_id = make_run(speed_factor="1x")
    await service.start(run_id, mode="auto")
    await asyncio.sleep(0.05)
    await service.pause(run_id)
    paused = await _wait_done(service, run_id)
    assert paused["status"] == "PAUSED"
    progress = len(paused["stage_results"])
    await asyncio.sleep(0.2)
    assert len(service.state(run_id)["stage_results"]) == progress  # nothing runs while paused
    await service.resume(run_id)
    state = await _wait_done(service, run_id)
    assert state["status"] == "FINAL_RESULT"
    types = _types(state)
    assert types.index("run.paused") < types.index("run.resumed")
    _assert_contiguous(state)


async def test_presentation_speed_scales_delay(
    database: Database, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    service = SimulationService(
        database, EventBus(), StageCache(0), executor=executor, stage_presentation_ms=20
    )
    slow, fast = make_run(speed_factor="0.5x"), make_run(speed_factor="instant")
    t0 = time.perf_counter()
    await service.start(slow, mode="auto")
    await _wait_done(service, slow)
    slow_s = time.perf_counter() - t0
    t0 = time.perf_counter()
    await service.start(fast, mode="auto")
    await _wait_done(service, fast)
    fast_s = time.perf_counter() - t0
    assert slow_s >= 6 * 0.040  # 6 stages x 20 ms x 2.0
    assert fast_s < slow_s
    stage = service.state(slow)["stage_results"][0]
    assert stage["presentation_ms"] == pytest.approx(40.0)


async def test_reset_keeps_parameters_and_allows_restart(
    service: SimulationService, make_run: Callable[..., str], database: Database
) -> None:
    run_id = make_run()
    await service.start(run_id, mode="stepwise")
    await service.advance(run_id)
    before = service.state(run_id)["parameters"]
    await service.reset(run_id)
    state = service.state(run_id)
    assert state["status"] == "INITIALIZED" and state["stage_results"] == []
    assert state["parameters"] == before and state["started_at"] is None
    assert _types(state)[-1] == "run.reset"
    await service.start(run_id, mode="stepwise")
    for _ in range(6):
        await service.advance(run_id)
    assert service.state(run_id)["status"] == "FINAL_RESULT"
    with pytest.raises(RunImmutableTransitionError):
        await service.reset(run_id)


async def test_abort_during_auto_run(
    database: Database, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    service = SimulationService(
        database, EventBus(), StageCache(100), executor=executor, stage_presentation_ms=30
    )
    run_id = make_run(speed_factor="1x")
    await service.start(run_id, mode="auto")
    await asyncio.sleep(0.07)
    await service.abort(run_id, reason="operator stop")
    state = service.state(run_id)
    assert state["status"] == "ABORTED" and state["abort_reason"] == "operator stop"
    partial = len(state["stage_results"])
    assert partial < 5
    await asyncio.sleep(0.15)
    after = service.state(run_id)
    assert len(after["stage_results"]) == partial and after["timeline"][-1]["type"] == "run.aborted"
    _assert_contiguous(after)


async def test_executor_failure_aborts_with_error_event(
    service: SimulationService, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    executor.fail_on = "PACKING"
    run_id = make_run(speed_factor="instant")
    await service.start(run_id, mode="auto")
    state = await _wait_done(service, run_id)
    assert state["status"] == "ABORTED" and state["abort_reason"] == "ERROR:INTERNAL_ERROR"
    assert _types(state)[-2:] == ["run.error", "run.aborted"]
    assert "boom in PACKING" in state["timeline"][-2]["payload"]["message"]


async def test_no_executor_means_capability_unavailable(
    database: Database, make_run: Callable[..., str]
) -> None:
    service = SimulationService(database, EventBus(), StageCache(10), executor=None)
    run_id = make_run()
    with pytest.raises(ExecutorUnavailableError):
        await service.start(run_id)
    await service.abort(run_id)  # commands that need no intelligence still work
    assert service.state(run_id)["status"] == "ABORTED"


async def test_stage_cache_serves_identical_inputs(
    service: SimulationService, executor: FakeExecutor, make_run: Callable[..., str]
) -> None:
    first, second = make_run(), make_run()
    for run_id in (first, second):
        await service.start(run_id, mode="stepwise")
        for _ in range(6):
            await service.advance(run_id)
    assert len(executor.stage_calls) == 5  # second run fully served from cache
    hits = [
        e["payload"]["cache_hit"]
        for e in service.state(second)["timeline"]
        if e["type"] == "stage.completed"
    ]
    assert hits == [True] * 5
    assert service.cache.stats().hits == 5
    first_rows = service.state(first)["stage_results"]
    second_rows = service.state(second)["stage_results"]
    assert [r["indicators"] for r in first_rows] == [r["indicators"] for r in second_rows]


async def test_events_are_published_in_order(
    service: SimulationService, make_run: Callable[..., str]
) -> None:
    run_id = make_run(speed_factor="instant")
    queue = service.bus.subscribe(run_id)
    await service.start(run_id, mode="auto")
    await _wait_done(service, run_id)
    published = []
    while not queue.empty():
        published.append(queue.get_nowait())
    persisted = service.state(run_id)["timeline"]
    assert [e["seq"] for e in published] == [e["seq"] for e in persisted]
    assert [e["type"] for e in published] == HAPPY_EVENTS


async def test_ten_concurrent_runs(
    service: SimulationService, make_run: Callable[..., str]
) -> None:
    ids = [make_run(speed_factor="instant") for _ in range(10)]
    await asyncio.gather(*(service.start(i, mode="auto") for i in ids))
    states = await asyncio.gather(*(_wait_done(service, i, timeout=15) for i in ids))
    for state in states:
        assert state["status"] == "FINAL_RESULT"
        assert _types(state) == HAPPY_EVENTS
        _assert_contiguous(state)


def test_recover_interrupted_runs(
    service: SimulationService, make_run: Callable[..., str], database: Database
) -> None:
    from app.db.repositories import RunRepository

    running, fresh = make_run(), make_run()
    with database.session() as s:
        RunRepository(s).set_status(RunRepository(s).get(running), "INJECTION")
    assert service.recover_interrupted() == [running]
    state = service.state(running)
    assert state["status"] == "ABORTED" and state["abort_reason"] == "SERVER_RESTART"
    assert state["timeline"][-1]["type"] == "run.aborted"
    assert service.state(fresh)["status"] == "INITIALIZED"
    with database.session() as s:
        assert s.scalars(select(StageResultRow)).all() == []
        assert s.scalars(select(Prediction)).all() == []
