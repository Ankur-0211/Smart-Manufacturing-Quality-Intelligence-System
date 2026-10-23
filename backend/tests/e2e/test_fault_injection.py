"""Fault injection on the real intelligence (roadmap R2-P10 task 3).

Faults are injected into the live intelligence instance the app serves, so every path is the
production one: router -> service -> intelligence -> error handler -> envelope.

- missing / invalid model artifacts -> 503 with the stable code, and /health "degraded";
- every typed intelligence error -> its HTTP status and code (roadmap 9.1 table);
- an unexpected exception -> 500 INTERNAL_ERROR without internals;
- a stage failing mid-run -> ABORTED with the error code, partial state kept and inspectable;
- invalid parameters -> 422 with the specific code; unknown ids -> 404; rate limit -> 429;
- a missing or invalid registry -> the app refuses to start.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import DEFAULT_STATUS, ErrorCode
from app.contracts import errors as intelligence_errors
from app.contracts.errors import IntelligenceError, ModelNotLoadedError, RegistryInvalidError
from app.db.seed import load_fleet, seed
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures"
API = "/api/v1"
MISSING = "/api/v1/simulation/runs/00000000-0000-0000-0000-000000000000"


def _app(tmp_path: Path, **over: Any) -> FastAPI:
    url = f"sqlite:///{(tmp_path / 'faults.db').as_posix()}"
    migrate(url)
    app = create_app(make_settings(database_url=url, intelligence_backend="real", **over))
    with app.state.db.session() as s:
        seed(s, load_fleet(DOMAIN / "fleet.yaml"))
    app.state.simulation.stage_presentation_ms = 0
    return app


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return _app(tmp_path)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _body(**recipe: float) -> dict[str, Any]:
    fixture = json.loads((FIXTURES / "recipe_nominal.json").read_text("utf-8"))
    ctx = fixture["context"]
    return {
        "machine_id": ctx["machine"]["machine_id"],
        "product_id": ctx["product"]["product_id"],
        "material_lot_id": ctx["material_lot"]["material_lot_id"],
        "parameters": {**fixture["recipe"], **recipe},
    }


def _error(response: Any) -> dict[str, Any]:
    body = response.json()
    assert body["data"] is None
    assert body["meta"]["request_id"]
    error: dict[str, Any] = body["error"]
    return error


def _finished_run(client: TestClient) -> str:
    run_id: str = client.post(f"{API}/simulation/runs", json=_body()).json()["data"]["run_id"]
    client.post(f"{API}/simulation/runs/{run_id}/start", json={"mode": "stepwise"})
    for _ in range(6):
        state = client.post(f"{API}/simulation/runs/{run_id}/advance").json()["data"]
    assert state["status"] == "FINAL_RESULT"
    return run_id


# --- missing / invalid artifacts -----------------------------------------------------------------


def test_model_not_loaded_gives_503_and_degraded_health(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unloaded(*_: Any, **__: Any) -> Any:
        raise ModelNotLoadedError("fusion bundle missing", hint="unpack the model archive")

    intelligence = app.state.intelligence
    for method in ("evaluate", "predict", "version_info"):
        monkeypatch.setattr(intelligence, method, unloaded)

    response = client.post(f"{API}/predict", json=_body())
    assert response.status_code == 503
    error = _error(response)
    assert (error["code"], error["message"], error["hint"]) == (
        "MODEL_NOT_LOADED",
        "fusion bundle missing",
        "unpack the model archive",
    )

    health = client.get(f"{API}/health")
    assert health.status_code == 200  # liveness still answers
    data = health.json()["data"]
    assert data["status"] == "degraded"
    assert data["model_loaded"] is False
    component = next(c for c in data["components"] if c["name"] == "intelligence")
    assert component == {
        "name": "intelligence",
        "available": False,
        "detail": "MODEL_NOT_LOADED: fusion bundle missing",
    }
    assert data["intelligence"]["model_version"] == "fusion-1.0.0"  # resolved at startup


@pytest.mark.parametrize(
    "error_class",
    [
        cls
        for cls in vars(intelligence_errors).values()
        if isinstance(cls, type)
        and issubclass(cls, IntelligenceError)
        and cls is not IntelligenceError
    ],
    ids=lambda cls: cls.code,
)
def test_every_intelligence_error_maps_to_its_status(
    app: FastAPI,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    error_class: type[IntelligenceError],
) -> None:
    def fail(*_: Any, **__: Any) -> Any:
        raise error_class("injected", field="parameters.melt_temp_c")

    monkeypatch.setattr(app.state.intelligence, "evaluate", fail)
    response = client.post(f"{API}/predict", json=_body())
    code = ErrorCode(error_class.code)
    assert response.status_code == DEFAULT_STATUS[code]
    error = _error(response)
    assert (error["code"], error["message"], error["field"]) == (
        code.value,
        "injected",
        "parameters.melt_temp_c",
    )


def test_unexpected_intelligence_exception_is_500_without_internals(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(*_: Any, **__: Any) -> Any:
        raise RuntimeError("secret path C:/models/fusion.joblib")

    monkeypatch.setattr(app.state.intelligence, "evaluate", crash)
    response = client.post(f"{API}/predict", json=_body())
    assert response.status_code == 500
    error = _error(response)
    assert error["code"] == "INTERNAL_ERROR"
    assert "secret" not in response.text and "joblib" not in response.text


# --- failure mid-run ---------------------------------------------------------------------------


def test_stage_failure_mid_run_aborts_with_the_code_and_keeps_partial_state(
    app: FastAPI, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    intelligence = app.state.intelligence
    real_run_stage = intelligence.run_stage
    calls = {"n": 0}

    def flaky(*args: Any, **kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 3:  # INJECTION
            raise ModelNotLoadedError("injection module bundle missing")
        return real_run_stage(*args, **kwargs)

    monkeypatch.setattr(intelligence, "run_stage", flaky)
    run_id = client.post(f"{API}/simulation/runs", json=_body()).json()["data"]["run_id"]
    client.post(f"{API}/simulation/runs/{run_id}/start", json={"mode": "stepwise"})
    for _ in range(3):
        client.post(f"{API}/simulation/runs/{run_id}/advance")

    state = client.get(f"{API}/simulation/runs/{run_id}").json()["data"]
    assert state["status"] == "ABORTED"
    assert state["abort_reason"] == "ERROR:MODEL_NOT_LOADED"
    assert [s["stage_name"] for s in state["stage_results"]] == [
        "MATERIAL_CONDITIONING",
        "PLASTICIZING",
    ]
    assert state["prediction"] is None
    errors = [e for e in state["timeline"] if e["type"] == "run.error"]
    assert errors and errors[0]["payload"] == {
        "code": "MODEL_NOT_LOADED",
        "message": "injection module bundle missing",
    }
    # The aborted run is final: further commands are refused, not silently accepted.
    retry = client.post(f"{API}/simulation/runs/{run_id}/advance")
    assert retry.status_code == 409


# --- invalid input, unknown ids, rate limits ---------------------------------------------------


@pytest.mark.parametrize(
    ("body", "code", "field"),
    [
        (_body(melt_temp_c=400), "PARAM_OUT_OF_RANGE", "parameters.melt_temp_c"),
        ({**_body(), "machine_id": "MC-03"}, "COUPLING_VIOLATION", None),  # 110 t < nominal 120 t
        (
            {**_body(), "parameters": {**_body()["parameters"], "colour": 1}},
            "UNKNOWN_PARAMETER",
            None,
        ),
        ({**_body(), "machine_id": "MC-99"}, "REFERENCE_NOT_FOUND", "machine_id"),
    ],
    ids=["out-of-range", "coupling", "unknown-field", "unknown-machine"],
)
def test_invalid_requests_get_specific_codes(
    client: TestClient, body: dict[str, Any], code: str, field: str | None
) -> None:
    for path in (f"{API}/simulation/runs", f"{API}/predict"):
        response = client.post(path, json=body)
        assert response.status_code in (404, 422), path
        error = _error(response)
        assert error["code"] == code, path
        if field:
            assert error["field"] == field, path


@pytest.mark.parametrize(
    ("method", "path", "body", "code"),
    [
        ("get", MISSING, None, "RUN_NOT_FOUND"),
        ("get", f"{MISSING}/lineage", None, "RUN_NOT_FOUND"),
        ("post", f"{MISSING}/start", {"mode": "auto"}, "RUN_NOT_FOUND"),
        (
            "post",
            f"{API}/whatif",
            {"base_run_id": "nope", "overrides": {"cooling_time_s": 12}},
            "RUN_NOT_FOUND",
        ),
        ("post", f"{API}/recommend", {"run_id": "nope"}, "RUN_NOT_FOUND"),
        (
            "post",
            f"{API}/whatif/compare",
            {"run_id_a": "nope", "run_id_b": "nope2"},
            "RUN_NOT_FOUND",
        ),
        ("get", f"{API}/predict/nope/explain", None, "PREDICTION_NOT_FOUND"),
    ],
)
def test_unknown_ids_are_404_with_a_stable_code(
    client: TestClient, method: str, path: str, body: Any, code: str
) -> None:
    response = client.request(method.upper(), path, json=body)
    assert response.status_code == 404
    assert _error(response)["code"] == code


def test_rate_limit_is_429_with_a_retry_hint(tmp_path: Path) -> None:
    app = _app(tmp_path, rate_limit_per_min=2)
    with TestClient(app, raise_server_exceptions=False) as client:
        run_id = _finished_run(client)
        codes = [
            client.post(f"{API}/recommend", json={"run_id": run_id}).status_code for _ in range(3)
        ]
        assert codes == [200, 200, 429]
        limited = client.post(f"{API}/recommend", json={"run_id": run_id})
        error = _error(limited)
        assert error["code"] == "RATE_LIMITED"
        assert error["hint"]


# --- startup -----------------------------------------------------------------------------------


def test_startup_refuses_a_missing_registry(tmp_path: Path) -> None:
    with pytest.raises(RegistryInvalidError, match="Constraint file not found"):
        create_app(make_settings(constraints_path=str(tmp_path / "missing.yaml")))


def test_startup_refuses_an_invalid_registry(tmp_path: Path) -> None:
    broken = tmp_path / "constraints.yaml"
    broken.write_text("parameters: [this is not a registry\n", "utf-8")
    with pytest.raises(Exception):  # noqa: B017 - any startup failure is correct; it must not start
        create_app(make_settings(constraints_path=str(broken)))


def test_demo_profile_refuses_mock_intelligence() -> None:
    with pytest.raises(Exception, match="SMQI_ENV=demo requires"):
        make_settings(env="demo", intelligence_backend="mock")
