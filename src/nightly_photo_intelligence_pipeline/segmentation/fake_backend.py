"""Deterministic synthetic segmentation metadata backend."""

from __future__ import annotations

import hashlib

from ..domain.provenance import ProducerType
from .contracts import (
    BoundingBox,
    MaskFormat,
    SegmentationInput,
    SegmentationProvenance,
    SegmentationResult,
    SegmentationStatus,
    validate_segmentation_result,
)


class FakeSegmentationBackend:
    backend_id = "fake-segmentation-v1"
    synthetic = True

    def predict(self, request: SegmentationInput) -> SegmentationResult:
        if request.image_width < 1 or request.image_height < 1:
            raise ValueError("image dimensions must be positive")
        digest = hashlib.sha256(request.case_id.encode("utf-8")).digest()
        x = float(digest[0] % 10) / 100.0 * request.image_width
        y = float(digest[1] % 10) / 100.0 * request.image_height
        box = BoundingBox(
            x=x,
            y=y,
            width=request.image_width * 0.50,
            height=request.image_height * 0.70,
        )
        result = SegmentationResult(
            case_id=request.case_id,
            image_width=request.image_width,
            image_height=request.image_height,
            person_index=request.person_index,
            mask_format=MaskFormat.METADATA_ONLY,
            confidence=1.0,
            bounding_box=box,
            quality_flags=("synthetic_input", "no_mask_artifact"),
            uncertainties=("synthetic_input",),
            status=SegmentationStatus.AVAILABLE,
            provenance=SegmentationProvenance(
                producer_type=ProducerType.FAKE_BACKEND,
                producer_id=self.backend_id,
                synthetic=True,
            ),
        )
        validate_segmentation_result(result)
        return result
