"""AT-N0-CLI-01: N0 commands and exit codes. AT-N0-GATE-01: non-dry-run ingest
locked. AT-N0-IDEM-01: dry-run idempotency with zero DB change."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.persistence.sqlite import StateStore

pytestmark = pytest.mark.acceptance


def test_at_n0_cli_01_help_and_commands(fixture_dir: Path) -> None:
    """AT-N0-CLI-01: the three N0 commands exist and respond to --help."""
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    assert "preflight" in help_result.output
    assert "status" in help_result.output
    assert "ingest" in help_result.output

    for cmd in ("preflight", "status", "ingest"):
        r = runner.invoke(app, [cmd, "--help"])
        assert r.exit_code == 0, f"{cmd} --help failed: {r.output}"


def test_at_n0_cli_01_status_empty_db_exit_zero(monkeypatch, tmp_path: Path) -> None:
    """AT-N0-CLI-01: status on a fresh install returns 0 with no DB present."""
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(tmp_path / "runtime"))
    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "not present" in result.output
    assert "N0" in result.output


def test_at_n0_gate_01_non_dry_run_locked(fixture_dir: Path, monkeypatch, tmp_path: Path) -> None:
    """AT-N0-GATE-01: ingest without --dry-run exits 8 with NPI_GATE_NOT_AUTHORIZED."""
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(tmp_path / "runtime"))
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "--input", str(fixture_dir)])
    assert result.exit_code == 8, f"expected exit 8, got {result.exit_code}: {result.output}"
    assert "NPI_GATE_NOT_AUTHORIZED" in result.output


def test_at_n0_idem_01_dry_run_idempotent_and_db_unchanged(
    fixture_dir: Path, monkeypatch, tmp_path: Path
) -> None:
    """AT-N0-IDEM-01: two dry-runs produce identical output; DB asset count stays 0."""
    runtime = tmp_path / "runtime"
    (runtime / "state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))

    # Seed an empty state DB so we can prove the dry-run does not mutate it.
    db_path = runtime / "state" / "npi_state.sqlite"
    store = StateStore.open(db_path)
    assert store.asset_count() == 0
    store.close()

    runner = CliRunner()
    r1 = runner.invoke(app, ["ingest", "--input", str(fixture_dir), "--dry-run"])
    r2 = runner.invoke(app, ["ingest", "--input", str(fixture_dir), "--dry-run"])
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    # Deterministic: identical normalized output.
    assert r1.output == r2.output, "dry-run output must be deterministic"
    # DB unchanged.
    store2 = StateStore.open(db_path, initialize=False)
    assert store2.asset_count() == 0, "dry-run must not write asset rows"
    store2.close()
    # Duplicate group is reported.
    assert "duplicate_groups: 1" in r1.output
    assert "files_scanned: 3" in r1.output
