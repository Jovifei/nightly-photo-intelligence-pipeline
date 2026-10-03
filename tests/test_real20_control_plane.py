from __future__ import annotations

import inspect
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.json_strict import load_json_strict
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
        return None

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

    def open_directory_for_cleanup(self, name: str) -> "FakeDirectory":
        return self.open_directory(name, writable=True)

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


def test_external_authority_must_bind_exact_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nightly_photo_intelligence_pipeline.real20 import admission

    plan = _plan(tmp_path)
    authority = {
        "schema_version": "npi-real20-control-plane-authority-v1",
        "status": "APPROVED",
        "owner_id": "Jovi",
        "scope": "R1_REAL20_CONTROL_PLANE_ONLY",
        "execution_authorized": True,
        "runtime_configuration_digest": plan.configuration_digest,
        "candidate_commit": "1" * 40,
        "candidate_tree": "2" * 40,
        "source_manifest_sha256": "3" * 64,
        "allowed_operations": [
            "BOOTSTRAP_FIXED_LEDGER_AND_PROBE_ROOTS",
            "RUN_SYNTHETIC_LEDGER_INHERITANCE_PROBE",
            "CLEAN_SYNTHETIC_PROBE_BY_PREOPENED_HANDLE",
        ],
        "production_n2b2": "LOCKED",
    }
    monkeypatch.setattr(
        admission,
        "control_bytes",
        lambda _path: __import__("json").dumps(authority).encode("utf-8"),
    )
    monkeypatch.setattr(
        control_plane,
        "candidate_identity",
        lambda _root: {
            "candidate_commit": "1" * 40,
            "candidate_tree": "2" * 40,
            "source_manifest_sha256": "4" * 64,
        },
    )

    with pytest.raises(Real20Error, match="AUTHORITY_INVALID"):
        control_plane.require_control_plane_execution_authority(tmp_path, plan)


def test_external_authority_accepts_exact_candidate_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nightly_photo_intelligence_pipeline.real20 import admission

    plan = _plan(tmp_path)
    identity = {
        "candidate_commit": "1" * 40,
        "candidate_tree": "2" * 40,
        "source_manifest_sha256": "3" * 64,
    }
    authority = {
        "schema_version": "npi-real20-control-plane-authority-v1",
        "status": "APPROVED",
        "owner_id": "Jovi",
        "scope": "R1_REAL20_CONTROL_PLANE_ONLY",
        "execution_authorized": True,
        "runtime_configuration_digest": plan.configuration_digest,
        **identity,
        "allowed_operations": [
            "BOOTSTRAP_FIXED_LEDGER_AND_PROBE_ROOTS",
            "RUN_SYNTHETIC_LEDGER_INHERITANCE_PROBE",
            "CLEAN_SYNTHETIC_PROBE_BY_PREOPENED_HANDLE",
        ],
        "production_n2b2": "LOCKED",
    }
    monkeypatch.setattr(
        admission,
        "control_bytes",
        lambda _path: __import__("json").dumps(authority).encode("utf-8"),
    )
    monkeypatch.setattr(control_plane, "candidate_identity", lambda _root: identity)

    assert (
        control_plane.require_control_plane_execution_authority(tmp_path, plan)
        == authority
    )


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
    ) -> dict[str, str]:
        claim = next(iter(probe.children.values()))
        return cleanup_helper.cleanup_preopened_probe(
            claim,
            capability,
            expected_probe_nonce_sha256=expected_probe_nonce_sha256,
            now=NOW,
        )

    monkeypatch.setattr(ledger_probe, "_run_cleanup_helper_process", cleanup)
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
        "_run_cleanup_helper_process",
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


def test_cleanup_helper_process_inherits_only_bound_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    closed: list[int] = []

    class Startup:
        lpAttributeList: dict[str, list[int]]

    def run(command: list[str], **kwargs: Any) -> Any:
        captured["command"] = command
        captured["kwargs"] = kwargs
        proof = {
            "schema_version": "npi-real20-cleanup-proof-v1",
            "cleanup_status": "CLEANUP_PASS",
            "probe_nonce_sha256": "e" * 64,
            "probe_object_sha256": "d" * 64,
            "cleanup_identity_sha256": cleanup_helper.cleanup_helper_identity_sha256(),
            "cleaned_at_utc": "2026-10-03T12:00:01+00:00",
        }
        return SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(proof),
            stderr="",
        )

    monkeypatch.setattr(ledger_probe.sys, "platform", "win32")
    monkeypatch.setattr(ledger_probe.subprocess, "STARTUPINFO", Startup, raising=False)
    monkeypatch.setattr(ledger_probe.subprocess, "run", run)
    monkeypatch.setattr(ledger_probe, "close_preopened_handle", closed.append)

    capability = {
        "capability_version": "npi-real20-cleanup-capability-v1",
        "probe_nonce_sha256": "e" * 64,
        "probe_object_sha256": "d" * 64,
        "cleanup_identity_sha256": cleanup_helper.cleanup_helper_identity_sha256(),
        "expires_at_utc": "2026-10-03T13:00:00+00:00",
    }
    proof = ledger_probe._run_cleanup_helper_process(
        123,
        capability,
        expected_probe_nonce_sha256="e" * 64,
    )

    assert proof["cleanup_status"] == "CLEANUP_PASS"
    assert captured["kwargs"]["startupinfo"].lpAttributeList == {"handle_list": [123]}
    assert captured["kwargs"]["close_fds"] is True
    assert "--project-root" not in captured["command"]
    assert closed == [123]


