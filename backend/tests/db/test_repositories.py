from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.errors import DuplicateError, NotFoundError
from app.db.models import Machine, MaterialLot, ProcessRun, Product, RunParameters
from app.db.repositories import (
    ModelVersionRepository,
    PredictionRepository,
    RecommendationRepository,
    ReferenceRepository,
    RunFilters,
    RunRepository,
    StageResultRepository,
)
from app.db.vocab import RECIPE_FIELDS

Refs = tuple[Machine, Product, MaterialLot]


def _run(session: Session, refs: Refs, recipe: dict[str, float], **kw: object) -> ProcessRun:
    m, p, lot = refs
    return RunRepository(session).create(
        machine=m,
        product=p,
        material_lot=lot,
        parameters=recipe,
        today=date(2026, 10, 15),
        **kw,  # type: ignore[arg-type]
    )


def _stage_values(name: str, index: int) -> dict[str, object]:
    return {
        "stage_name": name,
        "sequence_index": index,
        "substate": "COMPLETED",
        "health_score": 0.86,
        "risk_level": "LOW",
        "anomaly": {"flag": False, "score": 0.1, "method": "zscore", "contributors": []},
        "indicators": {"dryness_margin": 0.6, "viscosity_class": "NOMINAL"},
        "indicator_provenance": {
            "dryness_margin": "specification_derived",
            "viscosity_class": "dataset_derived",
        },
        "notes": ["regrind 15% near limit"],
        "upstream_out": {"viscosity_class": "NOMINAL", "moisture_flag": False},
    }


def _prediction_values(session: Session) -> dict[str, object]:
    mv = ModelVersionRepository(session).ensure_mock()
    return {
        "model_version_id": mv.id,
        "label": "FAIL",
        "p_fail": 0.71,
        "threshold_used": 0.42,
        "risk_level": "HIGH",
        "inference_backend": "mock",
        "caveats": [{"code": "MOCK_INFERENCE", "message": "mock", "features": []}],
    }


def test_run_parameters_columns_equal_canonical_recipe_fields() -> None:
    cols = [
        c.name
        for c in RunParameters.__table__.columns
        if c.name not in {"id", "run_id", "created_at"}
    ]
    assert cols == list(RECIPE_FIELDS)


