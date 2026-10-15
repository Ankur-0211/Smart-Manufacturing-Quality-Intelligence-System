"""Exhaustive transition-table test (roadmap §9.5.1, R2-P4 required test)."""

from __future__ import annotations

import itertools

import pytest

from app.db.vocab import RUN_STATUSES, STAGE_NAMES
from app.engine.state_machine import (
    Command,
    FsmState,
    InvalidTransitionError,
    RunImmutableTransitionError,
    next_stage,
    transition,
)

EXECUTING = (*STAGE_NAMES, "QUALITY_INSPECTION")


def _state(status: str, mode: str = "auto") -> FsmState:
    if status == "BLOCKED":
        return FsmState(status=status, mode=mode, blocked_stage="PLASTICIZING")
    if status == "PAUSED":
        return FsmState(status=status, mode=mode, status_before_pause="INJECTION")
    return FsmState(status=status, mode=mode)


def _expected(
    status: str, command: Command, mode: str
) -> tuple[str, tuple[str, ...]] | type[Exception]:
    """The roadmap table, written independently of the implementation."""
    terminal = status in ("FINAL_RESULT", "ABORTED")
    if command is Command.RESET:
        return RunImmutableTransitionError if terminal else ("INITIALIZED", ("run.reset",))
    if terminal:
        return InvalidTransitionError
    if command is Command.ABORT:
        return ("ABORTED", ("run.aborted",))
    if command is Command.ERROR:
        return ("ABORTED", ("run.error", "run.aborted"))
    if command is Command.START:
        return (
            ("MATERIAL_CONDITIONING", ("run.started",))
            if status == "INITIALIZED"
            else InvalidTransitionError
        )
    if command is Command.STAGE_DONE:
        return (next_stage(status), ()) if status in STAGE_NAMES else InvalidTransitionError
    if command is Command.BLOCK:
        return ("BLOCKED", ("stage.blocked",)) if status in STAGE_NAMES else InvalidTransitionError
    if command is Command.OVERRIDE:
        return (
            ("INJECTION", ("stage.override_acknowledged",))
            if status == "BLOCKED"
            else InvalidTransitionError
        )
    if command is Command.PAUSE:
        return (
            ("PAUSED", ("run.paused",))
            if mode == "auto" and status in EXECUTING
            else InvalidTransitionError
        )
    if command is Command.RESUME:
        return ("INJECTION", ("run.resumed",)) if status == "PAUSED" else InvalidTransitionError
    if command is Command.PREDICTED:
        return (
            ("FINAL_RESULT", ("prediction.ready", "run.completed"))
            if status == "QUALITY_INSPECTION"
            else InvalidTransitionError
        )
    raise AssertionError(command)


@pytest.mark.parametrize(
    ("status", "command", "mode"),
    list(itertools.product(RUN_STATUSES, list(Command), ["auto", "stepwise"])),
    ids=lambda v: str(v),
)
def test_every_state_command_pair(status: str, command: Command, mode: str) -> None:
    expected = _expected(status, command, mode)
    state = _state(status, mode)
    if isinstance(expected, type):
        with pytest.raises(expected):
            transition(state, command, mode=mode)
        return
    result = transition(state, command, mode=mode)
    assert (result.state.status, result.events) == expected


def test_full_auto_cycle_order() -> None:
    s = transition(FsmState(), Command.START, mode="auto").state
    seen = [s.status]
    while s.status in STAGE_NAMES:
        s = transition(s, Command.STAGE_DONE).state
        seen.append(s.status)
    s = transition(s, Command.PREDICTED).state
    seen.append(s.status)
    assert seen == [*STAGE_NAMES, "QUALITY_INSPECTION", "FINAL_RESULT"]


def test_block_override_continues_after_blocked_stage() -> None:
    s = FsmState(status="COOLING")
    s = transition(s, Command.BLOCK).state
    assert (s.status, s.blocked_stage) == ("BLOCKED", "COOLING")
    s = transition(s, Command.OVERRIDE, stage="COOLING").state
    assert (s.status, s.blocked_stage) == ("QUALITY_INSPECTION", None)


def test_override_for_wrong_stage_is_rejected() -> None:
    s = transition(FsmState(status="PLASTICIZING"), Command.BLOCK).state
    with pytest.raises(InvalidTransitionError, match="blocked stage is PLASTICIZING"):
        transition(s, Command.OVERRIDE, stage="INJECTION")


def test_reset_keeps_mode_and_pause_resume_restores_status() -> None:
    s = transition(FsmState(), Command.START, mode="stepwise").state
    assert transition(s, Command.RESET).state == FsmState(mode="stepwise")
    with pytest.raises(InvalidTransitionError):
        transition(s, Command.PAUSE)  # stepwise runs cannot pause (no task to pause)
    a = FsmState(status="PACKING", mode="auto")
    paused = transition(a, Command.PAUSE).state
    assert transition(paused, Command.RESUME).state == a


def test_start_rejects_unknown_mode() -> None:
    with pytest.raises(InvalidTransitionError, match="unknown mode"):
        transition(FsmState(), Command.START, mode="turbo")


def test_cache_key_is_numerically_canonical() -> None:
    from app.engine.cache import stage_cache_key

    a = stage_cache_key("S", {"mfi": 12, "flag": True}, {"x": {"y": [1, 2]}}, "m1", "c1")
    b = stage_cache_key("S", {"flag": True, "mfi": 12.0}, {"x": {"y": [1.0, 2.0]}}, "m1", "c1")
    assert a == b
    assert a != stage_cache_key("S", {"mfi": 12, "flag": 1}, {"x": {"y": [1, 2]}}, "m1", "c1")
    assert a != stage_cache_key("S", {"mfi": 12, "flag": True}, {"x": {"y": [1, 2]}}, "m2", "c1")
