"""Current-stage preflight positive and tamper-negative tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

import nightly_photo_intelligence_pipeline.cli as cli_module
import nightly_photo_intelligence_pipeline.preflight as preflight_module
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.authorization import AuthorizationSnapshot
from nightly_photo_intelligence_pipeline.domain.errors import (
    RuntimePolicyError,
    SourceRuntimeOverlapError,
)
from nightly_photo_intelligence_pipeline.ingest.g1_contract import (
    N0_BASELINE,
    N1_BASELINE,
    G1Approval,
    path_fingerprint,
    runtime_parent_fingerprint,
    validate_runtime_child,
)
from nightly_photo_intelligence_pipeline.ingest.read_only_capability import (
    CapabilityDisposition,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _synthetic_g1_authorization(root: Path) -> AuthorizationSnapshot:
    """Historical G1 fixture authority, isolated from active N2B0.7 state."""
    return AuthorizationSnapshot(
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
        active_execution_phase="G1",
        active_execution_capability="G1_CALIBRATION_20",
        source_photo_content_read="AUTHORIZED",
        sqlite_ingest_write="AUTHORIZED",
    )


def test_disk_preflight_fails_closed_below_safety_floor(monkeypatch: pytest.MonkeyPatch) -> None:
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(
        preflight_module.shutil,
        "disk_usage",
        lambda _path: Usage(total=10 * 1024**3, used=10 * 1024**3, free=0),
    )
    result = preflight_module._check_disk()
    assert result.status == "FAIL"
    assert "1 GiB safety floor" in result.notes


def _prepare_synthetic_current_stage(
    project_root: Path, tmp_path: Path
) -> tuple[Path, Path, Path, Path, str]:
    for item in ("PROJECT_STATE.json", "approvals", "tasks", "schemas", "config", "research"):
        source_item = project_root / item
        target = tmp_path / item
        if source_item.is_dir():
            shutil.copytree(source_item, target)
        else:
            shutil.copy2(source_item, target)

    source = tmp_path / "synthetic-source"
    runtime_parent = tmp_path / "runtime-parent"
    runtime_child = runtime_parent / "review"
    source.mkdir()
    runtime_child.mkdir(parents=True)
    names = [f"synthetic-{index:02d}.bin" for index in range(20)]
    for name in names:
        (source / name).write_bytes(b"synthetic fixture")
    manifest_path = tmp_path / "synthetic-manifest.txt"
    manifest_path.write_text("\n".join(names) + "\n", encoding="utf-8")
    manifest_sha = _sha256(manifest_path)

    g1_task_path = tmp_path / "tasks" / "gate_g1_calibration_20.yaml"
    g1_task = yaml.safe_load(g1_task_path.read_text(encoding="utf-8"))
    g1_task["dependencies"]["manifest_sha256"] = manifest_sha
    g1_task_path.write_text(yaml.safe_dump(g1_task, sort_keys=False), encoding="utf-8")

    approval_schema_path = tmp_path / "schemas" / "approval_record_v1_1.schema.json"
    approval_schema = json.loads(approval_schema_path.read_text(encoding="utf-8"))
    approval_schema["properties"]["manifest_sha256"]["const"] = manifest_sha
    approval_schema["properties"]["source_policy"]["properties"]["root_fingerprint_sha256"][
        "const"
    ] = path_fingerprint(source)
    approval_schema["properties"]["runtime_policy"]["properties"]["parent_fingerprint_sha256"][
        "const"
    ] = runtime_parent_fingerprint(runtime_parent)
    approval_schema_path.write_text(json.dumps(approval_schema), encoding="utf-8")
    task_schema_path = tmp_path / "schemas" / "task_contract_v1_1.schema.json"
    task_schema = json.loads(task_schema_path.read_text(encoding="utf-8"))
    task_schema["$defs"]["g1Dependencies"]["properties"]["manifest_sha256"]["const"] = manifest_sha
    task_schema_path.write_text(json.dumps(task_schema), encoding="utf-8")

    approval_path = tmp_path / "approvals" / "data_gate_approval_G1.yaml"
    approval = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
    approval["manifest_sha256"] = manifest_sha
    approval["source_policy"]["root_fingerprint_sha256"] = path_fingerprint(source)
    approval["runtime_policy"]["parent_fingerprint_sha256"] = runtime_parent_fingerprint(
        runtime_parent
    )
    approval["bindings"] = {
        "project_state_sha256": _sha256(tmp_path / "PROJECT_STATE.json"),
        "n1_task_sha256": _sha256(tmp_path / "tasks" / "phase_n1_ingest_state_machine.yaml"),
        "g1_task_sha256": _sha256(g1_task_path),
        "task_index_sha256": _sha256(tmp_path / "tasks" / "index.json"),
        "retry_policy_sha256": _sha256(tmp_path / "config" / "retry_policy_v1_1.yaml"),
        "error_taxonomy_sha256": _sha256(tmp_path / "config" / "error_taxonomy_v1_1.yaml"),
    }
    approval_path.write_text(yaml.safe_dump(approval, sort_keys=False), encoding="utf-8")
    return source, runtime_parent, runtime_child, manifest_path, manifest_sha


def test_cli_preflight_exits_zero_with_legal_synthetic_execution_config(
    project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, runtime_parent, runtime_child, manifest_path, manifest_sha = (
        _prepare_synthetic_current_stage(project_root, tmp_path)
    )
    monkeypatch.setattr(preflight_module, "find_project_root", lambda: tmp_path)
    import nightly_photo_intelligence_pipeline.ingest.g1_contract as contract_module

    monkeypatch.setattr(contract_module, "MANIFEST_SHA256", manifest_sha)
    monkeypatch.setattr(contract_module, "SOURCE_ROOT_FINGERPRINT_SHA256", path_fingerprint(source))
    monkeypatch.setattr(
        contract_module,
        "RUNTIME_PARENT_FINGERPRINT_SHA256",
        runtime_parent_fingerprint(runtime_parent),
    )
    assert contract_module.prepare_g1_execution.__kwdefaults__ is not None
    monkeypatch.setitem(
        contract_module.prepare_g1_execution.__kwdefaults__,
        "probe",
        lambda *_: CapabilityDisposition.DENIED,
    )
    monkeypatch.setenv("NPI_SOURCE_ROOT", str(source))
    monkeypatch.setenv("NPI_RUNTIME_PARENT", str(runtime_parent))
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime_child))
    monkeypatch.setenv("NPI_G1_MANIFEST", str(manifest_path))
    # Keep current authorization/schema validation real. Host/tool checks are
    # orthogonal to this deterministic synthetic execution-chain test.
    monkeypatch.setattr(preflight_module, "_BASE_CHECKS", (preflight_module._check_authorization,))
    result = CliRunner().invoke(app, ["preflight"])
    assert result.exit_code == 0, result.output
    assert "g1_execution_environment" in result.output
    assert "[PASS" in result.output


def test_g1_ingest_refuses_to_bypass_failed_current_preflight(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source"
    runtime = tmp_path / "runtime-parent" / "child"
    source.mkdir()
    runtime.mkdir(parents=True)
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("synthetic\n", encoding="utf-8")
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(runtime))
    monkeypatch.setattr(
        cli_module,
        "load_authorization",
        lambda: _synthetic_g1_authorization(tmp_path),
    )
    monkeypatch.setattr(
        cli_module,
        "run_preflight",
        lambda: [
            preflight_module.CheckResult(name="current_authorization_contracts", status="FAIL")
        ],
    )
    called = False

    def forbidden_manifest_load(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("manifest must not load after a failed preflight")

    monkeypatch.setattr(cli_module.G1FrozenManifest, "load", forbidden_manifest_load)
    result = CliRunner().invoke(
        app,
        [
            "ingest",
            "--input",
            str(source),
            "--g1-frozen-manifest",
            str(manifest),
        ],
    )
    assert result.exit_code == 3
    assert "NPI_PREFLIGHT_UNSATISFIED" in result.output
    assert not called


@pytest.mark.parametrize(
    ("relative_path", "old", "new"),
    [
        ("PROJECT_STATE.json", '"N2": "LOCKED"', '"N2": "AUTHORIZED"'),
        (
            "approvals/data_gate_approval_G1.yaml",
            'status: "APPROVED"',
            'status: "NOT_APPROVED"',
        ),
        (
            "approvals/data_gate_approval_G1.yaml",
            N1_BASELINE,
            "0" * 40,
        ),
        (
            "approvals/phase_completion_N1.yaml",
            'status: "APPROVED"',
            'status: "NOT_APPROVED"',
        ),
        (
            "tasks/index.json",
            '"completion_approval": "approvals/phase_completion_N1.yaml"',
            '"completion_approval": "approvals/missing.yaml"',
        ),
        (
            "tasks/gate_g1_calibration_20.yaml",
            'n1_completion_approval: "approvals/phase_completion_N1.yaml"',
            'n1_completion_approval: "approvals/missing.yaml"',
        ),
        (
            "config/retry_policy_v1_1.yaml",
            "max_attempts: 2",
            "max_attempts: 99",
        ),
        (
            "config/error_taxonomy_v1_1.yaml",
            'schema_version: "1.1"',
            'schema_version: "9.9"',
        ),
    ],
)
def test_current_authorization_preflight_rejects_tampering(
    project_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    old: str,
    new: str,
) -> None:
    for item in ("PROJECT_STATE.json", "approvals", "tasks", "schemas", "config"):
        source = project_root / item
        target = tmp_path / item
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    target = tmp_path / relative_path
    content = target.read_text(encoding="utf-8")
    assert old in content
    target.write_text(content.replace(old, new, 1), encoding="utf-8")
    monkeypatch.setattr(preflight_module, "find_project_root", lambda: tmp_path)
    assert preflight_module._check_authorization().status == "FAIL"


def test_manifest_hash_tamper_is_a_preflight_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = tmp_path / "manifest.txt"
    manifest.write_text("\n".join(f"entry-{index}" for index in range(20)), encoding="utf-8")
    monkeypatch.setenv("NPI_SOURCE_ROOT", str(tmp_path / "source"))
    monkeypatch.setenv("NPI_RUNTIME_PARENT", str(tmp_path / "parent"))
    monkeypatch.setenv("NPI_RUNTIME_ROOT", str(tmp_path / "parent" / "child"))
    monkeypatch.setenv("NPI_G1_MANIFEST", str(manifest))
    monkeypatch.setattr(preflight_module, "find_project_root", lambda: tmp_path)

    class Approval:
        manifest_sha256 = "0" * 64
        manifest_count = 20

    import nightly_photo_intelligence_pipeline.ingest.g1_contract as contract_module

    monkeypatch.setattr(contract_module, "load_g1_approval", lambda _root: Approval())
    result = preflight_module._check_source_runtime_separation()
    assert result.status == "FAIL"


def test_runtime_parent_allows_distinct_children_and_rejects_escape(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    parent = tmp_path / "runtime"
    child_a = parent / "work"
    child_b = parent / "review"
    outside = tmp_path / "outside"
    for path in (source, child_a, child_b, outside):
        path.mkdir(parents=True)
    approval = G1Approval(
        manifest_sha256=hashlib.sha256(b"synthetic").hexdigest(),
        manifest_count=20,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_parent_fingerprint_sha256=runtime_parent_fingerprint(parent),
        n0_baseline=N0_BASELINE,
        n1_baseline=N1_BASELINE,
        expires_at=datetime.now().astimezone() + timedelta(days=1),
    )
    for child in (child_a, child_b):
        validate_runtime_child(
            source_root=source,
            runtime_parent=parent,
            runtime_child=child,
            approval=approval,
        )
    with pytest.raises(RuntimePolicyError):
        validate_runtime_child(
            source_root=source,
            runtime_parent=parent,
            runtime_child=outside,
            approval=approval,
        )
    overlap_parent = source / "runtime"
    overlap_child = overlap_parent / "child"
    overlap_child.mkdir(parents=True)
    overlap_approval = G1Approval(
        manifest_sha256=approval.manifest_sha256,
        manifest_count=20,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_parent_fingerprint_sha256=runtime_parent_fingerprint(overlap_parent),
        n0_baseline=N0_BASELINE,
        n1_baseline=N1_BASELINE,
        expires_at=approval.expires_at,
    )
    with pytest.raises(SourceRuntimeOverlapError):
        validate_runtime_child(
            source_root=source,
            runtime_parent=overlap_parent,
            runtime_child=overlap_child,
            approval=overlap_approval,
        )


def test_runtime_child_junction_escape_is_rejected(tmp_path: Path, junction_factory) -> None:
    source = tmp_path / "source"
    parent = tmp_path / "runtime"
    outside = tmp_path / "outside"
    for path in (source, parent, outside):
        path.mkdir()
    link = parent / "review"
    if not junction_factory(link, outside):
        pytest.skip("junction creation unavailable")
    approval = G1Approval(
        manifest_sha256=hashlib.sha256(b"synthetic").hexdigest(),
        manifest_count=20,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_parent_fingerprint_sha256=runtime_parent_fingerprint(parent),
        n0_baseline=N0_BASELINE,
        n1_baseline=N1_BASELINE,
        expires_at=datetime.now().astimezone() + timedelta(days=1),
    )
    with pytest.raises(RuntimePolicyError):
        validate_runtime_child(
            source_root=source,
            runtime_parent=parent,
            runtime_child=link,
            approval=approval,
        )


def test_runtime_parent_ancestor_junction_is_rejected(tmp_path: Path, junction_factory) -> None:
    source = tmp_path / "source"
    outside = tmp_path / "outside"
    source.mkdir()
    outside.mkdir()
    ancestor_link = tmp_path / "runtime-link"
    if not junction_factory(ancestor_link, outside):
        pytest.skip("junction creation unavailable")
    parent = ancestor_link / "approved-parent"
    child = parent / "review"
    child.mkdir(parents=True)
    approval = G1Approval(
        manifest_sha256=hashlib.sha256(b"synthetic").hexdigest(),
        manifest_count=20,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_parent_fingerprint_sha256=runtime_parent_fingerprint(parent),
        n0_baseline=N0_BASELINE,
        n1_baseline=N1_BASELINE,
        expires_at=datetime.now().astimezone() + timedelta(days=1),
    )
    with pytest.raises(RuntimePolicyError, match="ancestry"):
        validate_runtime_child(
            source_root=source,
            runtime_parent=parent,
            runtime_child=child,
            approval=approval,
        )