def test_cleanup_helper_process_rejects_unbound_success_proof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Startup:
        lpAttributeList: dict[str, list[int]]

    def run(_command: list[str], **_kwargs: Any) -> Any:
        return SimpleNamespace(
            returncode=0,
            stdout=__import__("json").dumps(
                {
                    "schema_version": "npi-real20-cleanup-proof-v1",
                    "cleanup_status": "CLEANUP_PASS",
                    "probe_nonce_sha256": "9" * 64,
                    "probe_object_sha256": "d" * 64,
                    "cleanup_identity_sha256": cleanup_helper.cleanup_helper_identity_sha256(),
                    "cleaned_at_utc": "2026-10-03T12:00:01+00:00",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(ledger_probe.sys, "platform", "win32")
    monkeypatch.setattr(ledger_probe.subprocess, "STARTUPINFO", Startup, raising=False)
    monkeypatch.setattr(ledger_probe.subprocess, "run", run)
    monkeypatch.setattr(ledger_probe, "close_preopened_handle", lambda _handle: None)
    capability = {
        "capability_version": "npi-real20-cleanup-capability-v1",
        "probe_nonce_sha256": "e" * 64,
        "probe_object_sha256": "d" * 64,
        "cleanup_identity_sha256": cleanup_helper.cleanup_helper_identity_sha256(),
        "expires_at_utc": "2026-10-03T13:00:00+00:00",
    }

    with pytest.raises(Real20Error, match="CLEANUP_NOT_VERIFIED"):
        ledger_probe._run_cleanup_helper_process(
            123,
            capability,
            expected_probe_nonce_sha256="e" * 64,
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


def test_owner_authority_draft_is_schema_valid_but_not_authorized(project_root: Path) -> None:
    schema = load_json_strict(
        project_root / "schemas/owner_real20_control_plane_bootstrap_v1.schema.json"
    )
    value = load_json_strict(
        project_root / "approvals/owner_real20_control_plane_bootstrap_v1.DRAFT.json"
    )
    assert list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)
    ) == []
    assert value["status"] == "DRAFT_NOT_AUTHORIZED"
    assert value["execution_authorized"] is False


def test_bootstrap_and_probe_schemas_are_strict(project_root: Path) -> None:
    bootstrap_schema = load_json_strict(
        project_root / "schemas/real20_control_plane_bootstrap_evidence_v1.schema.json"
    )
    bootstrap = {
        "schema_version": "npi-real20-control-plane-bootstrap-v1",
        "status": "BOOTSTRAP_BOUND",
        "runtime_configuration_digest": "a" * 64,
        "ledger_object_sha256": "b" * 64,
        "probe_root_object_sha256": "c" * 64,
        "ledger_policy_sha256": "d" * 64,
        "probe_policy_sha256": "d" * 64,
    }
    assert list(
        Draft202012Validator(
            bootstrap_schema, format_checker=FormatChecker()
        ).iter_errors(bootstrap)
    ) == []

    probe_schema = load_json_strict(
        project_root / "schemas/real20_ledger_probe_result_v2.schema.json"
    )
    probe_result = {
        "schema_version": "npi-real20-ledger-probe-result-v2",
        "status": "ADMISSION_ELIGIBLE",
        "ledger_acl_probe": {
            "contract_version": "npi-real20-ledger-acl-probe-v2",
            "status": "ADMISSION_ELIGIBLE",
            "inheritance_status": "PROBE_PASS",
            "cleanup_status": "CLEANUP_PASS",
            "probe_nonce_sha256": "e" * 64,
            "runner_identity_sha256": "a" * 64,
            "cleanup_identity_sha256": "b" * 64,
            "ledger_policy_sha256": "c" * 64,
            "probe_policy_sha256": "c" * 64,
            "probe_object_sha256": "d" * 64,
            "ledger_object_sha256": "f" * 64,
            "created_at_utc": "2026-10-03T12:00:00Z",
            "expires_at_utc": "2026-10-03T12:20:00Z",
        },
        "cleanup_capability": {
            "capability_version": "npi-real20-cleanup-capability-v1",
            "probe_nonce_sha256": "e" * 64,
            "probe_object_sha256": "d" * 64,
            "cleanup_identity_sha256": "b" * 64,
            "expires_at_utc": "2026-10-03T12:20:00Z",
        },
        "cleanup_proof": {
            "schema_version": "npi-real20-cleanup-proof-v1",
            "cleanup_status": "CLEANUP_PASS",
            "probe_nonce_sha256": "e" * 64,
            "probe_object_sha256": "d" * 64,
            "cleanup_identity_sha256": "b" * 64,
            "cleaned_at_utc": "2026-10-03T12:00:01Z",
        },
    }
    assert list(
        Draft202012Validator(
            probe_schema, format_checker=FormatChecker()
        ).iter_errors(probe_result)
    ) == []
