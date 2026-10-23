"""API server for the Playwright E2E suite (roadmap R2-P10 §9).

Starts from a fresh SQLite database every time (migrated and seeded from fleet.yaml), with
``SMQI_ENV=test`` and Role 1's **real** intelligence, and serves the built SPA from
``frontend/dist``. The E2E run is therefore deterministic and never touches ``var/smqi.db``.

Usage (Playwright's ``webServer`` runs this after ``npm run build``):
    uv run python scripts/e2e_server.py [--port 8001]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    work = Path(tempfile.gettempdir()) / "smqi-e2e"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    url = f"sqlite:///{(work / 'e2e.db').as_posix()}"
    os.environ.update(
        {
            "SMQI_ENV": "test",
            "SMQI_INTELLIGENCE_BACKEND": "real",
            "SMQI_DATABASE_URL": url,
            "SMQI_FRONTEND_DIST": str(ROOT / "frontend" / "dist"),
            "SMQI_LOG_FORMAT": "console",
            "SMQI_LOG_LEVEL": "WARNING",
            # The journey makes a handful of sensitivity/recommend calls in quick succession.
            "SMQI_RATE_LIMIT_PER_MIN": "1000",
        }
    )

    import uvicorn

    from app.core.config import get_settings
    from app.db.seed import load_fleet, seed
    from app.db.session import Database
    from tests.db.conftest import migrate  # test helper: one migration code path

    migrate(url)
    settings = get_settings()
    database = Database(url)
    with database.session() as s:
        seed(s, load_fleet(settings.fleet_path))
    database.dispose()

    from app.main import create_app

    uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
