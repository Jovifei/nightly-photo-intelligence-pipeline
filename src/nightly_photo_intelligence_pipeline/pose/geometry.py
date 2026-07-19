"""Pure deterministic pose geometry; no image or model access."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

from ..domain.errors import BenchmarkValidationError
from .contracts import AnatomicalSide, Coordinate, JointAngle, Keypoint, MirrorStrategy, PoseResult

_KEYPOINT_MIRROR_MAP = {
    "left_shoulder": "right_shoulder",
    "right_shoulder": "left_shoulder",
    "left_hip": "right_hip",
    "right_hip": "left_hip",
    "nose": "nose",
}
_SIDE_MIRROR_MAP = {
    AnatomicalSide.LEFT: AnatomicalSide.RIGHT,
    AnatomicalSide.RIGHT: AnatomicalSide.LEFT,
    AnatomicalSide.CENTER: AnatomicalSide.CENTER,
    AnatomicalSide.NOT_APPLICABLE: AnatomicalSide.NOT_APPLICABLE,
    AnatomicalSide.UNKNOWN: AnatomicalSide.UNKNOWN,
}


def mirror_coordinate(coordinate: Coordinate, image_width: int) -> Coordinate:
    if image_width < 1:
        raise BenchmarkValidationError("image width must be positive")
    return Coordinate(
        pixel_x=round((image_width - 1) - coordinate.pixel_x, 12),
        pixel_y=coordinate.pixel_y,
        # Fixed precision preserves the explicit double-mirror identity contract.
        normalized_x=round(1.0 - coordinate.normalized_x, 12),
        normalized_y=coordinate.normalized_y,
    )


def mirror_keypoints(keypoints: Iterable[Keypoint], image_width: int) -> tuple[Keypoint, ...]:
    return tuple(
        Keypoint(
            keypoint_id=_KEYPOINT_MIRROR_MAP.get(point.keypoint_id, point.keypoint_id),
            partition=point.partition,
            coordinate=None
            if point.coordinate is None
            else mirror_coordinate(point.coordinate, image_width),
            confidence=point.confidence,
            visibility=point.visibility,
            anatomical_side=_SIDE_MIRROR_MAP[point.anatomical_side],
        )
        for point in keypoints
    )


def mirror_pose(result: PoseResult, image_width: int) -> PoseResult:
    return PoseResult(
        case_id=result.case_id,
        person_index=result.person_index,
        keypoint_set_id=result.keypoint_set_id,
        keypoints=mirror_keypoints(result.keypoints, image_width),
        provenance=result.provenance,
        mirror_strategy=(
            MirrorStrategy.HORIZONTAL_FLIP
            if result.mirror_strategy == MirrorStrategy.NOT_MIRRORED
            else MirrorStrategy.NOT_MIRRORED
        ),
        image_width=result.image_width,
        image_height=result.image_height,
        joint_angles=result.joint_angles,
        uncertainties=result.uncertainties,
        model_artifact_present=result.model_artifact_present,
    )


def joint_angle(
    first: Coordinate | None, vertex: Coordinate | None, last: Coordinate | None
) -> JointAngle:
    if first is None or vertex is None or last is None:
        return JointAngle(None, "MISSING_KEYPOINT", 0.0)
    a_x, a_y = first.pixel_x - vertex.pixel_x, first.pixel_y - vertex.pixel_y
    b_x, b_y = last.pixel_x - vertex.pixel_x, last.pixel_y - vertex.pixel_y
    a_norm, b_norm = math.hypot(a_x, a_y), math.hypot(b_x, b_y)
    if a_norm == 0.0 or b_norm == 0.0:
        return JointAngle(None, "UNDEFINED_ZERO_LENGTH", 0.0)
    cosine = max(-1.0, min(1.0, (a_x * b_x + a_y * b_y) / (a_norm * b_norm)))
    return JointAngle(math.degrees(math.acos(cosine)), "DEFINED", 1.0)


def derive_joint_angles(
    keypoints: Mapping[str, Keypoint], specifications: Mapping[str, tuple[str, str, str]]
) -> dict[str, JointAngle]:
    derived: dict[str, JointAngle] = {}
    for name, spec in specifications.items():
        first = keypoints.get(spec[0])
        vertex = keypoints.get(spec[1])
        last = keypoints.get(spec[2])
        derived[name] = joint_angle(
            first.coordinate if first else None,
            vertex.coordinate if vertex else None,
            last.coordinate if last else None,
        )
    return derived


def stable_person_order(results: Iterable[PoseResult]) -> tuple[PoseResult, ...]:
    """Return deterministic person ordering without inspecting image content."""

    return tuple(sorted(results, key=lambda item: (item.person_index, item.keypoint_set_id)))
