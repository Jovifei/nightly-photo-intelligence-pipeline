"""Typed, model-agnostic pose contracts for N2A.

The contracts deliberately carry provenance and synthetic markers. A VLM text
answer is never a valid pose producer, and fake results cannot be exported as
real model output.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from ..domain.errors import (
    BenchmarkValidationError,
    InvalidSideLabelError,
)
from ..domain.numeric import require_finite_number
from ..domain.provenance import Provenance


class KeypointPartition(StrEnum):
    BODY = "BODY"
    HAND_LEFT = "HAND_LEFT"
    HAND_RIGHT = "HAND_RIGHT"
    FACE = "FACE"


class Visibility(StrEnum):
    VISIBLE = "VISIBLE"
    OCCLUDED = "OCCLUDED"
    OUT_OF_FRAME = "OUT_OF_FRAME"
    UNKNOWN = "UNKNOWN"


class MirrorStrategy(StrEnum):
    NOT_MIRRORED = "NOT_MIRRORED"
    HORIZONTAL_FLIP = "HORIZONTAL_FLIP"
    UNKNOWN = "UNKNOWN"


class AnatomicalSide(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    CENTER = "CENTER"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Coordinate:
    """Pixel and normalized coordinates for one image coordinate system."""

    pixel_x: float
    pixel_y: float
    normalized_x: float
    normalized_y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "pixel_x", require_finite_number(self.pixel_x))
        object.__setattr__(self, "pixel_y", require_finite_number(self.pixel_y))
        object.__setattr__(self, "normalized_x", require_finite_number(self.normalized_x))
        object.__setattr__(self, "normalized_y", require_finite_number(self.normalized_y))

    def is_finite(self) -> bool:
        return True


@dataclass(frozen=True)
class PoseInput:
    """Metadata-only input used by fake backends and benchmark planning."""

    case_id: str
    image_width: int
    image_height: int
    person_count_hint: int = 1
    mirror_strategy: MirrorStrategy = MirrorStrategy.NOT_MIRRORED


PoseProvenance = Provenance


@dataclass(frozen=True)
class Keypoint:
    keypoint_id: str
    partition: KeypointPartition
    coordinate: Coordinate | None
    confidence: float
    visibility: Visibility
    anatomical_side: AnatomicalSide = AnatomicalSide.CENTER

    def __post_init__(self) -> None:
        if not self.keypoint_id:
            raise BenchmarkValidationError("keypoint_id is required")
        try:
            partition = KeypointPartition(self.partition)
            visibility = Visibility(self.visibility)
        except ValueError as exc:
            raise BenchmarkValidationError("keypoint enum is not authorized") from exc
        try:
            side = AnatomicalSide(self.anatomical_side)
        except ValueError as exc:
            raise InvalidSideLabelError("anatomical_side must be an explicit enum value") from exc
        confidence = require_finite_number(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise BenchmarkValidationError("confidence must be in the accepted range")
        object.__setattr__(self, "partition", partition)
        object.__setattr__(self, "visibility", visibility)
        object.__setattr__(self, "anatomical_side", side)
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True)
class JointAngle:
    degrees: float | None
    status: str
    confidence: float
    method: str = "DETERMINISTIC_VECTOR_ANGLE"

    def __post_init__(self) -> None:
        if self.degrees is not None:
            degrees = require_finite_number(self.degrees)
            if not 0.0 <= degrees <= 360.0:
                raise BenchmarkValidationError("joint angle must be in the accepted range")
            object.__setattr__(self, "degrees", degrees)
        confidence = require_finite_number(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise BenchmarkValidationError("joint-angle confidence must be in the accepted range")
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True)
class PoseResult:
    case_id: str
    person_index: int
    keypoint_set_id: str
    keypoints: tuple[Keypoint, ...]
    provenance: PoseProvenance
    mirror_strategy: MirrorStrategy
    image_width: int = 0
    image_height: int = 0
    joint_angles: Mapping[str, JointAngle] = field(default_factory=dict)
    uncertainties: tuple[str, ...] = ()
    model_artifact_present: bool = False

    def __post_init__(self) -> None:
        if not self.case_id:
            raise BenchmarkValidationError("case_id is required")
        if not self.keypoint_set_id:
            raise BenchmarkValidationError("keypoint_set_id is required")
        if self.person_index < 0 or self.image_width < 1 or self.image_height < 1:
            raise BenchmarkValidationError("pose dimensions and person index must be valid")
        try:
            mirror_strategy = MirrorStrategy(self.mirror_strategy)
        except ValueError as exc:
            raise BenchmarkValidationError("mirror strategy is not authorized") from exc
        object.__setattr__(self, "mirror_strategy", mirror_strategy)
        for point in self.keypoints:
            if point.coordinate is None:
                continue
            if not 0.0 <= point.coordinate.pixel_x <= self.image_width - 1:
                raise BenchmarkValidationError("pixel x coordinate is outside image bounds")
            if not 0.0 <= point.coordinate.pixel_y <= self.image_height - 1:
                raise BenchmarkValidationError("pixel y coordinate is outside image bounds")
            if not 0.0 <= point.coordinate.normalized_x <= 1.0:
                raise BenchmarkValidationError("normalized x coordinate is outside image bounds")
            if not 0.0 <= point.coordinate.normalized_y <= 1.0:
                raise BenchmarkValidationError("normalized y coordinate is outside image bounds")

    @property
    def synthetic(self) -> bool:
        return self.provenance.synthetic

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "person_index": self.person_index,
            "keypoint_set_id": self.keypoint_set_id,
            "keypoints": [
                {
                    "keypoint_id": point.keypoint_id,
                    "partition": point.partition.value,
                    "coordinate": None
                    if point.coordinate is None
                    else {
                        "pixel_x": point.coordinate.pixel_x,
                        "pixel_y": point.coordinate.pixel_y,
                        "normalized_x": point.coordinate.normalized_x,
                        "normalized_y": point.coordinate.normalized_y,
                    },
                    "confidence": point.confidence,
                    "visibility": point.visibility.value,
                    "anatomical_side": point.anatomical_side.value,
                }
                for point in self.keypoints
            ],
            "provenance": {
                "producer_type": self.provenance.producer_type,
                "producer_id": self.provenance.producer_id,
                "model_id": self.provenance.model_id,
                "model_revision": self.provenance.model_revision,
                "artifact_sha256": self.provenance.artifact_sha256,
                "synthetic": self.provenance.synthetic,
            },
            "mirror_strategy": self.mirror_strategy.value,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "joint_angles": {
                name: {
                    "degrees": angle.degrees,
                    "status": angle.status,
                    "confidence": angle.confidence,
                    "method": angle.method,
                }
                for name, angle in sorted(self.joint_angles.items())
            },
            "uncertainties": list(self.uncertainties),
            "model_artifact_present": self.model_artifact_present,
        }
