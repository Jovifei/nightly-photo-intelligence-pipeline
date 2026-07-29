"""Current local-research acquisition contract remains narrowly bounded."""

from __future__ import annotations

import copy
import json

import pytest
import yaml
from jsonschema import Draft202012Validator


def _read_json(project_root, rel: str) -> dict:
    return json.loads((project_root / rel).read_text(encoding="utf-8"))


def _schema_errors(project_root, name: str, document: object) -> list:
    schema = _read_json(project_root, f"schemas/{name}")
    return list(Draft202012Validator(schema).iter_errors(document))


def test_n2b1r_contracts_are_schema_valid_and_research_only(project_root) -> None:
    task = yaml.safe_load(
        (project_root / "tasks/phase_n2b1r_local_research_model_acquisition.yaml").read_text(
            encoding="utf-8"
        )
    )
    approval = yaml.safe_load(
        (project_root / "approvals/owner_local_research_execution_N2B1R_to_N5R.yaml").read_text(
            encoding="utf-8"
        )
    )
    register = _read_json(project_root, "research/N2B1R_local_research_artifact_register.json")
    assert not _schema_errors(project_root, "task_contract_n2b1r_v1_0.schema.json", task)
    assert not _schema_errors(
        project_root, "owner_local_research_execution_v1_0.schema.json", approval
    )
    assert not _schema_errors(project_root, "n2b1r_artifact_register_v1.schema.json", register)
    assert register["weights_rights"]["status"] == "UNKNOWN_NOT_COMMERCIAL_CLEARANCE"
    assert len(register["artifacts"]) == 3
    assert all(item["official_sha256"] is None for item in register["artifacts"])
    assert "model_load_or_inference" in task["forbidden"]
    assert "real_photo_read_or_directory_enumeration" in task["forbidden"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value["phase"].update({"status": "LOCKED"}),
        lambda value: value["data_gate"].update({"allowed_assets": "all photos"}),
        lambda value: value["approval"].update({"artifact_register": "other.json"}),
        lambda value: value["mandatory_stop"].update({"value": False}),
    ],
)
def test_n2b1r_task_schema_rejects_scope_tampering(project_root, mutate) -> None:
    task = yaml.safe_load(
        (project_root / "tasks/phase_n2b1r_local_research_model_acquisition.yaml").read_text(
            encoding="utf-8"
        )
    )
    mutate(task)
    assert _schema_errors(project_root, "task_contract_n2b1r_v1_0.schema.json", task)


def test_n2b1r_register_rejects_sha_or_domain_substitution(project_root) -> None:
    register = _read_json(project_root, "research/N2B1R_local_research_artifact_register.json")
    tampered = copy.deepcopy(register)
    tampered["artifacts"][0]["official_sha256"] = "0" * 64
    assert _schema_errors(project_root, "n2b1r_artifact_register_v1.schema.json", tampered)
    tampered = copy.deepcopy(register)
    tampered["artifacts"][0]["allowed_final_domains"] = ["mirror.invalid"]
    assert _schema_errors(project_root, "n2b1r_artifact_register_v1.schema.json", tampered)


def test_n2b1r_acquisition_evidence_is_redacted_and_schema_valid(project_root) -> None:
    evidence = _read_json(project_root, "research/N2B1R_acquisition_evidence.json")
    assert not _schema_errors(project_root, "n2b1r_acquisition_evidence_v1.schema.json", evidence)
    assert evidence["artifact_count"] == len(evidence["artifacts"]) == 3
    assert {item["id"] for item in evidence["artifacts"]} == {
        "torchvision-keypointrcnn-resnet50-fpn-coco-v1",
        "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
        "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1",
    }
    serialized = json.dumps(evidence, sort_keys=True)
    assert "\\\\" not in serialized
    assert "/home/" not in serialized
    assert evidence["prohibited_actions"] == {
        "cache_promotion": "NOT_PERFORMED",
        "dependency_install": "NOT_PERFORMED",
        "model_load_or_inference": "NOT_PERFORMED",
        "source_photo_or_exif_read": "NOT_PERFORMED",
        "sqlite_ingest_write": "NOT_PERFORMED",
        "derived_image_output": "NOT_PERFORMED",
    }