def test_create_run_snapshots_context(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    assert run.status == "INITIALIZED" and not run.is_whatif and run.parent_run_id is None
    snap = run.context_snapshot
    assert snap["machine"]["machine_id"] == "MC-03"
    assert snap["machine"]["machine_age_days"] == (date(2026, 10, 15) - date(2020, 1, 1)).days
    assert snap["machine"]["days_since_maintenance"] == 44
    assert snap["material_lot"]["material_lot_id"] == "A-771"
    assert run.parameters.as_dict() == recipe

    # Later reference edits never alter the snapshot.
    refs[2].moisture_pct = 0.2
    session.flush()
    session.expire_all()
    assert (
        RunRepository(session).get(run.id).context_snapshot["material_lot"]["moisture_pct"] == 0.04
    )


def test_create_run_rejects_incomplete_recipe(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    bad = dict(recipe)
    bad.pop("melt_temp_c")
    bad["warp_magic"] = 1.0
    with pytest.raises(ValueError, match=r"missing=\['melt_temp_c'\] unknown=\['warp_magic'\]"):
        _run(session, refs, bad)


def test_foreign_keys_are_enforced(session: Session, recipe: dict[str, float]) -> None:
    session.add(
        ProcessRun(machine_id=999, product_id=999, material_lot_id=999, context_snapshot={})
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_check_constraints_reject_unknown_status(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    session.commit()
    run.status = "EXPLODED"
    with pytest.raises(IntegrityError):
        session.flush()


def test_whatif_requires_parent(session: Session, refs: Refs, recipe: dict[str, float]) -> None:
    m, p, lot = refs
    session.add(
        ProcessRun(machine=m, product=p, material_lot=lot, is_whatif=True, context_snapshot={})
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_list_filters_and_pagination(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    repo = RunRepository(session)
    parent = _run(session, refs, recipe)
    _run(session, refs, recipe, parent_run_id=parent.id)
    _run(session, refs, recipe, inference_backend="mock")
    rows, total = repo.search(limit=2)
    assert total == 3 and len(rows) == 2
    assert repo.search(RunFilters(is_whatif=True))[1] == 1
    assert repo.search(RunFilters(is_whatif=False))[1] == 2
    assert repo.search(RunFilters(machine_code="MC-03"))[1] == 3
    assert repo.search(RunFilters(machine_code="MC-99"))[1] == 0
    assert repo.search(RunFilters(inference_backend="mock"))[1] == 1


def test_list_filters_by_prediction_label(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    _run(session, refs, recipe)
    PredictionRepository(session).add(run, **_prediction_values(session))
    rows, total = RunRepository(session).search(RunFilters(label="FAIL", risk_level="HIGH"))
    assert total == 1 and rows[0].id == run.id


def test_get_unknown_run(session: Session) -> None:
    with pytest.raises(NotFoundError):
        RunRepository(session).get("00000000-0000-0000-0000-000000000000")


def test_terminal_status_sets_completed_at(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    RunRepository(session).set_status(run, "FINAL_RESULT", current_stage=None)
    assert run.completed_at is not None


def test_lineage_tree(session: Session, refs: Refs, recipe: dict[str, float]) -> None:
    root = _run(session, refs, recipe)
    a = _run(session, refs, recipe, parent_run_id=root.id, scenario_label="a")
    _run(session, refs, recipe, parent_run_id=root.id, scenario_label="b")
    _run(session, refs, recipe, parent_run_id=a.id, scenario_label="a1")
    tree = RunRepository(session).lineage(root.id)
    assert [c.run.scenario_label for c in tree.children] == ["a", "b"]
    assert [g.run.scenario_label for g in tree.children[0].children] == ["a1"]


def test_whatif_copy_keeps_parent_rows(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    parent = _run(session, refs, recipe)
    stages = StageResultRepository(session)
    src = stages.add(parent, **_stage_values("MATERIAL_CONDITIONING", 1))
    child = _run(session, refs, recipe, parent_run_id=parent.id)
    copy = stages.copy_for_child(src, child)
    assert copy.run_id == child.id and copy.reused_from_stage_result_id == src.id
    assert copy.indicators == src.indicators and copy.health_score == src.health_score
    assert [r.id for r in stages.for_run(parent.id)] == [src.id]


def test_json_payloads_round_trip(
    session: Session, database: object, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    values = _stage_values("MATERIAL_CONDITIONING", 1)
    StageResultRepository(session).add(run, **values)
    session.commit()
    session.expunge_all()
    row = StageResultRepository(session).get(run.id, "MATERIAL_CONDITIONING")
    for key in ("anomaly", "indicators", "indicator_provenance", "notes", "upstream_out"):
        assert getattr(row, key) == values[key]


def test_recommendation_latest_request(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    repo = RecommendationRepository(session)
    cand = {
        "predicted_p_fail": 0.2,
        "predicted_label": "PASS",
        "delta_p_fail": -0.5,
        "constraint_status": "ALL_SATISFIED",
    }
    repo.add_batch(run, "req-1", [{**cand, "option_rank": 1}])
    repo.add_batch(run, "req-2", [{**cand, "option_rank": 2}, {**cand, "option_rank": 1}])
    latest = repo.latest_for_run(run.id)
    assert [(r.request_id, r.option_rank) for r in latest] == [("req-2", 1), ("req-2", 2)]


def test_model_version_upsert_switches_active(session: Session) -> None:
    repo = ModelVersionRepository(session)
    repo.upsert("fusion", "0.1.0", algorithm="xgboost", is_active=True)
    repo.upsert("fusion", "1.0.0", algorithm="xgboost", is_active=True)
    active = repo.active("fusion")
    assert active is not None and active.semver == "1.0.0"
    assert sum(1 for m in repo.all_versions() if m.name == "fusion" and m.is_active) == 1
    assert repo.ensure_mock().id == repo.ensure_mock().id


def test_duplicate_lot_does_not_roll_back_caller(session: Session, refs: Refs) -> None:
    ref = ReferenceRepository(session)
    ref.create_material(
        lot_code="B-100",
        resin_grade="PP-H",
        mfi=10,
        moisture_pct=0.02,
        regrind_pct=0,
        colourant_pct=0,
    )
    with pytest.raises(DuplicateError):
        ref.create_material(
            lot_code="A-771",
            resin_grade="PP-H",
            mfi=10,
            moisture_pct=0.02,
            regrind_pct=0,
            colourant_pct=0,
        )
    # The earlier insert in the same transaction survives.
    assert session.scalar(select(MaterialLot).where(MaterialLot.lot_code == "B-100")) is not None
    assert inspect(refs[0]).persistent


def test_abort_interrupted_runs(session: Session, refs: Refs, recipe: dict[str, float]) -> None:
    repo = RunRepository(session)
    fresh = _run(session, refs, recipe)
    running = _run(session, refs, recipe)
    repo.set_status(running, "INJECTION")
    done = _run(session, refs, recipe)
    repo.set_status(done, "FINAL_RESULT")
    stepwise = _run(session, refs, recipe, mode="stepwise")
    repo.set_status(stepwise, "PACKING")
    blocked = _run(session, refs, recipe)
    repo.set_status(blocked, "BLOCKED", blocked_stage="PLASTICIZING")
    paused = _run(session, refs, recipe)
    repo.set_status(paused, "PAUSED", current_stage="COOLING")
    aborted = repo.abort_interrupted()
    assert aborted == [running.id]
    # Runs waiting for the user have no task to lose and survive a restart.
    assert (stepwise.status, blocked.status, paused.status) == ("PACKING", "BLOCKED", "PAUSED")
    assert running.status == "ABORTED" and running.abort_reason == "SERVER_RESTART"
    assert fresh.status == "INITIALIZED" and done.status == "FINAL_RESULT"


def test_timestamps_round_trip_as_utc(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    from datetime import UTC

    run = _run(session, refs, recipe)
    session.commit()
    session.expire_all()
    reloaded = RunRepository(session).get(run.id)
    assert reloaded.created_at.tzinfo is not None
    assert reloaded.created_at.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
    assert abs((reloaded.created_at - run.created_at.astimezone(UTC)).total_seconds()) < 1
