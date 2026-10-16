"""Module boundary rules (roadmap 3.2), checked statically via the AST.

Role 2 half (B1, B2, B7): application packages never import ML libraries, model internals,
or the offline pipeline. Role 1 adds the B3 checks for its own packages.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[1] / "app"

# Packages owned by Role 2 that sit in the request path.
ROLE2_PACKAGES = ["api", "schemas", "services", "engine", "db", "core"]

# B1 + B7: no ML libraries or offline pipeline in the application layer.
FORBIDDEN_LIBS = {"sklearn", "xgboost", "lightgbm", "shap", "joblib", "torch", "ml_pipeline"}
# B2: no direct use of model internals. The intelligence interface is reached via app.contracts.
FORBIDDEN_APP_MODULES = ("app.intelligence", "app.ml", "app.recommendation")

# The single wiring point allowed to construct the real facade (roadmap 9.1 factory).
FACADE_WIRING_ALLOWED = {APP_DIR / "api" / "deps.py": {"app.intelligence.facade"}}


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _is_forbidden(module: str) -> bool:
    """Whole-package match: ``app.intelligence_mock`` is not ``app.intelligence``."""
    return any(module == f or module.startswith(f + ".") for f in FORBIDDEN_APP_MODULES)


def _python_files(*dirs: Path) -> list[Path]:
    files: list[Path] = []
    for d in dirs:
        if d.is_dir():
            files.extend(sorted(d.rglob("*.py")))
    return files


ROLE2_FILES = [*_python_files(*(APP_DIR / p for p in ROLE2_PACKAGES)), APP_DIR / "main.py"]


@pytest.mark.parametrize("path", ROLE2_FILES, ids=lambda p: str(p.relative_to(APP_DIR)))
def test_application_layer_does_not_import_ml(path: Path) -> None:
    allowed = FACADE_WIRING_ALLOWED.get(path, set())
    for module in _imported_modules(path):
        root = module.split(".")[0]
        assert root not in FORBIDDEN_LIBS, f"{path.name} imports ML library '{module}' (rule B1/B7)"
        if module in allowed:
            continue
        assert not _is_forbidden(module), (
            f"{path.name} imports intelligence internals '{module}' (rule B2); "
            "use app.contracts.interface.QualityIntelligence instead"
        )


def test_mock_does_not_import_role1_internals() -> None:
    # Roadmap R2-P1 #15: the mock may use app.contracts and app.domain only.
    for path in _python_files(APP_DIR / "intelligence_mock"):
        for module in _imported_modules(path):
            assert not _is_forbidden(module), f"{path.name} imports '{module}'"
            assert module.split(".")[0] not in FORBIDDEN_LIBS, f"{path.name} imports '{module}'"


def test_boundary_checker_detects_violations(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("import joblib\nfrom app.ml.predict import x\n", encoding="utf-8")
    assert {"joblib", "app.ml.predict"} <= _imported_modules(bad)
    assert _is_forbidden("app.intelligence.facade")
    assert _is_forbidden("app.intelligence")
    assert not _is_forbidden("app.intelligence_mock.mock")
