"""Seed the demo history through the public API (roadmap 16.2).

Runs real simulations via HTTP with the deterministic contract-fixture recipes; it never writes
runs or predictions into the database directly. Idempotent: a scenario whose label already exists
is skipped.

Usage (API running in the demo profile, database migrated and seeded):
    uv run python scripts/seed_demo_runs.py [--base-url http://localhost:8000] [--api-key KEY]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).resolve().parents[1] / "backend" / "tests" / "contract" / "fixtures"
API = "/api/v1"
TERMINAL_OR_WAITING = {"FINAL_RESULT", "ABORTED", "BLOCKED"}


@dataclass(frozen=True)
class DemoScenario:
    label: str
    fixture: str
    note: str
    # Setpoints changed from the fixture recipe; the fixtures themselves belong to Role 1.
    overrides: dict[str, float] = field(default_factory=dict)


SCENARIOS = (
    DemoScenario("demo: nominal recipe", "recipe_nominal.json", "nominal PASS"),
    DemoScenario("demo: short cooling", "recipe_short_cooling.json", "HC-004 warning"),
    DemoScenario(
        "demo: high injection pressure",
        "recipe_nominal.json",
        "FAIL with an Injection anomaly; a what-if at 1100 bar flips it (demo segments 2-6)",
        overrides={"inj_pressure_bar": 1800.0},
    ),
    DemoScenario(
        "demo: melt above ceiling",
        "recipe_melt_ceiling_breach.json",
        "left BLOCKED at HC-001 for the live override",
    ),
)


class SeedError(RuntimeError):
    pass


def _data(resp: httpx.Response) -> Any:
    body = resp.json()
    if resp.status_code >= 400 or body.get("error"):
        error = body.get("error") or {}
        where = f"{resp.request.method} {resp.request.url.path}"
        raise SeedError(f"{where}: {error.get('code')} {error.get('message')}")
    return body["data"]


def _existing_labels(client: httpx.Client) -> set[str]:
    rows = _data(client.get(f"{API}/simulation/runs", params={"limit": 200}))
    return {r["scenario_label"] for r in rows if r.get("scenario_label")}


def run_scenario(client: httpx.Client, scenario: DemoScenario) -> dict[str, Any]:
    fixture = json.loads((FIXTURES / scenario.fixture).read_text(encoding="utf-8"))
    ctx = fixture["context"]
    body = {
        "machine_id": ctx["machine"]["machine_id"],
        "product_id": ctx["product"]["product_id"],
        "material_lot_id": ctx["material_lot"]["material_lot_id"],
        "parameters": {**fixture["recipe"], **scenario.overrides},
        "mode": "stepwise",
        "speed_factor": "instant",
        "scenario_label": scenario.label,
    }
    run_id = _data(client.post(f"{API}/simulation/runs", json=body))["run_id"]
    state = _data(client.post(f"{API}/simulation/runs/{run_id}/start", json={"mode": "stepwise"}))
    for _ in range(6):  # five stages + quality inspection
        if state["status"] in TERMINAL_OR_WAITING:
            break
        state = _data(client.post(f"{API}/simulation/runs/{run_id}/advance"))
    prediction = state.get("prediction") or {}
    return {
        "label": scenario.label,
        "run_id": run_id,
        "status": state["status"],
        "blocked_stage": state.get("blocked_stage"),
        "result": prediction.get("label"),
        "p_fail": prediction.get("p_fail"),
        "note": scenario.note,
    }


def seed_demo_runs(client: httpx.Client) -> list[dict[str, Any]]:
    """Create every missing demo scenario; returns one summary per created run."""
    health = _data(client.get(f"{API}/health"))
    if health["intelligence"]["is_mock"]:
        raise SeedError("refusing to seed demo history from MOCK intelligence (roadmap 9.2)")
    existing = _existing_labels(client)
    return [run_scenario(client, s) for s in SCENARIOS if s.label not in existing]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--api-key", default=os.environ.get("SMQI_API_KEY"))
    args = parser.parse_args(argv)
    headers = {"X-API-Key": args.api_key} if args.api_key else {}
    try:
        with httpx.Client(base_url=args.base_url, headers=headers, timeout=30) as client:
            created = seed_demo_runs(client)
    except (SeedError, httpx.HTTPError) as exc:
        print(f"seed_demo_runs: {exc}", file=sys.stderr)
        return 1
    for row in created:
        print(json.dumps(row))
    print(f"seed_demo_runs: {len(created)} run(s) created", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
