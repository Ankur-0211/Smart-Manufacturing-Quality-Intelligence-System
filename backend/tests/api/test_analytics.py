"""Analytics over stored runs (roadmap R2-P8 required tests): aggregations on a seeded DB match
hand-computed numbers, default exclusions apply and are togglable, parameter buckets follow the
registry window, and the SPC endpoint returns the stored series."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.db.models import ModelVersion, Prediction, StageResultRow
from app.db.repositories import ReferenceRepository, RunRepository
from app.db.seed import load_fleet, seed
from app.db.vocab import RECIPE_FIELDS
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
API = "/api/v1/analytics"
T0 = datetime(2026, 10, 20, 8, 0, tzinfo=UTC)

# (machine, lot, status, backend, is_whatif, label, p_fail, risk, melt, override, plasticizing risk)
RUNS: list[tuple[Any, ...]] = [
    ("MC-01", "A-771", "FINAL_RESULT", "real", False, "FAIL", 0.8, "HIGH", 200.0, True, "HIGH"),
    ("MC-01", "A-771", "FINAL_RESULT", "real", False, "PASS", 0.2, "LOW", 230.0, False, "NORMAL"),
    ("MC-02", "C-904", "FINAL_RESULT", "real", False, "PASS", 0.3, "LOW", 290.0, False, None),
    (
        "MC-02",
        "A-771",
        "FINAL_RESULT",
        "mock",
        False,
        "FAIL",
        0.9,
        "HIGH",
        230.0,
        False,
        "CRITICAL",
    ),
    ("MC-02", "A-771", "FINAL_RESULT", "real", True, "FAIL", 0.6, "MEDIUM", 230.0, False, None),
    ("MC-01", "A-771", "BLOCKED", "real", False, None, None, None, 300.0, False, None),
]


def _insert(app: Any) -> list[str]:
    ids: list[str] = []
    with app.state.db.session() as s:
        refs = ReferenceRepository(s)
        model = ModelVersion(name="fusion", semver="9.9.9", algorithm="test")
        s.add(model)
        s.flush()
        runs = RunRepository(s)
        for i, (
            mc,
            lot,
            status,
            backend,
            whatif,
            label,
            p,
            risk,
            melt,
            ovr,
            stage_risk,
        ) in enumerate(RUNS):
            recipe = {f: 1.0 for f in RECIPE_FIELDS} | {"melt_temp_c": melt}
            run = runs.create(
                machine=refs.machine(mc),
                product=refs.product("PP-JBOX-42"),
                material_lot=refs.material(lot),
                parameters=recipe,
                parent_run_id=ids[1] if whatif else None,
                inference_backend=backend,
            )
            run.created_at = (
                T0 + timedelta(hours=i) + (timedelta(days=1) if i >= 3 else timedelta())
            )
            if stage_risk:
                s.add(
                    StageResultRow(
                        run_id=run.id,
                        stage_name="PLASTICIZING",
                        sequence_index=1,
                        substate="COMPLETED",
                        health_score=0.5,
                        risk_level=stage_risk,
                    )
                )
            if label:
                s.add(
                    Prediction(
                        run_id=run.id,
                        model_version_id=model.id,
                        label=label,
                        p_fail=p,
                        threshold_used=0.35,
                        risk_level=risk,
                        constraint_override_applied=ovr,
                        inference_backend=backend,
                    )
                )
            s.flush()
            run.status = status
            s.flush()
            ids.append(run.id)
    return ids


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    url = f"sqlite:///{(tmp_path / 'analytics.db').as_posix()}"
    migrate(url)
    app = create_app(make_settings(database_url=url))
    with app.state.db.session() as s:
        seed(s, load_fleet(DOMAIN / "fleet.yaml"))
    _insert(app)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _get(client: TestClient, path: str, **params: Any) -> Any:
    response = client.get(f"{API}{path}", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_summary_default_exclusions_match_hand_counts(client: TestClient) -> None:
    data = _get(client, "/summary")
    assert data["filters"] == {
        "include_whatif": False,
        "include_mock": False,
        "include_unfinished": False,
        "created_from": None,
        "created_to": None,
    }
    assert data["excluded"] == {"whatif": 1, "mock": 1, "unfinished": 1}
    assert (data["runs"], data["with_prediction"], data["predicted_fail"]) == (3, 3, 1)
    assert data["predicted_fail_rate"] == pytest.approx(1 / 3)
    assert data["mean_p_fail"] == pytest.approx((0.8 + 0.2 + 0.3) / 3)
    assert data["risk_levels"] == {"HIGH": 1, "LOW": 2}
    assert data["not_releasable"] == 1
    assert data["stage_risk_frequency"] == [
        {"stage": "PLASTICIZING", "counts": {"HIGH": 1, "NORMAL": 1}, "total": 2}
    ]
    assert [(d["day"], d["runs"], d["predicted_fail"]) for d in data["runs_over_time"]] == [
        ("2026-10-20", 3, 1)
    ]


def test_every_exclusion_is_togglable(client: TestClient) -> None:
    data = _get(client, "/summary", include_whatif=True, include_mock=True, include_unfinished=True)
    assert data["excluded"] == {}
    assert (data["runs"], data["with_prediction"], data["predicted_fail"]) == (6, 5, 3)
    assert data["predicted_fail_rate"] == pytest.approx(3 / 5)
    assert data["stage_risk_frequency"][0]["counts"] == {"HIGH": 1, "NORMAL": 1, "CRITICAL": 1}
    assert _get(client, "/summary", include_mock=True)["runs"] == 4
    assert _get(client, "/summary", include_whatif=True)["runs"] == 4


def test_date_range_filters_runs(client: TestClient) -> None:
    data = _get(
        client,
        "/summary",
        include_whatif=True,
        include_mock=True,
        include_unfinished=True,
        **{"from": "2026-10-21T00:00:00Z"},
    )
    assert data["runs"] == 3  # the last three are a day later


def test_by_machine_and_material(client: TestClient) -> None:
    machines = _get(client, "/by-machine")["rows"]
    assert [
        (r["key"], r["runs"], r["predicted_fail"], r["predicted_fail_rate"]) for r in machines
    ] == [
        ("MC-01", 2, 1, 0.5),
        ("MC-02", 1, 0, 0.0),
    ]
    lots = _get(client, "/by-material")
    assert lots["group"] == "lot"
    assert [(r["key"], r["runs"]) for r in lots["rows"]] == [("A-771", 2), ("C-904", 1)]
    grades = _get(client, "/by-material", group="resin_grade")["rows"]
    assert [(r["key"], r["runs"], r["predicted_fail"]) for r in grades] == [
        ("PP-C", 1, 0),
        ("PP-H", 2, 1),
    ]


def test_by_parameter_buckets_follow_the_registry_window(client: TestClient) -> None:
    data = _get(client, "/by-parameter", parameter="melt_temp_c", buckets=5)
    assert data["window"] == {"min": 180.0, "max": 295.0}  # constraints-1.0.0
    assert data["unit"] == "c"
    assert [(r["lo"], r["hi"]) for r in data["rows"]] == [
        (180.0, 203.0),
        (203.0, 226.0),
        (226.0, 249.0),
        (249.0, 272.0),
        (272.0, 295.0),
    ]
    assert [r["runs"] for r in data["rows"]] == [1, 0, 1, 0, 1]
    assert [r["predicted_fail_rate"] for r in data["rows"]] == [1.0, None, 0.0, None, 0.0]


def test_by_parameter_rejects_unknown_parameters(client: TestClient) -> None:
    response = client.get(f"{API}/by-parameter", params={"parameter": "colour"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_PARAMETER"


def test_spc_returns_the_stored_series_and_states_that_alerts_are_unavailable(
    client: TestClient,
) -> None:
    data = _get(client, "/spc", machine_id="MC-01", parameter="melt_temp_c")
    assert [p["value"] for p in data["series"]] == [200.0, 230.0]  # oldest first
    assert data["spc"]["available"] is False
    assert "CCR-004" in data["spc"]["reason"]
    assert data["alerts"] is None
    unfinished = _get(
        client, "/spc", machine_id="MC-01", parameter="melt_temp_c", include_unfinished=True
    )
    assert [p["value"] for p in unfinished["series"]] == [200.0, 230.0, 300.0]


def test_spc_unknown_machine(client: TestClient) -> None:
    response = client.get(f"{API}/spc", params={"machine_id": "MC-99", "parameter": "melt_temp_c"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REFERENCE_NOT_FOUND"
