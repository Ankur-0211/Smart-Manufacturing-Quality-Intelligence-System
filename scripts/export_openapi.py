"""Write the FastAPI OpenAPI document to docs/openapi.json (Role 2, roadmap 9.3.1).

The frontend generates its TypeScript types from this committed snapshot:
    uv run python scripts/export_openapi.py
    cd frontend && npm run gen:api
`backend/tests/api/test_openapi_snapshot.py` fails when the snapshot is stale.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = REPO_ROOT / "docs" / "openapi.json"


def render_openapi() -> str:
    sys.path.insert(0, str(REPO_ROOT / "backend"))
    from app.core.config import Settings
    from app.main import create_app

    app = create_app(Settings(_env_file=None))  # type: ignore[call-arg]
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    SNAPSHOT.write_text(render_openapi(), encoding="utf-8", newline="\n")
    print(f"wrote {SNAPSHOT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
