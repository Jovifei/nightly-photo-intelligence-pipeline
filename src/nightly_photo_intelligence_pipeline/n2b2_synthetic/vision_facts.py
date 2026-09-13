"""Build the authoritative, deterministic Vision Fact Contract (CODEX §8).

All facts come from deterministic models or deterministic computation. The
payload is canonicalised (sorted keys, no NaN/Infinity) and a ``fact_digest``
SHA-256 is computed over its UTF-8 bytes so that two executions of the same
image yield byte-identical facts (CODEX §8 immutability rule).
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from .config import DEEPLAB_MODEL_ID, KEYPOINT_MODEL_ID, LRASPP_MODEL_ID
from .torchvision_loader import RawPoseDetections, RawSegmentation


def _finite(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError("NPI_NONFINITE_VISION_FACT")
    return round(value, 6)


def _centroid(box: dict[str, float]) -> dict[str, float]:
    return {
        "x": _finite((box["x_min"] + box["x_max"]) / 2.0),
        "y": _finite((box["y_min"] + box["y_max"]) / 2.0),
    }


def _frame_contact(box: dict[str, float], width: int, height: int) -> dict[str, bool]:
    eps = 1.0
    return {
        "top": box["y_min"] <= eps,
        "bottom": box["y_max"] >= height - eps,
        "left": box["x_min"] <= eps,
        "right": box["x_max"] >= width - eps,
    }


def _negative_space(boxes: list[dict[str, float]], width: int, height: int) -> dict[str, Any]:
    """Versioned bbox-union empty-area proxy, not aesthetic negative space."""
    from ..engineering.geometry import measure_bbox_empty_area

    return measure_bbox_empty_area(boxes, width, height)


def build_vision_facts(
    *,
    case_id: str,
    image_sha256: str,
    generator_version: str,
    seed: int | None,
    width: int,
    height: int,
    pose: RawPoseDetections,
    seg_primary: RawSegmentation,
    seg_comparator: RawSegmentation,
) -> dict[str, Any]:
    """Return a dict conforming to ``n2b2_vision_fact_contract_v1_2.schema.json``."""

    person_count = len(pose.person_boxes)
    fact_ids = [
        "fact-person-count",
        "fact-pose-keypoints",
        "fact-seg-person-ratio",
        "fact-seg-comparator-person-ratio",
        "fact-subject-centroid",
        "fact-frame-contact",
        "fact-bbox-empty-area",
    ]
    uncertainties: list[dict[str, Any]] = [
        {
            "fact_id": "fact-bbox-empty-area",
            "description": (
                "Person-box empty-area proxy only; other objects, saliency and "
                "aesthetic negative space are not measured."
            ),
            "severity": "medium",
        }
    ]
    if abs(seg_primary.person_mask_ratio - seg_comparator.person_mask_ratio) > 0.25:
        uncertainties.append(
            {
                "fact_id": "fact-seg-person-ratio",
                "description": "LRASPP and DeepLab VOC person-mask estimates diverge beyond 0.25",
                "severity": "medium",
            }
        )

    payload: dict[str, Any] = {
        "schema_version": "1.2",
        "case_id": case_id,
        "image_sha256": image_sha256,
        "provenance": {
            "pose_model": KEYPOINT_MODEL_ID,
            "segmentation_model": LRASPP_MODEL_ID,
            "comparator_model": DEEPLAB_MODEL_ID,
            "generator_version": generator_version,
            "seed": seed,
        },
        "person_count": person_count,
        "person_boxes": [dict(b) for b in pose.person_boxes],
        "pose_keypoints": [[dict(k) for k in kp] for kp in pose.pose_keypoints],
        "pose_scores": [round(float(s), 4) for s in pose.pose_scores],
        "segmentation_person_ratio": _finite(seg_primary.person_mask_ratio),
        "segmentation_comparator_person_ratio": _finite(seg_comparator.person_mask_ratio),
        "subject_centroids": [_centroid(b) for b in pose.person_boxes],
        "frame_contact_flags": (
            _frame_contact(pose.person_boxes[0], width, height)
            if pose.person_boxes
            else {"top": False, "bottom": False, "left": False, "right": False}
        ),
        "negative_space_metrics": _negative_space(pose.person_boxes, width, height),
        "fact_ids": fact_ids,
        "uncertainties": uncertainties,
    }
    payload["fact_digest"] = compute_fact_digest(payload)
    return payload


def canonicalize(payload: dict[str, Any]) -> str:
    """Deterministic canonical JSON string (sorted keys, no whitespace)."""

    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def compute_fact_digest(payload: dict[str, Any]) -> str:
    """SHA-256 over the canonical bytes of the fact payload (excluding the
    digest field itself to avoid a self-reference loop)."""

    clean = {k: v for k, v in payload.items() if k != "fact_digest"}
    return hashlib.sha256(canonicalize(clean).encode("utf-8")).hexdigest()
