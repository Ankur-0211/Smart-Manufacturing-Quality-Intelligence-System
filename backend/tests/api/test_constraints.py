"""GET /api/v1/constraints (roadmap R2-P1 task 9 required tests), served from Role 1's registry."""

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
    assert data["version"] == data["registry_version"] == registry.version
    assert data["content_hash"] == registry.content_hash


def test_payload_carries_role1_registry_unchanged(client: TestClient) -> None:
    """Typed for the frontend, but nothing Role 1 publishes is dropped or altered."""
    data = client.get("/api/v1/constraints").json()["data"]
    public = client.app.state.registry.to_public_dict()  # type: ignore[attr-defined]
    assert {p["name"]: {k: v for k, v in p.items() if k != "name"} for p in data["parameters"]} == {
        name: {k: spec.get(k) for k in {**spec, **dict.fromkeys(_TYPED)}}
        for name, spec in public["parameters"].items()
    }
    for key in ("coupling_rules", "hard_constraints", "resin_grades", "risk_bands"):
        assert data[key] == public[key] or _superset(data[key], public[key]), key


_TYPED = (
    "kind", "stage", "unit", "dtype", "min", "max", "nominal", "step", "tolerance", "actionable",
    "change_cost", "max_step_change", "display_name", "provenance", "citation",
)  # fmt: skip


def _superset(served: object, source: object) -> bool:
    """Served payload = source plus typed fields defaulted to null/false where Role 1 omits them."""
    if isinstance(source, dict) and isinstance(served, dict):
        return all(k in served and _superset(served[k], v) for k, v in source.items())
    if isinstance(source, list) and isinstance(served, list):
        return len(source) == len(served) and all(map(_superset, served, source))
    return served == source


def test_constraints_carry_everything_a_slider_needs(client: TestClient) -> None:
    data = client.get("/api/v1/constraints").json()["data"]
    registry = client.app.state.registry  # type: ignore[attr-defined]
    assert [p["name"] for p in data["parameters"]][: len(RECIPE_FIELDS)] == list(RECIPE_FIELDS)
    for p in data["parameters"]:
        source = registry.get_parameter(p["name"])
        for key in ("min", "max", "nominal", "step", "unit", "display_name", "actionable"):
            assert p[key] == source[key], (p["name"], key)
    assert set(data["resin_grades"]) == set(registry.resin_grades)
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
