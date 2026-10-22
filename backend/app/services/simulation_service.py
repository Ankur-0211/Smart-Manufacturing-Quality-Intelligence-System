"""Simulation orchestration (roadmap §7.6, §9.5; R2-P4).

Owns the run lifecycle: auto mode (one asyncio task per run, presentation delays), stepwise mode
(one stage per ``advance`` call), pause/resume, BLOCKED + override, reset, abort, error handling.
Every state change and its events are committed in ONE transaction, then the events are published
(persist-then-publish). Intelligence is reached only through the ``StageExecutor`` port.

Concurrency: one ``asyncio.Lock`` per run serialises steps and commands. RESET/ABORT take the lock
before cancelling the run task, so a stage that is mid-flight can never commit after a reset.

A blocked stage's result is NOT written to ``stage_results`` (rows are immutable); it is carried in
the persisted ``stage.blocked`` event and written, marked ``overridden``, when the user overrides.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.errors import NotFoundError
from app.db.models import ProcessRun, SimulationEvent
from app.db.repositories import (
    EventRepository,
    LineageNode,
    PredictionRepository,
    ReferenceRepository,
    RunFilters,
    RunRepository,
    StageResultRepository,
    context_snapshot,
    reset_run_results,
)
from app.db.session import Database
from app.db.vocab import STAGE_NAMES, TERMINAL_STATUSES
from app.engine.cache import StageCache, stage_cache_key
from app.engine.events import EventBus, envelope_from_row
from app.engine.ports import StageExecutor
from app.engine.state_machine import (
    EXECUTING,
    QUALITY,
    Command,
    FsmState,
    InvalidTransitionError,
    transition,
)
from app.services.predictions import (
    persist_prediction,
    prediction_row_to_json,
    split_model_version,
)

log = get_logger(__name__)

#: Presentation-time multiplier per speed factor (Plan §7.4). ``instant`` skips animation.
SPEED_MULTIPLIER: dict[str, float] = {"0.5x": 2.0, "1x": 1.0, "2x": 0.5, "instant": 0.0}

EventSpec = tuple[str, str | None, Mapping[str, Any]]


#: (recipe, RunContext JSON snapshot) -> validated recipe; raises on violation.
ParameterValidator = Callable[[Mapping[str, float], Mapping[str, Any]], Mapping[str, float]]


class ExecutorUnavailableError(Exception):
    """No intelligence is bound yet -> HTTP 501 CAPABILITY_UNAVAILABLE."""


@dataclass
class _Handle:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    resume: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None


# ---------------------------------------------------------------------------
# Payload <-> row mapping (JSON in, JSON out; Role 2 never reshapes intelligence payloads)
# ---------------------------------------------------------------------------

_STAGE_JSON_COLUMNS = (
    "stage_name",
    "sequence_index",
    "substate",
    "health_score",
    "risk_level",
    "anomaly",
    "indicators",
    "indicator_provenance",
    "constraint_breaches",
    "notes",
    "inputs_used",
    "upstream_in",
    "upstream_out",
    "blocked",
    "block_reason",
    "module_version",
    "constraints_version",
    "compute_ms",
)


def stage_row_values(
    result: Mapping[str, Any], *, presentation_ms: float, overridden: bool
) -> dict[str, Any]:
    values = {k: result[k] for k in _STAGE_JSON_COLUMNS if k in result}
    anomaly = result.get("anomaly") or {}
    values.update(
        substate="COMPLETED",
        anomaly_flag=bool(anomaly.get("flag", False)),
        anomaly_score=float(anomaly.get("score", 0.0)),
        overridden=overridden,
        duration_ms=presentation_ms,
    )
    return values


def stage_row_to_json(row: Any) -> dict[str, Any]:
    out = {k: getattr(row, k) for k in _STAGE_JSON_COLUMNS}
    out["risk_ordinal"] = ("NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL").index(row.risk_level)
    out["overridden"] = row.overridden
    out["presentation_ms"] = row.duration_ms
    out["reused_from_stage_result_id"] = row.reused_from_stage_result_id
    return out


def process_input_of(run: ProcessRun) -> dict[str, Any]:
    """ProcessInput JSON (roadmap §7.7) from the run's frozen context and recipe."""
    return {"context": run.context_snapshot, "recipe": run.parameters.as_dict()}


