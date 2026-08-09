"""Contract tests added for the revised S3-only remediation boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from PIL import Image

from nightly_photo_intelligence_pipeline.n2b2_synthetic.fixture_manifest import (
    S3_MANIFEST_VERSION,
    load_s3_manifest,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.n2b1p_gate import validate_n2b1p_review
from nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client import OllamaClient
from nightly_photo_intelligence_pipeline.n2b2_synthetic.orchestrator import (
    R_S20_NOT_AUTHORIZED,
    SyntheticFixture,
    run_n2b2,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.torchvision_loader import RawSegmentation


def _write_fixture_set(root: Path) -> None:
    entries: list[dict[str, object]] = []
    cases = (
        ("n2b2-s3-01", "single_person", (220, 220, 220), 2026080901),
        ("n2b2-s3-02", "multi_person_or_occluded", (220, 220, 221), 2026080911),
        ("n2b2-s3-03", "negative_control", (220, 220, 222), 2026080921),
    )
    for case_id, case_type, color, seed in cases:
        filename = f"{case_id}.png"
        path = root / filename
        Image.new("RGB", (64, 48), color).save(path, format="PNG")
        data = path.read_bytes()
        entries.append(
            {
                "case_id": case_id,
                "case_type": case_type,
                "filename": filename,
                "image_sha256": hashlib.sha256(data).hexdigest(),
                "width": 64,
                "height": 48,
                "generator_version": "npi-comfyui-test",
                "seed": seed,
                "generation_parameters": {"steps": 30, "cfg": 6.0},
                "expected_processability": "processable",
                "person_expectation": "declared synthetic test case",
            }
        )
    (root / "fixture_manifest.json").write_text(
        json.dumps({"schema_version": S3_MANIFEST_VERSION, "fixtures": entries}), encoding="utf-8"
    )


def test_manifest_accepts_exact_three_cases_and_freezes_bytes(tmp_path: Path) -> None:
    _write_fixture_set(tmp_path)
    fixtures = load_s3_manifest(tmp_path)
    assert [fixture.case_type for fixture in fixtures] == [
        "single_person",
        "multi_person_or_occluded",
        "negative_control",
    ]
    assert all(
        fixture.image_sha256 == hashlib.sha256(fixture.image_bytes).hexdigest()
        for fixture in fixtures
    )


def test_manifest_rejects_path_escape_and_sha_tamper(tmp_path: Path) -> None:
    _write_fixture_set(tmp_path)
    manifest_path = tmp_path / "fixture_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fixtures"][0]["filename"] = "../outside.png"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="path escape"):
        load_s3_manifest(tmp_path)
    _write_fixture_set(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["fixtures"][0]["image_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        load_s3_manifest(tmp_path)


def test_independent_review_gate_does_not_require_phase_completion_record() -> None:
    evidence = {
        "result": "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
        "review_verdict": "PASS",
        "independent_reviewer": "reviewer",
        "external_review": {
            "reviewed_at_utc": "2026-08-06T14:01:27Z",
            "all_three_artifacts_cache_hit_verified": True,
            "prohibited_actions_confirmed": True,
        },
    }
    assert validate_n2b1p_review(evidence)[0]


def test_person_segmentation_fact_uses_explicit_person_ratio() -> None:
    assert RawSegmentation(person_mask_ratio=0.25).foreground_ratio == 0.25
    prompt = OllamaClient._build_prompt(
        vision_facts={"segmentation_person_ratio": 0.25},
        fact_digest="a" * 64,
        fact_ids=["fact-seg-person-ratio"],
        uncertainties=[],
    )
    assert "segmentation_person_ratio" in prompt


def test_s3_runner_rejects_s20_input_before_model_access() -> None:
    from nightly_photo_intelligence_pipeline.n2b2_synthetic.config import N2B2RunConfig

    config = N2B2RunConfig(
        project_root=Path("project-root"),
        cache_root=Path("cache-root"),
        fixtures_dir=Path("fixtures-root"),
        runtime_out_dir=Path("runtime-root"),
        s3_only=True,
    )
    result = run_n2b2(
        config=config,
        s3_fixtures=[],
        s20_fixtures=[SyntheticFixture("n2b2-s20-01", b"x", 1, 1)],
        reasoning_schema={},
        vision_schema={},
        n2b1p_sha="a" * 40,
        n2b1p_review_passed=True,
        start_head="b" * 40,
    )
    assert result.result == R_S20_NOT_AUTHORIZED
