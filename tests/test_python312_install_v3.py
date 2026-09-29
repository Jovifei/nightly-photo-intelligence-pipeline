from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _load(schema_rel: str, doc_rel: str) -> tuple[dict, dict]:
    schema = json.loads((ROOT / schema_rel).read_text(encoding="utf-8"))
    document = yaml.safe_load((ROOT / doc_rel).read_text(encoding="utf-8"))
    return schema, document


def test_install_v3_is_concrete_offline_approval() -> None:
    schema, document = _load(
        "schemas/owner_python312_environment_install_v3.schema.json",
        "approvals/owner_python312_environment_install_v3.yaml",
    )
    assert list(Draft202012Validator(schema).iter_errors(document)) == []
    assert document["interpreter_binding"]["version"] == "3.12.10"
    assert document["execution_authority"]["network_access"] == "DENY"


def test_install_v3_rejects_interpreter_or_wheelhouse_drift() -> None:
    schema, document = _load(
        "schemas/owner_python312_environment_install_v3.schema.json",
        "approvals/owner_python312_environment_install_v3.yaml",
    )
    forged = copy.deepcopy(document)
    forged["interpreter_binding"]["executable_sha256"] = "0" * 64
    assert list(Draft202012Validator(schema).iter_errors(forged))
    forged = copy.deepcopy(document)
    forged["wheelhouse_binding"]["manifest_sha256"] = "0" * 64
    assert list(Draft202012Validator(schema).iter_errors(forged))