def flat_input(process_input: Mapping[str, Any]) -> dict[str, Any]:
    ctx = process_input["context"]
    return {**ctx["machine"], **ctx["product"], **ctx["material_lot"], **process_input["recipe"]}


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class SimulationService:
    def __init__(
        self,
        db: Database,
        bus: EventBus,
        cache: StageCache,
        *,
        executor: StageExecutor | None = None,
        stage_presentation_ms: int = 1500,
    ) -> None:
        self.db = db
        self.bus = bus
        self.cache = cache
        self.executor = executor
        self.stage_presentation_ms = stage_presentation_ms
        self._handles: dict[str, _Handle] = {}

    # ----------------------------------------------------------------- helpers

    def _handle(self, run_id: str) -> _Handle:
        handle = self._handles.get(run_id)
        if handle is None:
            handle = self._handles[run_id] = _Handle()
        return handle

    def require_executor(self) -> StageExecutor:
        """The bound executor; ``ExecutorUnavailableError`` (HTTP 501) when none is bound."""
        return self._require_executor()

    def _require_executor(self) -> StageExecutor:
        if self.executor is None:
            raise ExecutorUnavailableError(
                "Simulation needs the intelligence layer; no StageExecutor is bound yet "
                "(waits for app.contracts and the mock/real QualityIntelligence)."
            )
        return self.executor

    @staticmethod
    def _fsm(run: ProcessRun) -> FsmState:
        return FsmState(
            status=run.status,
            mode=run.mode,
            blocked_stage=run.blocked_stage,
            status_before_pause=run.current_stage if run.status == "PAUSED" else None,
        )

    def _apply_sync(
        self,
        run_id: str,
        command: Command | None,
        *,
        mode: str | None = None,
        stage: str | None = None,
        payloads: Mapping[str, Mapping[str, Any]] | None = None,
        pre_events: Sequence[EventSpec] = (),
        post_events: Sequence[EventSpec] = (),
        run_updates: Mapping[str, Any] | None = None,
        extra_write: Callable[[Session, ProcessRun], None] | None = None,
    ) -> tuple[FsmState, list[dict[str, Any]]]:
        """One transaction: optional writes, FSM transition, status update, events."""
        with self.db.session() as s:
            runs = RunRepository(s)
            run = runs.get(run_id)
            state = self._fsm(run)
            events: list[EventSpec] = list(pre_events)
            # Validate the transition BEFORE any write, so illegal commands change nothing.
            result = (
                transition(state, command, mode=mode, stage=stage) if command is not None else None
            )
            fsm_stage = stage or (run.blocked_stage if command is Command.OVERRIDE else None)
            if extra_write is not None:
                extra_write(s, run)
            if result is not None:
                state = result.state
                for etype in result.events:
                    estage = (
                        fsm_stage
                        if etype.startswith("stage.")
                        else (QUALITY if etype == "prediction.ready" else None)
                    )
                    events.append((etype, estage, dict((payloads or {}).get(etype, {}))))
                if state.status in EXECUTING:
                    current: str | None = state.status
                elif state.status == "PAUSED":
                    current = state.status_before_pause
                elif state.status == "BLOCKED":
                    current = state.blocked_stage
                else:
                    current = None
                fields: dict[str, Any] = {
                    "mode": state.mode,
                    "blocked_stage": state.blocked_stage,
                    "current_stage": current,
                    **(run_updates or {}),
                }
                if state.status != run.status or run.status not in TERMINAL_STATUSES:
                    runs.set_status(run, state.status, **fields)
            events.extend(post_events)
            repo = EventRepository(s)
            rows = [
                repo.append(run_id, etype, payload, stage=estage)
                for etype, estage, payload in events
            ]
            envelopes = [envelope_from_row(r) for r in rows]
        return state, envelopes

    async def _apply(self, run_id: str, command: Command | None, **kwargs: Any) -> FsmState:
        state, envelopes = await asyncio.to_thread(self._apply_sync, run_id, command, **kwargs)
        for env in envelopes:
            self.bus.publish(env)
        return state

    async def _emit(self, run_id: str, events: Sequence[EventSpec]) -> None:
        await self._apply(run_id, None, post_events=events)

    def _load_sync(self, run_id: str) -> dict[str, Any]:
        with self.db.session() as s:
            run = RunRepository(s).get(run_id)
            return {
                "status": run.status,
                "speed_factor": run.speed_factor,
                "halt_on_critical": run.halt_on_critical,
                "process_input": process_input_of(run),
                "stage_results": [
                    stage_row_to_json(r) for r in StageResultRepository(s).for_run(run_id)
                ],
            }

    def _presentation_s(self, speed_factor: str) -> float:
        return self.stage_presentation_ms * SPEED_MULTIPLIER.get(speed_factor, 1.0) / 1000.0

    # ----------------------------------------------------------------- stage execution

    async def _step_locked(self, run_id: str) -> str:
        """Execute exactly one stage (or the quality stage). Caller holds the run lock."""
        executor = self._require_executor()
        ctx = await asyncio.to_thread(self._load_sync, run_id)
        status: str = ctx["status"]
        delay = self._presentation_s(ctx["speed_factor"])
        process_input = ctx["process_input"]

        if status in STAGE_NAMES:
            stage = status
            flat = flat_input(process_input)
            inputs = {k: flat.get(k) for k in executor.stage_inputs(stage)}
            previous = ctx["stage_results"]
            upstream = dict(previous[-1].get("upstream_out") or {}) if previous else {}
            index = STAGE_NAMES.index(stage) + 1
            await self._emit(
                run_id,
                [
                    (
                        "stage.started",
                        stage,
                        {"index": index, "inputs_in_scope": inputs, "upstream_in": upstream},
                    )
                ],
            )
            # Keyed on the full input, not the display slice: a stage may read fields that
            # Role 1's stage_inputs() attributes to an earlier stage (e.g. S2 reads moisture).
            key = stage_cache_key(
                stage,
                flat,
                upstream,
                executor.module_version(stage),
                executor.constraints_version,
            )
            result = self.cache.get(key)
            cache_hit = result is not None
            if result is None:
                t0 = time.perf_counter()
                result = await asyncio.to_thread(executor.run_stage, stage, process_input, upstream)
                result.setdefault("compute_ms", round((time.perf_counter() - t0) * 1000, 3))
                self.cache.put(key, result)
            if delay:
                await asyncio.sleep(delay)

            pre: list[EventSpec] = []
            anomaly = result.get("anomaly") or {}
            if anomaly.get("flag"):
                pre.append(("anomaly.flagged", stage, {**anomaly, "scope": f"stage:{stage}"}))
            for breach in result.get("constraint_breaches") or []:
                pre.append(("constraint.breached", stage, breach))

            if result.get("blocked") and ctx["halt_on_critical"]:
                critical = [
                    b
                    for b in result.get("constraint_breaches") or []
                    if b.get("severity") == "CRITICAL"
                ]
                state = await self._apply(
                    run_id,
                    Command.BLOCK,
                    stage=stage,
                    pre_events=pre,
                    payloads={
                        "stage.blocked": {
                            "reason": result.get("block_reason") or "critical constraint breach",
                            "breaches": critical,
                            "result": result,
                        }
                    },
                )
                return state.status

            presentation_ms = delay * 1000
            completed = {**result, "presentation_ms": presentation_ms, "cache_hit": cache_hit}

            def write(s: Session, run: ProcessRun) -> None:
                StageResultRepository(s).add(
                    run,
                    **stage_row_values(result, presentation_ms=presentation_ms, overridden=False),
                )

            state = await self._apply(
                run_id,
                Command.STAGE_DONE,
                pre_events=[*pre, ("stage.completed", stage, completed)],
                extra_write=write,
            )
            return state.status

        if status == QUALITY:
            await self._emit(run_id, [("stage.started", QUALITY, {"index": 6})])
            t0 = time.perf_counter()
            prediction = await asyncio.to_thread(
                executor.predict, process_input, ctx["stage_results"]
            )
            compute_ms = round((time.perf_counter() - t0) * 1000, 3)
            if delay:
                await asyncio.sleep(delay)
            split_model_version(str(prediction["model_version"]))  # reject before any write

            def write_prediction(s: Session, run: ProcessRun) -> None:
                persist_prediction(s, run, prediction, compute_ms=compute_ms)

            state = await self._apply(
                run_id,
                Command.PREDICTED,
                extra_write=write_prediction,
                payloads={
                    "prediction.ready": prediction,
                    "run.completed": {"status": "FINAL_RESULT"},
                },
            )
            return state.status

        raise InvalidTransitionError(status, Command.STAGE_DONE, "the run is not executing a stage")

    async def _fail(self, run_id: str, exc: Exception) -> None:
        log.exception("simulation_step_failed", run_id=run_id, exc_type=type(exc).__name__)
        payload = {"code": "INTERNAL_ERROR", "message": f"{type(exc).__name__}: {exc}"[:500]}
        try:
            await self._apply(
                run_id,
                Command.ERROR,
                payloads={"run.error": payload, "run.aborted": {"reason": "ERROR:INTERNAL_ERROR"}},
                run_updates={"abort_reason": "ERROR:INTERNAL_ERROR"},
            )
        except Exception:  # the run may already be terminal
            log.exception("simulation_fail_record_failed", run_id=run_id)

    async def _run_loop(self, run_id: str) -> None:
        handle = self._handle(run_id)
        try:
            while True:
                await handle.resume.wait()
                async with handle.lock:
                    status = await asyncio.to_thread(self._load_status, run_id)
                    if status not in EXECUTING:
                        return
                    try:
                        await self._step_locked(run_id)
                    except asyncio.CancelledError:
                        raise
                    except Exception as exc:
                        await self._fail(run_id, exc)
                        return
        finally:
            if handle.task is asyncio.current_task():
                handle.task = None

    def _load_status(self, run_id: str) -> str:
        with self.db.session() as s:
            status: str = RunRepository(s).get(run_id).status
            return status

    def _spawn(self, run_id: str) -> None:
        handle = self._handle(run_id)
        handle.resume.set()
        if handle.task is None or handle.task.done():
            handle.task = asyncio.create_task(self._run_loop(run_id), name=f"run-{run_id}")

    async def _stop_task(self, handle: _Handle) -> None:
        """Cancel the run task. Caller holds the run lock, so no step is mid-flight."""
        task, handle.task = handle.task, None
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    # ----------------------------------------------------------------- commands

    async def start(
        self, run_id: str, *, mode: str = "auto", speed_factor: str | None = None
    ) -> None:
        self._require_executor()
        if speed_factor is not None and speed_factor not in SPEED_MULTIPLIER:
            raise ValueError(f"unknown speed factor {speed_factor!r}")
        handle = self._handle(run_id)
        async with handle.lock:
            updates: dict[str, Any] = {"started_at": utcnow()}
            if speed_factor is not None:
                updates["speed_factor"] = speed_factor
            if self.executor is not None:
                updates["inference_backend"] = self.executor.inference_backend
                updates["constraints_version"] = self.executor.constraints_version
            state = await self._apply(
                run_id,
                Command.START,
                mode=mode,
                payloads={"run.started": {"mode": mode, "speed_factor": speed_factor}},
                run_updates=updates,
            )
        if state.mode == "auto":
            self._spawn(run_id)

    async def advance(self, run_id: str) -> str:
        """Stepwise: execute exactly one stage (roadmap §9.5.2)."""
        self._require_executor()
        handle = self._handle(run_id)
        async with handle.lock:
            run_state = await asyncio.to_thread(self._load_fsm, run_id)
            if run_state.mode != "stepwise":
                raise InvalidTransitionError(
                    run_state.status, Command.STAGE_DONE, "advance is only for stepwise runs"
                )
            if run_state.status not in EXECUTING:
                raise InvalidTransitionError(
                    run_state.status, Command.STAGE_DONE, "nothing to advance"
                )
            try:
                return await self._step_locked(run_id)
            except InvalidTransitionError:
                raise
            except Exception as exc:
                await self._fail(run_id, exc)
                return "ABORTED"

    def _load_fsm(self, run_id: str) -> FsmState:
        with self.db.session() as s:
            return self._fsm(RunRepository(s).get(run_id))

    async def pause(self, run_id: str) -> None:
        handle = self._handle(run_id)
        handle.resume.clear()
        try:
            async with handle.lock:
                await self._apply(run_id, Command.PAUSE)
        except Exception:
            handle.resume.set()
            raise

    async def resume(self, run_id: str) -> None:
        self._require_executor()
        handle = self._handle(run_id)
        async with handle.lock:
            await self._apply(run_id, Command.RESUME)
        self._spawn(run_id)

    async def override(self, run_id: str, *, stage: str, acknowledgement: str) -> None:
        self._require_executor()
        handle = self._handle(run_id)
        async with handle.lock:
            pending = await asyncio.to_thread(self._pending_blocked_result, run_id, stage)

            def write(s: Session, run: ProcessRun) -> None:
                StageResultRepository(s).add(
                    run, **stage_row_values(pending, presentation_ms=0.0, overridden=True)
                )
                run.override_count = run.override_count + 1

            state = await self._apply(
                run_id,
                Command.OVERRIDE,
                stage=stage,
                extra_write=write,
                payloads={
                    "stage.override_acknowledged": {
                        "acknowledgement": acknowledgement,
                        "breaches": [
                            b
                            for b in pending.get("constraint_breaches") or []
                            if b.get("severity") == "CRITICAL"
                        ],
                    }
                },
                post_events=[
                    (
                        "stage.completed",
                        stage,
                        {**pending, "overridden": True, "presentation_ms": 0.0, "cache_hit": False},
                    )
                ],
            )
        if state.mode == "auto":
            self._spawn(run_id)

    def _pending_blocked_result(self, run_id: str, stage: str) -> dict[str, Any]:
        with self.db.session() as s:
            row = s.scalar(
                select(SimulationEvent)
                .where(
                    SimulationEvent.run_id == run_id,
                    SimulationEvent.event_type == "stage.blocked",
                    SimulationEvent.stage == stage,
                )
                .order_by(SimulationEvent.seq.desc())
                .limit(1)
            )
            if row is None or "result" not in row.payload:
                raise InvalidTransitionError(
                    "BLOCKED", Command.OVERRIDE, f"no blocked result recorded for {stage}"
                )
            result: dict[str, Any] = dict(row.payload["result"])
            return result

    async def reset(self, run_id: str) -> None:
        handle = self._handle(run_id)
        async with handle.lock:
            await self._stop_task(handle)
            handle.resume.clear()
            await self._apply(
                run_id,
                Command.RESET,
                extra_write=lambda s, run: reset_run_results(s, run),
                run_updates={"started_at": None, "override_count": 0},
            )

    async def abort(self, run_id: str, *, reason: str | None = None) -> None:
        handle = self._handle(run_id)
        async with handle.lock:
            await self._stop_task(handle)
            handle.resume.clear()
            await self._apply(
                run_id,
                Command.ABORT,
                payloads={"run.aborted": {"reason": reason or "USER_ABORT"}},
                run_updates={"abort_reason": reason or "USER_ABORT"},
            )

    # ----------------------------------------------------------------- queries

    def state(self, run_id: str) -> dict[str, Any]:
        """SimulationState JSON (roadmap §7.17), also the polling/resync payload."""
        with self.db.session() as s:
            run = RunRepository(s).get(run_id)
            prediction = PredictionRepository(s).for_run(run_id)
            events = EventRepository(s).after(run_id, 0)
            return {
                "run_id": run.id,
                "status": run.status,
                "mode": run.mode,
                "speed_factor": run.speed_factor,
                "halt_on_critical": run.halt_on_critical,
                "blocked_stage": run.blocked_stage,
                "current_stage": run.current_stage,
                "override_count": run.override_count,
                "abort_reason": run.abort_reason,
                "created_at": run.created_at,
                "updated_at": run.updated_at,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
                "context": run.context_snapshot,
                "parameters": run.parameters.as_dict(),
                "stage_results": [
                    stage_row_to_json(r) for r in StageResultRepository(s).for_run(run_id)
                ],
                "prediction": (
                    prediction_row_to_json(prediction) if prediction is not None else None
                ),
                "timeline": [envelope_from_row(e) for e in events],
                "parent_run_id": run.parent_run_id,
                "is_whatif": run.is_whatif,
                "scenario_label": run.scenario_label,
                "inference_backend": run.inference_backend,
                "constraints_version": run.constraints_version,
                "last_seq": run.last_seq,
            }

    def ensure_run(self, run_id: str) -> None:
        """Raise NotFoundError if the run does not exist."""
        with self.db.session() as s:
            RunRepository(s).get(run_id)

    def stage(self, run_id: str, stage_name: str) -> dict[str, Any]:
        with self.db.session() as s:
            RunRepository(s).get(run_id)
            return stage_row_to_json(StageResultRepository(s).get(run_id, stage_name))

    @staticmethod
    def _summary(run: ProcessRun, prediction: Any) -> dict[str, Any]:
        mv = prediction.model_version if prediction is not None else None
        return {
            "run_id": run.id,
            "parent_run_id": run.parent_run_id,
            "is_whatif": run.is_whatif,
            "scenario_label": run.scenario_label,
            "status": run.status,
            "created_at": run.created_at,
            "machine_id": run.machine.code,
            "product_id": run.product.code,
            "material_lot_id": run.material_lot.lot_code,
            "label": prediction.label if prediction is not None else None,
            "p_fail": prediction.p_fail if prediction is not None else None,
            "risk_level": prediction.risk_level if prediction is not None else None,
            "model_version": f"{mv.name}-{mv.semver}" if mv is not None else None,
            "inference_backend": run.inference_backend,
        }

    def create_run(
        self,
        *,
        machine_id: str,
        product_id: str,
        material_lot_id: str,
        parameters: Mapping[str, float],
        validate_parameters: ParameterValidator,
        mode: str = "auto",
        speed_factor: str = "1x",
        halt_on_critical: bool = True,
        scenario_label: str | None = None,
        today: date | None = None,
    ) -> str:
        """Create an INITIALIZED run with a frozen context snapshot (roadmap R2-P4 task 5).

        ``validate_parameters(recipe, context_snapshot)`` is the registry check (tiers 1-2) supplied
        by the API layer; it runs after the references resolve so machine-dependent couplings
        (CPL-003/CPL-004) see this machine's limits. Raises ``NotFoundError`` for an unknown or
        inactive machine/product/lot.
        """
        executor = self._require_executor()
        with self.db.session() as s:
            refs = ReferenceRepository(s)
            machine, product = refs.machine(machine_id), refs.product(product_id)
            lot = refs.material(material_lot_id)
            if not machine.active:
                raise NotFoundError("machine", machine_id)
            if not product.active:
                raise NotFoundError("product", product_id)
            day = today or utcnow().date()
            snapshot = context_snapshot(machine, product, lot, today=day)
            recipe = validate_parameters(parameters, snapshot)
            run = RunRepository(s).create(
                machine=machine,
                product=product,
                material_lot=lot,
                parameters=recipe,
                mode=mode,
                speed_factor=speed_factor,
                halt_on_critical=halt_on_critical,
                scenario_label=scenario_label,
                inference_backend=executor.inference_backend,
                constraints_version=executor.constraints_version,
                today=day,
            )
            log.info("run_created", run_id=run.id, machine_id=machine_id, mode=mode)
            return run.id

    def list_runs(
        self, filters: RunFilters | None = None, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[dict[str, Any]], int]:
        with self.db.session() as s:
            rows, total = RunRepository(s).search(filters, limit=limit, offset=offset)
            predictions = PredictionRepository(s)
            return [self._summary(r, predictions.for_run(r.id)) for r in rows], total

    def lineage(self, run_id: str) -> dict[str, Any]:
        """``{run: ScenarioSummary, children: [...]}`` rooted at ``run_id`` (what-if tree)."""
        with self.db.session() as s:
            predictions = PredictionRepository(s)

            def node(n: LineageNode) -> dict[str, Any]:
                return {
                    "run": self._summary(n.run, predictions.for_run(n.run.id)),
                    "children": [node(c) for c in n.children],
                }

            return node(RunRepository(s).lineage(run_id))

    def set_label(self, run_id: str, label: str | None) -> dict[str, Any]:
        """Save scenario: the only mutation allowed on a finished run (roadmap §9.4)."""
        with self.db.session() as s:
            runs = RunRepository(s)
            run = runs.set_label(runs.get(run_id), label)
            return self._summary(run, PredictionRepository(s).for_run(run_id))

    # ----------------------------------------------------------------- lifecycle

    def recover_interrupted(self) -> list[str]:
        """Startup recovery (roadmap §9.5.1): unfinished started runs become ABORTED."""
        with self.db.session() as s:
            ids = RunRepository(s).abort_interrupted("SERVER_RESTART")
            events = EventRepository(s)
            for run_id in ids:
                events.append(run_id, "run.aborted", {"reason": "SERVER_RESTART"})
        return ids

    async def shutdown(self) -> None:
        for handle in list(self._handles.values()):
            task, handle.task = handle.task, None
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
