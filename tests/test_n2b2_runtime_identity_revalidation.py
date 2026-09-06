"""Fail-closed tests for the one-shot Ollama 0.33.3 revalidation gate."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from nightly_photo_intelligence_pipeline.n2b2_synthetic.runtime_identity_revalidation import (
    RevalidationGateError,
    assert_identity_stable,
    canonical_identity,
    snapshot_tree,
    validate_fresh_output,
    validate_revalidation_authorization,
)

BASE = "d83f96271f754763d61cedcc314fc725c840c86f"
REVIEW_SHA = "5fbd960ed55982a31c310320981545d91618e4c8052c07c43468f9ebc645f826"
MODEL_SHA = "6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7"
STATE_SHA = "2d60dd76584da60a876db975a3954feffb2566797910c19d6403627f584a1f2a"


def _identity(version: str) -> dict[str, object]:
    return {
        "model_name": "qwen3.5:9b",
        "full_local_digest": MODEL_SHA,
        "size_bytes": 6594474711,
        "quantization_level": "Q4_K_M",
        "capabilities": ["thinking", "vision", "completion", "tools"],
        "ollama_version": version,
    }


def _receipt() -> dict[str, object]:
    old_identity = _identity("0.32.15")
    authorized_identity = _identity("0.33.3")
    old_identity["canonical_identity_sha256"] = hashlib.sha256(
        canonical_identity(old_identity)
    ).hexdigest()
    authorized_identity["canonical_identity_sha256"] = hashlib.sha256(
        canonical_identity(authorized_identity)
    ).hexdigest()
    return {
        "schema_version": "1.0",
        "receipt_type": "OWNER_N2B2_OLLAMA_RUNTIME_IDENTITY_REVALIDATION",
        "status": "APPROVED",
        "owner_id": "Jovi",
        "issued_at_utc": "2026-09-06T00:00:00Z",
        "task": "N2B2_OLLAMA_RUNTIME_IDENTITY_REVALIDATION_20260906",
        "base_candidate": BASE,
        "external_review_sha256": REVIEW_SHA,
        "accepted_verdict": "INCONCLUSIVE",
        "accepted_blocker": "N2B2_S20_RESUME_BINDING_MISMATCH: model_identity",
        "old_identity": old_identity,
        "authorized_identity": authorized_identity,
        "project_state_sha256": STATE_SHA,
        "project_state_n2b2": "LOCKED",
        "production_unlock": False,
        "boundaries": {
            "real_photo": False,
            "real_exif": False,
            "g1_source": False,
            "sqlite": False,
            "real20": False,
            "app": False,
            "production_bundle": False,
            "model_download": False,
            "model_replacement": False,
        },
        "max_fresh_s3_runs": 1,
        "max_fresh_s20_runs": 1,
        "new_output_required": True,
        "old_evidence_mutation": False,
        "mandatory_external_review": True,
    }


def test_gate_accepts_only_the_owner_bound_version_transition() -> None:
    permit = validate_revalidation_authorization(
        _receipt(),
        review_sha256=REVIEW_SHA,
        review_text="`INCONCLUSIVE`\nN2B2_S20_RESUME_BINDING_MISMATCH: model_identity",
        project_state_sha256=STATE_SHA,
        project_state_n2b2="LOCKED",
        old_identity=_identity("0.32.15"),
        current_identity=_identity("0.33.3"),
        current_head=BASE,
    )
    assert permit.identity_diff_fields == ("ollama_version",)
    assert permit.old_identity_sha256 != permit.new_identity_sha256


def test_gate_accepts_receipt_identity_with_its_canonical_hash() -> None:
    receipt = _receipt()
    for key in ("old_identity", "authorized_identity"):
        identity = receipt[key]
        payload = dict(identity)
        payload.pop("canonical_identity_sha256")
        identity["canonical_identity_sha256"] = hashlib.sha256(
            canonical_identity(payload)
        ).hexdigest()
    permit = validate_revalidation_authorization(
        receipt,
        review_sha256=REVIEW_SHA,
        review_text="INCONCLUSIVE\nN2B2_S20_RESUME_BINDING_MISMATCH: model_identity",
        project_state_sha256=STATE_SHA,
        project_state_n2b2="LOCKED",
        old_identity=_identity("0.32.15"),
        current_identity=_identity("0.33.3"),
        current_head=BASE,
    )
    assert permit.identity_diff_fields == ("ollama_version",)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda value: value.__setitem__("external_review_sha256", "0" * 64),
        lambda value: value.__setitem__("accepted_verdict", "PASS_FOR_OWNER_REVIEW"),
        lambda value: value.__setitem__("accepted_blocker", "other"),
        lambda value: value.__setitem__("base_candidate", "1" * 40),
        lambda value: value["old_identity"].__setitem__("ollama_version", "0.31.0"),
        lambda value: value["authorized_identity"].__setitem__("ollama_version", "0.32.15"),
        lambda value: value["authorized_identity"].__setitem__("full_local_digest", "0" * 64),
        lambda value: value["authorized_identity"].__setitem__("size_bytes", 1),
        lambda value: value["authorized_identity"].__setitem__("quantization_level", "Q8_0"),
        lambda value: value["authorized_identity"].__setitem__("capabilities", ["completion"]),
        lambda value: value.__setitem__("project_state_n2b2", "APPROVED"),
    ],
)
def test_gate_rejects_every_bound_field_tamper(mutator: object) -> None:
    receipt = copy.deepcopy(_receipt())
    mutator(receipt)  # type: ignore[operator]
    with pytest.raises(RevalidationGateError):
        validate_revalidation_authorization(
            receipt,
            review_sha256=REVIEW_SHA,
            review_text="INCONCLUSIVE\nN2B2_S20_RESUME_BINDING_MISMATCH: model_identity",
            project_state_sha256=STATE_SHA,
            project_state_n2b2="LOCKED",
            old_identity=_identity("0.32.15"),
            current_identity=_identity("0.33.3"),
            current_head=BASE,
        )


def test_gate_rejects_generic_inconclusive_review_without_exact_blocker() -> None:
    with pytest.raises(RevalidationGateError):
        validate_revalidation_authorization(
            _receipt(),
            review_sha256=REVIEW_SHA,
            review_text="INCONCLUSIVE\nunrelated blocker",
            project_state_sha256=STATE_SHA,
            project_state_n2b2="LOCKED",
            old_identity=_identity("0.32.15"),
            current_identity=_identity("0.33.3"),
            current_head=BASE,
        )


def test_fresh_output_rejects_nonempty_git_cache_and_old_evidence(tmp_path: Path) -> None:
    project = tmp_path / "project"
    cache = tmp_path / "cache"
    old = tmp_path / "old"
    project.mkdir()
    cache.mkdir()
    old.mkdir()
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "existing.json").write_text("{}", encoding="utf-8")
    for candidate in (project, cache, old, nonempty):
        with pytest.raises(RevalidationGateError):
            validate_fresh_output(
                candidate, project_root=project, cache_root=cache, old_roots=(old,)
            )


def test_identity_stability_and_snapshot_reject_mutation(tmp_path: Path) -> None:
    assert_identity_stable(_identity("0.33.3"), _identity("0.33.3"))
    with pytest.raises(RevalidationGateError):
        assert_identity_stable(_identity("0.33.3"), _identity("0.32.15"))

    root = tmp_path / "release"
    root.mkdir()
    target = root / "checkpoint.json"
    target.write_text("immutable", encoding="utf-8")
    before = snapshot_tree(root)
    assert before.file_count == 1
    assert before.entries["checkpoint.json"] == hashlib.sha256(b"immutable").hexdigest()
    target.write_text("changed", encoding="utf-8")
    after = snapshot_tree(root)
    assert before.entries != after.entries


def test_canonical_identity_sorts_capabilities() -> None:
    assert canonical_identity(_identity("0.33.3")) == canonical_identity(
        {**_identity("0.33.3"), "capabilities": ["vision", "completion", "tools", "thinking"]}
    )


def test_owner_receipt_and_transition_schema_are_closed(project_root: Path) -> None:
    receipt_path = (
        project_root / "approvals/owner_n2b2_ollama_runtime_identity_revalidation_20260906.yaml"
    )
    schema_path = (
        project_root / "schemas/owner_n2b2_ollama_runtime_identity_revalidation_v1.schema.json"
    )
    receipt = yaml.safe_load(receipt_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert not list(Draft202012Validator(schema).iter_errors(receipt))
