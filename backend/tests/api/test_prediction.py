"""POST /predict, GET /predict/{id}/explain, /models (roadmap 9.3.2, R2-P3 required tests)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Prediction
from app.db.seed import load_fleet, seed
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
NOMINAL: dict[str, float] = json.loads(
    (
        Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "recipe_nominal.json"
    ).read_text("utf-8")
)["recipe"]


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    url = f"sqlite:///{(tmp_path / 'predict.db').as_posix()}"
    migrate(url)
    application = create_app(make_settings(database_url=url))
    with application.state.db.session() as s:
        seed(s, load_fleet(DOMAIN / "fleet.yaml"))
    return application


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _body(**over: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "machine_id": "MC-02",  # the nominal clamp force exceeds MC-03's rating (CPL-003)
        "product_id": "PP-JBOX-42",
        "material_lot_id": "A-771",
        "parameters": dict(NOMINAL),
    }
    body.update(over)
    return body


def test_predict_persists_a_mock_prediction(app: FastAPI, client: TestClient) -> None:
    resp = client.post("/api/v1/predict", json=_body())
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [r["stage_name"] for r in data["stage_results"]] == [
        "MATERIAL_CONDITIONING",
        "PLASTICIZING",
        "INJECTION",
        "PACKING",
        "COOLING",
    ]
    prediction = data["prediction"]
    assert prediction["is_mock"] is True and prediction["model_version"] == "mock-0.0.0"
    assert prediction["explanation"]["attributions"]
    with app.state.db.session() as s:
        row = s.scalars(select(Prediction).where(Prediction.id == data["prediction_id"])).one()
        assert row.run_id is None
        assert row.inference_backend == "mock"
        assert row.p_fail == prediction["p_fail"]
        assert row.input_snapshot is not None
        assert row.input_snapshot["recipe"]["melt_temp_c"] == NOMINAL["melt_temp_c"]


def test_predict_matches_a_simulation_run(client: TestClient) -> None:
    """One pipeline: /predict and a run of the same recipe agree (roadmap 9.1 #4)."""
    predicted = client.post("/api/v1/predict", json=_body()).json()["data"]["prediction"]
    run_id = client.post(
        "/api/v1/simulation/runs", json=_body(mode="stepwise", speed_factor="instant")
    ).json()["data"]["run_id"]
    client.post(f"/api/v1/simulation/runs/{run_id}/start", json={"mode": "stepwise"})
    for _ in range(6):
        client.post(f"/api/v1/simulation/runs/{run_id}/advance")
    run_prediction = client.get(f"/api/v1/simulation/runs/{run_id}").json()["data"]["prediction"]
    assert (run_prediction["p_fail"], run_prediction["label"]) == (
        predicted["p_fail"],
        predicted["label"],
    )


def test_predict_validates_like_run_creation(client: TestClient) -> None:
    bad = client.post("/api/v1/predict", json=_body(parameters={**NOMINAL, "melt_temp_c": 296}))
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "PARAM_OUT_OF_RANGE"
    coupling = client.post(
        "/api/v1/predict",
        json=_body(parameters={**NOMINAL, "hold_pressure_bar": 1000, "inj_pressure_bar": 900}),
    )
    assert coupling.json()["error"]["code"] == "COUPLING_VIOLATION"
    missing = client.post("/api/v1/predict", json=_body(machine_id="MC-99"))
    assert missing.status_code == 404
    assert missing.json()["error"]["field"] == "machine_id"


def test_hard_constraint_is_data_not_an_error(client: TestClient) -> None:
    resp = client.post("/api/v1/predict", json=_body(material_lot_id="D-105"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["stage_results"][0]["blocked"] is True
    assert data["prediction"]["risk_level"] == "CRITICAL"


def test_explain_returns_the_stored_explanation(client: TestClient) -> None:
    data = client.post("/api/v1/predict", json=_body()).json()["data"]
    resp = client.get(f"/api/v1/predict/{data['prediction_id']}/explain")
    assert resp.status_code == 200
    assert resp.json()["data"] == data["prediction"]["explanation"]


def test_explain_recomputes_when_not_stored(client: TestClient) -> None:
    data = client.post("/api/v1/predict", json=_body(include_explanation=False)).json()["data"]
    assert data["prediction"]["explanation"] is None
    with_it = client.post("/api/v1/predict", json=_body()).json()["data"]
    resp = client.get(f"/api/v1/predict/{data['prediction_id']}/explain")
    assert resp.status_code == 200
    assert resp.json()["data"] == with_it["prediction"]["explanation"]  # deterministic


def test_explain_unknown_prediction(client: TestClient) -> None:
    resp = client.get("/api/v1/predict/does-not-exist/explain")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "PREDICTION_NOT_FOUND"


def test_explain_from_an_unloaded_model_is_unavailable(app: FastAPI, client: TestClient) -> None:
    data = client.post("/api/v1/predict", json=_body(include_explanation=False)).json()["data"]
    info = app.state.intelligence.version_info()
    app.state.intelligence.version_info = lambda: info.model_copy(
        update={"model_version": "fusion-9.9.9"}
    )
    resp = client.get(f"/api/v1/predict/{data['prediction_id']}/explain")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "MODEL_NOT_LOADED"


def test_models_active_lists_the_mock(client: TestClient) -> None:
    data = client.get("/api/v1/models/active").json()["data"]
    assert data["is_mock"] is True
    assert data["intelligence"]["model_version"] == "mock-0.0.0"
    assert [m["version"] for m in data["models"]] == ["mock-0.0.0"]
    # provenance keys are always present (null when the bundle does not report them)
    assert {"dataset_hash", "git_sha", "bundle_sha256"} <= data["models"][0].keys()
    assert client.get("/api/v1/models").json()["data"][0]["algorithm"] == "mock"


def test_prediction_endpoints_need_the_api_key_when_set() -> None:
    with TestClient(create_app(make_settings(api_key="k"))) as c:
        assert c.post("/api/v1/predict", json=_body()).status_code == 401
        assert c.get("/api/v1/models/active").status_code == 401
