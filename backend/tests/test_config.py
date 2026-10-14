from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import REPO_ROOT, Environment, IntelligenceBackendMode
from tests.conftest import make_settings


@pytest.mark.parametrize("backend", ["mock", "hybrid"])
def test_demo_profile_refuses_non_real_intelligence(backend: str) -> None:
    with pytest.raises(ValidationError, match="requires SMQI_INTELLIGENCE_BACKEND=real"):
        make_settings(env="demo", intelligence_backend=backend)


def test_demo_profile_accepts_real_intelligence() -> None:
    s = make_settings(env="demo", intelligence_backend="real")
    assert s.env is Environment.DEMO
    assert s.intelligence_backend is IntelligenceBackendMode.REAL


def test_cors_origins_parsed_from_comma_string(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMQI_CORS_ORIGINS", "http://a.test, http://b.test")
    s = make_settings()
    assert s.cors_origins == ["http://a.test", "http://b.test"]


def test_relative_paths_resolve_against_repo_root() -> None:
    s = make_settings(model_dir="models", constraints_path="backend/app/domain/constraints.yaml")
    assert s.model_dir == (REPO_ROOT / "models").resolve()
    assert s.constraints_path.is_absolute()


def test_blank_api_key_means_disabled() -> None:
    assert make_settings(api_key="  ").api_key is None


def test_presentation_timing_bounds_follow_plan() -> None:
    # Plan 7.4: 1200-2000 ms per stage.
    with pytest.raises(ValidationError):
        make_settings(stage_presentation_ms=500)
