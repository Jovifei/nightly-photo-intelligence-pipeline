"""N2B0.5 rights/provenance evidence and locked download boundary."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def _validate(project_root: Path, schema_name: str, value: object) -> None:
    schema = json.loads((project_root / "schemas" / schema_name).read_text("utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(value))


def test_n2b0_5_approval_and_contract_are_bound_to_immutable_n2b0(project_root: Path) -> None:
    approval = yaml.safe_load(
        (project_root / "approvals" / "phase_completion_N2B0.yaml").read_text("utf-8")
    )
    _validate(project_root, "phase_completion_approval_n2b0_v1_0.schema.json", approval)
    assert approval["owner_decision"] == "N2B0_OWNER_APPROVED"
    assert approval["baseline"]["n2b0_commit"] == "f331621c84905aef921c612908d01d3a8a2f577a"
    assert approval["baseline"]["n2b0_tag"] == "n2b0-approved-2026-07-24"

    contract = yaml.safe_load(
        (project_root / "tasks" / "phase_n2b0_5_artifact_rights_and_provenance.yaml").read_text(
            "utf-8"
        )
    )
    _validate(project_root, "task_contract_n2b0_5_v1_0.schema.json", contract)
    assert contract["capability"] == "N2B0_5_ARTIFACT_RIGHTS_AND_PROVENANCE_CLOSURE"


def test_n2b0_5_rights_matrix_is_complete_and_fail_closed(project_root: Path) -> None:
    draft = yaml.safe_load(
        (project_root / "config" / "model_artifact_allowlist.draft.yaml").read_text("utf-8")
    )
    assert draft["status"] == "DRAFT_NOT_AUTHORIZED"
    assert len(draft["artifacts"]) == 4
    assert {item["weights_license"] for item in draft["artifacts"]} == {"UNKNOWN"}
    assert {item["commercial_use_status"] for item in draft["artifacts"]} == {
        "REQUIRES_OWNER_DECISION"
    }
    assert {item["qualification_status"] for item in draft["artifacts"]} == {"INCONCLUSIVE"}
    assert {item["artifact_expected_size_bytes"] for item in draft["artifacts"]} == {
        72010049,
        129787113,
        11349952,
        249505,
    }

    for name in (
        "N2B0_5_mmpose_weights_rights.md",
        "N2B0_5_paddleseg_weights_rights.md",
        "N2B0_5_mediapipe_artifact_identity.md",
    ):
        text = (project_root / "research" / name).read_text("utf-8")
        for field in (
            "CODE_LICENSE_CONFIRMED",
            "WEIGHTS_LICENSE_CONFIRMED",
            "COMMERCIAL_USE_CONFIRMED",
            "ARTIFACT_IDENTITY_CONFIRMED",
            "IMMUTABLE_REVISION_CONFIRMED",
            "OFFICIAL_SIZE_CONFIRMED",
            "OFFICIAL_HASH_CONFIRMED",
            "DOWNLOAD_DOMAIN_CONFIRMED",
            "REDIRECT_CHAIN_CONFIRMED",
            "READY_FOR_QUARANTINE_DOWNLOAD",
        ):
            assert field in text
        assert "READY_FOR_QUARANTINE_DOWNLOAD` | FAIL" in text
        assert "WEIGHTS_LICENSE_CONFIRMED` | UNKNOWN" in text


def test_n2b0_5_state_locks_download_execution_and_photos(project_root: Path) -> None:
    state = json.loads((project_root / "PROJECT_STATE.json").read_text("utf-8"))
    assert state["phase_status"]["N0"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N1"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["G1"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2A"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_5"] == "AUTHORIZED"
    assert state["phase_status"]["N2B1"] == "LOCKED"
    assert state["phase_status"]["N2B1_Q"] == "LOCKED"
    assert state["phase_status"]["N2B1_P"] == "LOCKED"
    assert state["phase_status"]["N2B2"] == "LOCKED"
    assert state["authorization"]["large_model_downloads"] == "NOT_AUTHORIZED"
    assert state["authorization"]["real_model_execution"] == "NOT_AUTHORIZED"
    assert state["required_stop_after"] == {
        "condition": "N2B0_5_AWAITING_OWNER_APPROVAL",
        "next_action": "WAIT_FOR_OWNER_APPROVAL",
    }


def test_n2b0_5_provenance_has_no_payload_or_photo_access(project_root: Path) -> None:
    report = (project_root / "reports" / "N2B0_5_rights_and_provenance_summary.md").read_text(
        "utf-8"
    )
    assert "Model download bytes: 0" in report
    assert "model execution: 0" in report
    assert "real photo reads: 0" in report
    assert "N2B0_5_RIGHTS_CLARIFICATION_BLOCKED" in report
    assert "DRAFT_NOT_AUTHORIZED" in report
