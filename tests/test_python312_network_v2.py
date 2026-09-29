from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("schema_path", "document_path"),
    [
        (
            "schemas/python312_tooling_network_approval_v2.schema.json",
            "tasks/tooling_python312_network_reacquisition_v2.yaml",
        ),
        (
            "schemas/owner_python312_network_reacquisition_v2.schema.json",
            "approvals/owner_python312_network_reacquisition_v2.yaml",
        ),
    ],
)
def test_bound_network_v2_documents_validate(schema_path: str, document_path: str) -> None:
    schema = json.loads((ROOT / schema_path).read_text(encoding="utf-8"))
    document = yaml.safe_load((ROOT / document_path).read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(document)) == []
    assert document["storage"]["non_reparse"] is True
    assert document["storage"]["outside_git"] is True
    assert document["storage"]["non_overlapping"] is True


def test_bound_network_v2_uses_concrete_storage_identity() -> None:
    task = yaml.safe_load(
        (ROOT / "tasks/tooling_python312_network_reacquisition_v2.yaml").read_text(encoding="utf-8")
    )
    assert task["storage"]["download_root_object_identity_sha256"] == (
        "08ecb7a0ebe151c1e4484f13177d534cbb2117745a3d9719f2b3338fa4285b90"
    )
    assert task["storage"]["path_attestation_sha256"] == (
        "6501002f9d0e144f2f19fb71e3b3bab1e0f290803e02df07c5f25815b5f9322f"
    )
    assert task["owner_authority"]["execution_requires_external_review"] is True
