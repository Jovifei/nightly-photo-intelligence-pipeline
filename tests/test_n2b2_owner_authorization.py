"""Owner authorization records for the bounded N2B2 synthetic candidate."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from nightly_photo_intelligence_pipeline.n2b2_synthetic.n2b1p_gate import (
    validate_bounded_synthetic_authorization,
)


def _load_yaml(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _validate(path: Path, schema_path: Path) -> dict[str, object]:
    value = _load_yaml(path)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value), key=lambda error: list(error.path)
    )
    assert not errors, errors[0].message if errors else "schema error"
    return value


def test_n2b1p_phase_completion_is_bound_to_current_candidate_and_state(project_root: Path) -> None:
    record = _validate(
        project_root / "approvals" / "phase_completion_N2B1P.yaml",
        project_root / "schemas" / "phase_completion_n2b1p_v1_0.schema.json",
    )
    state = json.loads((project_root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    assert record["phase_id"] == "N2B1P"
    assert record["status"] == "APPROVED"
    assert record["baseline"]["candidate_commit"] == "0fef0a8f6a2f2b2f75ce2fba3e3eef1e764037b8"
    assert record["baseline"]["parent_commit"] == "9b3d5a1cc4a6f81467ad98034ca8994d1ebab043"
    assert (
        record["baseline"]["project_state_sha256"]
        == hashlib.sha256((project_root / "PROJECT_STATE.json").read_bytes()).hexdigest()
    )
    assert state["phase_status"]["N2B2"] == "LOCKED"
    assert record["boundaries"]["n2b2_production_unlock"] is False


def test_n2b2_receipt_binds_n2b1p_completion_and_is_synthetic_only(project_root: Path) -> None:
    record = _validate(
        project_root / "approvals" / "owner_n2b2_synthetic_model_stack_validation.yaml",
        project_root / "schemas" / "owner_n2b2_synthetic_model_stack_v1_0.schema.json",
    )
    completion = project_root / "approvals" / "phase_completion_N2B1P.yaml"
    assert record["n2b1p_completion_sha256"] == hashlib.sha256(completion.read_bytes()).hexdigest()
    assert record["scope"] == "SYNTHETIC_GPU_S3_S20_ONLY"
    assert record["boundaries"] == {
        "real_photo": False,
        "real_exif": False,
        "g1_source": False,
        "sqlite": False,
        "real20": False,
        "project_state_mutation": False,
        "production_bundle": False,
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "REAL_PHOTO"),
        ("boundaries", {"real_photo": True}),
        ("boundaries", {"sqlite": True}),
        ("boundaries", {"project_state_mutation": True}),
    ],
)
def test_n2b2_receipt_rejects_scope_expansion(
    project_root: Path, field: str, value: object
) -> None:
    path = project_root / "approvals" / "owner_n2b2_synthetic_model_stack_validation.yaml"
    schema_path = project_root / "schemas" / "owner_n2b2_synthetic_model_stack_v1_0.schema.json"
    record = _load_yaml(path)
    mutated = copy.deepcopy(record)
    if field == "boundaries":
        mutated["boundaries"] = {**record["boundaries"], **value}
    else:
        mutated[field] = value
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert list(Draft202012Validator(schema).iter_errors(mutated))


def test_runtime_gate_accepts_bound_records_only(project_root: Path) -> None:
    completion_path = project_root / "approvals" / "phase_completion_N2B1P.yaml"
    receipt_path = project_root / "approvals" / "owner_n2b2_synthetic_model_stack_validation.yaml"
    state = json.loads((project_root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    ok, detail = validate_bounded_synthetic_authorization(
        _load_yaml(completion_path),
        _load_yaml(receipt_path),
        state,
        hashlib.sha256(completion_path.read_bytes()).hexdigest(),
    )
    assert ok, detail


def test_runtime_gate_rejects_receipt_hash_or_unlock_tampering(project_root: Path) -> None:
    completion_path = project_root / "approvals" / "phase_completion_N2B1P.yaml"
    receipt_path = project_root / "approvals" / "owner_n2b2_synthetic_model_stack_validation.yaml"
    state = json.loads((project_root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    completion = _load_yaml(completion_path)
    receipt = _load_yaml(receipt_path)
    receipt["n2b1p_completion_sha256"] = "0" * 64
    ok, detail = validate_bounded_synthetic_authorization(
        completion,
        receipt,
        state,
        hashlib.sha256(completion_path.read_bytes()).hexdigest(),
    )
    assert not ok
    assert "hash" in detail

    receipt = _load_yaml(receipt_path)
    receipt["boundaries"]["real_photo"] = True
    ok, detail = validate_bounded_synthetic_authorization(
        completion,
        receipt,
        state,
        hashlib.sha256(completion_path.read_bytes()).hexdigest(),
    )
    assert not ok
    assert "real_photo" in detail
