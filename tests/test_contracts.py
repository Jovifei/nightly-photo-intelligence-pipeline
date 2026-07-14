"""Current-stage approval, project-state, and task-contract validation."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

from nightly_photo_intelligence_pipeline.domain.authorization import load_authorization
from nightly_photo_intelligence_pipeline.ingest.g1_contract import load_g1_approval


def _schema(root: Path, name: str) -> dict:
    return json.loads((root / "schemas" / name).read_text(encoding="utf-8"))


def _errors(schema: dict, value: object) -> list:
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return list(validator.iter_errors(value))


def test_current_mutable_contracts_validate_and_are_consistent(project_root: Path) -> None:
    state = json.loads((project_root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    approval = yaml.safe_load(
        (project_root / "approvals" / "data_gate_approval_G1.yaml").read_text(encoding="utf-8")
    )
    n1_completion = yaml.safe_load(
        (project_root / "approvals" / "phase_completion_N1.yaml").read_text(encoding="utf-8")
    )
    n1 = yaml.safe_load(
        (project_root / "tasks" / "phase_n1_ingest_state_machine.yaml").read_text(encoding="utf-8")
    )
    g1 = yaml.safe_load(
        (project_root / "tasks" / "gate_g1_calibration_20.yaml").read_text(encoding="utf-8")
    )
    task_index = json.loads((project_root / "tasks" / "index.json").read_text(encoding="utf-8"))
    assert not _errors(_schema(project_root, "project_state_v1_1.schema.json"), state)
    assert not _errors(_schema(project_root, "approval_record_v1_1.schema.json"), approval)
    assert not _errors(
        _schema(project_root, "phase_completion_approval_v1_0.schema.json"), n1_completion
    )
    task_schema = _schema(project_root, "task_contract_v1_1.schema.json")
    assert not _errors(task_schema, n1)
    assert not _errors(task_schema, g1)
    assert not _errors(_schema(project_root, "task_index_v1_1.schema.json"), task_index)
    auth = load_authorization(project_root)
    assert auth.phase_id == "N1" and auth.phase_authorized
    assert auth.phase_status == "APPROVED_COMPLETE"
    assert auth.n1_baseline_commit == approval["baselines"]["N1"]
    assert auth.data_gate_id == "G1_CALIBRATION_20" and auth.data_gate_authorized
    assert auth.max_assets == approval["max_assets"] == g1["data_gate"]["max_assets"]
    assert n1["completion_approval"] == "approvals/phase_completion_N1.yaml"
    assert g1["dependencies"]["n1_completion_approval"] == n1["completion_approval"]
    assert task_index["completed"][1]["completion_approval"] == n1["completion_approval"]
    assert n1_completion["baseline"]["n1_commit"] == auth.n1_baseline_commit
    load_g1_approval(project_root)


@pytest.mark.parametrize(
    ("document", "mutation"),
    [
        ("state", lambda value: value["phase_status"].update({"N2": "AUTHORIZED"})),
        ("state", lambda value: value["data_scope"].update({"max_assets": 21})),
        ("approval", lambda value: value.update({"status": "NOT_APPROVED"})),
        ("approval", lambda value: value["baselines"].update({"N1": "0" * 40})),
        ("approval", lambda value: value["explicit_exclusions"].remove("model_downloads")),
        ("approval", lambda value: value["automatic_invalidation"].remove("owner_revocation")),
        ("approval", lambda value: value.update({"approved_at": "2026-07-15T00:00:00+08:00"})),
        ("g1", lambda value: value["data_gate"].update({"max_assets": 100})),
        ("g1", lambda value: value.pop("dependencies")),
        ("g1", lambda value: value.pop("pre_content_read_requirements")),
        ("g1", lambda value: value.pop("mandatory_stop")),
        ("g1", lambda value: value.pop("explicit_exclusions")),
        ("state", lambda value: value["authorization"].update({"gps_access": "AUTHORIZED"})),
    ],
)
def test_current_contract_schema_rejects_scope_tampering(
    project_root: Path, document: str, mutation
) -> None:
    values = {
        "state": json.loads((project_root / "PROJECT_STATE.json").read_text(encoding="utf-8")),
        "approval": yaml.safe_load(
            (project_root / "approvals" / "data_gate_approval_G1.yaml").read_text(encoding="utf-8")
        ),
        "g1": yaml.safe_load(
            (project_root / "tasks" / "gate_g1_calibration_20.yaml").read_text(encoding="utf-8")
        ),
    }
    value = copy.deepcopy(values[document])
    mutation(value)
    schema_name = {
        "state": "project_state_v1_1.schema.json",
        "approval": "approval_record_v1_1.schema.json",
        "g1": "task_contract_v1_1.schema.json",
    }[document]
    assert _errors(_schema(project_root, schema_name), value)


@pytest.mark.parametrize(
    "exclusion",
    [
        "21st_or_off_manifest_asset",
        "n2_through_n8",
        "g2_or_g3",
        "pose_segmentation_vlm_embedding",
        "model_downloads",
        "cloud_processing",
        "openclaw",
        "system_configuration_changes",
        "main_app_changes",
        "git_push_merge_release",
    ],
)
def test_g1_task_schema_requires_every_exclusion(project_root: Path, exclusion: str) -> None:
    value = yaml.safe_load(
        (project_root / "tasks" / "gate_g1_calibration_20.yaml").read_text(encoding="utf-8")
    )
    value["explicit_exclusions"].remove(exclusion)
    assert _errors(_schema(project_root, "task_contract_v1_1.schema.json"), value)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update({"status": "NOT_APPROVED"}),
        lambda value: value["baseline"].update({"n1_commit": "0" * 40}),
        lambda value: value["independent_reviewer"].update({"reviewed_commit": "0" * 40}),
    ],
)
def test_n1_completion_approval_schema_rejects_chain_tampering(
    project_root: Path, mutation
) -> None:
    value = yaml.safe_load(
        (project_root / "approvals" / "phase_completion_N1.yaml").read_text(encoding="utf-8")
    )
    mutation(value)
    assert _errors(_schema(project_root, "phase_completion_approval_v1_0.schema.json"), value)
