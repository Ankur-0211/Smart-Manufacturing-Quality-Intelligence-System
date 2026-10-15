"""Pure run state machine (roadmap §9.5.1, Plan §7.3).

``transition(state, command)`` returns the next state and the run-level event types to emit, or
raises. It performs no I/O and never computes intelligence; the orchestrator owns stage execution
and stage-level events (``stage.started``, ``stage.completed``, ``anomaly.flagged``,
``constraint.breached``).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from app.db.vocab import STAGE_NAMES, TERMINAL_STATUSES

QUALITY: Final = "QUALITY_INSPECTION"
#: Statuses in which the run is executing a stage (S1-S5 or the quality stage).
EXECUTING: Final = frozenset((*STAGE_NAMES, QUALITY))


class Command(StrEnum):
    START = "START"
    STAGE_DONE = "STAGE_DONE"
    BLOCK = "BLOCK"
    OVERRIDE = "OVERRIDE"
    PAUSE = "PAUSE"
    RESUME = "RESUME"
    RESET = "RESET"
    ABORT = "ABORT"
    PREDICTED = "PREDICTED"
    ERROR = "ERROR"


class InvalidTransitionError(Exception):
    """The command is not allowed in the current state -> HTTP 409 INVALID_STATE_TRANSITION."""

    def __init__(self, status: str, command: Command, reason: str = "") -> None:
        super().__init__(
            f"{command.value} is not allowed while the run is {status}"
            + (f": {reason}" if reason else "")
        )
        self.status = status
        self.command = command


class RunImmutableTransitionError(InvalidTransitionError):
    """RESET of a FINAL_RESULT/ABORTED run (UD-08) -> HTTP 409 RUN_IMMUTABLE."""


@dataclass(frozen=True)
class FsmState:
    status: str = "INITIALIZED"
    mode: str = "auto"
    blocked_stage: str | None = None
    status_before_pause: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


@dataclass(frozen=True)
class Transition:
    state: FsmState
    events: tuple[str, ...]


def next_stage(stage: str) -> str:
    """Stage after ``stage`` in the fixed cycle order; COOLING -> QUALITY_INSPECTION."""
    order = (*STAGE_NAMES, QUALITY)
    index = order.index(stage)
    if index + 1 >= len(order):
        raise ValueError(f"no stage after {stage}")
    return order[index + 1]


def transition(
    state: FsmState, command: Command, *, mode: str | None = None, stage: str | None = None
) -> Transition:
    s = state.status

    if command is Command.RESET:
        if state.terminal:
            raise RunImmutableTransitionError(
                s, command, "completed runs cannot be reset; re-run as a new run"
            )
        return Transition(FsmState(mode=state.mode), ("run.reset",))

    if state.terminal:
        raise InvalidTransitionError(s, command, "the run is finished")

    if command is Command.ABORT:
        return Transition(
            replace(state, status="ABORTED", status_before_pause=None), ("run.aborted",)
        )

    if command is Command.ERROR:
        return Transition(
            replace(state, status="ABORTED", status_before_pause=None), ("run.error", "run.aborted")
        )

    if command is Command.START:
        if s != "INITIALIZED":
            raise InvalidTransitionError(s, command)
        new_mode = mode or state.mode
        if new_mode not in ("auto", "stepwise"):
            raise InvalidTransitionError(s, command, f"unknown mode {new_mode!r}")
        return Transition(FsmState(status=STAGE_NAMES[0], mode=new_mode), ("run.started",))

    if command is Command.STAGE_DONE:
        if s not in STAGE_NAMES:
            raise InvalidTransitionError(s, command)
        return Transition(replace(state, status=next_stage(s)), ())

    if command is Command.BLOCK:
        if s not in STAGE_NAMES:
            raise InvalidTransitionError(s, command, "only stages S1-S5 can block")
        return Transition(replace(state, status="BLOCKED", blocked_stage=s), ("stage.blocked",))

    if command is Command.OVERRIDE:
        if s != "BLOCKED" or state.blocked_stage is None:
            raise InvalidTransitionError(s, command, "nothing is blocked")
        if stage is not None and stage != state.blocked_stage:
            raise InvalidTransitionError(
                s, command, f"blocked stage is {state.blocked_stage}, not {stage}"
            )
        return Transition(
            replace(state, status=next_stage(state.blocked_stage), blocked_stage=None),
            ("stage.override_acknowledged",),
        )

    if command is Command.PAUSE:
        if state.mode != "auto" or s not in EXECUTING:
            raise InvalidTransitionError(s, command, "only a running auto-mode run can pause")
        return Transition(replace(state, status="PAUSED", status_before_pause=s), ("run.paused",))

    if command is Command.RESUME:
        if s != "PAUSED" or state.status_before_pause is None:
            raise InvalidTransitionError(s, command)
        return Transition(
            replace(state, status=state.status_before_pause, status_before_pause=None),
            ("run.resumed",),
        )

    if command is Command.PREDICTED:
        if s != QUALITY:
            raise InvalidTransitionError(s, command)
        return Transition(
            replace(state, status="FINAL_RESULT"), ("prediction.ready", "run.completed")
        )

    raise InvalidTransitionError(s, command)  # pragma: no cover - exhaustive above
