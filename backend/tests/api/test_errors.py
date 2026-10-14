"""Error envelope behaviour (roadmap 9.3.1, 9.3.3, 9.3.4)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict, Field

from app.api.errors import ApiError, ErrorCode
from app.main import include_protected


class _Probe(BaseModel):
    model_config = ConfigDict(extra="forbid")

    melt_temp_c: float = Field(ge=180, le=295)
    cooling_time_s: float = Field(ge=5, le=60)


def _probe_router() -> APIRouter:
    router = APIRouter()

    @router.post("/_probe")
    def probe(body: _Probe) -> dict[str, float]:
        return {"ok": body.melt_temp_c}

    @router.get("/_boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    @router.get("/_api_error")
    def api_error() -> None:
        raise ApiError(
            ErrorCode.RUN_NOT_FOUND,
            "Run 123 not found",
            field="run_id",
            hint="Check the run id",
        )

    return router


def _client(app_factory: Callable[..., FastAPI], **overrides: object) -> TestClient:
    app = app_factory(**overrides)
    include_protected(app, _probe_router())
    return TestClient(app, raise_server_exceptions=False)


def _assert_error_envelope(resp_json: dict[str, object]) -> dict[str, object]:
    assert set(resp_json) == {"data", "error", "meta"}
    assert resp_json["data"] is None
    error = resp_json["error"]
    assert isinstance(error, dict)
    meta = resp_json["meta"]
    assert isinstance(meta, dict) and meta["request_id"]
    return error


def test_range_violation_maps_to_param_out_of_range(app_factory: Callable[..., FastAPI]) -> None:
    c = _client(app_factory)
    resp = c.post("/api/v1/_probe", json={"melt_temp_c": 312, "cooling_time_s": 20})
    assert resp.status_code == 422
    err = _assert_error_envelope(resp.json())
    assert err["code"] == "PARAM_OUT_OF_RANGE"
    assert err["field"] == "melt_temp_c"
    (detail,) = err["details"]  # type: ignore[misc]
    assert detail == {
        "field": "melt_temp_c",
        "code": "PARAM_OUT_OF_RANGE",
        "message": detail["message"],
        "limit": 295,
        "value": 312,
    }


def test_exact_bounds_are_accepted(app_factory: Callable[..., FastAPI]) -> None:
    c = _client(app_factory)
    assert (
        c.post("/api/v1/_probe", json={"melt_temp_c": 295, "cooling_time_s": 5}).status_code == 200
    )
    assert (
        c.post("/api/v1/_probe", json={"melt_temp_c": 180, "cooling_time_s": 60}).status_code == 200
    )


def test_unknown_field_maps_to_unknown_parameter(app_factory: Callable[..., FastAPI]) -> None:
    c = _client(app_factory)
    resp = c.post(
        "/api/v1/_probe",
        json={"melt_temp_c": 230, "cooling_time_s": 20, "warp_magic": 1},
    )
    assert resp.status_code == 422
    assert _assert_error_envelope(resp.json())["code"] == "UNKNOWN_PARAMETER"


def test_mixed_problems_map_to_validation_error(app_factory: Callable[..., FastAPI]) -> None:
    c = _client(app_factory)
    resp = c.post("/api/v1/_probe", json={"melt_temp_c": "hot"})
    assert resp.status_code == 422
    err = _assert_error_envelope(resp.json())
    assert err["code"] == "VALIDATION_ERROR"
    assert len(err["details"]) == 2  # type: ignore[arg-type]


def test_api_error_rendered_with_hint(app_factory: Callable[..., FastAPI]) -> None:
    resp = _client(app_factory).get("/api/v1/_api_error")
    assert resp.status_code == 404
    err = _assert_error_envelope(resp.json())
    assert err["code"] == "RUN_NOT_FOUND"
    assert err["field"] == "run_id"
    assert err["hint"] == "Check the run id"


def test_unhandled_exception_hides_internals(app_factory: Callable[..., FastAPI]) -> None:
    resp = _client(app_factory).get("/api/v1/_boom")
    assert resp.status_code == 500
    err = _assert_error_envelope(resp.json())
    assert err["code"] == "INTERNAL_ERROR"
    assert "secret internal detail" not in resp.text
    assert "Traceback" not in resp.text


def test_unknown_route_and_method(app_factory: Callable[..., FastAPI]) -> None:
    c = _client(app_factory)
    resp = c.get("/api/v1/does-not-exist")
    assert resp.status_code == 404
    assert _assert_error_envelope(resp.json())["code"] == "ROUTE_NOT_FOUND"
    resp = c.delete("/api/v1/health")
    assert resp.status_code == 405
    assert _assert_error_envelope(resp.json())["code"] == "METHOD_NOT_ALLOWED"


def test_api_key_enforced_only_when_configured(app_factory: Callable[..., FastAPI]) -> None:
    body = {"melt_temp_c": 230, "cooling_time_s": 20}

    open_client = _client(app_factory)
    assert open_client.post("/api/v1/_probe", json=body).status_code == 200

    locked = _client(app_factory, api_key="s3cret")
    resp = locked.post("/api/v1/_probe", json=body)
    assert resp.status_code == 401
    assert _assert_error_envelope(resp.json())["code"] == "UNAUTHORIZED"
    assert (
        locked.post("/api/v1/_probe", json=body, headers={"X-API-Key": "wrong"}).status_code == 401
    )
    assert (
        locked.post("/api/v1/_probe", json=body, headers={"X-API-Key": "s3cret"}).status_code == 200
    )
    # Liveness stays public.
    assert locked.get("/api/v1/health").status_code == 200
