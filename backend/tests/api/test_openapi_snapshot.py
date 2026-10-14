"""The committed OpenAPI snapshot must match the running app (frontend types depend on it)."""

from __future__ import annotations

from scripts.export_openapi import SNAPSHOT, render_openapi


def test_openapi_snapshot_is_current() -> None:
    assert SNAPSHOT.is_file(), "Run: uv run python scripts/export_openapi.py"
    assert SNAPSHOT.read_text(encoding="utf-8") == render_openapi(), (
        "docs/openapi.json is stale. Run `uv run python scripts/export_openapi.py` "
        "then `npm run gen:api` in frontend/."
    )
