"""What-if, compare, sensitivity, recommend and lineage (roadmap R2-P5 required tests).

Runs on Role 1's real facade (and, for the property test, on the mock too).
"""

from __future__ import annotations

import hashlib
import json
import statistics
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from sqlalchemy import select

from app.api.errors import ApiError
from app.api.validation import validate_recipe
from app.contracts.context import ProcessInput
from app.contracts.recipe import RECIPE_FIELDS
from app.db.models import Prediction, ProcessRun, Recommendation, RunParameters, StageResultRow
from app.db.seed import load_fleet, seed
from app.main import create_app
from tests.conftest import make_settings
from tests.db.conftest import migrate

DOMAIN = Path(__file__).resolve().parents[2] / "app" / "domain"
FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures"
API = "/api/v1"


def _make_app(tmp_path: Path, backend: str = "real", **over: Any) -> FastAPI:
    url = f"sqlite:///{(tmp_path / f'whatif-{backend}.db').as_posix()}"
    migrate(url)
    app = create_app(make_settings(database_url=url, intelligence_backend=backend, **over))
    with app.state.db.session() as s:
        seed(s, load_fleet(DOMAIN / "fleet.yaml"))
    app.state.simulation.stage_presentation_ms = 0
    return app


def _finished_run(client: TestClient, fixture: str = "recipe_nominal") -> str:
    data = json.loads((FIXTURES / f"{fixture}.json").read_text("utf-8"))
    ctx = data["context"]
    run_id: str = client.post(
        f"{API}/simulation/runs",
        json={
            "machine_id": ctx["machine"]["machine_id"],
            "product_id": ctx["product"]["product_id"],
            "material_lot_id": ctx["material_lot"]["material_lot_id"],
            "parameters": data["recipe"],
            "mode": "stepwise",
            "speed_factor": "instant",
        },
    ).json()["data"]["run_id"]
    client.post(f"{API}/simulation/runs/{run_id}/start", json={"mode": "stepwise"})
    for _ in range(6):
        state = client.post(f"{API}/simulation/runs/{run_id}/advance").json()["data"]
        if state["status"] == "FINAL_RESULT":
            break
    assert state["status"] == "FINAL_RESULT"
    return run_id


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    return _make_app(tmp_path)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def _whatif(client: TestClient, base: str, overrides: dict[str, float], **kw: Any) -> Any:
    return client.post(f"{API}/whatif", json={"base_run_id": base, "overrides": overrides, **kw})


