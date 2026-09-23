"""Focused default-entry and failure-lifecycle regressions (no ML execution).

Native handles are explicit test doubles; Windows handle/ACL acceptance remains
in the existing native suite. These tests do not replace the full CLI suite.
"""
from __future__ import annotations

import json
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from nightly_photo_intelligence_pipeline.real20 import admission, runner
from nightly_photo_intelligence_pipeline.real20.contracts import Real20Error


def public_arguments(tmp_path: Path) -> dict[str, Any]:
    result = {name: tmp_path / name for name in (
        "source_root", "manifest_path", "credential_path", "anchor_path",
        "runtime_identity_path", "model_identity_path", "ledger_root", "output_root", "cache_root",
    )}
    result["project_root"] = Path(runner.__file__).resolve().parents[3]
    return result


def test_public_denial_precedes_inner_runtime_and_factory(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[str] = []

    def deny(**_kwargs: Any) -> dict[str, Any]:
        calls.append("admission")
        raise Real20Error("REAL20_INDEPENDENT_REVIEW_REQUIRED")

    def not_reached(*_args: Any, **_kwargs: Any) -> Any:
        calls.append("unapproved_runtime")
        raise AssertionError("Runtime/factory must be unreachable on admission denial")

    monkeypatch.setattr(admission, "admit", deny)
    monkeypatch.setattr(runner, "_run_real20", not_reached)
    monkeypatch.setattr(runner, "default_backend_factory", not_reached)
    with pytest.raises(Real20Error, match="INDEPENDENT_REVIEW"):
        runner.run_real20(**public_arguments(tmp_path))
    assert calls == ["admission"]


def test_revalidation_keeps_path_and_handle_separate(tmp_path: Path, monkeypatch: Any) -> None:
    calls: list[dict[str, Any]] = []
    bound = object()
    args = public_arguments(tmp_path)

    def admit(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {"same": "verified-controls"}

    def inner(**kwargs: Any) -> dict[str, Any]:
        kwargs["revalidate"](bound)
        return {"status": "SIMULATED_ONLY"}

    monkeypatch.setattr(admission, "admit", admit)
    monkeypatch.setattr(runner, "_run_real20", inner)
    monkeypatch.setattr(runner, "default_backend_factory", lambda *_a, **_k: None)
    assert runner.run_real20(**args)["status"] == "SIMULATED_ONLY"
    assert len(calls) == 2
    assert all(call["ledger_root"] == args["ledger_root"] for call in calls)
    assert calls[0].get("bound_ledger") is None
    assert calls[1]["bound_ledger"] is bound


def test_revalidation_compares_to_original_admission(tmp_path: Path, monkeypatch: Any) -> None:
    responses = iter(({"anchor": "original"}, {"anchor": "changed"}))
    monkeypatch.setattr(admission, "admit", lambda **_kwargs: next(responses))
    monkeypatch.setattr(runner, "default_backend_factory", lambda *_a, **_k: None)

    def inner(**kwargs: Any) -> dict[str, Any]:
        kwargs["revalidate"](object())
        return {}

    monkeypatch.setattr(runner, "_run_real20", inner)
    with pytest.raises(Real20Error, match="ADMISSION_CHANGED"):
        runner.run_real20(**public_arguments(tmp_path))


@pytest.mark.parametrize("fault", [OSError("synthetic I/O"), TypeError("synthetic type"), KeyboardInterrupt()])
def test_failed_attempt_independent_checks_and_terminal(fault: BaseException, monkeypatch: Any) -> None:
    events: list[str] = []
    primary = RuntimeError("synthetic runner failure")

    def bad_check() -> None:
        events.append("bad_check")
        raise fault

    monkeypatch.setattr(runner, "_write_bound_new", lambda *_a: events.append("evidence") or b"failure")
    monkeypatch.setattr(runner, "_finish", lambda *_a, **kw: events.append(kw["status"]))
    with pytest.raises(BaseExceptionGroup) as caught:
        runner._record_failed_attempt(
            object(), object(), "a" * 64, primary=primary,
            checks=[bad_check, lambda: events.append("next_check")],
        )
    assert events == ["bad_check", "next_check", "evidence", "FAILED"]
    assert caught.value.exceptions == (primary, fault)


def test_evidence_failure_does_not_skip_terminal(monkeypatch: Any) -> None:
    terminal: list[dict[str, Any]] = []
    primary = ValueError("fake primary")

    def fail(*_args: Any) -> bytes:
        raise OSError("synthetic evidence device error")

    monkeypatch.setattr(runner, "_write_bound_new", fail)
    monkeypatch.setattr(runner, "_finish", lambda *_a, **kw: terminal.append(kw))
    with pytest.raises(ExceptionGroup) as caught:
        runner._record_failed_attempt(object(), object(), "a" * 64, primary=primary, checks=[])
    assert caught.value.exceptions[0] is primary
    assert terminal == [{"status": "FAILED", "evidence_sha": None, "evidence_status": "PERSISTENCE_FAILED"}]


def test_terminal_failure_retains_original_and_integrity_errors(monkeypatch: Any) -> None:
    primary = RuntimeError("synthetic primary")
    terminal_error = OSError("synthetic disk failure")
    monkeypatch.setattr(runner, "_write_bound_new", lambda *_a: b"failure")

    def fail(*_a: Any, **_k: Any) -> None:
        raise terminal_error

    monkeypatch.setattr(runner, "_finish", fail)
    with pytest.raises(ExceptionGroup) as caught:
        runner._record_failed_attempt(object(), object(), "a" * 64, primary=primary, checks=[])
    assert caught.value.exceptions == (primary, terminal_error)


def test_failure_record_redacts_exception_messages(monkeypatch: Any) -> None:
    records: list[dict[str, Any]] = []
    monkeypatch.setattr(runner, "_write_bound_new", lambda _d, _n, p: records.append(p) or b"failure")
    monkeypatch.setattr(runner, "_finish", lambda *_a, **_k: None)
    with pytest.raises(OSError):
        runner._record_failed_attempt(
            object(), object(), "a" * 64, primary=OSError("PRIVATE/source/photo.jpg"), checks=[],
        )
    assert "PRIVATE" not in json.dumps(records)
    assert records[0]["failure_types"] == ["OSError"]


class MemoryHandle:
    def __init__(self, directory: Any, name: str, *, fail_write: bool = False) -> None:
        self.directory, self.name, self.fail_write = directory, name, fail_write

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *_args: Any) -> None:
        return None

    def write(self, data: bytes) -> None:
        if self.fail_write:
            raise OSError("synthetic reservation write failure")
        self.directory.files[self.name] = data

    def flush(self) -> None:
        return None

    def read_all(self, *, max_bytes: int) -> bytes:
        return self.directory.files[self.name][:max_bytes]


class MemoryDirectory:
    def __init__(self, *, fail_write: bool = False) -> None:
        self.files: dict[str, bytes] = {}
        self.children: dict[str, MemoryDirectory] = {}
        self.fail_write = fail_write
        self.closed = False

    def __enter__(self) -> Any:
        return self

    def __exit__(self, *_args: Any) -> None:
        self.close()

    def create_directory(self, name: str) -> Any:
        if name in self.children:
            raise FileExistsError(name)
        child = MemoryDirectory(fail_write=self.fail_write)
        self.children[name] = child
        return child

    def create_file(self, name: str) -> MemoryHandle:
        if name in self.files:
            raise FileExistsError(name)
        return MemoryHandle(self, name, fail_write=self.fail_write)

    def open_file(self, name: str) -> MemoryHandle:
        return MemoryHandle(self, name)

    def list_names(self) -> set[str]:
        return set(self.files) | set(self.children)

    def close(self) -> None:
        self.closed = True


def test_partial_reservation_attempts_failed_terminal_and_retains_claim(monkeypatch: Any) -> None:
    ledger = MemoryDirectory(fail_write=True)
    terminal: list[tuple[Any, dict[str, Any]]] = []
    monkeypatch.setattr(runner, "_finish", lambda handle, **kw: terminal.append((handle, kw)))
    with pytest.raises(OSError):
        runner._reservation(ledger, "a" * 64, "b" * 64, datetime.now(UTC))
    child = ledger.children["a" * 64]
    assert child.closed
    assert len(terminal) == 1 and terminal[0][0] is child
    assert terminal[0][1]["status"] == "FAILED"
    with pytest.raises(Real20Error, match="ALREADY_CONSUMED"):
        runner._reservation(ledger, "a" * 64, "b" * 64, datetime.now(UTC))


def test_partial_reservation_terminal_error_is_not_hidden(monkeypatch: Any) -> None:
    ledger = MemoryDirectory(fail_write=True)

    def fail(*_a: Any, **_kw: Any) -> None:
        raise RuntimeError("synthetic terminal fault")

    monkeypatch.setattr(runner, "_finish", fail)
    with pytest.raises(ExceptionGroup) as caught:
        runner._reservation(ledger, "a" * 64, "b" * 64, datetime.now(UTC))
    assert {type(e) for e in caught.value.exceptions} == {OSError, RuntimeError}
    assert ledger.children["a" * 64].closed


def test_successful_reservation_is_returned_open() -> None:
    ledger = MemoryDirectory()
    child = runner._reservation(ledger, "a" * 64, "b" * 64, datetime.now(UTC))
    assert not child.closed
    assert json.loads(child.files["reservation.json"])["status"] == "RESERVED"
    child.close()


def test_exitstack_attempts_every_close_after_one_close_error() -> None:
    events: list[str] = []

    def close_bad() -> None:
        events.append("bad")
        raise OSError("synthetic close fault")

    with pytest.raises(OSError), ExitStack() as stack:
        stack.callback(lambda: events.append("first"))
        stack.callback(close_bad)
        stack.callback(lambda: events.append("last"))
    assert events == ["last", "bad", "first"]


def test_admit_uses_configured_path_in_plan_and_validates_bound_object(tmp_path: Path, monkeypatch: Any) -> None:
    from hashlib import sha256 as digest
    from datetime import timedelta

    def canonical(value: Any) -> bytes:
        return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()

    def hash_bytes(data: bytes) -> str:
        return digest(data).hexdigest()

    project, runtime, source, cache, out = [tmp_path / key for key in ("project", "runtime", "source", "cache", "out")]
    trusted = runtime / "owner-approvals"
    ledger = runtime / "real20-execution-ledger"
    identity = {"candidate_commit": "a" * 40, "candidate_tree": "b" * 40, "source_manifest_sha256": "c" * 64}
    handles: list[Any] = []

    class Bound:
        def __init__(self, identity: str = "native-object") -> None:
            self.identity = identity
            self.verified = False

        def _verify(self) -> None:
            self.verified = True

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *_args: Any) -> None:
            return None

    passed_handle = Bound()
    monkeypatch.setattr(admission, "BoundDirectory", Bound)
    monkeypatch.setattr(admission, "bind_existing_directory", lambda *_a, **_kw: Bound())
    monkeypatch.setattr(admission, "protect_consumption", lambda handle: handles.append(handle))
    monkeypatch.setattr(admission, "candidate_identity", lambda _p: identity)
    monkeypatch.setattr(admission, "path_fingerprint", lambda _p: "source-fingerprint")
    monkeypatch.setattr(admission, "quality_matrix", lambda *_a, **_kw: {"complete": True})
    monkeypatch.setattr(admission, "validate_data_receipt", lambda _value: None)
    monkeypatch.setattr(admission, "verify_source_read_only_capability", lambda *_a: SimpleNamespace(verified=True))
    checked: list[Path] = []

    def checked_path(path: Path, **_kw: Any) -> None:
        assert isinstance(path, Path), "A native handle must never be passed as a Path"
        checked.append(path)

    monkeypatch.setattr(admission, "checked_path", checked_path)
    monkeypatch.setattr(admission, "overlaps", lambda _a, _b: False)
    manifest = SimpleNamespace(sha256="d" * 64, source_fingerprint="source-fingerprint",
                               assets=[SimpleNamespace(relative_path="item.jpg")])
    monkeypatch.setattr(admission, "load_manifest", lambda _p: manifest)
    frozen, credential = b"item.jpg\n", b"fake-test-credential"
    monkeypatch.setattr(admission, "FROZEN_G1", hash_bytes(frozen))
    now = datetime.now(UTC)
    documents = {
        "data_receipt": {"not_before_utc": (now - timedelta(hours=1)).isoformat(),
                         "expires_at_utc": (now + timedelta(hours=1)).isoformat(),
                         "source_root_fingerprint": "source-fingerprint", "manifest_sha256": manifest.sha256,
                         "frozen_manifest_sha256": hash_bytes(frozen)},
        "code_review": {**identity, "verdict": "PASS_FOR_REAL20_EVALUATION"},
        "quality": {"checks": [], "python_supported": True, "status": "PASS", "candidate_commit": identity["candidate_commit"]},
    }
    plan = {"source_root": str(source), "output_root": str(out), "ledger_root": str(ledger), "cache_root": str(cache)}
    anchor = {
        **identity, "status": "APPROVED", "owner_id": "Jovi", "purpose": "REAL20_READ_ONLY_EVALUATION",
        "production_unlock": False, "credential_sha256": hash_bytes(credential),
        "h3_review_sha256": admission.H3_REVIEW, "path_plan_sha256": hash_bytes(canonical(plan)),
        **{label + "_sha256": hash_bytes(canonical(value)) for label, value in documents.items()},
    }
    content = {
        project / "approvals/n2b1p_runtime_configuration.json": canonical({"runtime_parent": str(runtime), "cache_root": str(cache)}),
        project / "schemas/n2b2_real20_owner_anchor_v1.schema.json": b"{}",
        trusted / "real20_execution_anchor.json": canonical(anchor),
        trusted / "real20_frozen_manifest.txt": frozen,
        trusted / "real20_lease.json": credential,
        **{trusted / ("real20_" + label + ".json"): canonical(value) for label, value in documents.items()},
    }
    # This test isolates path/handle behavior, not validation of a real permit.
    monkeypatch.setattr(admission, "control_bytes", lambda path: content.get(path, b"{}"))
    kwargs = dict(project_root=project, source_root=source, manifest_path=trusted / "real20_manifest.json",
                  credential_path=trusted / "real20_lease.json", anchor_path=trusted / "real20_execution_anchor.json",
                  ledger_root=ledger, output_root=out, cache_root=cache,
                  runtime_identity_path=trusted / "real20_runtime_identity.json",
                  model_identity_path=trusted / "real20_model_identity.json")
    first = admission.admit(**kwargs)
    second = admission.admit(**kwargs, bound_ledger=passed_handle)
    assert first == second and passed_handle.verified
    assert handles[-1] is passed_handle and ledger in checked
    with pytest.raises(Real20Error, match="LEDGER_OBJECT_CHANGED"):
        admission.admit(**kwargs, bound_ledger=Bound("different-native-object"))
    with pytest.raises(Real20Error, match="LEDGER_PATH_REQUIRED"):
        admission.admit(**{**kwargs, "ledger_root": passed_handle})
