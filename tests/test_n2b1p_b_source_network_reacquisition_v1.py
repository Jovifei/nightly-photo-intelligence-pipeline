from __future__ import annotations

import copy
import hashlib
import json
import socket
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline import n2b1p_b_source_network as network
from nightly_photo_intelligence_pipeline.cli import app

TASK_PATH = "tasks/phase_n2b1p_b_source_network_reacquisition_v1.yaml"
OWNER_PATH = "approvals/owner_n2b1p_b_source_network_reacquisition_v1.yaml"
RUNTIME_PATH = "approvals/n2b1p_b_source_network_runtime_configuration_v1.json"
REGISTER_PATH = "research/N2B1R_local_research_artifact_register.json"

def _git_text(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _valid_review_receipt(project_root: Path) -> dict[str, object]:
    baseline = yaml.safe_load(
        (project_root / "approvals/phase_completion_N2B1P.yaml").read_text(encoding="utf-8")
    )
    return {
        "schema_version": "1.0",
        "receipt_type": "EXTERNAL_EXACT_SHA_REVIEW_RECEIPT_V1",
        "task_id": "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1",
        "review_scope": "B_SOURCE_NETWORK_REACQUISITION_V1_CONTROL_PACKET_ONLY",
        "verdict": "DONE",
        "reviewed_head": _git_text(project_root, "rev-parse", "HEAD"),
        "reviewed_tree": _git_text(project_root, "rev-parse", "HEAD^{tree}"),
        "immutable_baseline_commit": baseline["baseline"]["candidate_commit"],
        "current_manifest_sha256": hashlib.sha256(
            (project_root / "MANIFEST.sha256").read_bytes()
        ).hexdigest(),
        "task_sha256": hashlib.sha256((project_root / TASK_PATH).read_bytes()).hexdigest(),
        "owner_approval_sha256": hashlib.sha256(
            (project_root / OWNER_PATH).read_bytes()
        ).hexdigest(),
        "runtime_configuration_sha256": hashlib.sha256(
            (project_root / RUNTIME_PATH).read_bytes()
        ).hexdigest(),
        "review_report_ref": "review_tools/NEXT_LOCAL_CODEX_PROMPT.md",
        "review_report_sha256": hashlib.sha256(
            (project_root / "review_tools/NEXT_LOCAL_CODEX_PROMPT.md").read_bytes()
        ).hexdigest(),
        "reviewed_at_utc": "2026-09-30T00:00:00Z",
    }


QUARANTINE_ATTESTATION_FLAGS = (
    "empty",
    "non_reparse",
    "outside_git",
    "outside_runtime",
    "outside_source",
    "outside_photo_source",
    "outside_cache",
    "outside_cache_root",
    "outside_route_b_cache_root",
    "outside_historical_cache_root",
    "outside_quality_python_venv",
    "outside_python_venv",
    "outside_historical_runtime_parent",
    "outside_historical_runtime_work",
    "outside_prior_quarantine",
)


def test_network_packet_is_ready_for_review_but_never_authorizes_execution(
    project_root: Path,
) -> None:
    result = network.check_b_source_network_control_packet(project_root)
    task = yaml.safe_load((project_root / TASK_PATH).read_text(encoding="utf-8"))
    owner = yaml.safe_load((project_root / OWNER_PATH).read_text(encoding="utf-8"))

    assert result["status"] == "B_SOURCE_NETWORK_REACQUISITION_READY_FOR_EXTERNAL_REVIEW"
    assert task["phase"]["id"] == "N2B1P"
    assert task["capability"] == "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
    assert task["review_candidate"]["task_id"] == "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
    assert owner["approval_type"] == "OWNER_N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
    for document in (task, owner):
        quarantine = document["quarantine"]
        assert quarantine["attestation_version"] == "V2"
        assert quarantine["attestation_ref"] == (
            "E_CLAUDE_ALLOW_DOWNLOAD/npi-n2b1p-b-source-quarantine-20260930-e9110783.attestation-v2.json"
        )
        assert quarantine["attestation_sha256"] == (
            "27d298c6f7b2ea146f8668edd3c7a4af75b5b9a9cfae0a9ab767ce666acc37e0"
        )
        assert all(quarantine[flag] is True for flag in QUARANTINE_ATTESTATION_FLAGS)
        assert quarantine["historical_runtime_configuration_sha256"] == (
            "f8d6a2779f85a2944d60b2a94ff99c392f45fe5adefbfead3441a3ce72fa682b"
        )
        assert quarantine["historical_cache_root_ref"] == (
            "E_CLAUDE_ALLOW_DOWNLOAD/npi-model-cache"
        )
        assert quarantine["photo_source_ref"] == "F_NPI_G1_SOURCE"
    assert result["scope_status"] == "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"
    assert result["task_status"] == "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"
    assert result["owner_status"] == "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"
    assert result["runtime_status"] == "DRAFT_NOT_AUTHORIZED"
    assert result["execution_status"] == "NOT_RUN"
    assert result["execution_authority"] == "NOT_AUTHORIZED"
    assert result["network_access"] == "DENY"
    assert result["pre_download_external_review"] == "PASS_REQUIRED"
    assert result["mandatory_stop"] == (
        "EXTERNAL_REVIEW_B_SOURCE_NETWORK_REACQUISITION_V1_PRE_DOWNLOAD"
    )
    assert result["artifact_count"] == 3


def test_cli_network_check_reports_contract_only_status(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", denied_network)
    monkeypatch.setattr(socket, "create_connection", denied_network)
    result = CliRunner().invoke(
        app,
        ["n2b1p", "network-check", "--project-root", str(project_root)],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["network_access"] == "DENY"
    assert payload["execution_authority"] == "NOT_AUTHORIZED"
    assert payload["execution_status"] == "NOT_RUN"


def _patch_document(
    monkeypatch: pytest.MonkeyPatch,
    *,
    loader_name: str,
    relative_path: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    original = getattr(network, loader_name)

    def patched(project_root: Path, path: str) -> dict[str, Any]:
        value = original(project_root, path)
        if path != relative_path:
            return value
        changed = copy.deepcopy(dict(value))
        mutate(changed)
        return changed

    monkeypatch.setattr(network, loader_name, patched)


def _artifact(task: dict[str, Any]) -> dict[str, Any]:
    return next(
        item
        for item in task["artifacts"]
        if item["id"] == "torchvision-keypointrcnn-resnet50-fpn-coco-v1"
    )


@pytest.mark.parametrize(
    ("loader_name", "relative_path", "mutate"),
    [
        (
            "_load_yaml",
            TASK_PATH,
            lambda doc: doc["artifacts"].append(copy.deepcopy(doc["artifacts"][0])),
        ),
        (
            "_load_yaml",
            TASK_PATH,
            lambda doc: _artifact(doc).__setitem__("url", "https://evil.test/a.pth"),
        ),
        (
            "_load_yaml",
            TASK_PATH,
            lambda doc: _artifact(doc).__setitem__("local_sha256", "0" * 64),
        ),
        (
            "_load_yaml",
            TASK_PATH,
            lambda doc: _artifact(doc).__setitem__("byte_count", 237034794),
        ),
        (
            "_load_json",
            RUNTIME_PATH,
            lambda doc: doc["allowed_request_domains"].append("evil.test"),
        ),
        (
            "_load_json",
            RUNTIME_PATH,
            lambda doc: doc["allowed_final_domains"].append("evil.test"),
        ),
        (
            "_load_json",
            RUNTIME_PATH,
            lambda doc: doc.__setitem__("quarantine_root_ref", "E_CLAUDE_ALLOW_DOWNLOAD/other"),
        ),
        (
            "_load_json",
            RUNTIME_PATH,
            lambda doc: doc.__setitem__("quarantine_root_identity_sha256", "0" * 64),
        ),
        (
            "_load_json",
            RUNTIME_PATH,
            lambda doc: doc.__setitem__("configuration_digest", "0" * 64),
        ),
        (
            "_load_yaml",
            TASK_PATH,
            lambda doc: doc["quarantine"].pop("outside_photo_source"),
        ),
        (
            "_load_json",
            RUNTIME_PATH,
            lambda doc: doc.__setitem__("outside_quality_python_venv", False),
        ),
    ],
    ids=[
        "extra-artifact",
        "url-drift",
        "hash-drift",
        "size-drift",
        "extra-request-domain",
        "extra-final-domain",
        "path-drift",
        "identity-drift",
        "digest-drift",
        "missing-outside-photo-source",
        "false-outside-quality-python-venv",
    ],
)


def test_post_review_admission_binds_exact_current_head_and_report(project_root: Path) -> None:
    receipt = _valid_review_receipt(project_root)
    result = network.validate_external_exact_sha_review_receipt(project_root, receipt)
    assert result["status"] == "B_SOURCE_NETWORK_POST_REVIEW_ADMISSION_PASS"
    assert result["network_request_count"] == 0
    assert result["cache_promotion"] == "NOT_AUTHORIZED"
    stale = dict(receipt)
    stale["reviewed_head"] = "0" * 40
    with pytest.raises(network.GateNotAuthorizedError, match="reviewed_head"):
        network.validate_external_exact_sha_review_receipt(project_root, stale)
    blocked = dict(receipt)
    blocked["verdict"] = "CHANGES_REQUIRED"
    with pytest.raises(network.GateNotAuthorizedError, match="not DONE"):
        network.validate_external_exact_sha_review_receipt(project_root, blocked)


def test_cli_network_admission_reads_only_external_exact_receipt(
    project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def denied_network(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket, "socket", denied_network)
    monkeypatch.setattr(socket, "create_connection", denied_network)
    evidence_root = tmp_path / "npi-c2c-evidence-20260930"
    evidence_root.mkdir()
    receipt_path = evidence_root / "b-source-network-exact-sha-review-v1.json"
    receipt_path.write_text(
        json.dumps(_valid_review_receipt(project_root), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    result = CliRunner().invoke(
        app,
        [
            "n2b1p",
            "network-admission",
            "--project-root",
            str(project_root),
            "--review-receipt",
            str(receipt_path),
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "B_SOURCE_NETWORK_POST_REVIEW_ADMISSION_PASS"
    assert payload["network_request_count"] == 0


def test_network_packet_fails_closed_on_binding_drift(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    loader_name: str,
    relative_path: str,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    _patch_document(
        monkeypatch,
        loader_name=loader_name,
        relative_path=relative_path,
        mutate=mutate,
    )

    result = network.check_b_source_network_control_packet(project_root)

    assert result["status"] == "B_SOURCE_NETWORK_REACQUISITION_INVALID"
    assert result["network_access"] == "DENY"
    assert result["execution_authority"] == "NOT_AUTHORIZED"


def test_network_packet_rejects_tampered_historical_register(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_document(
        monkeypatch,
        loader_name="_load_json",
        relative_path=REGISTER_PATH,
        mutate=lambda document: document["artifacts"][0].__setitem__(
            "official_url", "https://evil.test/weights.pth"
        ),
    )
    result = network.check_b_source_network_control_packet(project_root)

    assert result["status"] == "B_SOURCE_NETWORK_REACQUISITION_INVALID"
    assert result["network_access"] == "DENY"


def test_network_packet_fails_closed_when_schema_bytes_drift(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = network._sha256_file

    def altered_digest(root: Path, relative: str) -> str:
        if relative == "schemas/n2b1p_b_source_network_runtime_configuration_v1.schema.json":
            return "0" * 64
        return original(root, relative)

    monkeypatch.setattr(network, "_sha256_file", altered_digest)
    result = network.check_b_source_network_control_packet(project_root)

    assert result["status"] == "B_SOURCE_NETWORK_REACQUISITION_INVALID"
    assert result["network_access"] == "DENY"
    assert result["execution_authority"] == "NOT_AUTHORIZED"


@pytest.mark.parametrize("flag", QUARANTINE_ATTESTATION_FLAGS)
@pytest.mark.parametrize("invalid_mode", ["missing", "false"])
def test_quarantine_scope_rejects_missing_or_false_outside_flags(
    flag: str,
    invalid_mode: str,
) -> None:
    flags = dict.fromkeys(QUARANTINE_ATTESTATION_FLAGS, True)
    if invalid_mode == "missing":
        flags.pop(flag)
    else:
        flags[flag] = False
    with pytest.raises(network.GateNotAuthorizedError):
        network._validate_quarantine_scope_flags(flags)
