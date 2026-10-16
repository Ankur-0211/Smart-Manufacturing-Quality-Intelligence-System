"""GET /api/v1/constraints (roadmap R2-P1 task 9 required tests)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.contracts.recipe import RECIPE_FIELDS
from app.main import create_app
from tests.conftest import make_settings


def test_constraints_returns_registry_version_and_hash(client: TestClient) -> None:
    resp = client.get("/api/v1/constraints")
    assert resp.status_code == 200
    data = resp.json()["data"]
    registry = client.app.state.registry  # type: ignore[attr-defined]
    assert data["version"] == registry.version == "constraints-0.1.0"
    assert data["content_hash"] == registry.content_hash
    assert data == registry.to_public_dict()  # the typed schema loses nothing


def test_constraints_carry_everything_a_slider_needs(client: TestClient) -> None:
    data = client.get("/api/v1/constraints").json()["data"]
    params = {p["name"]: p for p in data["parameters"]}
    assert [p["name"] for p in data["parameters"]][: len(RECIPE_FIELDS)] == list(RECIPE_FIELDS)
    melt = params["melt_temp_c"]
    assert {k: melt[k] for k in ("min", "max", "nominal", "step", "unit")} == {
        "min": 180.0,
        "max": 295.0,
        "nominal": 230.0,
        "step": 1.0,
        "unit": "c",
    }
    assert params["resin_grade"]["allowed_values"] == ["PP-H", "PP-C"]
    assert {r["id"] for r in data["coupling_rules"]} == {"CPL-001", "CPL-002", "CPL-003", "CPL-004"}


def test_etag_revalidation(client: TestClient) -> None:
    first = client.get("/api/v1/constraints")
    etag = first.headers["etag"]
    assert first.headers["cache-control"] == "no-cache"
    again = client.get("/api/v1/constraints", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""
    stale = client.get("/api/v1/constraints", headers={"If-None-Match": '"old"'})
    assert stale.status_code == 200


def test_constraints_require_api_key_when_configured() -> None:
    with TestClient(create_app(make_settings(api_key="s3cret"))) as c:
        assert c.get("/api/v1/constraints").status_code == 401
        ok = c.get("/api/v1/constraints", headers={"X-API-Key": "s3cret"})
        assert ok.status_code == 200
