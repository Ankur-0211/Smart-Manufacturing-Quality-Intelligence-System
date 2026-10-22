"""The API serves the production frontend build (UD-16, roadmap R2-P9 task 4)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_settings

INDEX = "<!doctype html><title>SMQI</title><div id=root></div>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX, "utf-8")
    (root / "assets" / "app-1234.js").write_text("console.log(1)", "utf-8")
    (tmp_path / "secret.txt").write_text("outside", "utf-8")
    return root


@pytest.fixture
def client(dist: Path) -> Iterator[TestClient]:
    with TestClient(create_app(make_settings(frontend_dist=str(dist)))) as c:
        yield c


def test_index_and_assets_are_served(client: TestClient) -> None:
    root = client.get("/")
    assert root.status_code == 200
    assert root.text == INDEX
    assert root.headers["cache-control"] == "no-cache"
    asset = client.get("/assets/app-1234.js")
    assert asset.status_code == 200
    assert asset.text == "console.log(1)"


def test_client_routes_fall_back_to_index(client: TestClient) -> None:
    for path in ("/history/abc", "/analytics", "/what-if/compare"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.text == INDEX


def test_api_routes_win_and_unknown_api_routes_keep_the_envelope(client: TestClient) -> None:
    assert client.get("/api/v1/health").json()["data"] is not None
    missing = client.get("/api/v1/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ROUTE_NOT_FOUND"


def test_no_path_traversal_out_of_the_build(client: TestClient) -> None:
    response = client.get("/../secret.txt")
    assert "outside" not in response.text
    response = client.get("/%2e%2e/secret.txt")
    assert "outside" not in response.text


def test_without_a_build_root_is_a_route_not_found(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(frontend_dist=str(tmp_path / "missing")))) as c:
        response = c.get("/")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "ROUTE_NOT_FOUND"
