from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256
from nightly_photo_intelligence_pipeline.n2b2_synthetic.torchvision_loader import (
    FakeTorchVisionBackend,
)
from nightly_photo_intelligence_pipeline.real20 import (
    EXIF_ALLOWLIST,
    Real20Error,
    prepare_real20,
)
from nightly_photo_intelligence_pipeline.real20.contracts import load_manifest
from nightly_photo_intelligence_pipeline.real20.exif import read_real20_exif
from nightly_photo_intelligence_pipeline.real20.identity import candidate_identity
from nightly_photo_intelligence_pipeline.real20.runner import _run_real20 as run_real20


class CountingBackend(FakeTorchVisionBackend):
    def __init__(self, *, fail_on_pose: int | None = None) -> None:
        self.pose_calls = 0
        self.segmentation_calls = 0
        self.fail_on_pose = fail_on_pose

    def detect_pose(self, image_bytes: bytes):  # type: ignore[no-untyped-def]
        self.pose_calls += 1
        if self.fail_on_pose == self.pose_calls:
            raise RuntimeError("worker failure")
        return super().detect_pose(image_bytes)

    def segment(self, image_bytes: bytes, role):  # type: ignore[no-untyped-def]
        self.segmentation_calls += 1
        return super().segment(image_bytes, role)

    def runtime_attestation(self) -> dict[str, object]:
        return {
            "device": "cpu",
            "dtype": "float32",
            "cuda_available": False,
            "fallback": False,
        }


class MutatingBackend(CountingBackend):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path

    def detect_pose(self, image_bytes: bytes):  # type: ignore[no-untyped-def]
        result = super().detect_pose(image_bytes)
        self.path.write_bytes(b"changed-source")
        return result


class ExclusiveBackend(CountingBackend):
    def __init__(self) -> None:
        super().__init__()
        self.loaded = False

    def detect_pose(self, image_bytes):
        assert not self.loaded, "multiple heavy roles resident"
        self.loaded = True
        return super().detect_pose(image_bytes)

    def segment(self, image_bytes, role):
        assert not self.loaded, "multiple heavy roles resident"
        self.loaded = True
        return super().segment(image_bytes, role)

    def unload(self, role=None):
        self.loaded = False


def test_heavy_roles_are_unloaded_before_next_role(tmp_path):
    project = _project(tmp_path)
    manifest, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest)
    backend = ExclusiveBackend()
    result = _run(project, source, manifest, controls, backend)
    assert result["unique_inference_count"] == 19
    assert not backend.loaded


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "PROJECT_STATE.json").write_bytes(canonical({"phase_status": {"N2B2": "LOCKED"}}))
    (root / "README.md").write_text("test project\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    for args in (
        ("config", "user.name", "Real20 Test"),
        ("config", "user.email", "real20@example.invalid"),
    ):
        subprocess.run(["git", "-C", str(root), *args], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "test candidate"], check=True)
    return root


