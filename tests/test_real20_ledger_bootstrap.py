from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.real20.ledger_bootstrap import (
    check_ledger_bootstrap,
)


def _project(tmp_path: Path, runtime: Path) -> Path:
    project = tmp_path / "project"
    (project / "approvals").mkdir(parents=True)
    (project / "PROJECT_STATE.json").write_text(
        json.dumps({"phase_status": {"N2B2": "LOCKED"}}), encoding="utf-8"
    )
    (project / "approvals" / "n2b1p_runtime_configuration.json").write_text(
        json.dumps({"runtime_parent": str(runtime), "cache_root": str(tmp_path / "cache")}),
        encoding="utf-8",
    )
    return project


def test_missing_real20_ledger_reports_owner_preprovision_required(tmp_path: Path) -> None:
    project = _project(tmp_path, tmp_path / "runtime")
    (tmp_path / "runtime").mkdir()

    result = check_ledger_bootstrap(project)

    assert result == {
        "status": "OWNER_PREPROVISION_REQUIRED",
        "error_code": "REAL20_LEDGER_ROOT_MISSING",
    }
    assert not (tmp_path / "runtime" / "real20-execution-ledger").exists()


def test_differently_named_ledger_is_never_reused(tmp_path: Path) -> None:
    project = _project(tmp_path, tmp_path / "runtime")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "n2b2-controlled-execution-ledger").mkdir()

    result = check_ledger_bootstrap(project)

    assert result["status"] == "OWNER_PREPROVISION_REQUIRED"
    assert result["error_code"] == "REAL20_LEDGER_ROOT_MISSING"


def test_existing_ledger_without_probe_envelope_is_not_ready(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, tmp_path / "runtime")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    ledger = runtime / "real20-execution-ledger"
    ledger.mkdir()

    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.real20.ledger_bootstrap._verify_ledger_policy",
        lambda _ledger: None,
    )

    result = check_ledger_bootstrap(project)

    assert result == {
        "status": "PROBE_CONFIGURATION_NOT_AVAILABLE",
        "error_code": "REAL20_LEDGER_PROBE_NOT_AVAILABLE",
    }


def test_cli_missing_probe_fails_closed_with_redacted_json(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, tmp_path / "runtime")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "real20-execution-ledger").mkdir()

    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.real20.ledger_bootstrap._verify_ledger_policy",
        lambda _ledger: None,
    )

    result = CliRunner().invoke(
        app,
        ["real20", "ledger-bootstrap-check", "--project-root", str(project)],
    )

    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "status": "PROBE_CONFIGURATION_NOT_AVAILABLE",
        "error_code": "REAL20_LEDGER_PROBE_NOT_AVAILABLE",
    }
    assert str(runtime) not in result.stdout


def test_existing_ledger_with_unknown_policy_fails_closed(tmp_path: Path, monkeypatch) -> None:
    project = _project(tmp_path, tmp_path / "runtime")
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "real20-execution-ledger").mkdir()

    def fail_policy(_ledger: Path) -> None:
        raise OSError("unknown security descriptor")

    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.real20.ledger_bootstrap._verify_ledger_policy",
        fail_policy,
    )

    assert check_ledger_bootstrap(project) == {
        "status": "OBJECT_OR_POLICY_MISMATCH",
        "error_code": "REAL20_LEDGER_POLICY_INVALID",
    }


def test_cli_has_no_arbitrary_ledger_path_option(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "real20",
            "ledger-bootstrap-check",
            "--project-root",
            str(tmp_path),
            "--ledger-path",
            str(tmp_path / "other-ledger"),
        ],
    )

    assert result.exit_code != 0
    assert "no such option" in result.output.lower()


def test_cli_resolves_relative_project_root(monkeypatch, tmp_path: Path) -> None:
    project = _project(tmp_path, tmp_path / "runtime")
    (tmp_path / "runtime").mkdir()
    monkeypatch.chdir(project)

    result = CliRunner().invoke(
        app,
        ["real20", "ledger-bootstrap-check", "--project-root", "."],
    )

    assert result.exit_code == 1
    assert '"error_code": "REAL20_LEDGER_ROOT_MISSING"' in result.stdout
