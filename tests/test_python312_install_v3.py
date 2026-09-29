from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from nightly_photo_intelligence_pipeline.python312_install_gate import (
    validate_interpreter_binding,
)

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
    assert document["pre_install_revalidation"]["required_before_venv"] is True
    assert document["pre_install_revalidation"]["only_then_create_venv"] is True
    assert document["pre_install_revalidation"]["target_venv_under_download_root"] is True
    assert document["pre_install_revalidation"]["target_venv_outside_git_worktree"] is True
    assert document["pre_install_revalidation"]["wheelhouse_manifest_under_root"] is True


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


def test_pre_install_interpreter_revalidation_rejects_drift() -> None:
    observed = {
        "sha256": "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a",
        "size": 104952,
        "version": "3.12.10",
        "platform": "win_amd64",
        "abi": "cp312",
        "venv_module_available": True,
        "pip_module_available": True,
        "system_python_unchanged": True,
        "target_venv_separate": True,
    }
    validate_interpreter_binding(observed)
    observed["size"] = 1
    try:
        validate_interpreter_binding(observed)
    except ValueError as error:
        assert "size" in str(error)
    else:  # pragma: no cover - explicit fail-closed assertion
        raise AssertionError("interpreter size drift was accepted")