def _manifest(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    source = tmp_path / "source"
    source.mkdir()
    assets: list[dict[str, Any]] = []
    hashes: list[str] = []
    for index in range(19):
        path = source / f"photo-{index:02d}.jpg"
        Image.new("RGB", (32 + index, 24), (index, 20, 40)).save(path, format="JPEG")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes.append(digest)
        assets.append(
            {
                "asset_id": f"asset-{index:02d}",
                "relative_path": path.name,
                "sha256": digest,
            }
        )
    assets.append(
        {
            "asset_id": "asset-19",
            "relative_path": "photo-19.jpg",
            "sha256": hashes[-1],
            "duplicate_of": "asset-18",
        }
    )
    (source / "photo-19.jpg").write_bytes((source / "photo-18.jpg").read_bytes())
    manifest = {
        "schema_version": "npi-real20-manifest-v2",
        "source_type": "OWNER_FROZEN_REAL_PHOTO_SNAPSHOT",
        "source_fingerprint": "test-source-fingerprint",
        "assets": assets,
    }
    path = tmp_path / "manifest.json"
    path.write_bytes(canonical(manifest))
    return path, source, manifest


def _controls(
    tmp_path: Path,
    project: Path,
    manifest_path: Path,
    *,
    expires: datetime | None = None,
    purpose: str = "REAL20_READ_ONLY_EVALUATION",
) -> dict[str, Path]:
    identity = candidate_identity(project)
    runtime = {
        "device": "cpu",
        "dtype": "float32",
        "cuda_available": False,
        "fallback": False,
    }
    model = {"facts_schema": "1.2", "pose": "existing", "segmentation": "existing"}
    runtime_path = tmp_path / "runtime.json"
    model_path = tmp_path / "model.json"
    runtime_path.write_bytes(canonical(runtime))
    model_path.write_bytes(canonical(model))
    manifest_hash = sha256(manifest_path.read_bytes())
    credential: dict[str, Any] = {
        "schema_version": "npi-real20-execution-lease-v1",
        "status": "APPROVED",
        "owner_id": "Jovi",
        "purpose": purpose,
        "not_before_utc": "2026-01-01T00:00:00Z",
        "expires_at_utc": (expires or datetime.now(UTC) + timedelta(hours=2))
        .isoformat()
        .replace("+00:00", "Z"),
        "bindings": {
            "candidate_commit": identity["candidate_commit"],
            "candidate_tree": identity["candidate_tree"],
            "project_state_sha256": identity["project_state_sha256"],
            "manifest_sha256": manifest_hash,
            "source_fingerprint_sha256": sha256(b"test-source-fingerprint"),
            "runtime_identity_sha256": sha256(canonical(runtime)),
            "model_identity_sha256": sha256(canonical(model)),
            "facts_schema_version": "1.2",
        },
        "scope": {
            "max_assets": 20,
            "max_unique_inferences": 19,
            "max_runs": 1,
            "exif_allowlist": list(EXIF_ALLOWLIST),
        },
        "boundaries": {
            "real_photo_read": True,
            "real_exif_read": True,
            "source_mutation": False,
            "acl_change": False,
            "sqlite_write": False,
            "app_write": False,
            "production_bundle": False,
            "model_download": False,
            "model_replacement": False,
            "n2b2_unlock": False,
            "push_merge_release": False,
        },
        "production_n2b2": "LOCKED",
    }
    credential_path = tmp_path / "credential.json"
    credential_path.write_bytes(canonical(credential))
    anchor = {
        "schema_version": "npi-real20-owner-anchor-v1",
        "status": "APPROVED",
        "owner_id": "Jovi",
        "purpose": "REAL20_READ_ONLY_EVALUATION",
        "credential_sha256": sha256(credential_path.read_bytes()),
        "production_unlock": False,
        "n2b2": "LOCKED",
    }
    anchor_path = tmp_path / "anchor.json"
    anchor_path.write_bytes(canonical(anchor))
    return {
        "credential": credential_path,
        "anchor": anchor_path,
        "runtime": runtime_path,
        "model": model_path,
        "ledger": tmp_path / "ledger",
        "output": tmp_path / "output",
    }


def _run(
    project: Path,
    source: Path,
    manifest: Path,
    controls: dict[str, Path],
    backend: CountingBackend,
    *,
    revalidate: Any = None,
) -> dict[str, Any]:
    controls["ledger"].mkdir(exist_ok=True)
    controls["output"].mkdir(exist_ok=True)
    return run_real20(
        project_root=project,
        source_root=source,
        manifest_path=manifest,
        credential_path=controls["credential"],
        anchor_path=controls["anchor"],
        runtime_identity_path=controls["runtime"],
        model_identity_path=controls["model"],
        ledger_root=controls["ledger"],
        output_root=controls["output"],
        backend_factory=lambda: backend,
        runtime_probe=backend.runtime_attestation,
        capability_probe=lambda *_: True,
        revalidate=revalidate,
    )


def _terminal(ledger: Path, credential_sha: str) -> dict[str, Any]:
    from nightly_photo_intelligence_pipeline.real20.ledger import read_terminal_record
    from nightly_photo_intelligence_pipeline.windows_bound_promotion import bind_existing_directory

    with (
        bind_existing_directory(ledger, writable=True, append_only=True) as root,
        root.open_directory(credential_sha, writable=True) as claim,
    ):
        return read_terminal_record(claim, credential_sha)


def test_prepare_is_draft_and_does_not_read_source(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    h3 = tmp_path / "h3.json"
    h3.write_bytes(
        canonical(
            {"h3_source": {"candidate": "ffc4130"}, "h3_closeout": {"ledger_status": "COMPLETE"}}
        )
    )
    output = tmp_path / "plan.json"

    result = prepare_real20(
        project_root=project,
        manifest_path=manifest_path,
        h3_provenance_path=h3,
        output_path=output,
        h3_candidate="ffc4130",
    )

    assert result["execution_authorized"] is False
    assert result["execution_draft"]["issued"] is False
    assert result["selection"]["canonical_count"] == 19
    assert str(source) not in output.read_text(encoding="utf-8")


def test_run_infers_each_unique_asset_once_and_keeps_n2b2_locked(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest_path)
    backend = CountingBackend()

    result = _run(project, source, manifest_path, controls, backend)

    assert result["status"] == "REAL20_COMPLETE"
    assert result["facts_schema_version"] == "1.2"
    assert result["asset_count"] == 20
    assert result["unique_inference_count"] == 19
    assert backend.pose_calls == 19
    assert backend.segmentation_calls == 38
    payload = json.loads((controls["output"] / "real20_result.json").read_text(encoding="utf-8"))
    assert payload["project_state_n2b2"] == "LOCKED"
    assert payload["assets"][-1]["action"] == "REFERENCE_ONLY"
    assert str(source) not in json.dumps(payload)
    assert _terminal(controls["ledger"], result["credential_sha256"])["status"] == "COMPLETE"


def test_synthetic_or_expired_credential_is_rejected_before_source_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(
        tmp_path, project, manifest_path, purpose="SYNTHETIC_S3_S20_ENGINEERING_VALIDATION"
    )
    controls["ledger"].mkdir()
    controls["output"].mkdir()
    from nightly_photo_intelligence_pipeline.real20 import runner

    monkeypatch.setattr(
        runner,
        "_source_bytes",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("opened")),
    )
    with pytest.raises(Real20Error, match="REAL20_CREDENTIAL_PURPOSE_INVALID"):
        _run(project, source, manifest_path, controls, CountingBackend())


def test_worker_failure_consumes_credential_and_second_run_is_denied(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest_path)
    first = CountingBackend(fail_on_pose=2)
    controls["ledger"].mkdir()
    controls["output"].mkdir()
    with pytest.raises(RuntimeError, match="worker failure"):
        _run(project, source, manifest_path, controls, first)
    credential_hash = sha256(controls["credential"].read_bytes())
    assert _terminal(controls["ledger"], credential_hash)["status"] == "FAILED"
    controls["output"] = controls["output"].parent / "second-output"
    controls["output"].mkdir()
    with pytest.raises(Real20Error, match="REAL20_CREDENTIAL_ALREADY_CONSUMED"):
        _run(project, source, manifest_path, controls, CountingBackend())


def test_real20_exif_only_returns_explicit_allowlist(tmp_path: Path) -> None:
    path = tmp_path / "exif.jpg"
    image = Image.new("RGB", (16, 16), (20, 30, 40))
    exif = image.getexif()
    exif[33434] = (1, 60)
    exif[34855] = 400
    exif[42035] = "secret-device"
    image.save(path, format="JPEG", exif=exif)

    result = read_real20_exif(path.read_bytes())

    assert set(result["fields"]) <= set(EXIF_ALLOWLIST)
    assert "secret-device" not in json.dumps(result)


def test_manifest_rejects_21st_entry_and_ads_path(tmp_path: Path) -> None:
    manifest_path, _, manifest = _manifest(tmp_path)
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    value["assets"].append(dict(value["assets"][0]))
    manifest_path.write_bytes(canonical(value))
    with pytest.raises(Real20Error, match="REAL20_EXACTLY_20_REQUIRED"):
        load_manifest(manifest_path)

    value["assets"] = manifest["assets"]
    value["assets"][0]["relative_path"] = "photo.jpg:secret"
    manifest_path.write_bytes(canonical(value))
    with pytest.raises(Real20Error, match="REAL20_ASSET_PATH_INVALID"):
        load_manifest(manifest_path)


def test_runtime_identity_drift_blocks_before_reservation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest_path)
    controls["ledger"].mkdir()
    controls["output"].mkdir()
    with pytest.raises(Real20Error, match="REAL20_RUNTIME_IDENTITY_DRIFT"):
        run_real20(
            project_root=project,
            source_root=source,
            manifest_path=manifest_path,
            credential_path=controls["credential"],
            anchor_path=controls["anchor"],
            runtime_identity_path=controls["runtime"],
            model_identity_path=controls["model"],
            ledger_root=controls["ledger"],
            output_root=controls["output"],
            backend_factory=CountingBackend,
            runtime_probe=lambda: {"drift": True},
            capability_probe=lambda *_: True,
        )
    assert not list(controls["ledger"].iterdir())


