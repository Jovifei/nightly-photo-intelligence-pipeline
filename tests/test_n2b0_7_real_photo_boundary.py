"""N2B0.7 must reject every public source-content runner before I/O."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from typer.testing import CliRunner

import nightly_photo_intelligence_pipeline.cli as cli_module
import nightly_photo_intelligence_pipeline.ingest.runner as runner_module
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.authorization import load_authorization
from nightly_photo_intelligence_pipeline.domain.errors import GateNotAuthorizedError
from nightly_photo_intelligence_pipeline.ingest.g1_contract import (
    N0_BASELINE,
    N1_BASELINE,
    G1Approval,
    G1ExecutionPermit,
    path_fingerprint,
    prepare_g1_execution,
    runtime_parent_fingerprint,
)
from nightly_photo_intelligence_pipeline.ingest.manifest import (
    G1FrozenManifest,
    Manifest,
)
from nightly_photo_intelligence_pipeline.ingest.read_only_capability import (
    ReadOnlyCapabilityResult,
)
from nightly_photo_intelligence_pipeline.ingest.runner import (
    run_dry_run_ingest,
    run_g1_calibration_ingest,
    run_real_ingest,
)


def _manifest(tmp_path: Path) -> G1FrozenManifest:
    path = tmp_path / "synthetic-g1-manifest.txt"
    path.write_text("\n".join(f"asset-{index:02d}.jpg" for index in range(20)) + "\n")
    return G1FrozenManifest.load(path)


def _approval(source: Path, runtime_parent: Path, manifest: G1FrozenManifest) -> G1Approval:
    return G1Approval(
        manifest_sha256=manifest.sha256,
        manifest_count=manifest.count,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_parent_fingerprint_sha256=runtime_parent_fingerprint(runtime_parent),
        n0_baseline=N0_BASELINE,
        n1_baseline=N1_BASELINE,
        expires_at=datetime.now().astimezone() + timedelta(days=1),
    )


def _permit(source: Path, runtime: Path, manifest: G1FrozenManifest) -> G1ExecutionPermit:
    return G1ExecutionPermit(
        manifest_sha256=manifest.sha256,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_child_fingerprint_sha256=path_fingerprint(runtime),
        read_only=ReadOnlyCapabilityResult("OS_ENFORCED_READ_ONLY_VERIFIED", 20),
    )


def test_n2b0_7_refuses_permit_before_readonly_probe(project_root: Path, tmp_path: Path) -> None:
    source = tmp_path / "source"
    runtime_parent = tmp_path / "runtime-parent"
    runtime = runtime_parent / "child"
    source.mkdir()
    runtime.mkdir(parents=True)
    manifest = _manifest(tmp_path)
    probe_called = False

    def forbidden_probe(*_args, **_kwargs):
        nonlocal probe_called
        probe_called = True
        raise AssertionError("N2B0.7 must fail before the source read-only probe")

    with pytest.raises(GateNotAuthorizedError, match="source-content read"):
        prepare_g1_execution(
            source_root=source,
            runtime_parent=runtime_parent,
            runtime_child=runtime,
            auth=load_authorization(project_root),
            manifest=manifest,
            approval=_approval(source, runtime_parent, manifest),
            probe=forbidden_probe,
        )
    assert not probe_called


def test_n2b0_7_refuses_all_ingest_runners_before_source_or_store_access(
    project_root: Path, tmp_path: Path, config, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    runtime = tmp_path / "runtime"
    source.mkdir()
    runtime.mkdir()
    manifest = _manifest(tmp_path)
    auth = load_authorization(project_root)
    opened = False
    exif_read = False
    enumerated = False

    def forbidden_open(*_args, **_kwargs):
        nonlocal opened
        opened = True
        raise AssertionError("N2B0.7 must not open source files")

    def forbidden_exif(*_args, **_kwargs):
        nonlocal exif_read
        exif_read = True
        raise AssertionError("N2B0.7 must not read EXIF")

    def forbidden_enumeration(*_args, **_kwargs):
        nonlocal enumerated
        enumerated = True
        raise AssertionError("N2B0.7 must not enumerate source content")

    monkeypatch.setattr(runner_module, "open_source_file", forbidden_open)
    monkeypatch.setattr(runner_module, "read_exif", forbidden_exif)
    monkeypatch.setattr(runner_module, "_enumerate_source_files", forbidden_enumeration)

    with pytest.raises(GateNotAuthorizedError, match="source-content read"):
        run_dry_run_ingest(source, runtime, config, auth=auth)
    with pytest.raises(GateNotAuthorizedError, match="source-content read"):
        run_real_ingest(
            source,
            runtime,
            config,
            auth,
            object(),  # type: ignore[arg-type]
            Manifest(fixture_set="synthetic", files=()),
        )
    with pytest.raises(GateNotAuthorizedError, match="source-content read"):
        run_g1_calibration_ingest(
            source,
            runtime,
            config,
            auth,
            object(),  # type: ignore[arg-type]
            manifest,
            permit=_permit(source, runtime, manifest),
        )

    assert not opened
    assert not exif_read
    assert not enumerated


def test_n2b0_7_cli_ingest_rejects_before_manifest_or_store_access(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The CLI must not weaken the library-level source-content denial."""
    source = tmp_path / "not-a-photo-source"
    runtime = tmp_path / "runtime"
    forbidden_calls: list[str] = []

    def forbidden(name: str):
        def _call(*_args, **_kwargs):
            forbidden_calls.append(name)
            raise AssertionError(f"N2B0.7 CLI reached {name}")

        return _call

    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))
    monkeypatch.setattr(cli_module, "load_config", forbidden("load_config"))
    monkeypatch.setattr(cli_module, "validate_roots", forbidden("validate_roots"))
    monkeypatch.setattr(cli_module, "run_preflight", forbidden("run_preflight"))
    monkeypatch.setattr(cli_module.G1FrozenManifest, "load", forbidden("manifest_load"))
    monkeypatch.setattr(cli_module.StateStore, "open", forbidden("state_store_open"))

    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "--input",
            str(source),
            "--g1-frozen-manifest",
            str(tmp_path / "not-read.txt"),
        ],
    )

    assert result.exit_code == 8, result.output
    assert "NPI_GATE_NOT_AUTHORIZED" in result.output
    assert "source-content read" in result.output
    assert forbidden_calls == []


def test_n2b0_7_cli_resume_rejects_before_database_resolution_or_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resume is a mutating ingest operation and is locked for N2B0.7."""
    forbidden_calls: list[str] = []

    def forbidden(name: str):
        def _call(*_args, **_kwargs):
            forbidden_calls.append(name)
            raise AssertionError(f"N2B0.7 CLI reached {name}")

        return _call

    monkeypatch.setattr(cli_module, "_resolve_db_path", forbidden("resolve_db_path"))
    monkeypatch.setattr(cli_module.StateStore, "open", forbidden("state_store_open"))

    result = CliRunner().invoke(app, ["resume"])

    assert result.exit_code == 8, result.output
    assert "NPI_GATE_NOT_AUTHORIZED" in result.output
    assert "SQLite ingest write" in result.output
    assert forbidden_calls == []
