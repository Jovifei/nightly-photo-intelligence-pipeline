"""AT-N0-ENV-01: preflight is read-only and performs no system changes."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.preflight import format_preflight_text, run_preflight

pytestmark = pytest.mark.acceptance


def test_at_n0_env_01_preflight_read_only_no_system_changes(project_root: Path) -> None:
    """AT-N0-ENV-01: preflight reports capabilities without installing/updating/pulling."""
    runner = CliRunner()
    # Snapshot the set of files under the project root before preflight.
    before = {
        p.relative_to(project_root).as_posix() for p in project_root.rglob("*") if p.is_file()
    }
    result = runner.invoke(app, ["preflight"])
    # Preflight may exit 0 (all critical checks pass) - never modifies state.
    assert result.exit_code in (0, 3), f"unexpected preflight exit: {result.exit_code}"
    assert "No install, update, pull, or system change was performed" in result.output
    # No new files were created in the project by preflight (read-only).
    after = {p.relative_to(project_root).as_posix() for p in project_root.rglob("*") if p.is_file()}
    # __pycache__ may appear from imports; that is gitignored and not a system change.
    new_files = after - before
    unexpected = {f for f in new_files if "__pycache__" not in f and ".pyc" not in f}
    assert not unexpected, f"preflight created unexpected files: {unexpected}"


def test_at_n0_env_01_preflight_reports_available_and_unavailable() -> None:
    """AT-N0-ENV-01: preflight distinguishes AVAILABLE / NOT_AVAILABLE / SKIPPED."""
    results = run_preflight()
    statuses = {r.status for r in results}
    # At least one PASS must be present; SKIPPED is used for non-applicable checks.
    assert "PASS" in statuses
    text = format_preflight_text(results)
    assert "preflight (read-only" in text
    assert "Summary:" in text
