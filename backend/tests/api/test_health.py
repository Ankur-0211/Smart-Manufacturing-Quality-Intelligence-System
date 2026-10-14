from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.ids import is_valid_uuid
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate


def test_health_returns_envelope(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"data", "error", "meta"}
    assert body["error"] is None
    assert body["meta"]["api_version"] == "1"
    assert isinstance(body["meta"]["latency_ms"], float)
    assert body["data"]["env"] == "test"
    assert body["data"]["intelligence_backend"] == "mock"


def test_health_reports_unbuilt_components_honestly(client: TestClient) -> None:
    data = client.get("/api/v1/health").json()["data"]
    # DB and intelligence do not exist yet in R2-P1, so the service must say "degraded".
    assert data["status"] == "degraded"
    assert data["db"] is False
    assert data["model_loaded"] is False
    names = {c["name"]: c["available"] for c in data["components"]}
    assert names["api"] is True
    assert names["database"] is False
    assert names["intelligence"] is False


def test_request_id_generated_and_echoed(client: TestClient) -> None:
    resp = client.get("/api/v1/health")
    rid = resp.headers["x-request-id"]
    assert is_valid_uuid(rid)
    assert resp.json()["meta"]["request_id"] == rid


def test_request_id_from_client_is_honoured(client: TestClient) -> None:
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "demo-req-001"})
    assert resp.headers["x-request-id"] == "demo-req-001"
    assert resp.json()["meta"]["request_id"] == "demo-req-001"


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "bad id <script>"})
    assert is_valid_uuid(resp.headers["x-request-id"])


def test_openapi_served_under_api_prefix(client: TestClient) -> None:
    resp = client.get("/api/v1/openapi.json")
    assert resp.status_code == 200
    assert "/api/v1/health" in resp.json()["paths"]


def test_cors_allows_configured_frontend_origin(client: TestClient) -> None:
    resp = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert resp.headers["access-control-allow-origin"] == "http://localhost:5173"
    other = client.get("/api/v1/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in other.headers


def test_health_reports_migrated_database(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'h.db').as_posix()}"
    migrate(url)
    with TestClient(create_app(make_settings(database_url=url))) as c:
        data = c.get("/api/v1/health").json()["data"]
    assert data["db"] is True
    db = next(comp for comp in data["components"] if comp["name"] == "database")
    assert db["available"] is True and db["detail"].startswith("at head")
