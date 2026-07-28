"""Closed, metadata-only N2B0.7 artifact qualification evidence."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from jsonschema import Draft202012Validator


def _read_json(project_root, rel: str) -> dict:
    return json.loads((project_root / rel).read_text(encoding="utf-8"))


def test_n2b0_7_qualification_record_is_schema_valid_and_fail_closed(project_root) -> None:
    record = _read_json(project_root, "research/N2B0_7_torchvision_artifact_qualification.json")
    schema = _read_json(project_root, "schemas/n2b0_7_artifact_qualification_v1.schema.json")
    assert not list(Draft202012Validator(schema).iter_errors(record))
    assert record["result"] == "N2B0_7_ARTIFACT_QUALIFICATION_BLOCKED"
    assert all(
        candidate["weights_license"] == "UNKNOWN"
        and candidate["commercial_use"] == "UNKNOWN"
        and candidate["qualification"].startswith("BLOCKED_")
        for candidate in record["artifact_candidates"]
    )
    assert all(value == 0 for value in record["prohibited_action_counters"].values())
    assert record["official_evidence"]["weights_license_status"] == (
        "NOT_PUBLISHED_IN_LISTED_TORCHVISION_V0_22_1_METADATA"
    )
    assert record["official_evidence"]["commercial_use_status"] == (
        "NOT_PUBLISHED_IN_LISTED_TORCHVISION_V0_22_1_METADATA"
    )


def test_n2b0_7_preserves_exact_variant_identity_and_official_domains(project_root) -> None:
    record = _read_json(project_root, "research/N2B0_7_torchvision_artifact_qualification.json")
    candidates = {candidate["id"]: candidate for candidate in record["artifact_candidates"]}
    pose = candidates["torchvision-keypointrcnn-resnet50-fpn-coco-v1"]
    assert pose["requested_variant"] == pose["official_variant"] == "COCO_V1"
    assert pose["requested_filename"] != pose["official_filename"]
    assert pose["official_filename"] == "keypointrcnn_resnet50_fpn_coco-fc266e95.pth"
    assert pose["official_legacy_variant"] == "COCO_LEGACY"
    assert pose["official_legacy_filename"] == pose["requested_filename"]
    assert pose["official_source_url"] == (
        "https://raw.githubusercontent.com/pytorch/vision/v0.22.1/"
        "torchvision/models/detection/keypoint_rcnn.py"
    )
    assert pose["official_url"] == (
        "https://download.pytorch.org/models/keypointrcnn_resnet50_fpn_coco-fc266e95.pth"
    )
    assert pose["claimed_size_megabytes"] == 226.054
    expected_segmentation = {
        "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1": (
            "https://raw.githubusercontent.com/pytorch/vision/v0.22.1/"
            "torchvision/models/segmentation/lraspp.py",
            "lraspp_mobilenet_v3_large-d234d4ea.pth",
            12.49,
        ),
        "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1": (
            "https://raw.githubusercontent.com/pytorch/vision/v0.22.1/"
            "torchvision/models/segmentation/deeplabv3.py",
            "deeplabv3_mobilenet_v3_large-fc3c493d.pth",
            42.301,
        ),
    }
    for candidate_id, (source_url, filename, size_megabytes) in expected_segmentation.items():
        candidate = candidates[candidate_id]
        assert candidate["official_source_url"] == source_url
        assert candidate["official_filename"] == filename
        assert candidate["official_url"] == f"https://download.pytorch.org/models/{filename}"
        assert candidate["claimed_size_megabytes"] == size_megabytes
    assert {
        candidate["person_class_index"]
        for key, candidate in candidates.items()
        if key != pose["id"]
    } == {15}
    for candidate in candidates.values():
        assert urlparse(candidate["official_source_url"]).netloc == "raw.githubusercontent.com"
        assert urlparse(candidate["official_url"]).netloc == "download.pytorch.org"
        assert candidate["official_digest"]["algorithm"] == "SHA256_PREFIX"
        assert candidate["official_digest"]["complete_sha256_published"] is False


def test_n2b0_7_state_keeps_download_execution_and_follow_on_phases_locked(project_root) -> None:
    state = _read_json(project_root, "PROJECT_STATE.json")
    assert state["phase_status"]["N2B0_7"] == "AUTHORIZED"
    assert state["required_stop_after"] == {
        "condition": "N2B0_7_ARTIFACT_QUALIFICATION_BLOCKED",
        "next_action": "WAIT_FOR_OWNER_ARTIFACT_DECISION",
    }
    assert state["authorization"]["large_model_downloads"] == "NOT_AUTHORIZED"
    assert state["authorization"]["real_model_execution"] == "NOT_AUTHORIZED"
    assert all(
        state["phase_status"][phase] == "LOCKED"
        for phase in ("N2B1", "N2B1_Q", "N2B1_P", "N2B2", "N3")
    )
