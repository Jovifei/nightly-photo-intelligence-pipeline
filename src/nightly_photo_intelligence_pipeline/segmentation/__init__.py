"""Model-free segmentation metadata contracts for N2A."""

from .contracts import (
    BoundingBox,
    MaskFormat,
    NormalizedBoundingBox,
    SegmentationInput,
    SegmentationProvenance,
    SegmentationResult,
    SegmentationStatus,
)

__all__ = [
    "BoundingBox",
    "NormalizedBoundingBox",
    "MaskFormat",
    "SegmentationInput",
    "SegmentationProvenance",
    "SegmentationResult",
    "SegmentationStatus",
]
