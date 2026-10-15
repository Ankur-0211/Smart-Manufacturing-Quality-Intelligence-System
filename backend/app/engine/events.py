"""Simulation events: envelope, persist-then-publish bus, SSE framing (roadmap §9.5.3-9.5.4).

Every event is written to ``simulation_events`` (allocating ``seq``) and committed BEFORE it is
published to live subscribers, so a client can always recover with ``Last-Event-ID`` replay.
"""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import Mapping
from datetime import UTC
from typing import Any, Final

from app.db.models import SimulationEvent

EVENTS_VERSION: Final = "1"

EVENT_TYPES: Final = (
    "run.started",
    "stage.started",
    "stage.progress",
    "stage.completed",
    "anomaly.flagged",
    "constraint.breached",
    "stage.blocked",
    "stage.override_acknowledged",
    "prediction.ready",
    "run.completed",
    "run.paused",
    "run.resumed",
    "run.reset",
    "run.aborted",
    "run.error",
)
#: After one of these the server closes the SSE stream (roadmap §9.5.4).
TERMINAL_EVENTS: Final = frozenset({"run.completed", "run.aborted"})


def iso_z(dt: Any) -> str:
    """ISO-8601 UTC with a Z suffix (roadmap §7.1). SQLite returns naive datetimes in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return str(dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"))


def envelope_from_row(row: SimulationEvent) -> dict[str, Any]:
    return {
        "run_id": row.run_id,
        "seq": row.seq,
        "ts": iso_z(row.created_at),
        "type": row.event_type,
        "stage": row.stage,
        "payload": row.payload,
    }


def format_sse(envelope: Mapping[str, Any]) -> str:
    """One SSE frame: ``id``, ``event``, single-line JSON ``data``, blank line."""
    data = json.dumps(envelope, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return f"id: {envelope['seq']}\nevent: {envelope['type']}\ndata: {data}\n\n"


KEEPALIVE_FRAME: Final = ": keepalive\n\n"


class EventBus:
    """Per-run fan-out of committed events to live SSE subscribers (single event loop)."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, run_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[run_id].add(queue)
        return queue

    def unsubscribe(self, run_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        subs = self._subscribers.get(run_id)
        if subs is not None:
            subs.discard(queue)
            if not subs:
                del self._subscribers[run_id]

    def publish(self, envelope: Mapping[str, Any]) -> None:
        for queue in list(self._subscribers.get(str(envelope["run_id"]), ())):
            queue.put_nowait(dict(envelope))

    def subscriber_count(self, run_id: str) -> int:
        return len(self._subscribers.get(run_id, ()))
