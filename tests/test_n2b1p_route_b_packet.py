from __future__ import annotations

import json
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _validate(schema_name: str, document_name: str, *, yaml_document: bool = False) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    path = ROOT / document_name
    document = (
        yaml.safe_load(path.read_text(encoding="utf-8"))
        if yaml_document
        else json.loads(path.read_text(encoding="utf-8"))
    )
    assert list(Draft202012Validator(schema).iter_errors(document)) == []


def test_route_b_packet_is_closed_and_not_authorized() -> None:
    _validate(
        "n2b1p_cache_reprovision_v2.schema.json",
        "tasks/phase_n2b1p_cache_reprovision_v2.yaml",
        yaml_document=True,
    )
    _validate(
        "owner_n2b1p_cache_reprovision_v2.schema.json",
        "approvals/owner_n2b1p_cache_reprovision_v2.yaml",
        yaml_document=True,
    )
    _validate(
        "n2b1p_reprovision_runtime_configuration_v2.schema.json",
        "approvals/n2b1p_reprovision_runtime_configuration_v2.json",
    )
    _validate("n2b1p_b_source_evidence_v1.schema.json", "research/N2B1P_b_source_evidence_v1.json")
    task = yaml.safe_load(
        (ROOT / "tasks/phase_n2b1p_cache_reprovision_v2.yaml").read_text(encoding="utf-8")
    )
    assert task["status"] == "DRAFT_NOT_AUTHORIZED"
    assert task["authorities"]["b_cache"]["status"] == "NOT_AUTHORIZED"
    assert task["authorities"]["b_source"]["status"] == "NOT_AUTHORIZED"
    assert task["authorities"]["b_cache"]["network_access"] == "DENY"


def test_route_b_packet_rejects_source_digest_drift() -> None:
    schema = json.loads(
        (ROOT / "schemas/n2b1p_b_source_evidence_v1.schema.json").read_text(encoding="utf-8")
    )
    document = json.loads(
        (ROOT / "research/N2B1P_b_source_evidence_v1.json").read_text(encoding="utf-8")
    )
    document["artifacts"][0]["local_sha256"] = "0" * 64
    assert list(Draft202012Validator(schema).iter_errors(document))
