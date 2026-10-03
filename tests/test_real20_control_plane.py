from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.real20 import cleanup_helper, control_plane
from nightly_photo_intelligence_pipeline.real20 import ledger_bootstrap, ledger_probe
from nightly_photo_intelligence_pipeline.real20.contracts import Real20Error

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


class FakeFile:
    def __init__(self, parent: "FakeDirectory", name: str) -> None:
        self.parent = parent
        self.name = name

    def __enter__(self) -> "FakeFile":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def write(self, data: bytes) -> None:
        self.parent.files[self.name] = data

    def flush(self) -> None:
        return None

    def read_all(self, *, max_bytes: int) -> bytes:
        return self.parent.files[self.name][:max_bytes]

    def access_check(self, desired_access: int) -> Any:
        if self.parent.unknown_access:
            return SimpleNamespace(granted=None, win32_error=87)
        return SimpleNamespace(granted=desired_access == 0x00000004, win32_error=None)

    def delete_owned(self) -> None:
        del self.parent.files[self.name]


class FakeDirectory:
    _next_handle = 100

    def __init__(
        self,
        digest: str,
        *,
        policy: str = "c" * 64,
        parent: "FakeDirectory | None" = None,
        name: str | None = None,
        unknown_access: bool = False,
        forbid_create: bool = False,
    ) -> None:
        self.identity = SimpleNamespace(digest=digest)
        self.policy = policy
        self.parent = parent
        self.name = name
        self.unknown_access = unknown_access
        self.forbid_create = forbid_create
        self.files: dict[str, bytes] = {}
        self.children: dict[str, FakeDirectory] = {}
        self.deleted = False
        self.closed = False

    def __enter__(self) -> "FakeDirectory":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _verify(self) -> None:
        if self.closed:
            raise AssertionError("closed fake handle")

    def close(self) -> None:
        self.closed = False

    def list_names(self) -> set[str]:
        return set(self.files) | set(self.children)

    def security_policy_digest(self) -> str:
        return self.policy

    def access_check(self, desired_access: int) -> Any:
        if self.unknown_access:
            return SimpleNamespace(granted=None, win32_error=87)
        return SimpleNamespace(granted=False, win32_error=None)

    def create_directory(self, name: str) -> "FakeDirectory":
        if self.forbid_create:
            raise AssertionError("production ledger claim namespace was touched")
        if name in self.children:
            raise FileExistsError(name)
        child = FakeDirectory(
            ("%064x" % (len(self.children) + 10))[-64:],
            policy=self.policy,
            parent=self,
            name=name,
            unknown_access=self.unknown_access,
        )
        self.children[name] = child
        return child

    def open_directory(self, name: str, *, writable: bool | None = None) -> "FakeDirectory":
        del writable
        return self.children[name]

    def create_file(self, name: str) -> FakeFile:
        if name in self.files:
            raise FileExistsError(name)
        self.files[name] = b""
        return FakeFile(self, name)

    def open_file(self, name: str) -> FakeFile:
        if name not in self.files:
            raise FileNotFoundError(name)
        return FakeFile(self, name)

    def open_file_for_cleanup(self, name: str) -> FakeFile:
        return self.open_file(name)

    def delete_owned_empty(self) -> None:
        if self.list_names():
            raise AssertionError("fake directory not empty")
        self.deleted = True
        if self.parent is not None and self.name is not None:
            self.parent.children.pop(self.name, None)

    def release_for_inheritance(self) -> tuple[int, str]:
        FakeDirectory._next_handle += 1
        return FakeDirectory._next_handle, self.identity.digest


def _plan(tmp_path: Path) -> control_plane.Real20ControlPlanePlan:
    runtime = tmp_path / "runtime"
    return control_plane.Real20ControlPlanePlan(
        runtime_parent=runtime,
        work_root=runtime / "work",
        cache_root=tmp_path / "cache",
        configuration_digest="f" * 64,
        ledger_root=runtime / control_plane.LEDGER_LEAF,
        probe_root=runtime / control_plane.PROBE_ROOT_LEAF,
        bootstrap_evidence=runtime / control_plane.BOOTSTRAP_EVIDENCE_LEAF,
    )


def _patch_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> control_plane.Real20ControlPlanePlan:
    plan = _plan(tmp_path)
    monkeypatch.setattr(ledger_bootstrap, "load_control_plane_plan", lambda _root: plan)
    monkeypatch.setattr(ledger_probe, "load_control_plane_plan", lambda _root: plan)
    monkeypatch.setattr(
        ledger_bootstrap, "require_control_plane_execution_authority", lambda *_args: {}
    )
    monkeypatch.setattr(
        ledger_probe, "require_control_plane_execution_authority", lambda *_args: {}
    )
    return plan


