"""Synthetic-only N2A benchmark product path and N2B fail-closed boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from ..domain.authorization import AuthorizationSnapshot, load_authorization
from ..domain.errors import (
    BackendNotAvailableError,
    BenchmarkValidationError,
    FakeBackendProvenanceMismatchError,
    ModelNotAuthorizedError,
    NpiError,
    SchemaValidationFailedError,
)
from ..domain.provenance import ProducerType
from ..pose.contracts import PoseInput, PoseResult
from ..pose.fake_backend import FakePoseBackend
from ..pose.validation import validate_pose_result
from ..segmentation.contracts import (
    SegmentationInput,
    SegmentationResult,
    validate_segmentation_result,
)
from ..segmentation.fake_backend import FakeSegmentationBackend
from .metrics import (
    BenchmarkAggregate,
    BenchmarkCaseResult,
    BenchmarkCaseStatus,
    BenchmarkErrorCategory,
    error_category_for,
    not_measured,
)
from .protocol import BenchmarkCase, BenchmarkPlan, BenchmarkProfile
from .schema import validate_document, validate_fragment


@dataclass(frozen=True)
class BenchmarkRunReport:
    profile: BenchmarkProfile
    backend_id: str
    cases: tuple[BenchmarkCaseResult, ...]
    aggregate: BenchmarkAggregate

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "contract_type": "BENCHMARK_REPORT",
            "schema_version": "1.1",
            "profile": self.profile.value,
            "backend_id": self.backend_id,
            "backend_type": "FAKE_BACKEND",
            "synthetic": True,
            "cases": [case.to_redacted_dict() for case in self.cases],
            "aggregate": self.aggregate.to_redacted_dict(),
        }


def plan_profile(profile: BenchmarkProfile) -> BenchmarkPlan:
    """Build a deterministic metadata-only plan without constructing a backend."""

    plan = BenchmarkPlan.for_profile(profile)
    validate_document(plan.to_redacted_dict())
    return plan


def benchmark_status(auth: AuthorizationSnapshot | None = None) -> dict[str, object]:
    snapshot = auth or load_authorization()
    return {
        "n2a": snapshot.n2a_status,
        "n2b_model_download_and_inference": snapshot.n2b_status,
        "profiles": [profile.value for profile in BenchmarkProfile],
        "model_execution": "LOCKED" if not snapshot.n2b_model_authorized else "AUTHORIZED",
        "fake_validation": "AUTHORIZED" if snapshot.n2a_authorized else "LOCKED",
        "real_photo_reads": False,
        "model_downloads": "NOT_AUTHORIZED" if not snapshot.n2b_model_authorized else "AUTHORIZED",
    }


def _provenance_document(result: PoseResult | SegmentationResult) -> dict[str, object]:
    provenance = result.provenance
    if provenance.producer_type != ProducerType.FAKE_BACKEND or not provenance.synthetic:
        raise FakeBackendProvenanceMismatchError("fake backend result has invalid provenance")
    return {
        "producer_type": provenance.producer_type.value,
        "producer_id": provenance.producer_id,
        "synthetic": provenance.synthetic,
        "model_id": provenance.model_id,
        "model_revision": provenance.model_revision,
        "artifact_sha256": provenance.artifact_sha256,
    }


def _pose_document(results: tuple[PoseResult, ...], backend_id: str) -> dict[str, object]:
    if not results:
        raise SchemaValidationFailedError("synthetic pose case requires a person collection")
    primary = results[0]
    people = [
        {
            "person_index": result.person_index,
            "keypoint_set_id": result.keypoint_set_id,
            "coordinate_space": "PIXEL_AND_NORMALIZED",
            "keypoints": [
                {
                    "keypoint_id": point.keypoint_id,
                    "partition": point.partition.value,
                    "coordinate_space": "PIXEL_AND_NORMALIZED",
                    "pixel": {"x": point.coordinate.pixel_x, "y": point.coordinate.pixel_y},
                    "normalized": {
                        "x": point.coordinate.normalized_x,
                        "y": point.coordinate.normalized_y,
                    },
                    "confidence": point.confidence,
                    "visibility": point.visibility.value,
                    "anatomical_side": point.anatomical_side.value,
                }
                for point in result.keypoints
                if point.coordinate is not None
            ],
            "deterministic_derived": {"source": "KEYPOINTS_ONLY"},
            "raw_model_output_boundary": {"raw_model_output_present": False},
        }
        for result in results
    ]
    return {
        "contract_type": "POSE_CASE",
        "schema_version": "1.1",
        "case_id": primary.case_id,
        "profile": BenchmarkProfile.POSE.value,
        "backend_id": backend_id,
        "backend_type": "FAKE_BACKEND",
        "source_type": "SYNTHETIC",
        "synthetic": True,
        "image_width": primary.image_width,
        "image_height": primary.image_height,
        "people": people,
        "provenance": _provenance_document(primary),
        "uncertainties": list(primary.uncertainties),
        "model_artifact_present": primary.model_artifact_present,
    }


def _segmentation_document(result: SegmentationResult, backend_id: str) -> dict[str, object]:
    if result.bounding_box is None:
        raise SchemaValidationFailedError(
            "synthetic segmentation result requires bounding box metadata"
        )
    box = result.bounding_box
    return {
        "contract_type": "SEGMENTATION_CASE",
        "schema_version": "1.1",
        "case_id": result.case_id,
        "profile": BenchmarkProfile.SEGMENTATION.value,
        "backend_id": backend_id,
        "backend_type": "FAKE_BACKEND",
        "source_type": "SYNTHETIC",
        "synthetic": True,
        "image_width": result.image_width,
        "image_height": result.image_height,
        "person_index": result.person_index,
        "bbox": {
            "coordinate_space": "NORMALIZED",
            **box.normalized(result.image_width, result.image_height).to_dict(),
        },
        "mask_metadata": {"mask_format": result.mask_format.value, "artifact_path": None},
        "confidence": result.confidence,
        "confidence_status": "KNOWN",
        "quality_flags": list(result.quality_flags),
        "provenance": _provenance_document(result),
        "uncertainties": list(result.uncertainties),
        "mask_artifact_count": 0,
    }


def _error_case(
    case: BenchmarkCase, profile: BenchmarkProfile, backend_id: str, error: NpiError
) -> BenchmarkCaseResult:
    return BenchmarkCaseResult(
        case_id=case.case_id,
        profile=profile.value,
        backend_id=backend_id,
        backend_type="FAKE_BACKEND",
        synthetic=True,
        input_fixture_ref=case.fixture_ref,
        status=BenchmarkCaseStatus.ERROR,
        error_code=error.error_code,
        error_category=error_category_for(error.error_code),
        processing_time=not_measured(),
        gpu_peak_memory=not_measured(),
        cpu_peak_memory=not_measured(),
        deterministic_rerun_match=False,
        schema_valid=False,
        provenance={
            "producer_type": "FAKE_BACKEND",
            "producer_id": backend_id,
            "synthetic": True,
            "model_id": None,
            "model_revision": None,
            "artifact_sha256": None,
        },
        uncertainties=("synthetic_harness_error",),
        output_summary={
            "kind": "POSE" if profile == BenchmarkProfile.POSE else "SEGMENTATION",
            "person_count": 1,
            "artifact_count": 0,
            "keypoint_set_id": None,
            "keypoint_count": None,
            "geometry_valid": None,
            "mirror_side_valid": None,
            "bbox_valid": None,
            "mask_metadata_valid": None,
        },
    )


def _evaluate_pose_case(case: BenchmarkCase, backend: FakePoseBackend) -> BenchmarkCaseResult:
    try:
        request = PoseInput(case.case_id, case.image_width, case.image_height, case.expected_people)
        first = backend.predict_many(request)
        second = backend.predict_many(request)
        for person in first:
            validate_pose_result(person)
        document = _pose_document(first, backend.backend_id)
        validate_document(document)
        deterministic = tuple(person.to_redacted_dict() for person in first) == tuple(
            person.to_redacted_dict() for person in second
        )
        primary = first[0]
        result = BenchmarkCaseResult(
            case_id=case.case_id,
            profile=BenchmarkProfile.POSE.value,
            backend_id=backend.backend_id,
            backend_type="FAKE_BACKEND",
            synthetic=True,
            input_fixture_ref=case.fixture_ref,
            status=BenchmarkCaseStatus.PASS if deterministic else BenchmarkCaseStatus.FAIL,
            error_code=None if deterministic else "NPI_DETERMINISM_MISMATCH",
            error_category=None if deterministic else BenchmarkErrorCategory.DETERMINISM,
            processing_time=not_measured(),
            gpu_peak_memory=not_measured(),
            cpu_peak_memory=not_measured(),
            deterministic_rerun_match=deterministic,
            schema_valid=True,
            provenance=cast(dict[str, object], document["provenance"]),
            uncertainties=tuple(primary.uncertainties),
            output_summary={
                "kind": "POSE",
                "person_count": len(first),
                "artifact_count": 0,
                "keypoint_set_id": primary.keypoint_set_id,
                "keypoint_count": len(primary.keypoints),
                "geometry_valid": True,
                "mirror_side_valid": True,
                "bbox_valid": None,
                "mask_metadata_valid": None,
            },
        )
        validate_fragment("benchmarkCase", result.to_redacted_dict())
        return result
    except NpiError as error:
        return _error_case(case, BenchmarkProfile.POSE, backend.backend_id, error)
    except ValueError:
        return _error_case(
            case,
            BenchmarkProfile.POSE,
            backend.backend_id,
            BenchmarkValidationError("invalid synthetic pose benchmark case"),
        )


def _evaluate_segmentation_case(
    case: BenchmarkCase, backend: FakeSegmentationBackend
) -> BenchmarkCaseResult:
    try:
        request = SegmentationInput(case.case_id, case.image_width, case.image_height)
        first = backend.predict(request)
        second = backend.predict(request)
        validate_segmentation_result(first)
        document = _segmentation_document(first, backend.backend_id)
        validate_document(document)
        deterministic = first.to_redacted_dict() == second.to_redacted_dict()
        result = BenchmarkCaseResult(
            case_id=case.case_id,
            profile=BenchmarkProfile.SEGMENTATION.value,
            backend_id=backend.backend_id,
            backend_type="FAKE_BACKEND",
            synthetic=True,
            input_fixture_ref=case.fixture_ref,
            status=BenchmarkCaseStatus.PASS if deterministic else BenchmarkCaseStatus.FAIL,
            error_code=None if deterministic else "NPI_DETERMINISM_MISMATCH",
            error_category=None if deterministic else BenchmarkErrorCategory.DETERMINISM,
            processing_time=not_measured(),
            gpu_peak_memory=not_measured(),
            cpu_peak_memory=not_measured(),
            deterministic_rerun_match=deterministic,
            schema_valid=True,
            provenance=cast(dict[str, object], document["provenance"]),
            uncertainties=tuple(first.uncertainties),
            output_summary={
                "kind": "SEGMENTATION",
                "person_count": 1,
                "artifact_count": 0,
                "keypoint_set_id": None,
                "keypoint_count": None,
                "geometry_valid": None,
                "mirror_side_valid": None,
                "bbox_valid": True,
                "mask_metadata_valid": True,
            },
        )
        validate_fragment("benchmarkCase", result.to_redacted_dict())
        return result
    except NpiError as error:
        return _error_case(case, BenchmarkProfile.SEGMENTATION, backend.backend_id, error)
    except ValueError:
        return _error_case(
            case,
            BenchmarkProfile.SEGMENTATION,
            backend.backend_id,
            BenchmarkValidationError("invalid synthetic segmentation benchmark case"),
        )


def validate_profile(
    profile: BenchmarkProfile,
    backend: str,
    auth: AuthorizationSnapshot | None = None,
) -> BenchmarkRunReport:
    """Execute the only N2A runnable path: deterministic fake metadata validation."""

    snapshot = auth or load_authorization()
    if not snapshot.n2a_authorized:
        raise BackendNotAvailableError("N2A fake benchmark validation is not authorized")
    if backend != "fake":
        raise BackendNotAvailableError("only the synthetic fake backend is available in N2A")
    plan = plan_profile(profile)
    if profile == BenchmarkProfile.POSE:
        pose_fake = FakePoseBackend()
        cases = tuple(_evaluate_pose_case(case, pose_fake) for case in plan.cases)
        backend_id = pose_fake.backend_id
    else:
        segmentation_fake = FakeSegmentationBackend()
        cases = tuple(_evaluate_segmentation_case(case, segmentation_fake) for case in plan.cases)
        backend_id = segmentation_fake.backend_id
    aggregate = BenchmarkAggregate(profile.value, backend_id, cases)
    report = BenchmarkRunReport(profile, backend_id, cases, aggregate)
    validate_document(report.to_redacted_dict())
    return report


def run_profile(
    profile: BenchmarkProfile, auth: AuthorizationSnapshot | None = None
) -> BenchmarkAggregate:
    """Fail closed before a real backend can be constructed or invoked."""

    snapshot = auth or load_authorization()
    if not snapshot.n2b_model_authorized:
        raise ModelNotAuthorizedError(
            f"benchmark execution is locked for profile {profile.value}; N2B is not authorized"
        )
    raise ModelNotAuthorizedError(
        "model-backed benchmark runner is not implemented in N2A; use the approved N2B gate"
    )