def _row_hashes(app: FastAPI, run_id: str) -> str:
    with app.state.db.session() as s:
        rows: list[Any] = [s.get(ProcessRun, run_id)]
        rows += s.scalars(select(RunParameters).where(RunParameters.run_id == run_id)).all()
        rows += s.scalars(select(StageResultRow).where(StageResultRow.run_id == run_id)).all()
        rows += s.scalars(select(Prediction).where(Prediction.run_id == run_id)).all()
        payload = [{c.key: getattr(r, c.key) for c in type(r).__table__.columns} for r in rows]
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _strip(obj: Any) -> Any:
    """Canonical JSON without wall-clock timing."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in {"compute_ms", "prediction_id"}}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    return obj


# ---------------------------------------------------------------- what-if


def test_cooling_change_recomputes_only_cooling(app: FastAPI, client: TestClient) -> None:
    base = _finished_run(client)
    parent = client.get(f"{API}/simulation/runs/{base}").json()["data"]
    old_cooling = parent["parameters"]["cooling_time_s"]
    resp = _whatif(client, base, {"cooling_time_s": old_cooling + 2.0}, label="cooler")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["reused_stages"] == [
        "MATERIAL_CONDITIONING",
        "PLASTICIZING",
        "INJECTION",
        "PACKING",
    ]
    assert data["recomputed_stages"] == ["COOLING"]
    diff = data["diff"]
    # UD-09: cycle time follows the changed stage time.
    assert {p["name"]: (p["from"], p["to"]) for p in diff["parameters"]} == {
        "cooling_time_s": (old_cooling, old_cooling + 2.0),
        "cycle_time_s": (
            parent["parameters"]["cycle_time_s"],
            parent["parameters"]["cycle_time_s"] + 2.0,
        ),
    }
    assert diff["cycle_time"]["delta_s"] == 2.0
    unchanged = [s for s in diff["stages"] if s["stage"] != "COOLING"]
    assert all(s["change"] == "unchanged" for s in unchanged)
    assert diff["prediction"]["p_fail_from"] == parent["prediction"]["p_fail"]
    assert diff["prediction"]["p_fail_to"] == data["prediction"]["p_fail"]
    assert diff["prediction"]["flipped"] == (
        parent["prediction"]["label"] != data["prediction"]["label"]
    )

    child = client.get(f"{API}/simulation/runs/{data['run_id']}").json()["data"]
    assert child["is_whatif"] and child["parent_run_id"] == base
    assert child["status"] == "FINAL_RESULT" and child["scenario_label"] == "cooler"
    assert child["context"] == parent["context"]  # parent's frozen snapshot, not re-derived
    reused = [r for r in child["stage_results"] if r["reused_from_stage_result_id"] is not None]
    assert [r["stage_name"] for r in reused] == data["reused_stages"]


def test_melt_change_recomputes_from_plasticizing(client: TestClient) -> None:
    base = _finished_run(client)
    data = _whatif(client, base, {"melt_temp_c": 240.0}, persist=False).json()["data"]
    assert data["reused_stages"] == ["MATERIAL_CONDITIONING"]
    assert data["recomputed_stages"] == ["PLASTICIZING", "INJECTION", "PACKING", "COOLING"]
    assert [p["name"] for p in data["diff"]["parameters"]] == ["melt_temp_c"]


def test_parent_rows_never_change(app: FastAPI, client: TestClient) -> None:
    base = _finished_run(client)
    before = _row_hashes(app, base)
    _whatif(client, base, {"melt_temp_c": 240.0, "cooling_time_s": 14.0})
    _whatif(client, base, {"hold_time_s": 5.0}, persist=False)
    assert _row_hashes(app, base) == before


def test_persist_false_writes_nothing(app: FastAPI, client: TestClient) -> None:
    base = _finished_run(client)
    with app.state.db.session() as s:
        counts = [len(s.scalars(select(m)).all()) for m in (ProcessRun, StageResultRow, Prediction)]
    data = _whatif(client, base, {"melt_temp_c": 240.0}, persist=False).json()["data"]
    assert data["run_id"] is None
    with app.state.db.session() as s:
        after = [len(s.scalars(select(m)).all()) for m in (ProcessRun, StageResultRow, Prediction)]
    assert after == counts


def test_whatif_validation_and_errors(client: TestClient) -> None:
    base = _finished_run(client)
    bad = _whatif(client, base, {"warp_knob": 1.0})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "UNKNOWN_PARAMETER"
    out = _whatif(client, base, {"melt_temp_c": 999.0})
    assert out.status_code == 422 and out.json()["error"]["field"] == "overrides.melt_temp_c"
    coupling = _whatif(client, base, {"hold_pressure_bar": 1300.0, "inj_pressure_bar": 900.0})
    assert coupling.json()["error"]["code"] == "COUPLING_VIOLATION"
    assert _whatif(client, "nope", {"melt_temp_c": 240.0}).status_code == 404
    unfinished = client.post(
        f"{API}/simulation/runs",
        json={
            "machine_id": "MC-02",
            "product_id": "PP-JBOX-42",
            "material_lot_id": "A-771",
            "parameters": json.loads((FIXTURES / "recipe_nominal.json").read_text("utf-8"))[
                "recipe"
            ],
        },
    ).json()["data"]["run_id"]
    conflict = _whatif(client, unfinished, {"melt_temp_c": 240.0})
    assert conflict.status_code == 409


def test_whatif_on_a_whatif_builds_lineage(client: TestClient) -> None:
    base = _finished_run(client)
    child = _whatif(client, base, {"melt_temp_c": 240.0}, label="hotter").json()["data"]["run_id"]
    grandchild = _whatif(client, child, {"cooling_time_s": 14.0}).json()["data"]["run_id"]
    sibling = _whatif(client, base, {"hold_time_s": 5.0}).json()["data"]["run_id"]
    tree = client.get(f"{API}/simulation/runs/{base}/lineage").json()["data"]
    assert tree["run"]["run_id"] == base
    assert [c["run"]["run_id"] for c in tree["children"]] == [child, sibling]
    assert tree["children"][0]["run"]["scenario_label"] == "hotter"
    assert [g["run"]["run_id"] for g in tree["children"][0]["children"]] == [grandchild]
    assert client.get(f"{API}/simulation/runs/nope/lineage").status_code == 404


def test_single_whatif_latency_budget(client: TestClient) -> None:
    """Plan §24.4: a single what-if < 100 ms with real intelligence (median, server side)."""
    base = _finished_run(client)
    timings = []
    for i in range(7):
        t0 = time.perf_counter()
        resp = _whatif(client, base, {"cooling_time_s": 12.0 + i * 0.5}, persist=False)
        timings.append(time.perf_counter() - t0)
        assert resp.status_code == 200
    assert statistics.median(timings) < 0.100


# ---------------------------------------------------------------- compare / sensitivity


def test_compare_two_runs(client: TestClient) -> None:
    a = _finished_run(client)
    b = _finished_run(client, "recipe_short_cooling")
    diff = client.post(f"{API}/whatif/compare", json={"run_id_a": a, "run_id_b": b}).json()["data"]
    assert [p["name"] for p in diff["parameters"]] == ["cooling_time_s"]
    assert diff["constraint_compliance"]["warnings_to"] >= 1  # HC-004 on the short-cooling run


def test_sensitivity_sweep(client: TestClient) -> None:
    base = _finished_run(client)
    resp = client.post(
        f"{API}/whatif/sensitivity",
        json={"base_run_id": base, "parameter": "cooling_time_s", "steps": 10},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]["points"]) == 10


def test_sensitivity_is_rate_limited(tmp_path: Path) -> None:
    app = _make_app(tmp_path, rate_limit_per_min=2)
    with TestClient(app, raise_server_exceptions=False) as c:
        base = _finished_run(c)
        body = {"base_run_id": base, "parameter": "cooling_time_s", "steps": 3}
        codes = [c.post(f"{API}/whatif/sensitivity", json=body).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------------------------------------------------------------- recommend


def test_recommend_persists_rows_with_request_and_model(app: FastAPI, client: TestClient) -> None:
    base = _finished_run(client)
    resp = client.post(f"{API}/recommend", json={"run_id": base, "max_changes": 2})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["request_id"] and data["base_p_fail"] is not None
    assert data["disclaimer_key"] == "DISCLAIMER_RECOMMENDATION"
    with app.state.db.session() as s:
        rows = s.scalars(
            select(Recommendation).where(Recommendation.request_id == data["request_id"])
        ).all()
        assert len(rows) == len(data["candidates"])
        assert all(r.run_id == base and r.model_version_id is not None for r in rows)
        assert [r.option_rank for r in rows] == [c["option_rank"] for c in data["candidates"]]


def test_recommend_needs_a_final_run(client: TestClient) -> None:
    run_id = client.post(
        f"{API}/simulation/runs",
        json={
            "machine_id": "MC-02",
            "product_id": "PP-JBOX-42",
            "material_lot_id": "A-771",
            "parameters": json.loads((FIXTURES / "recipe_nominal.json").read_text("utf-8"))[
                "recipe"
            ],
        },
    ).json()["data"]["run_id"]
    resp = client.post(f"{API}/recommend", json={"run_id": run_id})
    assert resp.status_code == 409
    assert client.post(f"{API}/recommend", json={"run_id": "nope"}).status_code == 404


# ---------------------------------------------------------------- property test (D11)


@pytest.fixture(scope="module", params=["real", "mock"])
def property_env(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory
) -> Iterator[tuple[FastAPI, TestClient, str]]:
    app = _make_app(tmp_path_factory.mktemp(request.param), backend=request.param)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield app, c, _finished_run(c)


_REGISTRY_OVERRIDES = st.dictionaries(
    keys=st.sampled_from(list(RECIPE_FIELDS)),
    values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    min_size=1,
    max_size=4,
)


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(fractions=_REGISTRY_OVERRIDES)
def test_partial_resimulation_equals_full_run(
    property_env: tuple[FastAPI, TestClient, str], fractions: dict[str, float]
) -> None:
    """For random valid override sets, partial re-sim == fresh full run (JSON-canonical)."""
    app, client, base = property_env
    registry = app.state.registry
    parent = client.get(f"{API}/simulation/runs/{base}").json()["data"]
    overrides = {}
    for name, f in fractions.items():
        spec = registry.get_parameter(name)
        steps = round((spec["max"] - spec["min"]) / spec["step"])
        overrides[name] = round(spec["min"] + round(f * steps) * spec["step"], 6)
    merged = {**parent["parameters"], **overrides}
    if "cycle_time_s" not in overrides:
        merged["cycle_time_s"] = round(
            parent["parameters"]["cycle_time_s"]
            + sum(
                merged[k] - parent["parameters"][k]
                for k in ("fill_time_s", "hold_time_s", "cooling_time_s")
            ),
            6,
        )
    try:
        validate_recipe(registry, merged, context=parent["context"])
    except ApiError:
        assume(False)

    resp = _whatif(client, base, overrides, persist=False)
    assert resp.status_code == 200, resp.json()
    partial = resp.json()["data"]

    full = app.state.intelligence.evaluate(
        ProcessInput.model_validate({"context": parent["context"], "recipe": merged}),
        include_explanation=True,
    )
    assert _strip(partial["stage_results"]) == _strip(
        [r.model_dump(mode="json") for r in full.stage_results]
    )
    assert _strip(partial["prediction"]) == _strip(full.prediction.model_dump(mode="json"))


def test_parent_from_another_model_is_fully_recomputed(tmp_path: Path) -> None:
    """Stages are reused only from the same model + limits; a mock-era parent never leaks into a
    real what-if."""
    mock_app = _make_app(tmp_path, backend="mock")
    with TestClient(mock_app) as c:
        base = _finished_run(c)
    mock_app.state.db.dispose()
    url = str(mock_app.state.settings.database_url)
    real_app = create_app(make_settings(database_url=url, intelligence_backend="real"))
    with TestClient(real_app) as c:
        data = _whatif(c, base, {"cooling_time_s": 14.0}, persist=False).json()["data"]
    assert data["reused_stages"] == []
    assert data["prediction"]["is_mock"] is False
