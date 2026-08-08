"""N2B1P cache-promotion completion remains redacted and fail-closed."""

from __future__ import annotations

import copy
import json

import pytest
from jsonschema import Draft202012Validator

from nightly_photo_intelligence_pipeline.domain.errors import GateNotAuthorizedError
from nightly_photo_intelligence_pipeline.local_research_promotion import load_authorized_promotion


def _read_json(project_root, rel: str) -> dict:
    return json.loads((project_root / rel).read_text(encoding="utf-8"))


def test_n2b1p_evidence_is_schema_valid_and_exactly_bound(project_root) -> None:
    evidence = _read_json(project_root, "research/N2B1P_cache_promotion_evidence.json")
    schema = _read_json(project_root, "schemas/n2b1p_cache_promotion_evidence_v1.schema.json")
    assert not list(Draft202012Validator(schema).iter_errors(evidence))
    assert evidence["result"] == "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"
    assert [item["first_pass_status"] for item in evidence["artifacts"]] == ["PROMOTED"] * 3
    assert [item["verification_status"] for item in evidence["artifacts"]] == ["CACHE_HIT"] * 3
    assert all(value == "NOT_PERFORMED" for value in evidence["prohibited_actions"].values())
    assert "\\" not in json.dumps(evidence, sort_keys=True)


def test_n2b1p_loader_rejects_an_artifact_outside_exact_evidence(project_root) -> None:
    with pytest.raises(GateNotAuthorizedError):
        load_authorized_promotion("unbound-artifact", project_root=project_root)


def test_n2b1p_evidence_schema_rejects_a_broadened_prohibited_action(project_root) -> None:
    evidence = _read_json(project_root, "research/N2B1P_cache_promotion_evidence.json")
    schema = _read_json(project_root, "schemas/n2b1p_cache_promotion_evidence_v1.schema.json")
    tampered = copy.deepcopy(evidence)
    tampered["prohibited_actions"]["cuda_execution"] = "PERFORMED"
    assert list(Draft202012Validator(schema).iter_errors(tampered))
