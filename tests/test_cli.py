"""AT-N0-CLI-01: N0 commands and exit codes.
AT-N0-GATE-01 (N1 phase-boundary): non-dry-run ingest is authorized on G0
manifest fixtures; a non-manifest (4th) asset is rejected.
AT-N0-IDEM-01: dry-run idempotency with zero DB change."""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

import nightly_photo_intelligence_pipeline.cli as cli_module
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.authorization import AuthorizationSnapshot
from nightly_photo_intelligence_pipeline.ingest.g1_contract import (
    N0_BASELINE,
    N1_BASELINE,
    G1Approval,
    path_fingerprint,
    runtime_parent_fingerprint,
)
from nightly_photo_intelligence_pipeline.persistence.sqlite import StateStore

pytestmark = pytest.mark.acceptance


def _authorize_historical_g0(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    snapshot = AuthorizationSnapshot(
        phase_id="N1",
        phase_status="APPROVED_COMPLETE",
        data_gate_id="G0_THREE_SYNTHETIC_FIXTURES",
        data_gate_status="AUTHORIZED",
        real_photo_access="NOT_AUTHORIZED",
        large_model_downloads="NOT_AUTHORIZED",
        openclaw_activation="NOT_AUTHORIZED",
        exif_real_data_read="NOT_AUTHORIZED",
        project_root=root,
        max_assets=3,
        n0_baseline_commit="72a81f5984838b74304d23263ac450ea4b5a3a9a",
        n1_baseline_commit="ca812cb71c4a09d273f64d9a6f2747ac3facf4cc",
    )
    monkeypatch.setattr(cli_module, "load_authorization", lambda: snapshot)


def _authorize_historical_g1(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    snapshot = AuthorizationSnapshot(
        phase_id="N1",
        phase_status="APPROVED_COMPLETE",
        data_gate_id="G1_CALIBRATION_20",
        data_gate_status="AUTHORIZED",
        real_photo_access="AUTHORIZED",
        large_model_downloads="NOT_AUTHORIZED",
        openclaw_activation="NOT_AUTHORIZED",
        exif_real_data_read="AUTHORIZED_NON_SENSITIVE_ONLY",
        project_root=root,
        max_assets=20,
        n0_baseline_commit=N0_BASELINE,
        n1_baseline_commit=N1_BASELINE,
    )
    monkeypatch.setattr(cli_module, "load_authorization", lambda: snapshot)


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
    _authorize_historical_g0(monkeypatch, tmp_path)
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
    assert store.schema_version() == "3"
    store.close()


def test_at_n1_gate_fourth_asset_rejected(fixture_dir: Path, monkeypatch, tmp_path: Path) -> None:
    """AT-N0-GATE-01 (N1): a 4th asset NOT in the G0 manifest is rejected (exit 8)."""
    src = tmp_path / "src_extra"
    _authorize_historical_g0(monkeypatch, tmp_path)
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
    _authorize_historical_g0(monkeypatch, tmp_path)
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
    _authorize_historical_g0(monkeypatch, tmp_path)
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


@pytest.mark.parametrize("dry_run", [False, True])
def test_current_g1_gate_rejects_directory_wide_ingest_before_runner(
    fixture_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    dry_run: bool,
) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("directory-wide runner must not execute under G1")

    monkeypatch.setattr(cli_module, "run_dry_run_ingest", forbidden)
    monkeypatch.setattr(cli_module, "run_real_ingest", forbidden)
    command = ["ingest", "--input", str(fixture_dir)]
    if dry_run:
        command.append("--dry-run")
    result = CliRunner().invoke(app, command)
    assert result.exit_code == 8
    assert "NPI_GATE_NOT_AUTHORIZED" in result.output
    assert not (runtime / "state" / "npi_state.sqlite").exists()


def test_db_path_uses_captured_runtime_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = tmp_path / "captured"
    changed = tmp_path / "changed"
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(changed))
    assert cli_module._resolve_db_path(captured) == (captured / "state" / "npi_state.sqlite")


def test_g1_runtime_removed_after_permit_is_rejected_before_db_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    parent = tmp_path / "runtime-parent"
    child = parent / "review"
    source.mkdir()
    child.mkdir(parents=True)
    manifest_path = tmp_path / "synthetic-manifest.txt"
    manifest_path.write_text("synthetic\n", encoding="utf-8")
    monkeypatch.setenv("NPI_RUNTIME_PARENT", str(parent))
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(child))
    _authorize_historical_g1(monkeypatch, tmp_path)
    monkeypatch.setattr(
        cli_module,
        "run_preflight",
        lambda: [SimpleNamespace(status="PASS")],
    )
    approval = G1Approval(
        manifest_sha256="0" * 64,
        manifest_count=20,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_parent_fingerprint_sha256=runtime_parent_fingerprint(parent),
        n0_baseline=N0_BASELINE,
        n1_baseline=N1_BASELINE,
        expires_at=datetime.now().astimezone() + timedelta(days=1),
    )
    monkeypatch.setattr(cli_module, "load_g1_approval", lambda _root: approval)
    monkeypatch.setattr(
        cli_module.G1FrozenManifest,
        "load",
        lambda *_args, **_kwargs: SimpleNamespace(),
    )

    def permit_then_remove(**_kwargs):
        child.rmdir()
        return SimpleNamespace()

    monkeypatch.setattr(cli_module, "prepare_g1_execution", permit_then_remove)

    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("database must not open after runtime child disappears")

    monkeypatch.setattr(cli_module.StateStore, "open", forbidden_open)
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "--input",
            str(source),
            "--g1-frozen-manifest",
            str(manifest_path),
        ],
    )
    assert result.exit_code == 4
    assert "NPI_RUNTIME_POLICY_INVALID" in result.output
    assert not child.exists()
