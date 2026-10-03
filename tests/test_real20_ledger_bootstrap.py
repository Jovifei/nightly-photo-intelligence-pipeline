from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.real20 import ledger_bootstrap
from nightly_photo_intelligence_pipeline.real20.control_plane import (
    BOOTSTRAP_EVIDENCE_LEAF,
    LEDGER_LEAF,
    PROBE_ROOT_LEAF,
    Real20ControlPlanePlan,
)


class _File:
    def __init__(self, parent: "_Directory", name: str) -> None:
        self.parent = parent
        self.name = name

    def __enter__(self) -> "_File":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read_all(self, *, max_bytes: int) -> bytes:
        return self.parent.files[self.name][:max_bytes]


class _Directory:
    def __init__(self, digest: str, *, policy: str = "c" * 64) -> None:
        self.identity = SimpleNamespace(digest=digest)
        self.policy = policy
        self.children: dict[str, _Directory] = {}
        self.files: dict[str, bytes] = {}

    def __enter__(self) -> "_Directory":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def _verify(self) -> None:
        return None

    def security_policy_digest(self) -> str:
        return self.policy

    def open_directory(self, name: str, *, writable: bool | None = None) -> "_Directory":
        del writable
        if name not in self.children:
            raise FileNotFoundError(name)
        return self.children[name]

    def open_file(self, name: str) -> _File:
        if name not in self.files:
            raise FileNotFoundError(name)
        return _File(self, name)


def _plan(tmp_path: Path) -> Real20ControlPlanePlan:
    runtime = tmp_path / "runtime"
    return Real20ControlPlanePlan(
        runtime_parent=runtime,
        work_root=runtime / "work",
        cache_root=tmp_path / "cache",
        configuration_digest="f" * 64,
        ledger_root=runtime / LEDGER_LEAF,
        probe_root=runtime / PROBE_ROOT_LEAF,
        bootstrap_evidence=runtime / BOOTSTRAP_EVIDENCE_LEAF,
    )


def test_missing_fixed_objects_reports_owner_bootstrap_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path)
    parent = _Directory("1" * 64)
    monkeypatch.setattr(ledger_bootstrap, "load_control_plane_plan", lambda _root: plan)
    monkeypatch.setattr(ledger_bootstrap, "bind_existing_directory", lambda *_a, **_k: parent)

    result = ledger_bootstrap.check_ledger_bootstrap(tmp_path)

    assert result == {
        "status": "OWNER_BOOTSTRAP_REQUIRED",
        "error_code": "REAL20_CONTROL_PLANE_OBJECT_MISSING",
    }


def test_exact_bootstrap_evidence_is_required_for_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path)
    parent = _Directory("1" * 64)
    ledger = _Directory("2" * 64)
    probe = _Directory("3" * 64)
    parent.children[LEDGER_LEAF] = ledger
    parent.children[PROBE_ROOT_LEAF] = probe
    monkeypatch.setattr(ledger_bootstrap, "load_control_plane_plan", lambda _root: plan)
    monkeypatch.setattr(ledger_bootstrap, "bind_existing_directory", lambda *_a, **_k: parent)

    result = ledger_bootstrap.check_ledger_bootstrap(tmp_path)

    assert result == {
        "status": "NOT_READY",
        "error_code": "REAL20_BOOTSTRAP_EVIDENCE_MISSING",
    }


def test_bootstrap_evidence_object_binding_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = _plan(tmp_path)
    parent = _Directory("1" * 64)
    ledger = _Directory("2" * 64)
    probe = _Directory("3" * 64)
    parent.children[LEDGER_LEAF] = ledger
    parent.children[PROBE_ROOT_LEAF] = probe
    parent.files[BOOTSTRAP_EVIDENCE_LEAF] = (
        b'{"schema_version":"npi-real20-control-plane-bootstrap-v1",'
        b'"status":"BOOTSTRAP_BOUND",'
        b'"runtime_configuration_digest":"' + b"f" * 64 + b'",'
        b'"ledger_object_sha256":"' + b"9" * 64 + b'",'
        b'"probe_root_object_sha256":"' + b"3" * 64 + b'",'
        b'"ledger_policy_sha256":"' + b"c" * 64 + b'",'
        b'"probe_policy_sha256":"' + b"c" * 64 + b'"}'
    )
    monkeypatch.setattr(ledger_bootstrap, "load_control_plane_plan", lambda _root: plan)
    monkeypatch.setattr(ledger_bootstrap, "bind_existing_directory", lambda *_a, **_k: parent)

    result = ledger_bootstrap.check_ledger_bootstrap(tmp_path)

    assert result == {
        "status": "NOT_READY",
        "error_code": "REAL20_BOOTSTRAP_EVIDENCE_MISMATCH",
    }


@pytest.mark.parametrize("option", ["--ledger-path", "--probe-path", "--cleanup-path"])
def test_cli_has_no_arbitrary_control_plane_path_options(
    tmp_path: Path, option: str
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "real20",
            "ledger-bootstrap-check",
            "--project-root",
            str(tmp_path),
            option,
            str(tmp_path / "other"),
        ],
    )

    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_cli_bootstrap_check_redacts_runtime_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nightly_photo_intelligence_pipeline import real20

    monkeypatch.setattr(
        real20,
        "check_ledger_bootstrap",
        lambda _root: {
            "status": "NOT_READY",
            "error_code": "REAL20_BOOTSTRAP_EVIDENCE_MISSING",
        },
    )
    result = CliRunner().invoke(
        app,
        ["real20", "ledger-bootstrap-check", "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 1
    assert "REAL20_BOOTSTRAP_EVIDENCE_MISSING" in result.output
    assert str(tmp_path) not in result.output
