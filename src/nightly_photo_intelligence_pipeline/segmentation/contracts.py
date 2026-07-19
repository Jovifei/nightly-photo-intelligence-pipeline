"""Typed segmentation metadata with no mask bytes or image artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from ..domain.errors import (
    BenchmarkValidationError,
    InconsistentBoundingBoxError,
    InvalidBoundingBoxError,
)
from ..domain.numeric import require_finite_number
from ..domain.provenance import Provenance, validate_provenance


class MaskFormat(StrEnum):
    METADATA_ONLY = "METADATA_ONLY"
    BINARY_MASK = "BINARY_MASK"
    SOFT_MASK = "SOFT_MASK"


class SegmentationStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    OCCLUDED = "OCCLUDED"
    OUT_OF_FRAME = "OUT_OF_FRAME"
    NOT_MEASURED = "NOT_MEASURED"


@dataclass(frozen=True)
class BoundingBox:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", require_finite_number(self.x))
        object.__setattr__(self, "y", require_finite_number(self.y))
        object.__setattr__(self, "width", require_finite_number(self.width))
        object.__setattr__(self, "height", require_finite_number(self.height))
        if self.x < 0.0 or self.y < 0.0 or self.width <= 0.0 or self.height <= 0.0:
            raise InvalidBoundingBoxError("bounding box dimensions must be positive and in bounds")

    def is_finite(self) -> bool:
        return True

    @property
    def right(self) -> float:
        """Derived only; it is never an independent public schema field."""

        return self.x + self.width

    @property
    def bottom(self) -> float:
        """Derived only; it is never an independent public schema field."""

        return self.y + self.height

    def normalized(self, image_width: int, image_height: int) -> NormalizedBoundingBox:
        if image_width < 1 or image_height < 1:
            raise BenchmarkValidationError("image dimensions must be positive")
        return NormalizedBoundingBox(
            x=self.x / image_width,
            y=self.y / image_height,
            width=self.width / image_width,
            height=self.height / image_height,
        )


@dataclass(frozen=True)
class NormalizedBoundingBox:
    """The sole serialized BBox contract: x/y/width/height in [0, 1]."""

    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        _validate_normalized_bbox_values(self.x, self.y, self.width, self.height)
        object.__setattr__(self, "x", float(self.x))
        object.__setattr__(self, "y", float(self.y))
        object.__setattr__(self, "width", float(self.width))
        object.__setattr__(self, "height", float(self.height))

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def to_dict(self) -> dict[str, float]:
        return {"x": self.x, "y": self.y, "width": self.width, "height": self.height}


def _validate_normalized_bbox_values(x: object, y: object, width: object, height: object) -> None:
    normalized_x = require_finite_number(x)
    normalized_y = require_finite_number(y)
    normalized_width = require_finite_number(width)
    normalized_height = require_finite_number(height)
    if normalized_x < 0.0 or normalized_y < 0.0:
        raise InvalidBoundingBoxError("bounding box origin must be non-negative")
    if normalized_width <= 0.0 or normalized_height <= 0.0:
        raise InvalidBoundingBoxError("bounding box dimensions must be positive")
    if normalized_x + normalized_width > 1.0 or normalized_y + normalized_height > 1.0:
        raise InconsistentBoundingBoxError("normalized bounding box exceeds its unit frame")


def validate_normalized_bbox_mapping(box: Mapping[str, object]) -> None:
    """Apply the DTO BBox semantics to a public Schema payload."""

    required = {"coordinate_space", "x", "y", "width", "height"}
    if set(box) != required or box.get("coordinate_space") != "NORMALIZED":
        raise InvalidBoundingBoxError("public bounding box has an invalid field set")
    _validate_normalized_bbox_values(box["x"], box["y"], box["width"], box["height"])


@dataclass(frozen=True)
class SegmentationInput:
    case_id: str
    image_width: int
    image_height: int
    person_index: int = 0


SegmentationProvenance = Provenance


@dataclass(frozen=True)
class SegmentationResult:
    case_id: str
    image_width: int
    image_height: int
    person_index: int
    mask_format: MaskFormat
    confidence: float
    bounding_box: BoundingBox | None
    quality_flags: tuple[str, ...]
    uncertainties: tuple[str, ...]
    status: SegmentationStatus
    provenance: SegmentationProvenance
    mask_artifact_present: bool = False

    def __post_init__(self) -> None:
        if (
            not self.case_id
            or self.image_width < 1
            or self.image_height < 1
            or self.person_index < 0
        ):
            raise BenchmarkValidationError("segmentation identity and dimensions must be valid")
        try:
            mask_format = MaskFormat(self.mask_format)
            status = SegmentationStatus(self.status)
        except ValueError as exc:
            raise BenchmarkValidationError("segmentation enum is not authorized") from exc
        confidence = require_finite_number(self.confidence)
        if not 0.0 <= confidence <= 1.0:
            raise BenchmarkValidationError("segmentation confidence must be in the accepted range")
        object.__setattr__(self, "mask_format", mask_format)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "confidence", confidence)
        if self.bounding_box is not None:
            box = self.bounding_box
            if box.right > self.image_width or box.bottom > self.image_height:
                raise InconsistentBoundingBoxError("pixel bounding box exceeds image bounds")

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "person_index": self.person_index,
            "mask_format": self.mask_format.value,
            "confidence": self.confidence,
            "bounding_box": None
            if self.bounding_box is None
            else self.bounding_box.normalized(self.image_width, self.image_height).to_dict(),
            "quality_flags": list(self.quality_flags),
            "uncertainties": list(self.uncertainties),
            "status": self.status.value,
            "provenance": {
                "producer_type": self.provenance.producer_type,
                "producer_id": self.provenance.producer_id,
                "model_id": self.provenance.model_id,
                "model_revision": self.provenance.model_revision,
                "artifact_sha256": self.provenance.artifact_sha256,
                "synthetic": self.provenance.synthetic,
            },
            "mask_artifact_present": self.mask_artifact_present,
        }


def validate_segmentation_result(result: SegmentationResult) -> None:
    """Reject invalid metadata and any synthetic mask artifact."""

    if not result.case_id:
        raise BenchmarkValidationError("case_id is required")
    if result.image_width < 1 or result.image_height < 1:
        raise BenchmarkValidationError("image dimensions must be positive")
    if result.person_index < 0:
        raise BenchmarkValidationError("person_index must be non-negative")
    if not 0.0 <= result.confidence <= 1.0:
        raise BenchmarkValidationError("confidence must be in the accepted range")
    validate_provenance(result.provenance)
    if result.provenance.synthetic and result.mask_artifact_present:
        raise BenchmarkValidationError("synthetic result cannot contain a mask artifact")
    if result.bounding_box is not None:
        box = result.bounding_box
        if box.right > result.image_width:
            raise InconsistentBoundingBoxError("bounding box exceeds image width")
        if box.bottom > result.image_height:
            raise InconsistentBoundingBoxError("bounding box exceeds image height")
