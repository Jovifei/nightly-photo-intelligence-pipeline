from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.errors import GateNotAuthorizedError
from nightly_photo_intelligence_pipeline.n2b1p_reprovision import (
    _historical_artifacts,
    _historical_runtime,
    check_python312_tooling_control_plane,
    check_reprovision_control_plane,
    validate_b_source_record,
    validate_owner_provisioned_root,
    validate_reprovision_document,
)


def _draft(project_root: Path) -> dict[str, object]:
    return yaml.safe_load(
        (project_root / "tasks" / "phase_n2b1p_cache_reprovision_v1.yaml").read_text(
            encoding="utf-8"
        )
    )


def _validate(project_root: Path, document: dict[str, object]) -> None:
    configuration_digest, cache_identity = _historical_runtime(project_root)
    validate_reprovision_document(
        document,
        historical_configuration_digest=configuration_digest,
        historical_cache_root_identity=cache_identity,
        historical_artifacts=_historical_artifacts(project_root),
    )


def test_route_b_and_python312_control_planes_are_ready_but_not_executable(
    project_root: Path,
) -> None:
    route_b = check_reprovision_control_plane(project_root)
    tooling = check_python312_tooling_control_plane(project_root)

    assert route_b["status"] == "ROUTE_B_CONTROL_PLANE_READY"
    assert route_b["execution_authority"] == "NOT_AUTHORIZED"
    assert route_b["network_access"] == "DENY"
    assert tooling["status"] == "PY312_TOOLING_CONTROL_PLANE_READY"
    assert tooling["execution_authority"] == "NOT_AUTHORIZED"
    assert tooling["installation"] == "NOT_AUTHORIZED"


def test_cli_rejects_caller_supplied_cache_or_quarantine_paths(project_root: Path) -> None:
    for command in ("reprovision-check", "tooling-check"):
        result = CliRunner().invoke(
            app,
            ["n2b1p", command, "--project-root", str(project_root), "--cache-root", "other"],
        )
        assert result.exit_code != 0
        assert "no such option" in result.output.lower()


def test_route_b_rejects_legacy_configuration_tampering(project_root: Path) -> None:
    document = _draft(project_root)
    superseded = dict(document["superseded_runtime_configuration"])
    superseded["configuration_digest"] = "0" * 64
    document["superseded_runtime_configuration"] = superseded

    with pytest.raises(GateNotAuthorizedError, match="configuration digest"):
        _validate(project_root, document)


def test_route_b_rejects_fourth_or_changed_artifact(project_root: Path) -> None:
    document = _draft(project_root)
    artifacts = list(document["artifacts"])
    artifacts.append(copy.deepcopy(artifacts[0]))
    document["artifacts"] = artifacts
    with pytest.raises(GateNotAuthorizedError, match="exactly three"):
        _validate(project_root, document)

    document = _draft(project_root)
    changed = [dict(item) for item in document["artifacts"]]
    changed[0]["byte_count"] = int(changed[0]["byte_count"]) + 1
    document["artifacts"] = changed
    with pytest.raises(GateNotAuthorizedError, match="historical binding"):
        _validate(project_root, document)


def test_route_b_rejects_network_enabled_b_cache(project_root: Path) -> None:
    document = _draft(project_root)
    authorities = copy.deepcopy(document["authorities"])
    authorities["b_cache"]["network_access"] = "ALLOW"
    document["authorities"] = authorities

    with pytest.raises(GateNotAuthorizedError, match="B-cache authority"):
        _validate(project_root, document)


@pytest.mark.parametrize(
    "field,value",
    [
        ("empty", False),
        ("non_reparse", False),
        ("outside_runtime", False),
        ("outside_source", False),
        ("outside_quarantine", False),
        ("identity_matches", False),
    ],
)
def test_owner_root_attestation_fails_closed(field: str, value: object) -> None:
    attestation: dict[str, object] = {
        "status": "OWNER_PREPROVISIONED",
        "empty": True,
        "non_reparse": True,
        "outside_runtime": True,
        "outside_source": True,
        "outside_quarantine": True,
        "identity_matches": True,
        "object_identity_sha256": "a" * 64,
    }
    attestation[field] = value
    with pytest.raises(GateNotAuthorizedError):
        validate_owner_provisioned_root(attestation)


def test_missing_b_source_record_blocks_b_cache() -> None:
    with pytest.raises(GateNotAuthorizedError, match="B-source evidence"):
        validate_b_source_record({"status": "NOT_AUTHORIZED", "artifacts": []})


def test_tooling_check_does_not_create_or_install(monkeypatch, project_root: Path) -> None:
    def forbidden(*_args, **_kwargs):
        raise AssertionError("control-plane check attempted filesystem mutation")

    monkeypatch.setattr(Path, "mkdir", forbidden)
    result = check_python312_tooling_control_plane(project_root)
    assert result["status"] == "PY312_TOOLING_CONTROL_PLANE_READY"
