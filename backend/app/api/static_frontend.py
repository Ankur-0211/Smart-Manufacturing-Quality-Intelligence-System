"""Serve the production frontend build from the API process (UD-16, roadmap R2-P9 task 4).

One process, one origin: the SPA is at ``/`` and the API at ``/api/v1``, so the demo needs no CORS.
Client-side routes (``/history/<id>``, ``/analytics`` ...) fall back to ``index.html``. Paths under
``/api`` never fall back: an unknown API route keeps its ``ROUTE_NOT_FOUND`` envelope.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def frontend_available(dist: Path) -> bool:
    return (dist / "index.html").is_file()


def mount_frontend(app: FastAPI, dist: Path) -> None:
    """Register the catch-all after every API router. Call only when ``frontend_available``."""
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404)
        candidate = (root / path).resolve()
        # Never serve outside the build directory (path traversal), and never a directory.
        if path and candidate.is_relative_to(root) and candidate.is_file():
            return FileResponse(candidate)
        # index.html must be revalidated so a new build is picked up; hashed assets are cached.
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