def test_wrong_candidate_binding_and_missing_worker_runtime_block_before_reservation(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest_path)
    credential = json.loads(controls["credential"].read_text(encoding="utf-8"))
    credential["bindings"]["candidate_commit"] = "0" * 40
    controls["credential"].write_bytes(canonical(credential))
    anchor = json.loads(controls["anchor"].read_text(encoding="utf-8"))
    anchor["credential_sha256"] = sha256(controls["credential"].read_bytes())
    controls["anchor"].write_bytes(canonical(anchor))
    controls["ledger"].mkdir()
    controls["output"].mkdir()
    with pytest.raises(Real20Error, match="REAL20_CREDENTIAL_BINDING_MISMATCH"):
        _run(project, source, manifest_path, controls, CountingBackend())
    assert not list(controls["ledger"].iterdir())

    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    controls = _controls(runtime_root, project, manifest_path)
    controls["ledger"].mkdir()
    controls["output"].mkdir()
    with pytest.raises(Real20Error, match="REAL20_WORKER_RUNTIME_UNAVAILABLE"):
        run_real20(
            project_root=project,
            source_root=source,
            manifest_path=manifest_path,
            credential_path=controls["credential"],
            anchor_path=controls["anchor"],
            runtime_identity_path=controls["runtime"],
            model_identity_path=controls["model"],
            ledger_root=controls["ledger"],
            output_root=controls["output"],
            backend_factory=CountingBackend,
            runtime_probe=lambda: (_ for _ in ()).throw(
                Real20Error("REAL20_WORKER_RUNTIME_UNAVAILABLE")
            ),
            capability_probe=lambda *_: True,
        )
    assert not list(controls["ledger"].iterdir())


