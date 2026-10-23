"""Real-intelligence integration (roadmap R2-P5 tasks 1, 4, 5, 12) and the demo profile (16.2).

Runs the app with ``SMQI_INTELLIGENCE_BACKEND=real``: Role 1's ``RealQualityIntelligence``.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import ModelVersion
from app.db.seed import load_fleet, seed
from app.main import create_app
from scripts.seed_demo_runs import SCENARIOS, SeedError, seed_demo_runs
from tests.conftest import make_settings
from tests.db.conftest import migrate

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"


def _seeded_url(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'real.db').as_posix()}"
    migrate(url)
    app = create_app(make_settings(database_url=url))
    with app.state.db.session() as s:
        seed(s, load_fleet(DOMAIN / "fleet.yaml"))
    app.state.db.dispose()
    return url


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    return _seeded_url(tmp_path)


@pytest.fixture
def real_app(db_url: str) -> FastAPI:
    return create_app(make_settings(database_url=db_url, intelligence_backend="real"))


@pytest.fixture
def client(real_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(real_app, raise_server_exceptions=False) as c:
        yield c


def _active(app: FastAPI) -> list[str]:
    with app.state.db.session() as s:
        rows = s.scalars(select(ModelVersion).where(ModelVersion.is_active.is_(True))).all()
        return [f"{r.name}-{r.semver}" for r in rows]


def test_startup_registers_the_serving_model(real_app: FastAPI, client: TestClient) -> None:
    info = real_app.state.intelligence.version_info()
    assert not info.is_mock
    assert _active(real_app) == [info.model_version]  # the seed's mock row is deactivated
    data = client.get("/api/v1/models/active").json()["data"]
    assert data["is_mock"] is False
    assert [m["version"] for m in data["models"]] == [info.model_version]
    assert data["models"][0]["algorithm"] == "role1-facade"
    assert data["models"][0]["constraints_version"] == info.constraints_version


def test_switching_backends_keeps_one_active_model(db_url: str) -> None:
    for backend, expected in (
        ("real", "fusion-1.0.0"),
        ("mock", "mock-0.0.0"),
        ("real", "fusion-1.0.0"),
    ):
        app = create_app(make_settings(database_url=db_url, intelligence_backend=backend))
        with TestClient(app):
            assert _active(app) == [expected]
        app.state.db.dispose()


def test_health_reports_real_intelligence(client: TestClient) -> None:
    data = client.get("/api/v1/health").json()["data"]
    assert data["status"] == "ok"
    assert data["intelligence_backend"] == "real" and data["model_loaded"] is True
    intelligence = next(c for c in data["components"] if c["name"] == "intelligence")
    assert intelligence["detail"].startswith("Real intelligence")


def test_global_explanation(client: TestClient) -> None:
    data = client.get("/api/v1/models/active/global-explanation").json()["data"]
    assert data["model_version"] == "fusion-1.0.0"
    assert data["mean_abs_shap"]


def test_predictions_reference_the_registered_model(real_app: FastAPI, client: TestClient) -> None:
    body = client.post(
        "/api/v1/predict",
        json={
            "machine_id": "MC-02",
            "product_id": "PP-JBOX-42",
            "material_lot_id": "A-771",
            "parameters": {
                p["name"]: p["nominal"]
                for p in client.get("/api/v1/constraints").json()["data"]["parameters"]
            },
        },
    ).json()["data"]
    assert body["prediction"]["model_version"] == "fusion-1.0.0"
    assert body["prediction"]["is_mock"] is False
    with real_app.state.db.session() as s:
        algorithms = {r.algorithm for r in s.scalars(select(ModelVersion)).all()}
    assert "unregistered" not in algorithms  # the prediction found the startup row


def test_demo_profile_requires_real(db_url: str) -> None:
    with pytest.raises(ValueError, match="demo"):
        make_settings(database_url=db_url, env="demo", intelligence_backend="mock")
    app = create_app(make_settings(database_url=db_url, env="demo", intelligence_backend="real"))
    with TestClient(app) as c:
        assert c.get("/api/v1/health").json()["data"]["env"] == "demo"


def test_seed_demo_runs_through_the_api(db_url: str) -> None:
    app = create_app(make_settings(database_url=db_url, env="demo", intelligence_backend="real"))
    app.state.simulation.stage_presentation_ms = 0
    with TestClient(app) as c:
        created = seed_demo_runs(c)
        assert [r["label"] for r in created] == [s.label for s in SCENARIOS]
        by_label = {r["label"]: r for r in created}
        assert by_label["demo: nominal recipe"]["status"] == "FINAL_RESULT"
        assert by_label["demo: nominal recipe"]["result"] == "PASS"
        assert by_label["demo: short cooling"]["status"] == "FINAL_RESULT"
        high = by_label["demo: high injection pressure"]
        assert (high["status"], high["result"]) == ("FINAL_RESULT", "FAIL")
        blocked = by_label["demo: melt above ceiling"]
        assert (blocked["status"], blocked["blocked_stage"]) == ("BLOCKED", "PLASTICIZING")
        assert seed_demo_runs(c) == []  # idempotent
        history = c.get("/api/v1/simulation/runs").json()["data"]
        assert {r["inference_backend"] for r in history} == {"real"}


def test_seed_refuses_mock(db_url: str) -> None:
    with (
        TestClient(create_app(make_settings(database_url=db_url))) as c,
        pytest.raises(SeedError, match="MOCK"),
    ):
        seed_demo_runs(c)
