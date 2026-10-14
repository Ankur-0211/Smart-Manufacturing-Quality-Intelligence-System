"""FastAPI dependencies.

The intelligence factory ``get_intelligence()`` (roadmap 9.1) is added here once
``app.contracts`` v0.1.0 from Role 1 is available (R2-P1 tasks 8-10).
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, Request

from app.api.errors import ApiError, ErrorCode
from app.core.config import Settings
from app.db.session import Database


def app_settings(request: Request) -> Settings:
    """The Settings instance the app was created with (see ``create_app``)."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(app_settings)]


def app_database(request: Request) -> Database:
    """The Database (engine + session factory) owned by this app instance."""
    database: Database = request.app.state.db
    return database


DatabaseDep = Annotated[Database, Depends(app_database)]


def require_api_key(
    settings: SettingsDep,
    x_api_key: Annotated[str | None, Header()] = None,
) -> None:
    """Optional static API key (Plan 16.6): enforced only when ``SMQI_API_KEY`` is set."""
    if settings.api_key is None:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, settings.api_key):
        raise ApiError(
            ErrorCode.UNAUTHORIZED,
            "Missing or invalid X-API-Key header",
            hint="Send the X-API-Key header configured for this deployment.",
        )
