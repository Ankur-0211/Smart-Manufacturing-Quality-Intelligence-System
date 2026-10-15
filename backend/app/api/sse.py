"""SSE stream for one run (roadmap §9.5.4).

Order of operations prevents loss: subscribe to the live bus FIRST, then replay persisted events
with ``seq > Last-Event-ID``, then stream live events, skipping anything already sent. If a live
event arrives with a gap, the missing events are read from the DB before it is sent. The stream
ends after ``run.completed`` / ``run.aborted`` (or immediately after replay if the run is already
finished), sends ``: keepalive`` comments while idle, and stops when the client disconnects.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request

from app.db.repositories import EventRepository, RunRepository
from app.db.session import Database
from app.db.vocab import TERMINAL_STATUSES
from app.engine.events import (
    KEEPALIVE_FRAME,
    TERMINAL_EVENTS,
    EventBus,
    envelope_from_row,
    format_sse,
)

SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # disable proxy buffering (roadmap R2-P4 risk note)
}


def parse_last_event_id(value: str | None) -> int:
    try:
        return max(0, int(value)) if value is not None else 0
    except ValueError:
        return 0


def _events_after(db: Database, run_id: str, after_seq: int) -> tuple[list[dict[str, Any]], bool]:
    with db.session() as s:
        terminal = RunRepository(s).get(run_id).status in TERMINAL_STATUSES
        events = [envelope_from_row(e) for e in EventRepository(s).after(run_id, after_seq)]
    return events, terminal


async def run_event_stream(
    request: Request,
    *,
    db: Database,
    bus: EventBus,
    run_id: str,
    last_event_id: int,
    keepalive_s: float = 15.0,
) -> AsyncIterator[str]:
    queue = bus.subscribe(run_id)
    try:
        sent = last_event_id
        replay, terminal = await asyncio.to_thread(_events_after, db, run_id, sent)
        for env in replay:
            yield format_sse(env)
            sent = env["seq"]
            if env["type"] in TERMINAL_EVENTS:
                return
        if terminal:
            return
        while True:
            if await request.is_disconnected():
                return
            try:
                env = await asyncio.wait_for(queue.get(), timeout=keepalive_s)
            except TimeoutError:
                yield KEEPALIVE_FRAME
                continue
            if env["seq"] <= sent:
                continue
            batch = [env]
            if env["seq"] > sent + 1:
                missing, _ = await asyncio.to_thread(_events_after, db, run_id, sent)
                batch = [e for e in missing if e["seq"] <= env["seq"]] or [env]
            for item in batch:
                yield format_sse(item)
                sent = item["seq"]
                if item["type"] in TERMINAL_EVENTS:
                    return
    finally:
        with contextlib.suppress(Exception):
            bus.unsubscribe(run_id, queue)
