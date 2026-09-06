"""Bounded Case 17 fixture selection and v2 manifest construction."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .config import TorchVisionRole
from .fixture_manifest import SyntheticFixture
from .metrics import MetricsCollector
from .s20_manifest import (
    S20_CASE17_GENERATOR_VERSION,
    S20_CASE17_REMEDIATION_SEEDS,
    S20_MANIFEST_NAME,
    S20_MANIFEST_V2_VERSION,
    S20_V1_MANIFEST_SHA256,
    load_s20_manifest,
)
from .torchvision_loader import load_backend, verify_cache_hit

CASE17 = "n2b2-s20-17"
DESIGN_REVIEW = "N2B2_S20_CASE17_FIXTURE_REMEDIATION_REQUIRES_DESIGN_REVIEW"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _load_candidate_manifest(candidate_dir: Path) -> list[dict[str, Any]]:
    path = candidate_dir / "case17_candidates.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{DESIGN_REVIEW}: candidate manifest missing")
    payload = json.loads(path.read_text(encoding="utf-8"))
    candidates = payload.get("candidates") if isinstance(payload, dict) else None
    if not isinstance(candidates, list) or len(candidates) != len(S20_CASE17_REMEDIATION_SEEDS):
        raise ValueError(f"{DESIGN_REVIEW}: candidate count is not exactly four")
    by_seed: dict[int, dict[str, Any]] = {}
    for item in candidates:
        if not isinstance(item, dict) or not isinstance(item.get("seed"), int):
            raise ValueError(f"{DESIGN_REVIEW}: invalid candidate record")
        seed = item["seed"]
        if seed in by_seed or seed not in S20_CASE17_REMEDIATION_SEEDS:
            raise ValueError(f"{DESIGN_REVIEW}: candidate seed set drift")
        filename = item.get("filename")
        if (
            not isinstance(filename, str)
            or Path(filename).is_absolute()
            or ".." in Path(filename).parts
        ):
            raise ValueError(f"{DESIGN_REVIEW}: candidate filename escape")
        image = (candidate_dir / filename).resolve(strict=True)
        try:
            inside = image.is_relative_to(candidate_dir.resolve(strict=True))
        except AttributeError:  # pragma: no cover - Python 3.8 compatibility guard
            inside = str(image).startswith(str(candidate_dir.resolve(strict=True)))
        if not inside or image.suffix.lower() != ".png":
            raise ValueError(f"{DESIGN_REVIEW}: candidate image outside candidate directory")
        if _sha(image) != item.get("image_sha256"):
            raise ValueError(f"{DESIGN_REVIEW}: candidate image hash mismatch")
        by_seed[seed] = item
    return [by_seed[seed] for seed in sorted(by_seed)]


def _candidate_fixture(candidate_dir: Path, item: dict[str, Any]) -> SyntheticFixture:
    path = (candidate_dir / str(item["filename"])).resolve(strict=True)
    data = path.read_bytes()
    return SyntheticFixture(
        case_id=CASE17,
        case_type="minimal_composition",
        image_bytes=data,
        image_sha256=_sha(path),
        width=int(item["width"]),
        height=int(item["height"]),
        generator_version=S20_CASE17_GENERATOR_VERSION,
        seed=int(item["seed"]),
        generation_parameters=dict(item["generation_parameters"]),
        expected_processability="processable",
        person_expectation="expected_person_count=1",
        acceptance_profile="strict",
    )


def _score_candidate(
    backend: Any,
    fixture: SyntheticFixture,
    metrics: MetricsCollector,
) -> dict[str, Any]:
    pose = backend.detect_pose(fixture.image_bytes)
    primary = backend.segment(fixture.image_bytes, TorchVisionRole.SEGMENTATION_PRIMARY)
    comparator = backend.segment(
        fixture.image_bytes, TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR
    )
    return {
        "seed": fixture.seed,
        "image_sha256": fixture.image_sha256,
        "person_count": len(pose.person_boxes),
        "keypoint_groups": len(pose.pose_keypoints),
        "keypoint_lengths": [len(group) for group in pose.pose_keypoints],
        "lraspp_person_mask_ratio": primary.person_mask_ratio,
        "deeplab_person_mask_ratio": comparator.person_mask_ratio,
        "strict_pass": (
            len(pose.person_boxes) == 1
            and len(pose.pose_keypoints) == 1
            and len(pose.pose_keypoints[0]) == 17
            and primary.person_mask_ratio > 0
        ),
        "runtime_attestation": backend.runtime_attestation(),
        "elapsed_seconds": metrics.cpu_rss_peak,
    }


def build_case17_v2_manifest(
    *,
    baseline_manifest_dir: Path,
    candidate_dir: Path,
    out_dir: Path,
    cache_root: Path,
    cache_subdirs: dict[Any, str],
) -> dict[str, Any]:
    """Select the first strict candidate and create a complete external v2 set."""

    baseline_manifest_dir = Path(baseline_manifest_dir).resolve(strict=True)
    candidate_dir = Path(candidate_dir).resolve(strict=True)
    out_dir = Path(out_dir).resolve()
    if out_dir.exists():
        raise RuntimeError("N2B2_S20_CASE17_REMEDIATION_RUNTIME_ALREADY_EXISTS")
    baseline_manifest = baseline_manifest_dir / S20_MANIFEST_NAME
    if _sha(baseline_manifest) != S20_V1_MANIFEST_SHA256:
        raise ValueError("N2B2_S20_FAILURE_EVIDENCE_DRIFT: v1 manifest hash mismatch")
    baseline = load_s20_manifest(baseline_manifest_dir)
    candidates = _load_candidate_manifest(candidate_dir)
    out_dir.mkdir(parents=True)
    for fixture in baseline:
        shutil.copyfile(
            baseline_manifest_dir / f"{fixture.case_id}.png", out_dir / f"{fixture.case_id}.png"
        )

    selected: dict[str, Any] | None = None
    diagnostic: list[dict[str, Any]] = []
    verify_cache_hit(cache_root, cache_subdirs)
    backend = load_backend("real", cache_root, cache_subdirs, device="cuda")
    try:
        for item in candidates:
            metrics = MetricsCollector()
            fixture = _candidate_fixture(candidate_dir, item)
            try:
                result = _score_candidate(backend, fixture, metrics)
            except Exception as exc:
                result = {
                    "seed": fixture.seed,
                    "image_sha256": fixture.image_sha256,
                    "strict_pass": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            diagnostic.append(result)
            if result.get("strict_pass") and selected is None:
                selected = item
    finally:
        backend.unload()
    (out_dir / "case17_candidate_capability.json").write_bytes(
        _canonical({"candidates": diagnostic})
    )
    if selected is None:
        raise ValueError(f"{DESIGN_REVIEW}: no strict Case 17 candidate")

    selected_source = (candidate_dir / str(selected["filename"])).resolve(strict=True)
    selected_target = out_dir / "n2b2-s20-17.png"
    shutil.copyfile(selected_source, selected_target)
    preserved = [
        fixture.case_id
        for fixture in baseline
        if fixture.case_id != CASE17
        and _sha(out_dir / f"{fixture.case_id}.png") == fixture.image_sha256
    ]
    if len(preserved) != 19:
        raise ValueError(f"{DESIGN_REVIEW}: preserved fixture byte proof failed")
    record = {
        "schema_version": "n2b2-s20-case17-remediation-v1",
        "case_id": CASE17,
        "source_manifest_sha256": S20_V1_MANIFEST_SHA256,
        "candidate_seeds": list(S20_CASE17_REMEDIATION_SEEDS),
        "selected_seed": selected["seed"],
        "selected_image_sha256": _sha(selected_target),
        "preserved_case_count": 19,
        "synthetic_only": True,
        "model_and_threshold_unchanged": True,
        "candidate_capability": diagnostic,
    }
    record_path = out_dir / "case17_remediation_record.json"
    record_path.write_bytes(_canonical(record))
    baseline_payload = json.loads(baseline_manifest.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = []
    for entry in baseline_payload["fixtures"]:
        item = dict(entry)
        item["generator_version"] = baseline_payload["generator_version"]
        if item["case_id"] == CASE17:
            item["seed"] = selected["seed"]
            item["generator_version"] = S20_CASE17_GENERATOR_VERSION
            item["image_sha256"] = _sha(selected_target)
            item["generation_parameters"] = dict(selected["generation_parameters"])
        entries.append(item)
    v2 = {
        "schema_version": S20_MANIFEST_V2_VERSION,
        "fixture_set": "N2B2_S20_SYNTHETIC",
        "fixture_set_version": "N2B2_S20_SYNTHETIC_V2",
        "source_manifest_sha256": S20_V1_MANIFEST_SHA256,
        "case17_remediation_record_sha256": _sha(record_path),
        "fixtures": entries,
    }
    (out_dir / S20_MANIFEST_NAME).write_bytes(_canonical(v2))
    # Re-load the final bytes through the strict v2 loader before returning.
    load_s20_manifest(out_dir, baseline_manifest_dir=baseline_manifest_dir)
    return {
        "selected_seed": selected["seed"],
        "selected_image_sha256": _sha(selected_target),
        "preserved_case_count": len(preserved),
        "manifest_sha256": _sha(out_dir / S20_MANIFEST_NAME),
        "diagnostic_path": "case17_candidate_capability.json",
    }
