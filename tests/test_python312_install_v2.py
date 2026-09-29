from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _validated(schema_rel: str, doc_rel: str) -> dict:
    schema = json.loads((ROOT / schema_rel).read_text(encoding="utf-8"))
    document = yaml.safe_load((ROOT / doc_rel).read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(document)) == []
    return document


def test_install_v2_is_offline_and_wheelhouse_bound() -> None:
    task = _validated(
        "schemas/python312_tooling_environment_install_v2.schema.json",
        "tasks/tooling_python312_environment_install_v2.yaml",
    )
    approval = _validated(
        "schemas/owner_python312_environment_install_v2.schema.json",
        "approvals/owner_python312_environment_install_v2.yaml",
    )
    assert task["network"]["access"] == "DENY"
    assert (
        task["wheelhouse"]["manifest_sha256"] == approval["wheelhouse_binding"]["manifest_sha256"]
    )
    assert approval["execution_authority"]["no_network_during_install"] is True


def test_install_v2_rejects_network_or_wheelhouse_drift() -> None:
    schema = json.loads(
        (ROOT / "schemas/owner_python312_environment_install_v2.schema.json").read_text(
            encoding="utf-8"
        )
    )
    approval = yaml.safe_load(
        (ROOT / "approvals/owner_python312_environment_install_v2.yaml").read_text(encoding="utf-8")
    )
    forged = copy.deepcopy(approval)
    forged["execution_authority"]["network_access"] = "ALLOW"
    assert list(Draft202012Validator(schema).iter_errors(forged))
    forged = copy.deepcopy(approval)
    forged["wheelhouse_binding"]["manifest_sha256"] = "0" * 64
    assert list(Draft202012Validator(schema).iter_errors(forged))
