"""Fail-closed validation for pose results."""

from __future__ import annotations

from ..domain.errors import BenchmarkValidationError, InvalidSideLabelError
from ..domain.provenance import ProducerType, validate_provenance
from .contracts import AnatomicalSide, Keypoint, PoseResult

_KEYPOINT_SIDE_RULES: dict[str, frozenset[AnatomicalSide]] = {
    "left_shoulder": frozenset({AnatomicalSide.LEFT}),
    "right_shoulder": frozenset({AnatomicalSide.RIGHT}),
    "left_hip": frozenset({AnatomicalSide.LEFT}),
    "right_hip": frozenset({AnatomicalSide.RIGHT}),
    "nose": frozenset({AnatomicalSide.CENTER, AnatomicalSide.NOT_APPLICABLE}),
}


def expected_sides(keypoint_id: str) -> frozenset[AnatomicalSide] | None:
    """Return an explicit keypoint-set mapping, never a substring inference."""

    return _KEYPOINT_SIDE_RULES.get(keypoint_id)


def validate_keypoint_side(point: Keypoint) -> None:
    allowed = expected_sides(point.keypoint_id)
    if allowed is not None and point.anatomical_side not in allowed:
        raise InvalidSideLabelError("keypoint_id and anatomical_side are incompatible")
    if allowed is not None and point.anatomical_side == AnatomicalSide.UNKNOWN:
        raise InvalidSideLabelError("paired keypoint cannot use UNKNOWN anatomical_side")


def validate_pose_result(result: PoseResult) -> None:
    if not result.case_id:
        raise BenchmarkValidationError("case_id is required")
    if result.person_index < 0:
        raise BenchmarkValidationError("person_index must be non-negative")
    if not result.keypoint_set_id:
        raise BenchmarkValidationError("keypoint_set_id is required")
    if result.image_width < 1 or result.image_height < 1:
        raise BenchmarkValidationError("image dimensions must be positive")
    validate_provenance(result.provenance)
    if result.provenance.producer_type == ProducerType.REAL_MODEL and result.synthetic:
        raise BenchmarkValidationError("REAL_MODEL provenance cannot be synthetic")
    if result.synthetic and result.model_artifact_present:
        raise BenchmarkValidationError("synthetic result cannot contain a model artifact")
    for point in result.keypoints:
        validate_keypoint_side(point)
        if not 0.0 <= point.confidence <= 1.0:
            raise BenchmarkValidationError("confidence must be in the accepted range")
        if point.coordinate is not None:
            if not 0.0 <= point.coordinate.pixel_x <= result.image_width - 1:
                raise BenchmarkValidationError("pixel x coordinate out of range")
            if not 0.0 <= point.coordinate.pixel_y <= result.image_height - 1:
                raise BenchmarkValidationError("pixel y coordinate out of range")
            if not 0.0 <= point.coordinate.normalized_x <= 1.0:
                raise BenchmarkValidationError("normalized x coordinate out of range")
            if not 0.0 <= point.coordinate.normalized_y <= 1.0:
                raise BenchmarkValidationError("normalized y coordinate out of range")
    for angle in result.joint_angles.values():
        if angle.degrees is not None and not 0.0 <= angle.degrees <= 360.0:
            raise BenchmarkValidationError("joint angle out of range")