def test_source_mutation_after_worker_fails_and_is_recorded(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest_path)
    controls["ledger"].mkdir()
    controls["output"].mkdir()
    with pytest.raises(Real20Error, match="REAL20_SOURCE_INTEGRITY_CHANGED"):
        _run(project, source, manifest_path, controls, MutatingBackend(source / "photo-00.jpg"))
    credential_hash = sha256(controls["credential"].read_bytes())
    failure = json.loads((controls["output"] / "real20_failure.json").read_text(encoding="utf-8"))
    assert failure["error_code"] == "REAL20_SOURCE_INTEGRITY_CHANGED"
    assert _terminal(controls["ledger"], credential_hash)["status"] == "FAILED"


def test_actual_cli_path_uses_explicit_synthetic_test_mode(tmp_path: Path) -> None:
    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest_path)
    controls["ledger"].mkdir()
    controls["output"].mkdir()
    env = {"PYTHONPATH": str(Path(__file__).parents[1] / "src")}
    command = [
        sys.executable,
        "-m",
        "nightly_photo_intelligence_pipeline",
        "real20",
        "run",
        "--project-root",
        str(project),
        "--source-root",
        str(source),
        "--manifest",
        str(manifest_path),
        "--credential",
        str(controls["credential"]),
        "--anchor",
        str(controls["anchor"]),
        "--runtime-identity",
        str(controls["runtime"]),
        "--model-identity",
        str(controls["model"]),
        "--ledger-root",
        str(controls["ledger"]),
        "--output-root",
        str(controls["output"]),
        "--backend",
        "fake",
        "--synthetic-test-mode",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={**__import__("os").environ, **env},
    )
    assert completed.returncode != 0
    assert "REAL20_FAKE_BACKEND_TEST_ONLY" in completed.stderr
    assert not list(controls["ledger"].iterdir())


def test_runtime_guard_checks_claim_parent_before_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nightly_photo_intelligence_pipeline.real20 import admission, runner

    project = _project(tmp_path)
    manifest_path, source, _ = _manifest(tmp_path)
    controls = _controls(tmp_path, project, manifest_path)
    backend = CountingBackend()
    model = json.loads(controls["model"].read_bytes())
    runtime = json.loads(controls["runtime"].read_bytes())
    runtime["models"] = model
    controls["runtime"].write_bytes(canonical(runtime))
    credential = json.loads(controls["credential"].read_bytes())
    credential["bindings"]["runtime_identity_sha256"] = sha256(canonical(runtime))
    credential_bytes = canonical(credential)
    controls["credential"].write_bytes(credential_bytes)
    anchor = json.loads(controls["anchor"].read_bytes())
    anchor["credential_sha256"] = sha256(credential_bytes)
    controls["anchor"].write_bytes(canonical(anchor))
    backend.runtime_attestation = lambda: runtime
    parent_checks: list[Any] = []
    original = admission.protect_consumption

    def observe_parent(handle: Any) -> None:
        result = handle.parent_access_check(0x00000040)
        parent_checks.append(result)
        original(handle)

    def unexpected_source_open(*_args: Any, **_kwargs: Any) -> bytes:
        raise AssertionError("source image opened before the ledger mutation gate")

    monkeypatch.setattr(admission, "protect_consumption", observe_parent)
    monkeypatch.setattr(runner, "_source_bytes", unexpected_source_open)
    with pytest.raises(Real20Error, match="REAL20_LEDGER_MUTATION_NOT_DENIED"):
        _run(project, source, manifest_path, controls, backend, revalidate=lambda *_: None)
    assert len(parent_checks) == 1
    assert parent_checks[0].granted is True and parent_checks[0].win32_error is None
    assert backend.pose_calls == 0
    credential_sha = sha256(controls["credential"].read_bytes())
    assert _terminal(controls["ledger"], credential_sha)["status"] == "FAILED"
