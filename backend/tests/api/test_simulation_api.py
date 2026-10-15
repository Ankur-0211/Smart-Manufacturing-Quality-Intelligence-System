"""Simulation endpoints over HTTP (roadmap §9.3.2, §9.5.4)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.repositories import RunRepository
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate
from tests.services.conftest import FakeExecutor, create_test_run

API = "/api/v1/simulation/runs"


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    url = f"sqlite:///{(tmp_path / 'api.db').as_posix()}"
    migrate(url)
    application = create_app(make_settings(database_url=url))
    application.state.simulation.executor = FakeExecutor()
    application.state.simulation.stage_presentation_ms = 0
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _run(app: FastAPI, **kw: Any) -> str:
    return create_test_run(app.state.db, **kw)


def _err(resp: httpx.Response) -> str:
    code: str = resp.json()["error"]["code"]
    return code


def _parse_sse(body: str) -> list[dict[str, Any]]:
    frames = []
    for block in body.split("\n\n"):
        lines = [ln for ln in block.splitlines() if ln and not ln.startswith(":")]
        if not lines:
            continue
        fields = dict(ln.split(": ", 1) for ln in lines)
        data = json.loads(fields["data"])
        assert fields["id"] == str(data["seq"]) and fields["event"] == data["type"]
        frames.append(data)
    return frames


# ------------------------------------------------------------------ commands and queries


def test_stepwise_run_over_http(app: FastAPI, client: TestClient) -> None:
    run_id = _run(app)
    resp = client.post(f"{API}/{run_id}/start", json={"mode": "stepwise"})
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "MATERIAL_CONDITIONING"
    for _ in range(6):
        state = client.post(f"{API}/{run_id}/advance").json()["data"]
    assert state["status"] == "FINAL_RESULT"
    assert len(state["stage_results"]) == 5 and state["prediction"]["model_version"] == "mock-0.0.0"
    assert state["timeline"][-1]["type"] == "run.completed"

    stage = client.get(f"{API}/{run_id}/stages/PACKING").json()["data"]
    assert stage["stage_name"] == "PACKING" and stage["risk_ordinal"] == 0

    listing = client.get(API, params={"label": "FAIL"})
    assert listing.json()["meta"]["total"] == 1
    row = listing.json()["data"][0]
    assert (row["machine_id"], row["product_id"], row["material_lot_id"]) == (
        "MC-03",
        "PP-JBOX-42",
        "A-771",
    )
    assert row["p_fail"] == 0.71 and row["inference_backend"] == "mock"
    # Timestamps carry an explicit UTC offset so browsers never read them as local time.
    assert row["created_at"].endswith("Z") or row["created_at"].endswith("+00:00")
    assert state["completed_at"].endswith("Z") or state["completed_at"].endswith("+00:00")

    labelled = client.patch(f"{API}/{run_id}/label", json={"scenario_label": "baseline"})
    assert labelled.status_code == 200 and labelled.json()["data"]["scenario_label"] == "baseline"


def test_auto_run_completes_over_http(app: FastAPI, client: TestClient) -> None:
    run_id = _run(app)
    client.post(f"{API}/{run_id}/start", json={"mode": "auto", "speed_factor": "instant"})
    for _ in range(200):
        if client.get(f"{API}/{run_id}").json()["data"]["status"] == "FINAL_RESULT":
            break
    else:
        pytest.fail("auto run did not finish")


def test_blocked_override_over_http(app: FastAPI, client: TestClient) -> None:
    app.state.simulation.executor.block.add("INJECTION")
    run_id = _run(app)
    client.post(f"{API}/{run_id}/start", json={"mode": "stepwise"})
    for _ in range(3):
        state = client.post(f"{API}/{run_id}/advance").json()["data"]
    assert state["status"] == "BLOCKED" and state["blocked_stage"] == "INJECTION"
    assert _err(client.post(f"{API}/{run_id}/advance")) == "INVALID_STATE_TRANSITION"
    bad = client.post(
        f"{API}/{run_id}/override", json={"stage": "INJECTION", "acknowledgement": ""}
    )
    assert bad.status_code == 422
    ok = client.post(
        f"{API}/{run_id}/override", json={"stage": "INJECTION", "acknowledgement": "accepted"}
    )
    assert ok.json()["data"]["status"] == "PACKING"


def test_error_mapping(app: FastAPI, client: TestClient) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"{API}/{missing}")
    assert resp.status_code == 404 and _err(resp) == "RUN_NOT_FOUND"
    assert client.get(f"{API}/{missing}/events").status_code == 404

    run_id = _run(app)
    resp = client.post(f"{API}/{run_id}/advance")
    assert resp.status_code == 409 and _err(resp) == "INVALID_STATE_TRANSITION"
    assert client.post(f"{API}/{run_id}/start", json={"mode": "turbo"}).status_code == 422
    assert client.post(f"{API}/{run_id}/start", json={"speed_factor": "10x"}).status_code == 422
    assert client.get(f"{API}/{run_id}/stages/QUALITY_INSPECTION").status_code == 422

    client.post(f"{API}/{run_id}/start", json={"mode": "stepwise"})
    for _ in range(6):
        client.post(f"{API}/{run_id}/advance")
    resp = client.post(f"{API}/{run_id}/reset")
    assert resp.status_code == 409 and _err(resp) == "RUN_IMMUTABLE"
    resp = client.post(f"{API}/{run_id}/abort")
    assert resp.status_code == 409 and _err(resp) == "INVALID_STATE_TRANSITION"


def test_without_executor_simulation_is_capability_unavailable(
    app: FastAPI, client: TestClient
) -> None:
    app.state.simulation.executor = None
    run_id = _run(app)
    resp = client.post(f"{API}/{run_id}/start", json={})
    assert resp.status_code == 501 and _err(resp) == "CAPABILITY_UNAVAILABLE"
    assert (
        client.post(f"{API}/{run_id}/abort", json={"reason": "cleanup"}).json()["data"]["status"]
        == "ABORTED"
    )


def test_startup_recovery_aborts_interrupted_runs(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'r.db').as_posix()}"
    migrate(url)
    app = create_app(make_settings(database_url=url))
    run_id = create_test_run(app.state.db)
    with app.state.db.session() as s:
        runs = RunRepository(s)
        runs.set_status(runs.get(run_id), "COOLING")
    with TestClient(app) as c:  # lifespan runs recovery
        state = c.get(f"{API}/{run_id}").json()["data"]
    assert state["status"] == "ABORTED" and state["abort_reason"] == "SERVER_RESTART"


# ------------------------------------------------------------------ SSE


async def test_sse_replays_finished_run_and_closes(app: FastAPI) -> None:
    run_id = _run(app)
    service = app.state.simulation
    await service.start(run_id, mode="stepwise")
    for _ in range(6):
        await service.advance(run_id)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get(f"{API}/{run_id}/events")
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-cache"
        frames = _parse_sse(resp.text)
        assert [f["seq"] for f in frames] == list(range(1, len(frames) + 1))
        assert frames[0]["type"] == "run.started" and frames[-1]["type"] == "run.completed"

        resumed = await c.get(f"{API}/{run_id}/events", headers={"Last-Event-ID": "10"})
        tail = _parse_sse(resumed.text)
        assert [f["seq"] for f in tail] == list(range(11, len(frames) + 1))


async def test_sse_streams_a_live_auto_run(app: FastAPI) -> None:
    run_id = _run(app)
    service = app.state.simulation
    service.stage_presentation_ms = 5
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        stream = asyncio.create_task(c.get(f"{API}/{run_id}/events"))
        await asyncio.sleep(0.05)  # let the subscriber attach before the run starts
        await service.start(run_id, mode="auto", speed_factor="1x")
        resp = await asyncio.wait_for(stream, timeout=10)
    frames = _parse_sse(resp.text)
    types = [f["type"] for f in frames]
    assert types[0] == "run.started" and types[-1] == "run.completed"
    assert [f["seq"] for f in frames] == list(range(1, len(frames) + 1))
    assert types.count("stage.completed") == 5
