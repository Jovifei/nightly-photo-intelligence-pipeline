"""Deterministic synthetic pose backend for contract tests only."""

from __future__ import annotations

import hashlib

from ..domain.provenance import ProducerType
from .contracts import (
    AnatomicalSide,
    Coordinate,
    Keypoint,
    KeypointPartition,
    PoseInput,
    PoseProvenance,
    PoseResult,
    Visibility,
)
from .validation import validate_pose_result


class FakePoseBackend:
    backend_id = "fake-pose-v1"
    synthetic = True

    def predict(self, request: PoseInput) -> PoseResult:
        """Return the primary synthetic person for protocol compatibility."""

        return self.predict_many(request)[0]

    def predict_many(self, request: PoseInput) -> tuple[PoseResult, ...]:
        """Return a stable anonymous person collection from metadata only."""

        if request.image_width < 1 or request.image_height < 1:
            raise ValueError("image dimensions must be positive")
        if request.person_count_hint < 1:
            raise ValueError("person_count_hint must be positive")
        return tuple(
            self._predict_person(request, person_index)
            for person_index in range(request.person_count_hint)
        )

    def _predict_person(self, request: PoseInput, person_index: int) -> PoseResult:
        digest = hashlib.sha256(request.case_id.encode("utf-8")).digest()
        x_offset = ((digest[0] % 5) + person_index) / 100.0
        point_specs = (
            ("left_shoulder", AnatomicalSide.LEFT, round(0.35 + x_offset, 12), 0.30),
            ("right_shoulder", AnatomicalSide.RIGHT, round(0.65 + x_offset, 12), 0.30),
            ("left_hip", AnatomicalSide.LEFT, round(0.40 + x_offset, 12), 0.62),
            ("right_hip", AnatomicalSide.RIGHT, round(0.60 + x_offset, 12), 0.62),
            ("nose", AnatomicalSide.CENTER, 0.50 + x_offset, 0.18),
        )
        points = tuple(
            Keypoint(
                keypoint_id=keypoint_id,
                partition=KeypointPartition.BODY,
                coordinate=Coordinate(
                    pixel_x=round(x * (request.image_width - 1), 12),
                    pixel_y=round(y * (request.image_height - 1), 12),
                    normalized_x=x,
                    normalized_y=y,
                ),
                confidence=1.0,
                visibility=Visibility.VISIBLE,
                anatomical_side=side,
            )
            for keypoint_id, side, x, y in point_specs
        )
        result = PoseResult(
            case_id=request.case_id,
            person_index=person_index,
            keypoint_set_id="synthetic.body.v1",
            keypoints=points,
            provenance=PoseProvenance(
                producer_type=ProducerType.FAKE_BACKEND,
                producer_id=self.backend_id,
                synthetic=True,
            ),
            mirror_strategy=request.mirror_strategy,
            image_width=request.image_width,
            image_height=request.image_height,
            uncertainties=("synthetic_input",),
        )
        validate_pose_result(result)
        return result
