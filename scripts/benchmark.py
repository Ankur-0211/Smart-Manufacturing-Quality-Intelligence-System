"""Performance pass against the Plan §24.4 budgets (roadmap R2-P9 task 5).

Self-contained: builds the app on a temporary migrated and seeded SQLite database with Role 1's
real intelligence, then times

- the intelligence layer directly (``run_stage``, ``evaluate``, ``explain``), and
- the same work end to end through the HTTP API (validation, persistence, envelope included).

Prints a Markdown table with p50/p95/max per operation and the budget verdict. Numbers are for
the machine it runs on; record them with the date and machine in docs/integration_status.md.

Usage:
    uv run python scripts/benchmark.py [--n 60]
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from app.contracts.context import ProcessInput  # noqa: E402
from app.contracts.enums import INTELLIGENCE_STAGES  # noqa: E402
from app.contracts.stage import UpstreamContext  # noqa: E402
from app.core.config import Settings  # noqa: E402
from app.db.seed import load_fleet, seed  # noqa: E402
from app.main import create_app  # noqa: E402

FIXTURES = ROOT / "backend" / "tests" / "contract" / "fixtures"
API = "/api/v1"


@dataclass(frozen=True)
class Budget:
    label: str
    ms: float
    stat: str  # which statistic the budget applies to: "p95" or "max"


@dataclass
class Row:
    operation: str
    samples: list[float]
    budget: Budget | None

    def line(self) -> str:
        s = sorted(self.samples)
        p50 = statistics.median(s)
        p95 = s[min(len(s) - 1, round(0.95 * (len(s) - 1)))]
        worst = s[-1]
        verdict = "—"
        if self.budget:
            value = p95 if self.budget.stat == "p95" else worst
            verdict = ("✓ " if value <= self.budget.ms else "✗ ") + self.budget.label
        return f"| {self.operation} | {len(s)} | {p50:.1f} | {p95:.1f} | {worst:.1f} | {verdict} |"


def timed(fn: Callable[[], Any], n: int, warmup: int = 2) -> list[float]:
    for _ in range(warmup):
        fn()
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000)
    return out


def ok(response: Any) -> Any:
    assert response.status_code < 400, response.text
    return response.json()["data"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n", type=int, default=60, help="samples for the fast operations")
    args = parser.parse_args()
    # Windows consoles default to cp1252, which cannot print the table's symbols.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    n = args.n

    tmp = Path(tempfile.mkdtemp(prefix="smqi-bench-"))
    url = f"sqlite:///{(tmp / 'bench.db').as_posix()}"
    from tests.db.conftest import migrate  # test helper: one migration code path

    migrate(url)
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        database_url=url,
        intelligence_backend="real",
        log_level="WARNING",
        rate_limit_per_min=10_000,  # measure the work, not the limiter
        frontend_dist=str(tmp / "no-frontend"),
    )
    app = create_app(settings)
    with app.state.db.session() as s:
        seed(s, load_fleet(settings.fleet_path))
    app.state.simulation.stage_presentation_ms = 0

    fixture = json.loads((FIXTURES / "recipe_nominal.json").read_text("utf-8"))
    inp = ProcessInput.model_validate(fixture)
    intelligence = app.state.intelligence
    ctx = fixture["context"]
    body = {
        "machine_id": ctx["machine"]["machine_id"],
        "product_id": ctx["product"]["product_id"],
        "material_lot_id": ctx["material_lot"]["material_lot_id"],
        "parameters": fixture["recipe"],
    }

    rows: list[Row] = []

    def run_stage() -> None:
        upstream = UpstreamContext()
        for stage in INTELLIGENCE_STAGES:
            upstream = intelligence.run_stage(stage, inp, upstream).upstream_out

    per_stage = [t / len(INTELLIGENCE_STAGES) for t in timed(run_stage, n)]
    rows.append(
        Row(
            "intelligence `run_stage` (mean of 5 stages)", per_stage, Budget("p95 < 5 ms", 5, "p95")
        )
    )
    rows.append(
        Row(
            "intelligence `evaluate` (no explanation)",
            timed(lambda: intelligence.evaluate(inp, include_explanation=False), n),
            Budget("p95 < 150 ms", 150, "p95"),
        )
    )
    pipeline = intelligence.evaluate(inp, include_explanation=False)
    rows.append(
        Row(
            "intelligence `explain`",
            timed(
                lambda: intelligence.explain(inp, pipeline.stage_results, pipeline.prediction), n
            ),
            Budget("p95 < 300 ms", 300, "p95"),
        )
    )

    with TestClient(app) as client:
        rows.append(
            Row(
                "API `POST /predict` (no explanation)",
                timed(
                    lambda: ok(
                        client.post(f"{API}/predict", json={**body, "include_explanation": False})
                    ),
                    n,
                ),
                Budget("p95 < 150 ms", 150, "p95"),
            )
        )
        prediction_id = ok(client.post(f"{API}/predict", json=body))["prediction_id"]
        rows.append(
            Row(
                "API `GET /predict/{id}/explain`",
                timed(lambda: ok(client.get(f"{API}/predict/{prediction_id}/explain")), n),
                Budget("p95 < 300 ms", 300, "p95"),
            )
        )

        def instant_run() -> str:
            run_id: str = ok(
                client.post(
                    f"{API}/simulation/runs",
                    json={**body, "mode": "auto", "speed_factor": "instant"},
                )
            )["run_id"]
            ok(client.post(f"{API}/simulation/runs/{run_id}/start", json={"mode": "stepwise"}))
            for _ in range(6):
                state = ok(client.post(f"{API}/simulation/runs/{run_id}/advance"))
                if state["status"] == "FINAL_RESULT":
                    return run_id
            raise AssertionError(state["status"])

        rows.append(
            Row(
                "API full run, 6 stepwise calls (create → FINAL_RESULT)",
                timed(instant_run, max(10, n // 3)),
                Budget("p95 < 300 ms compute", 300, "p95"),
            )
        )
        base = instant_run()
        rows.append(
            Row(
                "API `POST /whatif` (persist=false)",
                timed(
                    lambda: ok(
                        client.post(
                            f"{API}/whatif",
                            json={
                                "base_run_id": base,
                                "overrides": {"cooling_time_s": 14},
                                "persist": False,
                            },
                        )
                    ),
                    n,
                ),
                None,
            )
        )
        rows.append(
            Row(
                "API `POST /whatif/sensitivity` (40 points)",
                timed(
                    lambda: ok(
                        client.post(
                            f"{API}/whatif/sensitivity",
                            json={"base_run_id": base, "parameter": "melt_temp_c", "steps": 40},
                        )
                    ),
                    max(5, n // 6),
                ),
                Budget("< 1.5 s", 1500, "max"),
            )
        )
        rows.append(
            Row(
                "API `POST /recommend`",
                timed(
                    lambda: ok(client.post(f"{API}/recommend", json={"run_id": base})),
                    max(5, n // 6),
                ),
                Budget("< 5 s", 5000, "max"),
            )
        )
        rows.append(
            Row(
                "API `GET /analytics/summary`",
                timed(lambda: ok(client.get(f"{API}/analytics/summary")), n),
                None,
            )
        )

    print(f"Python {sys.version.split()[0]} · {os.cpu_count()} CPUs · n={n} · times in ms\n")
    print("| Operation | n | p50 | p95 | max | Budget (Plan §24.4) |")
    print("|---|---|---|---|---|---|")
    for row in rows:
        print(row.line())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
