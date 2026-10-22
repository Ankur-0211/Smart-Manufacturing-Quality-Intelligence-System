from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Environment, IntelligenceBackendMode, Settings
from app.main import create_app


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "env": Environment.TEST,
        "intelligence_backend": IntelligenceBackendMode.MOCK,
        "log_format": "console",
        "log_level": "WARNING",
        # Never touch var/smqi.db from tests; DB tests pass a migrated temp file instead.
        "database_url": "sqlite:///:memory:",
        # Never serve a developer's local frontend build from test apps.
        "frontend_dist": "/nonexistent-frontend-dist",
    }
    base.update(overrides)
    # _env_file=None: tests never read a developer's local .env
    return Settings(_env_file=None, **base)  # type: ignore[call-arg]


@pytest.fixture
def settings() -> Settings:
    return make_settings()


@pytest.fixture
def app_factory() -> Callable[..., FastAPI]:
    def _factory(**overrides: object) -> FastAPI:
        return create_app(make_settings(**overrides))

    return _factory


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    app = create_app(settings)
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
