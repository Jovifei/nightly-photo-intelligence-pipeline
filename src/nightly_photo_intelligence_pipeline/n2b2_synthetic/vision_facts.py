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
        # Canonicalise non-finite to 0.0; this is a defensive guard because the
        # contract forbids NaN/Infinity in any fact payload.
        return 0.0
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


def _union_area(boxes: list[tuple[float, float, float, float]]) -> float:
    xs = sorted({x for box in boxes for x in (box[0], box[2])})
    slabs: list[float] = []
    for left, right in zip(xs, xs[1:], strict=False):
        intervals = sorted((y0, y1) for x0, y0, x1, y1 in boxes if x0 < right and x1 > left)
        occupied = 0.0
        if intervals:
            start, end = intervals[0]
            for low, high in intervals[1:]:
                if low > end:
                    occupied += end - start
                    start, end = low, high
                else:
                    end = max(end, high)
            occupied += end - start
        slabs.append((right - left) * occupied)
    return math.fsum(slabs)


def _negative_space(boxes: list[dict[str, float]], width: int, height: int) -> dict[str, Any]:
    if width <= 0 or height <= 0 or len(boxes) > 256:
        raise ValueError("invalid negative-space frame")
    normalized: list[tuple[float, float, float, float]] = []
    for box in boxes:
        try:
            x0, y0, x1, y1 = (float(box[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("invalid negative-space box") from exc
        if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
            raise ValueError("invalid negative-space box")
        if x0 > x1 or y0 > y1:
            raise ValueError("inverted negative-space box")
        x0, x1 = max(0.0, min(float(width), x0)), max(0.0, min(float(width), x1))
        y0, y1 = max(0.0, min(float(height), y0)), max(0.0, min(float(height), y1))
        if x0 < x1 and y0 < y1:
            normalized.append((x0 / width, y0 / height, x1 / width, y1 / height))

    def empty(region: tuple[float, float, float, float]) -> float:
        rx0, ry0, rx1, ry1 = region
        clipped = [
            (max(x0, rx0), max(y0, ry0), min(x1, rx1), min(y1, ry1))
            for x0, y0, x1, y1 in normalized
        ]
        occupied = _union_area([box for box in clipped if box[0] < box[2] and box[1] < box[3]])
        area = (rx1 - rx0) * (ry1 - ry0)
        return _finite(max(0.0, min(1.0, 1.0 - occupied / area)))

    return {
        "method": "bbox-union-half-frame-empty-area-v1",
        "measurement_kind": "BBOX_EMPTY_AREA_PROXY_NOT_AESTHETIC_NEGATIVE_SPACE",
        "coordinate_system": "pixel_edges",
        "directional_denominator": "corresponding_half_frame_area",
        "left_ratio": empty((0.0, 0.0, 0.5, 1.0)),
        "right_ratio": empty((0.5, 0.0, 1.0, 1.0)),
        "top_ratio": empty((0.0, 0.0, 1.0, 0.5)),
        "bottom_ratio": empty((0.0, 0.5, 1.0, 1.0)),
        "total_negative_ratio": empty((0.0, 0.0, 1.0, 1.0)),
    }


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
    """Return a dict conforming to ``n2b2_vision_fact_contract.schema.json``."""

    person_count = len(pose.person_boxes)
    fact_ids = [
        "fact-person-count",
        "fact-pose-keypoints",
        "fact-seg-person-ratio",
        "fact-seg-comparator-person-ratio",
        "fact-subject-centroid",
        "fact-frame-contact",
        "fact-negative-space",
    ]
    uncertainties: list[dict[str, Any]] = []
    if abs(seg_primary.person_mask_ratio - seg_comparator.person_mask_ratio) > 0.25:
        uncertainties.append(
            {
                "fact_id": "fact-seg-person-ratio",
                "description": "LRASPP and DeepLab VOC person-mask estimates diverge beyond 0.25",
                "severity": "medium",
            }
        )

    payload: dict[str, Any] = {
        "schema_version": "1.1",
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

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_fact_digest(payload: dict[str, Any]) -> str:
    """SHA-256 over the canonical bytes of the fact payload (excluding the
    digest field itself to avoid a self-reference loop)."""

    clean = {k: v for k, v in payload.items() if k != "fact_digest"}
    return hashlib.sha256(canonicalize(clean).encode("utf-8")).hexdigest()
