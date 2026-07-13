"""Shared pytest fixtures for the N0 test suite."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIXTURE_DIR = ROOT / "fixtures" / "three_image_smoke_set"
FIXTURE_MANIFEST = ROOT / "fixtures" / "fixture_manifest.json"


@pytest.fixture(scope="session")
def project_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def fixture_dir() -> Path:
    return FIXTURE_DIR


@pytest.fixture(scope="session")
def fixture_manifest() -> dict:
    return json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture()
def config():
    from nightly_photo_intelligence_pipeline.domain.models import load_config

    return load_config()


@pytest.fixture()
def runtime_root(tmp_path) -> Path:
    rt = tmp_path / "runtime"
    (rt / "state").mkdir(parents=True, exist_ok=True)
    return rt


@pytest.fixture()
def db_path(runtime_root) -> Path:
    return runtime_root / "state" / "npi_state.sqlite"


def make_junction(link: Path, target: Path) -> bool:
    """Create an NTFS junction (no admin privilege required). Returns success.

    Returns False on non-Windows or if creation fails (caller should skip).
    """
    if sys.platform != "win32":
        return False
    try:
        proc = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and link.exists()


@pytest.fixture()
def junction_factory():
    return make_junction


@pytest.fixture(autouse=True)
def _isolate_runtime_env(monkeypatch, tmp_path):
    """Ensure tests never touch a real runtime root or source root env."""
    monkeypatch.delenv("NPI_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("NPI_SOURCE_ROOT", raising=False)
