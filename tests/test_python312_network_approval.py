from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _load(schema_rel: str, document_rel: str) -> tuple[dict, dict]:
    schema = json.loads((ROOT / schema_rel).read_text(encoding="utf-8"))
    document = yaml.safe_load((ROOT / document_rel).read_text(encoding="utf-8"))
    return schema, document


def _errors(schema: dict, document: dict) -> list[str]:
    return [error.message for error in Draft202012Validator(schema).iter_errors(document)]


def test_network_packet_is_valid_only_as_unbound_pre_execution_state() -> None:
    schema, document = _load(
        "schemas/owner_python312_network_reacquisition_v1.schema.json",
        "approvals/owner_python312_network_reacquisition_v1.yaml",
    )
    assert _errors(schema, document) == []
    assert document["status"] == "OWNER_AUTHORIZED_AWAITING_STORAGE_BINDING"
    assert document["execution_authority"]["owner_authorized"] is False
    assert document["storage"]["binding_status"] == "UNRESOLVED_OWNER_STORAGE_BINDING"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("status",), "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"),
        (("execution_authority", "owner_authorized"), True),
        (("storage", "binding_status"), "BOUND"),
    ],
)
def test_unresolved_storage_binding_cannot_be_promoted_by_field_edit(
    path: tuple[str, ...], value: object
) -> None:
    schema, document = _load(
        "schemas/owner_python312_network_reacquisition_v1.schema.json",
        "approvals/owner_python312_network_reacquisition_v1.yaml",
    )
    forged = copy.deepcopy(document)
    target = forged
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    assert _errors(schema, forged)


def test_wheelhouse_evidence_binds_control_plane_and_current_authority_hashes() -> None:
    schema = json.loads(
        (ROOT / "schemas/python312_wheelhouse_evidence_v1.schema.json").read_text(encoding="utf-8")
    )
    minimal = {
        "schema_version": "1.0",
        "status": "PY312_WHEELHOUSE_QUALIFIED_AWAITING_EXTERNAL_REVIEW",
        "control_plane_commit": "a2c338b2fe9467d9668566eadfe0b1fc094df526",
        "network_task_sha256": "0" * 64,
        "network_owner_approval_sha256": "0" * 64,
        "network_schema_sha256": "0" * 64,
    }
    errors = _errors(schema, minimal)
    assert any("interpreter" in error or "direct_pin_roots" in error for error in errors)
    forged = copy.deepcopy(minimal)
    forged["reviewed_code_commit"] = "0494e866efcd9a11329d3631d97b032dc1dd60b0"
    assert any("reviewed_code_commit" in error for error in _errors(schema, forged))
