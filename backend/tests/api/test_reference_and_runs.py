"""Reference endpoints and run creation over HTTP (roadmap 9.3.2, R2-P3 required tests).

Runs against the real app wiring: seeded demo fleet, constraint registry and mock intelligence.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.seed import load_fleet, seed
from app.domain.constraint_loader import load_constraint_registry
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
NOMINAL: dict[str, float] = json.loads(
    (
        Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "recipe_nominal.json"
    ).read_text("utf-8")
)["recipe"]
RUNS = "/api/v1/simulation/runs"


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    url = f"sqlite:///{(tmp_path / 'ref.db').as_posix()}"
    migrate(url)
    application = create_app(make_settings(database_url=url))
    with application.state.db.session() as s:
        seed(s, load_fleet(DOMAIN / "fleet.yaml"))
    application.state.simulation.stage_presentation_ms = 0
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _error(resp: httpx.Response) -> dict[str, Any]:
    error: dict[str, Any] = resp.json()["error"]
    return error


def _body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "machine_id": "MC-02",  # the nominal clamp force exceeds MC-03's rating (CPL-003)
        "product_id": "PP-JBOX-42",
        "material_lot_id": "A-771",
        "parameters": dict(NOMINAL),
    }
    body.update(over)
    return body


# ---------------------------------------------------------------- reference


def test_reference_lists(client: TestClient) -> None:
    machines = client.get("/api/v1/machines").json()["data"]
    assert [m["machine_id"] for m in machines] == ["MC-01", "MC-02", "MC-03", "MC-04"]
    fleet = {
        m["machine_id"]: m
        for m in yaml.safe_load((DOMAIN / "fleet.yaml").read_text("utf-8"))["machines"]
    }
    for m in machines:
        src = fleet[m["machine_id"]]
        assert m["machine_type"] == src["machine_type"]
        assert m["max_clamp_force_ton"] == src["max_clamp_force_ton"]
        assert m["installed_on"] == src["installed_on"] and m["machine_age_days"] >= 0
    products = client.get("/api/v1/products").json()["data"]
    assert [p["product_id"] for p in products] == ["PP-JBOX-42", "PP-JBOX-42-4C"]
    lots = client.get("/api/v1/materials").json()["data"]
    assert {lot["material_lot_id"] for lot in lots} == {"A-771", "B-812", "C-904", "D-105"}


def test_create_material(client: TestClient) -> None:
    lot = {
        "material_lot_id": "C-100",
        "resin_grade": "PP-C",
        "mfi": 20,
        "moisture_pct": 0.02,
        "regrind_pct": 5,
        "colourant_pct": 1,
        "notes": "test lot",
    }
    resp = client.post("/api/v1/materials", json=lot)
    assert resp.status_code == 201
    assert resp.json()["data"]["mfi"] == 20.0
    assert "C-100" in {x["material_lot_id"] for x in client.get("/api/v1/materials").json()["data"]}

    dup = client.post("/api/v1/materials", json=lot)
    assert dup.status_code == 409 and _error(dup)["field"] == "material_lot_id"


@pytest.mark.parametrize(
    ("over", "code", "field"),
    [
        # Role 1's registry has no windows for lot attributes yet (CCR-004 #4): types only.
        ({"mfi": "high"}, "VALIDATION_ERROR", "mfi"),
        ({"resin_grade": "ABS"}, "VALIDATION_ERROR", "resin_grade"),
        ({"material_lot_id": "bad code!"}, "VALIDATION_ERROR", "material_lot_id"),
        ({"surprise": 1}, "UNKNOWN_PARAMETER", "surprise"),
    ],
)
def test_create_material_rejects(
    client: TestClient, over: dict[str, Any], code: str, field: str
) -> None:
    lot = {
        "material_lot_id": "C-101",
        "resin_grade": "PP-H",
        "mfi": 12,
        "moisture_pct": 0.03,
        "regrind_pct": 10,
        "colourant_pct": 2,
        **over,
    }
    resp = client.post("/api/v1/materials", json=lot)
    assert resp.status_code == 422
    assert _error(resp)["code"] == code
    assert _error(resp)["field"] == field


def test_reference_endpoints_need_the_api_key_when_set(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(api_key="k"))) as c:
        for path in ("/api/v1/machines", "/api/v1/products", "/api/v1/materials"):
            assert c.get(path).status_code == 401


# ---------------------------------------------------------------- run creation


def test_create_run_returns_initialized_state(client: TestClient) -> None:
    resp = client.post(RUNS, json=_body(scenario_label="baseline", mode="stepwise"))
    assert resp.status_code == 201
    state = resp.json()["data"]
    assert state["status"] == "INITIALIZED" and state["mode"] == "stepwise"
    assert state["scenario_label"] == "baseline"
    assert state["inference_backend"] == "mock"
    assert state["constraints_version"] == load_constraint_registry().version
    assert state["context"]["machine"]["machine_id"] == "MC-02"
    assert state["parameters"] == {k: float(v) for k, v in NOMINAL.items()}
    assert state["timeline"] == []


def test_created_run_runs_to_final_result(client: TestClient) -> None:
    run_id = client.post(RUNS, json=_body(speed_factor="instant", mode="stepwise")).json()["data"][
        "run_id"
    ]
    assert client.post(f"{RUNS}/{run_id}/start", json={"mode": "stepwise"}).status_code == 200
    for _ in range(6):
        assert client.post(f"{RUNS}/{run_id}/advance").status_code == 200
    state = client.get(f"{RUNS}/{run_id}").json()["data"]
    assert state["status"] == "FINAL_RESULT"
    assert state["prediction"]["is_mock"] is True


@pytest.mark.parametrize("bound", ["min", "max"])
def test_exact_bounds_are_accepted_and_one_step_beyond_rejected(
    client: TestClient, bound: str
) -> None:
    spec = next(
        p
        for p in client.get("/api/v1/constraints").json()["data"]["parameters"]
        if p["name"] == "screw_rpm"
    )
    edge = spec[bound]
    ok = client.post(RUNS, json=_body(parameters={**NOMINAL, "screw_rpm": edge}))
    assert ok.status_code == 201
    beyond = edge - spec["step"] if bound == "min" else edge + spec["step"]
    bad = client.post(RUNS, json=_body(parameters={**NOMINAL, "screw_rpm": beyond}))
    assert bad.status_code == 422
    error = _error(bad)
    assert error["code"] == "PARAM_OUT_OF_RANGE"
    assert error["constraint_version"] == load_constraint_registry().version
    (detail,) = error["details"]
    assert detail["field"] == "parameters.screw_rpm"
    assert (detail["value"], detail["limit"]) == (beyond, edge)


def test_coupling_violation_names_the_rule(client: TestClient) -> None:
    params = {**NOMINAL, "hold_pressure_bar": 1000, "inj_pressure_bar": 900}
    resp = client.post(RUNS, json=_body(parameters=params))
    assert resp.status_code == 422
    error = _error(resp)
    assert error["code"] == "COUPLING_VIOLATION"
    assert error["details"][0]["message"].startswith("CPL-001")


def test_runtime_hard_constraint_is_not_an_http_error(client: TestClient) -> None:
    # Wet lot D-105 breaches HC-006 only at runtime (BLOCKED stage), never at creation.
    resp = client.post(RUNS, json=_body(material_lot_id="D-105"))
    assert resp.status_code == 201


@pytest.mark.parametrize(
    ("over", "field"),
    [
        ({"machine_id": "MC-99"}, "machine_id"),
        ({"product_id": "NOPE"}, "product_id"),
        ({"material_lot_id": "Z-000"}, "material_lot_id"),
    ],
)
def test_unknown_reference_is_404(client: TestClient, over: dict[str, Any], field: str) -> None:
    resp = client.post(RUNS, json=_body(**over))
    assert resp.status_code == 404
    assert _error(resp)["code"] == "REFERENCE_NOT_FOUND" and _error(resp)["field"] == field


def test_recipe_shape_errors(client: TestClient) -> None:
    missing = dict(NOMINAL)
    del missing["cushion_mm"]
    resp = client.post(RUNS, json=_body(parameters=missing))
    assert resp.status_code == 422 and _error(resp)["code"] == "VALIDATION_ERROR"
    resp = client.post(RUNS, json=_body(parameters={**NOMINAL, "warp_knob": 1}))
    assert resp.status_code == 422 and _error(resp)["code"] == "UNKNOWN_PARAMETER"
    resp = client.post(RUNS, json=_body(mode="turbo"))
    assert resp.status_code == 422


def test_create_run_without_intelligence_is_501(app: FastAPI, client: TestClient) -> None:
    app.state.simulation.executor = None
    resp = client.post(RUNS, json=_body())
    assert resp.status_code == 501 and _error(resp)["code"] == "CAPABILITY_UNAVAILABLE"
