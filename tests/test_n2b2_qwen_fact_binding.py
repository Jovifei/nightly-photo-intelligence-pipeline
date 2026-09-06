"""Failure-first tests for the Qwen-to-vision-facts binding contract."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from nightly_photo_intelligence_pipeline.json_strict import load_json_strict
from nightly_photo_intelligence_pipeline.n2b2_synthetic.fixture_manifest import SyntheticFixture
from nightly_photo_intelligence_pipeline.n2b2_synthetic.qwen_fact_binding import (
    bind_reasoning_schema,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.qwen_reasoning import validate_reasoning
from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_bundle import write_case_bundle
from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_orchestrator import (
    _runtime_source_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = load_json_strict(ROOT / "schemas" / "n2b2_photography_reasoning.schema.json")


def _reasoning(case_id: str, digest: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "input_fact_digest": digest,
        "reasoning_based_on_fact_ids": ["fact-person-count"],
        "photographic_interpretation": {
            "scene_value": "medium",
            "composition_notes": "composition",
            "lighting_notes": "lighting",
            "tone_notes": "tone",
        },
        "story_candidates": {"safe": "a", "narrative": "b", "dynamic": "c"},
        "director_prompts": {
            "standard": "s",
            "dramatic": "d",
            "plan_b": "p",
            "technical": "t",
        },
        "uncertainties": [],
    }


def test_bound_schema_has_exact_runtime_constants_and_does_not_mutate_base() -> None:
    base = copy.deepcopy(SCHEMA)
    bound = bind_reasoning_schema(
        base,
        case_id="n2b2-s20-03",
        fact_digest="a" * 64,
        fact_ids=["fact-person-count", "fact-seg-person-ratio"],
    )
    assert base == SCHEMA
    assert bound["properties"]["case_id"] == {"const": "n2b2-s20-03"}
    assert bound["properties"]["input_fact_digest"] == {"const": "a" * 64}
    assert bound["properties"]["reasoning_based_on_fact_ids"]["items"]["enum"] == [
        "fact-person-count",
        "fact-seg-person-ratio",
    ]
    assert bound["properties"]["uncertainties"]["items"]["$ref"] == "#/$defs/qwen_uncertainty"
    assert bound["$defs"]["qwen_uncertainty"]["properties"]["related_fact_ids"]["items"][
        "enum"
    ] == [
        "fact-person-count",
        "fact-seg-person-ratio",
    ]


def test_reasoning_validation_rejects_exact_case_mismatch() -> None:
    digest = "b" * 64
    result = validate_reasoning(
        _reasoning("n2b2-s20-02", digest),
        case_id="n2b2-s20-03",
        input_fact_digest=digest,
        valid_fact_ids=["fact-person-count"],
        schema=SCHEMA,
    )
    assert not result.ok
    assert any("case_id mismatch" in item for item in result.errors)


def test_bundle_authoritative_digest_comes_from_facts_not_qwen_echo(tmp_path: Path) -> None:
    fixture = SyntheticFixture(
        case_id="n2b2-s20-03",
        case_type="strict",
        image_bytes=b"synthetic",
        image_sha256=hashlib.sha256(b"synthetic").hexdigest(),
        width=1,
        height=1,
    )
    facts = {
        "case_id": fixture.case_id,
        "fact_digest": "c" * 64,
        "fact_ids": ["fact-person-count"],
        "uncertainties": [],
    }
    reasoning = _reasoning(fixture.case_id, "d" * 64)
    write_case_bundle(
        tmp_path / fixture.case_id,
        fixture=fixture,
        facts=facts,
        reasoning=reasoning,
        disposition="STRICT_VALIDATION",
        qwen_binding={"echo_verified": False, "echoed_fact_digest": "d" * 64},
    )
    bundle = json.loads(
        (tmp_path / fixture.case_id / "reference_bundle.json").read_text(encoding="utf-8")
    )
    assert bundle["photographic_reasoning"]["input_fact_digest"] == "c" * 64
    assert bundle["photographic_reasoning"]["qwen_echo_verified"] is False


def test_runtime_source_manifest_covers_qwen_binding_files() -> None:
    manifest = _runtime_source_manifest(ROOT)
    paths = {item["path"] for item in manifest["files"]}
    assert "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/ollama_client.py" in paths
    assert "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/qwen_reasoning.py" in paths
    assert "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/qwen_fact_binding.py" in paths
    assert "schemas/n2b2_qwen_fact_binding_evidence.schema.json" in paths
    assert (
        manifest["runtime_source_sha256"]
        == hashlib.sha256(
            json.dumps(manifest["files"], sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    )
