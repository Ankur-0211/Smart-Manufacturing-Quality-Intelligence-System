"""Whole-journey integrity checks (roadmap R2-P10 tasks 4 and 5; §15.4).

- Scenario immutability: every database row of the original runs (run, parameters, stage results,
  prediction, events) hashes the same after a full journey of what-ifs, saved scenarios,
  comparisons, sweeps, recommendations, lineage and analytics. Children point at their parent.
- Analytics: what-if children and MOCK-scored runs are excluded by default, each exclusion is
  stated with its count, and every toggle brings the rows back.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Table, select

from app.db.models import Prediction, ProcessRun, RunParameters, SimulationEvent, StageResultRow
from app.db.seed import load_fleet, seed
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures"
API = "/api/v1"
ROW_TABLES: list[tuple[Table, Any]] = [
    (ProcessRun.__table__, ProcessRun.__table__.c.id),  # type: ignore[arg-type]
    (RunParameters.__table__, RunParameters.__table__.c.run_id),  # type: ignore[arg-type]
    (StageResultRow.__table__, StageResultRow.__table__.c.run_id),  # type: ignore[arg-type]
    (Prediction.__table__, Prediction.__table__.c.run_id),  # type: ignore[arg-type]
    (SimulationEvent.__table__, SimulationEvent.__table__.c.run_id),  # type: ignore[arg-type]
]


@pytest.fixture
def db_url(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'journey.db').as_posix()}"
    migrate(url)
    return url


def _app(db_url: str, backend: str) -> FastAPI:
    app = create_app(make_settings(database_url=db_url, intelligence_backend=backend))
    with app.state.db.session() as s:
        seed(s, load_fleet(DOMAIN / "fleet.yaml"))
    app.state.simulation.stage_presentation_ms = 0
    return app


@pytest.fixture
def client(db_url: str) -> Iterator[TestClient]:
    with TestClient(_app(db_url, "real"), raise_server_exceptions=False) as c:
        yield c


def _ok(response: Any) -> Any:
    assert response.status_code < 400, response.text
    return response.json()["data"]


def _recipe(**over: float) -> dict[str, Any]:
    fixture = json.loads((FIXTURES / "recipe_nominal.json").read_text("utf-8"))
    ctx = fixture["context"]
    return {
        "machine_id": ctx["machine"]["machine_id"],
        "product_id": ctx["product"]["product_id"],
        "material_lot_id": ctx["material_lot"]["material_lot_id"],
        "parameters": {**fixture["recipe"], **over},
    }


def _run(client: TestClient, *, override: bool = False, **recipe: float) -> str:
    run_id: str = _ok(client.post(f"{API}/simulation/runs", json=_recipe(**recipe)))["run_id"]
    _ok(client.post(f"{API}/simulation/runs/{run_id}/start", json={"mode": "stepwise"}))
    for _ in range(8):
        state = _ok(client.post(f"{API}/simulation/runs/{run_id}/advance"))
        if state["status"] == "BLOCKED" and override:
            state = _ok(
                client.post(
                    f"{API}/simulation/runs/{run_id}/override",
                    json={"stage": state["blocked_stage"], "acknowledgement": "integrity test"},
                )
            )
        if state["status"] == "FINAL_RESULT":
            return run_id
    raise AssertionError(state["status"])


def _row_hash(app: FastAPI, run_id: str) -> dict[str, str]:
    """sha256 of every row each table holds for the run, in a stable order."""
    out = {}
    with app.state.db.session() as s:
        for table, key in ROW_TABLES:
            rows = s.execute(select(table).where(key == run_id)).mappings().all()
            text = json.dumps(
                sorted(
                    (dict(r) for r in rows),
                    key=lambda r: json.dumps(r, sort_keys=True, default=str),
                ),
                sort_keys=True,
                default=str,
            )
            out[table.name] = hashlib.sha256(text.encode()).hexdigest()
    return out


def test_original_runs_are_never_rewritten_by_the_journey(client: TestClient) -> None:
    app: FastAPI = client.app  # type: ignore[assignment]
    originals = {
        "pass": _run(client),
        "fail": _run(client, inj_pressure_bar=1800),
        "not_releasable": _run(client, override=True, melt_temp_c=290),
    }
    before = {name: _row_hash(app, rid) for name, rid in originals.items()}
    assert all(h["predictions"] != hashlib.sha256(b"[]").hexdigest() for h in before.values())

    base = originals["fail"]
    # The whole decision-support journey on the originals.
    _ok(client.post(f"{API}/predict", json=_recipe()))
    explained = _ok(client.get(f"{API}/simulation/runs/{base}"))["prediction"]
    _ok(client.get(f"{API}/predict/{explained['prediction_id']}/explain"))
    for overrides in ({"inj_pressure_bar": 1100}, {"cooling_time_s": 12}, {"melt_temp_c": 240}):
        _ok(
            client.post(
                f"{API}/whatif",
                json={"base_run_id": base, "overrides": overrides, "persist": False},
            )
        )
    child = _ok(
        client.post(
            f"{API}/whatif",
            json={"base_run_id": base, "overrides": {"inj_pressure_bar": 1100}, "label": "flip"},
        )
    )["run_id"]
    grandchild = _ok(
        client.post(
            f"{API}/whatif", json={"base_run_id": child, "overrides": {"cooling_time_s": 12}}
        )
    )["run_id"]
    _ok(
        client.post(
            f"{API}/whatif",
            json={"base_run_id": originals["not_releasable"], "overrides": {"melt_temp_c": 230}},
        )
    )
    _ok(
        client.post(f"{API}/whatif/compare", json={"run_id_a": originals["pass"], "run_id_b": base})
    )
    _ok(
        client.post(
            f"{API}/whatif/sensitivity", json={"base_run_id": base, "parameter": "melt_temp_c"}
        )
    )
    _ok(client.post(f"{API}/recommend", json={"run_id": base}))
    _ok(client.get(f"{API}/simulation/runs/{base}/lineage"))
    _ok(client.get(f"{API}/simulation/runs"))
    for path in ("summary", "by-machine", "by-material", "by-parameter?parameter=melt_temp_c"):
        _ok(client.get(f"{API}/analytics/{path}"))

    # Finished runs refuse every state change.
    for command, body in (("reset", None), ("start", {"mode": "auto"}), ("abort", {"reason": "x"})):
        response = client.post(f"{API}/simulation/runs/{base}/{command}", json=body)
        assert response.status_code == 409, command

    after = {name: _row_hash(app, rid) for name, rid in originals.items()}
    assert after == before

    child_state = _ok(client.get(f"{API}/simulation/runs/{child}"))
    assert (child_state["parent_run_id"], child_state["is_whatif"]) == (base, True)
    assert _ok(client.get(f"{API}/simulation/runs/{grandchild}"))["parent_run_id"] == child
    tree = _ok(client.get(f"{API}/simulation/runs/{base}/lineage"))
    assert [c["run"]["run_id"] for c in tree["children"]] == [child]
    assert [g["run"]["run_id"] for g in tree["children"][0]["children"]] == [grandchild]


def test_analytics_excludes_whatif_and_mock_runs_by_default(db_url: str) -> None:
    # MOCK-scored history first (as from a development session), then the real system.
    with TestClient(_app(db_url, "mock")) as mock:
        _run(mock)
        _run(mock)
    with TestClient(_app(db_url, "real")) as client:
        passed, failed = _run(client), _run(client, inj_pressure_bar=1800)
        _ok(
            client.post(
                f"{API}/whatif",
                json={"base_run_id": failed, "overrides": {"inj_pressure_bar": 1100}},
            )
        )

        default = _ok(client.get(f"{API}/analytics/summary"))
        assert default["excluded"] == {"whatif": 1, "mock": 2, "unfinished": 0}
        assert (default["runs"], default["predicted_fail"]) == (2, 1)  # only the two real originals
        assert default["predicted_fail_rate"] == pytest.approx(0.5)

        assert _ok(client.get(f"{API}/analytics/summary?include_whatif=true"))["runs"] == 3
        assert _ok(client.get(f"{API}/analytics/summary?include_mock=true"))["runs"] == 4
        everything = _ok(
            client.get(f"{API}/analytics/summary?include_whatif=true&include_mock=true")
        )
        assert (everything["runs"], everything["excluded"]) == (5, {"unfinished": 0})

        # The breakdowns honour the same defaults.
        machines = _ok(client.get(f"{API}/analytics/by-machine"))["rows"]
        assert sum(r["runs"] for r in machines) == 2
        history = _ok(client.get(f"{API}/simulation/runs"))
        assert {r["inference_backend"] for r in history} == {
            "mock",
            "real",
        }  # history keeps everything
        assert passed != failed
