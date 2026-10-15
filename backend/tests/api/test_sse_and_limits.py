"""SSE generator edge cases and the rate limiter, tested without a full HTTP stack."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.rate_limit import TokenBucketLimiter, rate_limited
from app.api.sse import parse_last_event_id, run_event_stream
from app.db.repositories import EventRepository
from app.db.session import Database
from app.engine.events import EventBus, envelope_from_row, format_sse
from app.main import include_protected
from tests.db.conftest import migrate
from tests.services.conftest import create_test_run


class _FakeRequest:
    def __init__(self, disconnect_after: int = 10_000) -> None:
        self.calls = 0
        self.limit = disconnect_after

    async def is_disconnected(self) -> bool:
        self.calls += 1
        return self.calls > self.limit


@pytest.fixture
def db(tmp_path: Path) -> Database:
    url = f"sqlite:///{(tmp_path / 'sse.db').as_posix()}"
    migrate(url)
    return Database(url)


def _append(db: Database, run_id: str, etype: str) -> dict[str, Any]:
    with db.session() as s:
        return envelope_from_row(EventRepository(s).append(run_id, etype, {}))


async def _collect(gen: Any, n: int, timeout: float = 2.0) -> list[str]:
    out: list[str] = []

    async def take() -> None:
        async for frame in gen:
            out.append(frame)
            if len(out) >= n:
                return

    await asyncio.wait_for(take(), timeout)
    return out


def test_parse_last_event_id() -> None:
    assert parse_last_event_id(None) == 0
    assert parse_last_event_id("7") == 7
    assert parse_last_event_id("-3") == 0
    assert parse_last_event_id("abc") == 0


def test_frame_format() -> None:
    frame = format_sse(
        {"run_id": "r", "seq": 3, "ts": "t", "type": "stage.started", "stage": None, "payload": {}}
    )
    assert frame.startswith("id: 3\nevent: stage.started\ndata: {") and frame.endswith("}\n\n")
    assert frame.count("\n") == 4  # data is a single line


async def test_keepalive_while_idle_and_disconnect_stops(db: Database) -> None:
    run_id = create_test_run(db)
    bus = EventBus()
    request: Any = _FakeRequest(disconnect_after=3)
    gen = run_event_stream(
        request, db=db, bus=bus, run_id=run_id, last_event_id=0, keepalive_s=0.01
    )
    frames = [f async for f in gen]
    assert frames and all(f == ": keepalive\n\n" for f in frames)
    assert bus.subscriber_count(run_id) == 0  # unsubscribed on exit


async def test_live_gap_is_filled_from_db(db: Database) -> None:
    run_id = create_test_run(db)
    bus = EventBus()
    request: Any = _FakeRequest()
    gen = run_event_stream(request, db=db, bus=bus, run_id=run_id, last_event_id=0, keepalive_s=1)
    first = asyncio.ensure_future(gen.__anext__())
    await asyncio.sleep(0.05)
    e1 = _append(db, run_id, "run.started")
    bus.publish(e1)
    assert "event: run.started" in await asyncio.wait_for(first, 2)
    _append(db, run_id, "stage.started")  # committed but never published
    e3 = _append(db, run_id, "stage.completed")
    bus.publish(e3)
    frames = await _collect(gen, 2)
    assert ["id: 2" in frames[0], "id: 3" in frames[1]] == [True, True]
    bus.publish(e3)  # duplicate after reconnect-style replay is skipped
    e4 = _append(db, run_id, "run.aborted")
    bus.publish(e4)
    rest = [f async for f in gen]
    assert len(rest) == 1 and "event: run.aborted" in rest[0]  # stream closes after terminal event


def test_token_bucket_refills() -> None:
    now = [0.0]
    limiter = TokenBucketLimiter(2, clock=lambda: now[0])
    assert limiter.allow("c", "recommend")[0]
    assert limiter.allow("c", "recommend")[0]
    allowed, retry = limiter.allow("c", "recommend")
    assert not allowed and retry == pytest.approx(30.0)
    assert limiter.allow("other", "recommend")[0]  # per client
    assert limiter.allow("c", "sensitivity")[0]  # per bucket
    now[0] = 30.0
    assert limiter.allow("c", "recommend")[0]


def test_rate_limited_dependency_returns_429(app_factory: Callable[..., FastAPI]) -> None:
    app = app_factory(rate_limit_per_min=2)
    router = APIRouter()

    @router.get("/_expensive", dependencies=[Depends(rate_limited("recommend"))])
    def expensive() -> dict[str, bool]:
        return {"ok": True}

    include_protected(app, router)
    with TestClient(app) as c:
        assert c.get("/api/v1/_expensive").status_code == 200
        assert c.get("/api/v1/_expensive").status_code == 200
        resp = c.get("/api/v1/_expensive")
    assert resp.status_code == 429 and resp.json()["error"]["code"] == "RATE_LIMITED"
