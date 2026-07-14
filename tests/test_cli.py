"""AT-N0-CLI-01: N0 commands and exit codes.
AT-N0-GATE-01 (N1 phase-boundary): non-dry-run ingest is authorized on G0
manifest fixtures; a non-manifest (4th) asset is rejected.
AT-N0-IDEM-01: dry-run idempotency with zero DB change."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.persistence.sqlite import StateStore

pytestmark = pytest.mark.acceptance


def test_at_n0_cli_01_help_and_commands(fixture_dir: Path) -> None:
    """AT-N0-CLI-01: the N0/N1 commands exist and respond to --help."""
    runner = CliRunner()
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0
    for cmd in ("preflight", "status", "ingest", "resume", "report"):
        assert cmd in help_result.output
    for cmd in ("preflight", "status", "ingest", "resume", "report"):
        r = runner.invoke(app, [cmd, "--help"])
        assert r.exit_code == 0, f"{cmd} --help failed: {r.output}"


def test_at_n0_cli_01_status_empty_db_exit_zero(monkeypatch, tmp_path: Path) -> None:
    """AT-N0-CLI-01: status on a fresh install returns 0 with no DB present."""
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(tmp_path / "runtime"))
    runner = CliRunner()
    result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "not present" in result.output
    assert "N1" in result.output


def test_at_n1_gate_non_dry_run_authorized_for_manifest(
    fixture_dir: Path, monkeypatch, tmp_path: Path
) -> None:
    """AT-N0-GATE-01 (N1): non-dry-run ingest on the G0 manifest fixtures is
    authorized (exit 0). Two unique assets are created (the exact-duplicate
    pair collapses to one asset)."""
    runtime = tmp_path / "runtime"
    (runtime / "state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "--input", str(fixture_dir)])
    assert result.exit_code == 0, f"expected exit 0, got {result.exit_code}: {result.output}"
    assert "assets_created" in result.output
    assert "database_mutated: True" in result.output
    # DB now has 2 unique assets (3 fixtures, 1 exact-duplicate pair).
    store = StateStore.open(runtime / "state" / "npi_state.sqlite", initialize=False)
    assert store.asset_count() == 2
    assert store.schema_version() == "1"
    store.close()


def test_at_n1_gate_fourth_asset_rejected(fixture_dir: Path, monkeypatch, tmp_path: Path) -> None:
    """AT-N0-GATE-01 (N1): a 4th asset NOT in the G0 manifest is rejected (exit 8)."""
    src = tmp_path / "src_extra"
    src.mkdir()
    # A file whose name is NOT in the G0 manifest (renamed copy of a fixture).
    shutil.copy(fixture_dir / "fixture_b_tonal_abstract.png", src / "fixture_c_extra.png")
    runtime = tmp_path / "runtime_extra"
    (runtime / "state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))
    runner = CliRunner()
    result = runner.invoke(app, ["ingest", "--input", str(src)])
    assert result.exit_code == 8, f"expected exit 8, got {result.exit_code}: {result.output}"
    assert "NPI_GATE_NOT_AUTHORIZED" in result.output
    # No asset created for the rejected file.
    store = StateStore.open(runtime / "state" / "npi_state.sqlite", initialize=False)
    assert store.asset_count() == 0
    store.close()


def test_at_n0_idem_01_dry_run_idempotent_and_db_unchanged(
    fixture_dir: Path, monkeypatch, tmp_path: Path
) -> None:
    """AT-N0-IDEM-01: two dry-runs produce identical output; DB asset count stays 0."""
    runtime = tmp_path / "runtime"
    (runtime / "state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))

    db_path = runtime / "state" / "npi_state.sqlite"
    store = StateStore.open(db_path)
    assert store.asset_count() == 0
    store.close()

    runner = CliRunner()
    r1 = runner.invoke(app, ["ingest", "--input", str(fixture_dir), "--dry-run"])
    r2 = runner.invoke(app, ["ingest", "--input", str(fixture_dir), "--dry-run"])
    assert r1.exit_code == 0, r1.output
    assert r2.exit_code == 0, r2.output
    assert r1.output == r2.output, "dry-run output must be deterministic"
    store2 = StateStore.open(db_path, initialize=False)
    assert store2.asset_count() == 0, "dry-run must not write asset rows"
    store2.close()
    assert "duplicate_groups: 1" in r1.output
    assert "files_scanned: 3" in r1.output


def test_at_n1_real_ingest_idempotent_reingest(
    fixture_dir: Path, monkeypatch, tmp_path: Path
) -> None:
    """AT-N1: re-ingesting the same fixtures creates no new asset rows (idempotent)."""
    runtime = tmp_path / "runtime"
    (runtime / "state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))
    runner = CliRunner()
    r1 = runner.invoke(app, ["ingest", "--input", str(fixture_dir)])
    assert r1.exit_code == 0, r1.output
    store = StateStore.open(runtime / "state" / "npi_state.sqlite", initialize=False)
    first_count = store.asset_count()
    store.close()
    r2 = runner.invoke(app, ["ingest", "--input", str(fixture_dir)])
    assert r2.exit_code == 0, r2.output
    store2 = StateStore.open(runtime / "state" / "npi_state.sqlite", initialize=False)
    assert store2.asset_count() == first_count, "re-ingest must not add assets"
    # Second run reports all as duplicates.
    assert "assets_created: 0" in r2.output
    store2.close()