def test_trusted_plan_uses_only_fixed_runtime_children(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Path("F:" + chr(92) + "npi_runtime")
    config = SimpleNamespace(
        runtime_parent=runtime,
        work_root=runtime / "work",
        cache_root=Path("E:" + chr(92) + "cache"),
        configuration_digest="a" * 64,
    )
    monkeypatch.setattr(control_plane, "load_n2b1p_runtime_configuration", lambda _root: config)
    monkeypatch.setattr(control_plane, "paths_overlap", lambda *_args: False)

    plan = control_plane.load_control_plane_plan(Path("project"))

    assert plan.ledger_root.name == control_plane.LEDGER_LEAF
    assert plan.probe_root.name == control_plane.PROBE_ROOT_LEAF
    assert plan.bootstrap_evidence.name == control_plane.BOOTSTRAP_EVIDENCE_LEAF


def test_repository_draft_does_not_authorize_machine_execution(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    project = tmp_path / "project"
    (project / "approvals").mkdir(parents=True)
    (project / "approvals" / "owner_real20_control_plane_bootstrap_v1.DRAFT.json").write_text(
        "{}", encoding="utf-8"
    )
    with pytest.raises(Real20Error, match="AUTHORITY_REQUIRED"):
        control_plane.require_control_plane_execution_authority(project, plan)


def test_bootstrap_creates_fixed_objects_and_is_exactly_idempotent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    plan = _patch_plan(monkeypatch, tmp_path)
    parent = FakeDirectory("1" * 64, policy="c" * 64)
    monkeypatch.setattr(ledger_bootstrap, "bind_existing_directory", lambda *_a, **_k: parent)

    first = ledger_bootstrap.bootstrap_control_plane(tmp_path)
    second = ledger_bootstrap.bootstrap_control_plane(tmp_path)

    assert first["status"] == "BOOTSTRAP_CREATED"
    assert second["status"] == "BOOTSTRAP_ALREADY_BOUND"
    assert set(parent.children) == {control_plane.LEDGER_LEAF, control_plane.PROBE_ROOT_LEAF}
    assert set(parent.files) == {control_plane.BOOTSTRAP_EVIDENCE_LEAF}
    assert first["ledger_object_sha256"] == second["ledger_object_sha256"]
    assert first["probe_root_object_sha256"] == second["probe_root_object_sha256"]
    assert plan.configuration_digest == first["runtime_configuration_digest"]


def test_bootstrap_rejects_partial_preexisting_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_plan(monkeypatch, tmp_path)
    parent = FakeDirectory("1" * 64)
    parent.children[control_plane.LEDGER_LEAF] = FakeDirectory("2" * 64, parent=parent)
    monkeypatch.setattr(ledger_bootstrap, "bind_existing_directory", lambda *_a, **_k: parent)

    with pytest.raises(Real20Error, match="PARTIAL_STATE"):
        ledger_bootstrap.bootstrap_control_plane(tmp_path)


def _probe_fakes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    ledger_policy: str = "c" * 64,
    probe_policy: str = "c" * 64,
    unknown_access: bool = False,
) -> tuple[FakeDirectory, FakeDirectory]:
    plan = _patch_plan(monkeypatch, tmp_path)
    ledger = FakeDirectory("1" * 64, policy=ledger_policy, forbid_create=True)
    probe = FakeDirectory("2" * 64, policy=probe_policy, unknown_access=unknown_access)

    def bind(path: Path, **_kwargs: Any) -> FakeDirectory:
        if path == plan.ledger_root:
            return ledger
        if path == plan.probe_root:
            return probe
        raise AssertionError(f"unexpected bind {path!r}")

    monkeypatch.setattr(ledger_probe, "bind_existing_directory", bind)
    monkeypatch.setattr(
        ledger_probe, "check_ledger_bootstrap", lambda _root: {"status": "READY_EXISTING_CONTROL_PLANE"}
    )
    monkeypatch.setattr(ledger_probe, "current_process_identity_sha256", lambda: "a" * 64)
    from nightly_photo_intelligence_pipeline.real20 import admission

    monkeypatch.setattr(admission, "protect_consumption", lambda _handle: None)

    def cleanup(
        _raw_handle: int,
        capability: object,
        *,
        expected_probe_nonce_sha256: str,
        now: datetime,
    ) -> dict[str, str]:
        claim = next(iter(probe.children.values()))
        return cleanup_helper.cleanup_preopened_probe(
            claim,
            capability,
            expected_probe_nonce_sha256=expected_probe_nonce_sha256,
            now=now,
        )

    monkeypatch.setattr(ledger_probe, "cleanup_inherited_probe_handle", cleanup)
    return ledger, probe


def test_probe_produces_nonce_bound_admission_proof_without_real_ledger_claim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ledger, probe = _probe_fakes(monkeypatch, tmp_path)

    result = ledger_probe.run_ledger_probe(tmp_path, now=NOW, nonce_bytes=b"x" * 32)

    assert result["status"] == "ADMISSION_ELIGIBLE"
    proof = result["ledger_acl_probe"]
    capability = result["cleanup_capability"]
    assert proof["probe_nonce_sha256"] == capability["probe_nonce_sha256"]
    assert proof["probe_object_sha256"] == capability["probe_object_sha256"]
    assert proof["cleanup_identity_sha256"] == capability["cleanup_identity_sha256"]
    assert proof["ledger_object_sha256"] == ledger.identity.digest
    assert ledger.children == {}
    assert probe.children == {}


def test_probe_rejects_policy_mismatch_before_claim(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ledger, probe = _probe_fakes(
        monkeypatch, tmp_path, ledger_policy="c" * 64, probe_policy="d" * 64
    )
    with pytest.raises(Real20Error, match="POLICY_MISMATCH"):
        ledger_probe.run_ledger_probe(tmp_path, now=NOW, nonce_bytes=b"x" * 32)
    assert probe.children == {}


def test_probe_unknown_accesscheck_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ledger, probe = _probe_fakes(monkeypatch, tmp_path, unknown_access=True)
    with pytest.raises(Real20Error, match="DIRECTORY_RIGHTS_INVALID"):
        ledger_probe.run_ledger_probe(tmp_path, now=NOW, nonce_bytes=b"x" * 32)
    assert len(probe.children) == 1


def test_cleanup_failure_preserves_noneligible_probe_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ledger, probe = _probe_fakes(monkeypatch, tmp_path)
    monkeypatch.setattr(
        ledger_probe,
        "cleanup_inherited_probe_handle",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            Real20Error("REAL20_SYNTHETIC_CLEANUP_FAILURE")
        ),
    )

    result = ledger_probe.run_ledger_probe(tmp_path, now=NOW, nonce_bytes=b"x" * 32)

    assert result["status"] == "NOT_ADMISSION_ELIGIBLE"
    assert result["inheritance_status"] == "PROBE_PASS"
    assert result["cleanup_status"] == "CLEANUP_FAILED"
    assert result["error_code"] == "REAL20_SYNTHETIC_CLEANUP_FAILURE"
    assert len(probe.children) == 1


def _capability(claim: FakeDirectory, nonce_sha256: str) -> dict[str, str]:
    return {
        "capability_version": "npi-real20-cleanup-capability-v1",
        "probe_nonce_sha256": nonce_sha256,
        "probe_object_sha256": claim.identity.digest,
        "cleanup_identity_sha256": cleanup_helper.cleanup_helper_identity_sha256(),
        "expires_at_utc": "2026-10-03T13:00:00+00:00",
    }


def test_cleanup_helper_deletes_only_expected_children() -> None:
    nonce = "e" * 64
    root = FakeDirectory("1" * 64)
    claim = FakeDirectory("2" * 64, parent=root, name="probe")
    root.children["probe"] = claim
    claim.files["reservation.json"] = b"r"
    claim.files[f"terminal-v1-{nonce}.json"] = b"t"

    result = cleanup_helper.cleanup_preopened_probe(
        claim,
        _capability(claim, nonce),
        expected_probe_nonce_sha256=nonce,
        now=NOW,
    )

    assert result["cleanup_status"] == "CLEANUP_PASS"
    assert root.children == {}


def test_cleanup_helper_rejects_sibling_content() -> None:
    nonce = "e" * 64
    claim = FakeDirectory("2" * 64)
    claim.files["reservation.json"] = b"r"
    claim.files[f"terminal-v1-{nonce}.json"] = b"t"
    claim.files["unexpected.txt"] = b"x"

    with pytest.raises(Real20Error, match="CONTENT_MISMATCH"):
        cleanup_helper.cleanup_preopened_probe(
            claim,
            _capability(claim, nonce),
            expected_probe_nonce_sha256=nonce,
            now=NOW,
        )


def test_cleanup_helper_api_has_no_path_parameter() -> None:
    parameters = inspect.signature(cleanup_helper.cleanup_inherited_probe_handle).parameters
    assert "path" not in parameters
    assert "project_root" not in parameters
    assert set(parameters) == {
        "handle",
        "capability",
        "expected_probe_nonce_sha256",
        "now",
    }


@pytest.mark.parametrize("command", ["ledger-bootstrap", "ledger-probe", "ledger-probe-clean"])
def test_control_plane_cli_rejects_arbitrary_object_paths(tmp_path: Path, command: str) -> None:
    result = CliRunner().invoke(
        app,
        [
            "real20",
            command,
            "--project-root",
            str(tmp_path),
            "--probe-path",
            str(tmp_path / "other"),
        ],
    )
    assert result.exit_code != 0
    assert "no such option" in result.output.lower()
