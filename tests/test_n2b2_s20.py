from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from nightly_photo_intelligence_pipeline.n2b2_synthetic import s20_manifest as s20_manifest_module
from nightly_photo_intelligence_pipeline.n2b2_synthetic.case17_remediation import (
    _load_candidate_manifest,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.fixture_manifest import SyntheticFixture
from nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client import ModelIdentity
from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_bundle import (
    validate_artifact,
    verify_release_checksums,
    write_case_bundle,
    write_checksums,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_checkpoint import (
    assert_checkpoint_binding,
    load_checkpoint,
    write_checkpoint,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_manifest import (
    S20_CASE17_GENERATOR_VERSION,
    S20_CASE17_REMEDIATION_RECORD_NAME,
    S20_CASE17_REMEDIATION_SEEDS,
    S20_CASE_MATRIX,
    S20_GENERATOR_VERSION,
    S20_MANIFEST_V2_VERSION,
    S20_MANIFEST_VERSION,
    load_s20_manifest,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_orchestrator import (
    _canonical,
    _identity_dict,
    _repeat_cases,
    _validate_case,
    _write_qwen_failure_evidence,
    _write_visual_diagnostics,
    run_s20,
)


def _write_manifest(root: Path) -> None:
    entries = []
    for spec in S20_CASE_MATRIX:
        path = root / f"{spec.case_id}.png"
        image = Image.new("RGB", (spec.width, spec.height), (spec.seed % 255, 20, 40))
        image.save(path, format="PNG")
        entries.append(
            {
                "case_id": spec.case_id,
                "case_type": spec.case_type,
                "filename": path.name,
                "synthetic": True,
                "image_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "width": spec.width,
                "height": spec.height,
                "seed": spec.seed,
                "acceptance_profile": spec.acceptance_profile,
                "generation_parameters": {
                    "prompt": "synthetic test prompt",
                    "negative_prompt": "synthetic test negative",
                    "sampler": "dpmpp_2m",
                    "scheduler": "karras",
                    "steps": 30,
                    "cfg": 6.0,
                    "denoise": 1.0,
                    "checkpoint": "sd_xl_base_1.0.safetensors",
                    "checkpoint_sha256": "b" * 64,
                    "vae": "sdxl_vae.safetensors",
                    "vae_sha256": "c" * 64,
                    "comfyui_version": "0.19.5",
                    "port": 7865,
                    "prompt_id": "test-prompt",
                },
                "expected_processability": (
                    "unsupported" if spec.acceptance_profile == "unsupported" else "processable"
                ),
                "expected_person_count": spec.expected_person_count,
                "tags": list(spec.tags),
            }
        )
    (root / "fixture_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": S20_MANIFEST_VERSION,
                "fixture_set": "N2B2_S20_SYNTHETIC",
                "generator_version": S20_GENERATOR_VERSION,
                "fixtures": entries,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def test_s20_loader_freezes_exact_matrix(tmp_path: Path) -> None:
    _write_manifest(tmp_path)
    fixtures = load_s20_manifest(tmp_path, project_root=Path(__file__).parents[1])
    assert len(fixtures) == 20
    assert [item.case_id for item in fixtures] == [item.case_id for item in S20_CASE_MATRIX]
    assert fixtures[-1].acceptance_profile == "unsupported"


def test_s20_v2_loader_binds_nineteen_v1_bytes_and_case17_seed_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    baseline = tmp_path / "baseline"
    v2 = tmp_path / "v2"
    baseline.mkdir()
    v2.mkdir()
    _write_manifest(baseline)
    baseline_payload = json.loads((baseline / "fixture_manifest.json").read_text(encoding="utf-8"))
    for entry in baseline_payload["fixtures"]:
        shutil.copyfile(baseline / entry["filename"], v2 / entry["filename"])

    case17 = next(item for item in baseline_payload["fixtures"] if item["case_id"] == "n2b2-s20-17")
    replacement = Image.new("RGB", (1024, 768), (1, 2, 3))
    replacement.save(v2 / case17["filename"], format="PNG")
    record = {
        "schema_version": "n2b2-s20-case17-remediation-v1",
        "case_id": "n2b2-s20-17",
        "candidate_seeds": list(S20_CASE17_REMEDIATION_SEEDS),
        "selected_seed": S20_CASE17_REMEDIATION_SEEDS[0],
        "synthetic_only": True,
    }
    record_path = v2 / S20_CASE17_REMEDIATION_RECORD_NAME
    record_path.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
    entries = []
    for entry in baseline_payload["fixtures"]:
        item = dict(entry)
        item["generator_version"] = S20_GENERATOR_VERSION
        if item["case_id"] == "n2b2-s20-17":
            item["seed"] = S20_CASE17_REMEDIATION_SEEDS[0]
            item["generator_version"] = S20_CASE17_GENERATOR_VERSION
            item["image_sha256"] = hashlib.sha256((v2 / item["filename"]).read_bytes()).hexdigest()
        entries.append(item)
    baseline_digest = hashlib.sha256((baseline / "fixture_manifest.json").read_bytes()).hexdigest()
    monkeypatch.setattr(s20_manifest_module, "S20_V1_MANIFEST_SHA256", baseline_digest)
    payload = {
        "schema_version": S20_MANIFEST_V2_VERSION,
        "fixture_set": "N2B2_S20_SYNTHETIC",
        "fixture_set_version": "N2B2_S20_SYNTHETIC_V2",
        "source_manifest_sha256": baseline_digest,
        "case17_remediation_record_sha256": hashlib.sha256(record_path.read_bytes()).hexdigest(),
        "fixtures": entries,
    }
    (v2 / "fixture_manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    fixtures = load_s20_manifest(
        v2, project_root=Path(__file__).parents[1], baseline_manifest_dir=baseline
    )
    assert len(fixtures) == 20
    assert next(item for item in fixtures if item.case_id == "n2b2-s20-17").seed == 2026082117
    for item in fixtures:
        if item.case_id != "n2b2-s20-17":
            baseline_item = next(
                value for value in baseline_payload["fixtures"] if value["case_id"] == item.case_id
            )
            assert item.image_sha256 == baseline_item["image_sha256"]


def test_s20_v2_loader_requires_external_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_manifest(tmp_path)
    manifest_digest = hashlib.sha256((tmp_path / "fixture_manifest.json").read_bytes()).hexdigest()
    monkeypatch.setattr(s20_manifest_module, "S20_V1_MANIFEST_SHA256", manifest_digest)
    payload = json.loads((tmp_path / "fixture_manifest.json").read_text(encoding="utf-8"))
    payload["schema_version"] = S20_MANIFEST_V2_VERSION
    payload["fixture_set_version"] = "N2B2_S20_SYNTHETIC_V2"
    payload["source_manifest_sha256"] = manifest_digest
    payload["case17_remediation_record_sha256"] = "b" * 64
    (tmp_path / "fixture_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="baseline_manifest_dir is required"):
        load_s20_manifest(tmp_path, project_root=Path(__file__).parents[1])


def test_case17_candidate_loader_requires_four_predeclared_seeds(tmp_path: Path) -> None:
    (tmp_path / "candidates").mkdir()
    rows = []
    for seed in S20_CASE17_REMEDIATION_SEEDS:
        filename = f"candidates/case17-{seed}.png"
        image_path = tmp_path / filename
        Image.new("RGB", (1024, 768), (seed % 255, 2, 3)).save(image_path, format="PNG")
        rows.append(
            {
                "seed": seed,
                "filename": filename,
                "image_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            }
        )
    (tmp_path / "case17_candidates.json").write_text(
        json.dumps({"candidate_count": 4, "candidates": rows}), encoding="utf-8"
    )
    assert [item["seed"] for item in _load_candidate_manifest(tmp_path)] == list(
        S20_CASE17_REMEDIATION_SEEDS
    )


def test_case17_candidate_loader_rejects_seed_expansion(tmp_path: Path) -> None:
    (tmp_path / "case17_candidates.json").write_text(
        json.dumps(
            {
                "candidates": [
                    {"seed": 2026082199, "filename": "candidate.png", "image_sha256": "a" * 64}
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="CASE17_FIXTURE_REMEDIATION_REQUIRES_DESIGN_REVIEW"):
        _load_candidate_manifest(tmp_path)


def test_s20_case_bundle_uses_non_self_referential_checksums(tmp_path: Path) -> None:
    fixture = SyntheticFixture(
        case_id="n2b2-s20-01",
        case_type="single_person",
        image_bytes=b"synthetic",
        image_sha256="a" * 64,
        width=1,
        height=1,
    )
    facts = {
        "case_id": fixture.case_id,
        "fact_digest": "b" * 64,
        "fact_ids": ["fact-person-count"],
        "uncertainties": [],
    }
    reasoning = {
        "case_id": fixture.case_id,
        "input_fact_digest": facts["fact_digest"],
        "reasoning_based_on_fact_ids": facts["fact_ids"],
        "photographic_interpretation": {
            "scene_value": "medium",
            "composition_notes": "synthetic composition",
            "lighting_notes": "synthetic lighting",
            "tone_notes": "synthetic tone",
        },
        "story_candidates": {"safe": "a", "narrative": "b", "dynamic": "c"},
        "director_prompts": {
            "standard": "a",
            "dramatic": "b",
            "plan_b": "c",
            "technical": "d",
        },
        "uncertainties": [],
    }
    write_case_bundle(
        tmp_path / fixture.case_id,
        fixture=fixture,
        facts=facts,
        reasoning=reasoning,
        disposition="STRICT_VALIDATION",
    )
    bundle = json.loads(
        (tmp_path / fixture.case_id / "reference_bundle.json").read_text(encoding="utf-8")
    )
    checksums = bundle["checksums"]
    assert "bundle_sha256" not in checksums
    assert set(checksums) == {
        "vision_facts_sha256",
        "reasoning_sha256",
        "director_prompt_sha256",
    }


def test_s20_analysis_schema_matches_qwen_reasoning_object_shape(tmp_path: Path) -> None:
    fixture = SyntheticFixture(
        case_id="n2b2-s20-03",
        case_type="single_person",
        image_bytes=b"synthetic",
        image_sha256="a" * 64,
        width=1,
        height=1,
    )
    facts = {
        "case_id": fixture.case_id,
        "fact_digest": "b" * 64,
        "fact_ids": ["fact-person-count"],
        "uncertainties": [],
    }
    reasoning = {
        "photographic_interpretation": {
            "scene_value": "medium",
            "composition_notes": "composition",
            "lighting_notes": "lighting",
            "tone_notes": "tone",
        },
        "story_candidates": {"safe": "safe", "narrative": "narrative", "dynamic": "dynamic"},
        "director_prompts": {
            "standard": "standard",
            "dramatic": "dramatic",
            "plan_b": "plan b",
            "technical": "technical",
        },
        "reasoning_based_on_fact_ids": facts["fact_ids"],
        "uncertainties": [],
        "input_fact_digest": facts["fact_digest"],
    }
    write_case_bundle(
        tmp_path / fixture.case_id,
        fixture=fixture,
        facts=facts,
        reasoning=reasoning,
        disposition="STRICT_VALIDATION",
    )
    validate_artifact(
        tmp_path / fixture.case_id / "analysis.json",
        Path(__file__).parents[1] / "schemas" / "n2b2_s20_analysis.schema.json",
    )


def test_s20_qwen_failure_persists_contract_errors(tmp_path: Path) -> None:
    from nightly_photo_intelligence_pipeline.n2b2_synthetic.metrics import MetricsCollector

    _write_qwen_failure_evidence(
        tmp_path,
        reviewed_commit="4" * 40,
        qwen_errors={"n2b2-s20-03": ["input_fact_digest mismatch"]},
        metrics=MetricsCollector(),
    )
    summary = json.loads((tmp_path / "validation_summary.json").read_text(encoding="utf-8"))
    failure = json.loads((tmp_path / "failure_summary.json").read_text(encoding="utf-8"))
    assert summary["qwen_status"] == "FAIL"
    assert failure["qwen_started"] is True
    assert failure["qwen_errors"]["n2b2-s20-03"] == ["input_fact_digest mismatch"]


def test_visual_diagnostics_write_terminal_failure_only_for_failed_acceptance(
    tmp_path: Path,
) -> None:
    from nightly_photo_intelligence_pipeline.n2b2_synthetic.metrics import MetricsCollector

    common = {
        "first_facts": [],
        "second_facts": [],
        "repeat_rows": [],
        "reviewed_commit": "4" * 40,
        "metrics": MetricsCollector(),
    }
    _write_visual_diagnostics(tmp_path / "success", case_errors={}, **common)
    assert not (tmp_path / "success" / "failure_summary.json").exists()
    assert not (tmp_path / "success" / "validation_summary.json").exists()

    _write_visual_diagnostics(
        tmp_path / "failed", case_errors={"n2b2-s20-17": ["strict person_count 2 != 1"]}, **common
    )
    assert (tmp_path / "failed" / "failure_summary.json").is_file()
    assert (
        json.loads((tmp_path / "failed" / "failure_summary.json").read_text(encoding="utf-8"))[
            "qwen_started"
        ]
        is False
    )


@pytest.mark.parametrize(
    "mutation",
    [
        {"case_id": "duplicate"},
        {"filename": "../escape.png"},
        {"image_sha256": "0" * 64},
        {"acceptance_profile": "observation"},
    ],
)
def test_s20_loader_rejects_tampering(tmp_path: Path, mutation: dict[str, object]) -> None:
    _write_manifest(tmp_path)
    payload = json.loads((tmp_path / "fixture_manifest.json").read_text(encoding="utf-8"))
    payload["fixtures"][0].update(mutation)
    (tmp_path / "fixture_manifest.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="N2B2_S20_MANIFEST_INVALID"):
        load_s20_manifest(tmp_path, project_root=Path(__file__).parents[1])


def test_s20_checkpoint_binding_and_atomic_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "checkpoint.json"
    binding = {"reviewed_commit": "49e653b", "manifest_sha256": "a" * 64}
    write_checkpoint(path, {**binding, "status": "STARTED"})
    checkpoint = load_checkpoint(path)
    assert checkpoint is not None
    assert_checkpoint_binding(checkpoint, binding)
    with pytest.raises(ValueError, match="N2B2_S20_RESUME_BINDING_MISMATCH"):
        assert_checkpoint_binding(checkpoint, {**binding, "manifest_sha256": "b" * 64})


def test_s20_fixed_repeat_sample_has_exactly_five() -> None:
    fixtures = [
        type("Fixture", (), {"case_id": f"n2b2-s20-{index:02d}"})() for index in range(1, 21)
    ]
    assert len(_repeat_cases("49e653b", "c" * 64, fixtures)) == 5


def test_s20_negative_and_strict_acceptance_profiles() -> None:
    negative = type(
        "Fixture",
        (),
        {"acceptance_profile": "negative", "person_expectation": "expected_person_count=0"},
    )()
    facts = {
        "person_count": 0,
        "pose_keypoints": [],
        "segmentation_person_ratio": 0,
        "segmentation_comparator_person_ratio": 0,
    }
    assert _validate_case(negative, facts) == []

    strict = type(
        "Fixture",
        (),
        {"acceptance_profile": "strict", "person_expectation": "expected_person_count=1"},
    )()
    assert _validate_case(strict, {"person_count": 0, "pose_keypoints": []})


def _write_complete_release(root: Path) -> None:
    case_ids = [f"n2b2-s20-{index:02d}" for index in range(1, 21)]
    repeat_ids = case_ids[:5]
    identity = {}
    identity_sha256 = hashlib.sha256(
        (
            json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        ).encode("utf-8")
    ).hexdigest()
    for case_id in case_ids:
        for name in (
            "analysis.json",
            "vision_facts.json",
            "director_prompt.json",
            "reference_bundle.json",
        ):
            (root / "cases" / case_id / name).parent.mkdir(parents=True, exist_ok=True)
            (root / "cases" / case_id / name).write_text("{}", encoding="utf-8")
        for name in ("binding_validation.json", "raw_response.json"):
            (root / "diagnostics" / "qwen" / case_id / name).parent.mkdir(
                parents=True, exist_ok=True
            )
            payload = (
                json.dumps({"model_identity_sha256": identity_sha256})
                if name == "binding_validation.json"
                else "{}"
            )
            (root / "diagnostics" / "qwen" / case_id / name).write_text(payload, encoding="utf-8")
    for case_id in repeat_ids:
        for name in ("binding_validation.json", "raw_response.json"):
            (root / "diagnostics" / "qwen-repeat" / case_id / name).parent.mkdir(
                parents=True, exist_ok=True
            )
            payload = (
                json.dumps({"model_identity_sha256": identity_sha256})
                if name == "binding_validation.json"
                else "{}"
            )
            (root / "diagnostics" / "qwen-repeat" / case_id / name).write_text(
                payload, encoding="utf-8"
            )
    for name in (
        "binding_validation_1.json",
        "binding_validation_2.json",
        "probe_summary.json",
        "raw_response_1.json",
        "raw_response_2.json",
    ):
        (root / "diagnostics" / "qwen-probe" / name).parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps({"model_identity_sha256": identity_sha256})
            if name.startswith("binding_validation_")
            else "{}"
        )
        (root / "diagnostics" / "qwen-probe" / name).write_text(payload, encoding="utf-8")
    for name in (
        "acceptance_report.json",
        "repeatability_report.json",
        "visual_facts_first.json",
        "visual_facts_second.json",
    ):
        (root / "diagnostics" / name).parent.mkdir(parents=True, exist_ok=True)
        (root / "diagnostics" / name).write_text("{}", encoding="utf-8")
    (root / "synthetic_bundle_index.json").write_text(
        json.dumps({"bundle_count": 20, "cases": [{"case_id": case_id} for case_id in case_ids]}),
        encoding="utf-8",
    )
    (root / "validation_summary.json").write_text(
        json.dumps({"result": "N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"}),
        encoding="utf-8",
    )
    for name in (
        "fixture_manifest.json",
        "process_evidence.json",
        "cleanup_evidence.json",
        "repeatability_report.json",
        "runtime_metrics.json",
    ):
        (root / name).write_text("{}", encoding="utf-8")
    (root / "ollama_identity.json").write_text(json.dumps(identity), encoding="utf-8")
    (root / "checkpoint.json").write_text(
        json.dumps(
            {
                "schema_version": "n2b2-s20-checkpoint-v2",
                "reviewed_commit": "a" * 40,
                "review_record_sha256": "b" * 64,
                "manifest_sha256": "c" * 64,
                "runtime_source_sha256": "d" * 64,
                "qwen_receipt_sha256": "e" * 64,
                "artifact_integrity_receipt_sha256": "f" * 64,
                "model_identity": identity_sha256,
                "run_started_at_utc": "2026-08-11T00:00:00Z",
                "completed_stages": [
                    "vision_first",
                    "vision_repeat",
                    "vision_acceptance",
                    "qwen",
                    "bundles",
                ],
                "completed_cases": case_ids,
                "qwen_case_records": {
                    case_id: {
                        "raw_response_sha256": "1" * 64,
                        "binding_evidence_sha256": "2" * 64,
                        "validation_status": "PASS",
                    }
                    for case_id in case_ids
                },
                "qwen_repeat_case_ids": repeat_ids,
                "bundle_count": 20,
                "status": "COMPLETE",
            }
        ),
        encoding="utf-8",
    )
    write_checksums(root)


def test_complete_release_rejects_stale_failure_summary(tmp_path: Path) -> None:
    """A successful validation set cannot checksum a contradictory failure claim."""

    _write_complete_release(tmp_path)
    (tmp_path / "failure_summary.json").write_text(
        json.dumps({"result": "N2B2_S20_SYNTHETIC_VALIDATION_FAILED"}), encoding="utf-8"
    )
    write_checksums(tmp_path)

    with pytest.raises(ValueError, match="N2B2_S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH"):
        verify_release_checksums(tmp_path)


def test_complete_release_checksum_verifier_rejects_unlisted_file(tmp_path: Path) -> None:
    _write_complete_release(tmp_path)
    (tmp_path / "unexpected.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="N2B2_S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH"):
        verify_release_checksums(tmp_path)


def test_complete_release_checksum_verifier_accepts_exact_valid_set_and_rejects_tampering(
    tmp_path: Path,
) -> None:
    _write_complete_release(tmp_path)
    assert len(verify_release_checksums(tmp_path)) == len(
        [path for path in tmp_path.rglob("*") if path.is_file() and path.name != "CHECKSUMS.sha256"]
    )
    (tmp_path / "cases" / "n2b2-s20-01" / "analysis.json").write_text(
        '{"tampered":true}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="N2B2_S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH"):
        verify_release_checksums(tmp_path)


def test_complete_resume_verifies_artifacts_and_identity_without_model_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    manifest_dir = tmp_path / "manifest"
    runtime.mkdir()
    manifest_dir.mkdir()
    manifest_bytes = b"{}"
    (manifest_dir / "fixture_manifest.json").write_bytes(manifest_bytes)
    _write_complete_release(runtime)
    (runtime / "fixture_manifest.json").write_bytes(manifest_bytes)
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    identity = ModelIdentity(
        model_name="qwen3.5:9b",
        full_local_digest="6488c96fa5faab64bb65cbd30d4289e20e6130ef535a93ef9a49f42eda893ea7",
        size_bytes=1,
        format="gguf",
        family="qwen35",
        parameter_size="9.7B",
        quantization_level="Q4_K_M",
        capabilities=["vision"],
        license="unknown",
        modified_at="2026-08-11T00:00:00Z",
        ollama_version="test",
    )
    checkpoint = json.loads((runtime / "checkpoint.json").read_text(encoding="utf-8"))
    checkpoint["manifest_sha256"] = manifest_sha
    identity_sha256 = hashlib.sha256(_canonical(_identity_dict(identity))).hexdigest()
    checkpoint["model_identity"] = identity_sha256
    (runtime / "checkpoint.json").write_text(json.dumps(checkpoint), encoding="utf-8")
    (runtime / "ollama_identity.json").write_bytes(_canonical(_identity_dict(identity)))
    for evidence_path in runtime.glob("diagnostics/qwen/*/binding_validation.json"):
        evidence_path.write_text(
            json.dumps({"model_identity_sha256": identity_sha256}), encoding="utf-8"
        )
    for evidence_path in runtime.glob("diagnostics/qwen-repeat/*/binding_validation.json"):
        evidence_path.write_text(
            json.dumps({"model_identity_sha256": identity_sha256}), encoding="utf-8"
        )
    for evidence_path in runtime.glob("diagnostics/qwen-probe/binding_validation_*.json"):
        evidence_path.write_text(
            json.dumps({"model_identity_sha256": identity_sha256}), encoding="utf-8"
        )
    write_checksums(runtime)

    class IdentityOnlyOllama:
        calls = 0

        def verify_identity(self) -> ModelIdentity:
            self.calls += 1
            return identity

    client = IdentityOnlyOllama()
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_orchestrator._review_gate",
        lambda *_: ("b" * 64, "e" * 64, {"review": {"verdict": "PASS_FOR_OWNER_REVIEW"}}),
    )
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_orchestrator._artifact_integrity_gate",
        lambda *_args, **_kwargs: ("f" * 64, {}),
    )
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.s20_orchestrator._source_digest",
        lambda *_: "d" * 64,
    )
    config = SimpleNamespace(
        device="cuda",
        fixtures_dir=manifest_dir,
        runtime_out_dir=runtime,
        project_root=tmp_path,
        ollama_base_url="http://127.0.0.1:11434",
    )
    before = {
        path.relative_to(runtime): path.read_bytes()
        for path in runtime.rglob("*")
        if path.is_file()
    }
    result = run_s20(
        config=config,
        fixtures=[],
        reasoning_schema={},
        vision_schema={},
        reviewed_commit="a" * 40,
        review_record=tmp_path / "review.json",
        owner_receipt=tmp_path / "owner.yaml",
        qwen_receipt=tmp_path / "qwen.yaml",
        artifact_integrity_receipt=tmp_path / "integrity.yaml",
        resume=True,
        ollama=client,  # type: ignore[arg-type]
    )
    after = {
        path.relative_to(runtime): path.read_bytes()
        for path in runtime.rglob("*")
        if path.is_file()
    }
    assert result["resume_status"] == "ALREADY_COMPLETE_VERIFIED"
    assert client.calls == 1
    assert after == before

    (runtime / "cases" / "n2b2-s20-01" / "analysis.json").write_text(
        '{"tampered":true}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="N2B2_S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH"):
        run_s20(
            config=config,
            fixtures=[],
            reasoning_schema={},
            vision_schema={},
            reviewed_commit="a" * 40,
            review_record=tmp_path / "review.json",
            owner_receipt=tmp_path / "owner.yaml",
            qwen_receipt=tmp_path / "qwen.yaml",
            artifact_integrity_receipt=tmp_path / "integrity.yaml",
            resume=True,
            ollama=client,  # type: ignore[arg-type]
        )
    assert client.calls == 1


def test_independent_review_schema_rejects_a_self_audit(tmp_path: Path) -> None:
    review = {
        "schema_version": "n2b2-s20-independent-review-v1",
        "reviewed_commit": "a" * 40,
        "reviewed_parent": "b" * 40,
        "reviewer_identity": "implementer-self-audit",
        "independent": False,
        "verdict": "PASS_FOR_OWNER_REVIEW",
        "checks": {"git_topology": "PASS"},
        "evidence_hashes": {"validation_summary.json": "c" * 64},
        "findings": [],
    }
    path = tmp_path / "review_result.json"
    path.write_text(json.dumps(review), encoding="utf-8")

    with pytest.raises(ValueError, match="N2B2_S20_ARTIFACT_SCHEMA_INVALID"):
        validate_artifact(
            path,
            Path(__file__).parents[1] / "schemas" / "n2b2_s20_independent_review.schema.json",
        )
