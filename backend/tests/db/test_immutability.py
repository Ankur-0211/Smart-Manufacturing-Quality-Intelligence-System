"""Immutability rules (roadmap 9.4) enforced by app.db.guards and the repositories."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.db.errors import ImmutableRowError, RunImmutableError
from app.db.models import Machine, MaterialLot, ProcessRun, Product
from app.db.repositories import (
    EventRepository,
    ModelVersionRepository,
    PredictionRepository,
    RecommendationRepository,
    RunRepository,
    StageResultRepository,
    reset_run_results,
)

Refs = tuple[Machine, Product, MaterialLot]


def _run(session: Session, refs: Refs, recipe: dict[str, float]) -> ProcessRun:
    m, p, lot = refs
    return RunRepository(session).create(
        machine=m, product=p, material_lot=lot, parameters=recipe, today=date(2026, 10, 15)
    )


def _stage(session: Session, run: ProcessRun) -> None:
    StageResultRepository(session).add(
        run,
        stage_name="MATERIAL_CONDITIONING",
        sequence_index=1,
        substate="COMPLETED",
        health_score=0.9,
        risk_level="NORMAL",
    )


def _predict(session: Session, run: ProcessRun | None) -> None:
    mv = ModelVersionRepository(session).ensure_mock()
    PredictionRepository(session).add(
        run,
        model_version_id=mv.id,
        label="PASS",
        p_fail=0.1,
        threshold_used=0.42,
        risk_level="LOW",
        inference_backend="mock",
    )


def _finalise(session: Session, run: ProcessRun) -> None:
    RunRepository(session).set_status(run, "FINAL_RESULT")
    session.flush()


def test_run_parameters_cannot_be_updated(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    run.parameters.melt_temp_c = 999.0
    with pytest.raises(ImmutableRowError):
        session.flush()


def test_prediction_cannot_be_updated(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    _predict(session, run)
    prediction = PredictionRepository(session).for_run(run.id)
    assert prediction is not None
    prediction.p_fail = 0.0
    with pytest.raises(ImmutableRowError):
        session.flush()


def test_stage_result_cannot_be_updated(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    _stage(session, run)
    row = StageResultRepository(session).for_run(run.id)[0]
    row.health_score = 0.1
    with pytest.raises(ImmutableRowError):
        session.flush()


def test_events_and_recommendations_are_append_only(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    event = EventRepository(session).append(run.id, "run.started", {"x": 1})
    session.delete(event)
    with pytest.raises(ImmutableRowError):
        session.flush()
    session.rollback()

    run = _run(session, refs, recipe)
    (rec,) = RecommendationRepository(session).add_batch(
        run,
        "req-1",
        [
            {
                "option_rank": 1,
                "predicted_p_fail": 0.2,
                "predicted_label": "PASS",
                "delta_p_fail": -0.3,
                "constraint_status": "ALL_SATISFIED",
            }
        ],
    )
    rec.predicted_p_fail = 0.0
    with pytest.raises(ImmutableRowError):
        session.flush()


def test_terminal_run_rejects_new_results(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    _finalise(session, run)
    with pytest.raises(RunImmutableError):
        _stage(session, run)
    with pytest.raises(RunImmutableError):
        _predict(session, run)
    with pytest.raises(RunImmutableError):
        RunRepository(session).set_status(run, "INITIALIZED")


def test_terminal_run_only_label_is_mutable(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    _finalise(session, run)
    RunRepository(session).set_label(run, "cooler melt + longer cooling")
    assert run.scenario_label == "cooler melt + longer cooling"
    run.mode = "stepwise"
    with pytest.raises(RunImmutableError):
        session.flush()


def test_reset_clears_results_of_open_run(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    _stage(session, run)
    _predict(session, run)
    reset_run_results(session, run)
    assert StageResultRepository(session).for_run(run.id) == []
    assert PredictionRepository(session).for_run(run.id) is None
    assert run.parameters is not None  # parameters are kept (roadmap 9.5.1)


def test_reset_of_terminal_run_is_refused(
    session: Session, refs: Refs, recipe: dict[str, float]
) -> None:
    run = _run(session, refs, recipe)
    _stage(session, run)
    _finalise(session, run)
    with pytest.raises(RunImmutableError):
        reset_run_results(session, run)
    row = StageResultRepository(session).for_run(run.id)[0]
    session.delete(row)
    with pytest.raises(RunImmutableError):
        session.flush()


def test_stateless_prediction_without_run(session: Session) -> None:
    _predict(session, None)  # POST /predict rows have run_id NULL
