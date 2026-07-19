"""N2A remediation tests: fail-closed contracts and synthetic-only product harness."""

from __future__ import annotations

import copy
import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

import nightly_photo_intelligence_pipeline.benchmark.runner as benchmark_runner
from nightly_photo_intelligence_pipeline.benchmark.metrics import (
    BenchmarkCaseStatus,
    Measurement,
    MeasurementStatus,
)
from nightly_photo_intelligence_pipeline.benchmark.protocol import BenchmarkProfile
from nightly_photo_intelligence_pipeline.benchmark.runner import (
    _evaluate_pose_case,
    plan_profile,
    run_profile,
    validate_profile,
)
from nightly_photo_intelligence_pipeline.benchmark.schema import (
    strict_json_dumps,
    validate_document,
)
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.errors import (
    NPI_DETERMINISM_MISMATCH,
    NPI_INCONSISTENT_BOUNDING_BOX,
    NPI_INVALID_BOUNDING_BOX,
    NPI_MODEL_NOT_AUTHORIZED,
    NPI_NON_FINITE_NUMBER,
    NPI_SCHEMA_VALIDATION_FAILED,
    BenchmarkValidationError,
    FakeBackendProvenanceMismatchError,
    InconsistentBoundingBoxError,
    InvalidBoundingBoxError,
    InvalidMeasurementAttestationError,
    InvalidProvenanceError,
    InvalidSideLabelError,
    ModelNotAuthorizedError,
    NonFiniteNumberError,
    SchemaValidationFailedError,
)
from nightly_photo_intelligence_pipeline.domain.provenance import ProducerType, Provenance
from nightly_photo_intelligence_pipeline.pose.contracts import (
    AnatomicalSide,
    Coordinate,
    JointAngle,
    Keypoint,
    PoseInput,
)
from nightly_photo_intelligence_pipeline.pose.fake_backend import FakePoseBackend
from nightly_photo_intelligence_pipeline.pose.geometry import (
    derive_joint_angles,
    joint_angle,
    mirror_pose,
    stable_person_order,
)
from nightly_photo_intelligence_pipeline.pose.validation import validate_pose_result
from nightly_photo_intelligence_pipeline.segmentation.contracts import (
    NormalizedBoundingBox,
    SegmentationInput,
    validate_normalized_bbox_mapping,
)
from nightly_photo_intelligence_pipeline.segmentation.fake_backend import FakeSegmentationBackend


def _pose_document() -> dict[str, object]:
    result = FakePoseBackend().predict(PoseInput("n2a-pose-01", 640, 480))
    return benchmark_runner._pose_document((result,), "fake-pose-v1")


def _segmentation_document() -> dict[str, object]:
    result = FakeSegmentationBackend().predict(SegmentationInput("n2a-segmentation-01", 800, 600))
    return benchmark_runner._segmentation_document(result, "fake-segmentation-v1")


def test_fake_pose_contract_is_deterministic_explicitly_synthetic_and_valid() -> None:
    first = FakePoseBackend().predict(PoseInput("n2a-pose-01", 640, 480))
    second = FakePoseBackend().predict(PoseInput("n2a-pose-01", 640, 480))
    assert first.to_redacted_dict() == second.to_redacted_dict()
    assert first.provenance.producer_type == ProducerType.FAKE_BACKEND
    assert first.provenance.synthetic is True
    assert first.model_artifact_present is False
    validate_pose_result(first)


def test_pose_side_validation_uses_explicit_mapping_and_double_mirror_restores() -> None:
    result = FakePoseBackend().predict(PoseInput("n2a-pose-02", 640, 480))
    wrong_side = replace(result.keypoints[0], anatomical_side=AnatomicalSide.RIGHT)
    with pytest.raises(InvalidSideLabelError, match="incompatible") as exc_info:
        validate_pose_result(replace(result, keypoints=(wrong_side, *result.keypoints[1:])))
    assert exc_info.value.error_code == "NPI_INVALID_SIDE_LABEL"
    assert (
        mirror_pose(mirror_pose(result, 640), 640).to_redacted_dict() == result.to_redacted_dict()
    )


def test_pose_rejects_ambiguous_side_nonfinite_coordinates_and_missing_case() -> None:
    with pytest.raises(InvalidSideLabelError, match="explicit enum") as exc_info:
        Keypoint("left_shoulder", "BODY", None, 1.0, "VISIBLE", "left_or_right")
    assert exc_info.value.error_code == "NPI_INVALID_SIDE_LABEL"
    result = FakePoseBackend().predict(PoseInput("n2a-pose-03", 640, 480))
    with pytest.raises(NonFiniteNumberError) as non_finite:
        Coordinate(float("nan"), 1.0, 0.1, 0.1)
    assert non_finite.value.error_code == NPI_NON_FINITE_NUMBER
    with pytest.raises(BenchmarkValidationError, match="case_id") as missing_case:
        validate_pose_result(replace(result, case_id=""))
    assert missing_case.value.error_code == "NPI_INVALID_BENCHMARK_CASE"


def test_pose_geometry_and_stable_person_order_are_deterministic() -> None:
    one = FakePoseBackend().predict(PoseInput("n2a-pose-04", 640, 480))
    points = {point.keypoint_id: point for point in one.keypoints}
    angles = derive_joint_angles(
        points, {"shoulder_line": ("left_shoulder", "nose", "right_shoulder")}
    )
    assert angles["shoulder_line"].status == "DEFINED"
    assert (
        derive_joint_angles(points, {"missing": ("nose", "absent", "nose")})["missing"].status
        == "MISSING_KEYPOINT"
    )
    two = replace(one, person_index=2)
    assert [item.person_index for item in stable_person_order((two, one))] == [0, 2]


@pytest.mark.parametrize(
    "provenance",
    [
        pytest.param(
            {"producer_type": ProducerType.FAKE_BACKEND, "producer_id": "fake", "synthetic": False},
            id="fake-cannot-claim-real",
        ),
        pytest.param(
            {"producer_type": ProducerType.REAL_MODEL, "producer_id": "real", "synthetic": True},
            id="real-cannot-claim-synthetic",
        ),
        pytest.param(
            {"producer_type": ProducerType.REAL_MODEL, "producer_id": "real", "synthetic": False},
            id="real-requires-artifact-provenance",
        ),
        pytest.param(
            {"producer_type": "VLM_TEXT", "producer_id": "text", "synthetic": False},
            id="vlm-pose-producer-rejected",
        ),
    ],
)
def test_provenance_matrix_is_fail_closed(provenance: dict[str, object]) -> None:
    with pytest.raises(InvalidProvenanceError) as error:
        Provenance(**provenance)  # type: ignore[arg-type]
    assert error.value.error_code == "NPI_INVALID_PROVENANCE"


def test_fake_segmentation_is_metadata_only_deterministic_and_valid() -> None:
    first = FakeSegmentationBackend().predict(SegmentationInput("n2a-segmentation-01", 800, 600))
    second = FakeSegmentationBackend().predict(SegmentationInput("n2a-segmentation-01", 800, 600))
    assert first.to_redacted_dict() == second.to_redacted_dict()
    assert first.provenance.producer_type == ProducerType.FAKE_BACKEND
    assert first.mask_format.value == "METADATA_ONLY"
    assert first.mask_artifact_present is False
    assert first.to_redacted_dict()["provenance"]["model_id"] is None


@pytest.mark.parametrize(
    ("factory", "required_fragment"),
    [
        (_pose_document, "people"),
        (_pose_document, "provenance"),
        (_segmentation_document, "bbox"),
        (_segmentation_document, "mask_metadata"),
    ],
)
def test_schema_rejects_required_field_omissions(factory, required_fragment: str) -> None:
    document = factory()
    document.pop(required_fragment)
    with pytest.raises(SchemaValidationFailedError):
        validate_document(document)


def test_schema_rejects_vlm_fake_real_confusion_extra_property_and_bad_side() -> None:
    pose = _pose_document()
    vlm = copy.deepcopy(pose)
    vlm["provenance"]["producer_type"] = "VLM_TEXT"
    with pytest.raises(SchemaValidationFailedError):
        validate_document(vlm)
    fake_claims_real = copy.deepcopy(pose)
    fake_claims_real["synthetic"] = False
    with pytest.raises(SchemaValidationFailedError):
        validate_document(fake_claims_real)
    extra = copy.deepcopy(pose)
    extra["undeclared_property"] = True
    with pytest.raises(SchemaValidationFailedError):
        validate_document(extra)
    bad_side = copy.deepcopy(pose)
    bad_side["people"][0]["keypoints"][0]["anatomical_side"] = "UNKNOWN"
    with pytest.raises(SchemaValidationFailedError):
        validate_document(bad_side)


def test_schema_rejects_bbox_overflow_and_n2a_mask_paths() -> None:
    segmentation = _segmentation_document()
    segmentation["bbox"]["x"] = 800.0
    with pytest.raises(InconsistentBoundingBoxError) as bbox_error:
        validate_document(segmentation)
    assert bbox_error.value.error_code == NPI_INCONSISTENT_BOUNDING_BOX
    path_document = _segmentation_document()
    path_document["mask_metadata"]["artifact_path"] = "not-allowed-mask.png"
    with pytest.raises(SchemaValidationFailedError):
        validate_document(path_document)


def test_measurement_attestation_rejects_fabricated_values_and_missing_evidence() -> None:
    with pytest.raises(InvalidMeasurementAttestationError):
        Measurement(MeasurementStatus.NOT_MEASURED, 12.0, "MiB", None, None)
    with pytest.raises(InvalidMeasurementAttestationError):
        Measurement(MeasurementStatus.MEASURED, 12.0, "MiB", None, "env")
    report = validate_profile(BenchmarkProfile.POSE, "fake").to_redacted_dict()
    fabricated = copy.deepcopy(report)
    fabricated["cases"][0]["gpu_peak_memory"]["value"] = 12.0
    with pytest.raises(SchemaValidationFailedError):
        validate_document(fabricated)
    missing_source = copy.deepcopy(report)
    metric = missing_source["cases"][0]["processing_time"]
    metric.update(
        {
            "status": "MEASURED",
            "value": 1.0,
            "unit": "ms",
            "measurement_source": None,
            "environment_ref": "fake",
        }
    )
    with pytest.raises(SchemaValidationFailedError):
        validate_document(missing_source)


def test_plan_is_schema_valid_and_never_constructs_a_backend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden() -> None:
        raise AssertionError("plan must not instantiate a backend")

    monkeypatch.setattr(benchmark_runner, "FakePoseBackend", forbidden)
    plan = plan_profile(BenchmarkProfile.POSE)
    assert len(plan.cases) == 20
    assert plan.real_photo_reads is False
    validate_document(plan.to_redacted_dict())


@pytest.mark.parametrize("profile", [BenchmarkProfile.POSE, BenchmarkProfile.SEGMENTATION])
def test_fake_validate_runs_the_product_runner_for_all_twenty_cases(
    profile: BenchmarkProfile,
) -> None:
    report = validate_profile(profile, "fake")
    document = report.to_redacted_dict()
    assert len(document["cases"]) == 20
    assert all(case["status"] == "PASS" for case in document["cases"])
    if profile == BenchmarkProfile.POSE:
        two_people = next(case for case in document["cases"] if case["case_id"] == "n2a-pose-07")
        assert two_people["output_summary"]["person_count"] == 2
    assert document["aggregate"]["passed_cases"] == 20
    assert document["aggregate"]["ready_for_real_benchmark"] is False
    assert document["aggregate"]["no_artifact_attestation"] is True
    validate_document(document)


def test_runner_reports_determinism_and_schema_failures_without_native_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnstableFake(FakePoseBackend):
        calls = 0

        def predict_many(self, request: PoseInput):  # type: ignore[no-untyped-def]
            self.calls += 1
            results = super().predict_many(request)
            if self.calls % 2 == 0:
                return (replace(results[0], uncertainties=("different",)), *results[1:])
            return results

    case = plan_profile(BenchmarkProfile.POSE).cases[0]
    mismatch = _evaluate_pose_case(case, UnstableFake())
    assert mismatch.status == "FAIL"
    assert mismatch.error_code == NPI_DETERMINISM_MISMATCH
    monkeypatch.setattr(
        benchmark_runner, "_pose_document", lambda *_args: {"contract_type": "POSE_CASE"}
    )
    invalid = _evaluate_pose_case(case, FakePoseBackend())
    assert invalid.status == "ERROR"
    assert invalid.error_code == NPI_SCHEMA_VALIDATION_FAILED


def test_fake_provenance_mismatch_is_stable_and_direct_real_runner_cannot_bypass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = plan_profile(BenchmarkProfile.POSE).cases[0]
    monkeypatch.setattr(
        benchmark_runner,
        "_provenance_document",
        lambda *_args: (_ for _ in ()).throw(FakeBackendProvenanceMismatchError("redacted")),
    )
    invalid = _evaluate_pose_case(case, FakePoseBackend())
    assert invalid.error_code == "NPI_FAKE_BACKEND_PROVENANCE_MISMATCH"
    with pytest.raises(ModelNotAuthorizedError):
        run_profile(BenchmarkProfile.POSE)


def test_benchmark_cli_plan_validate_and_real_run_gate() -> None:
    runner = CliRunner()
    plan = runner.invoke(app, ["benchmark", "plan", "--profile", "pose"])
    assert plan.exit_code == 0, plan.output
    assert json.loads(plan.stdout)["case_count"] == 20
    validate = runner.invoke(
        app, ["benchmark", "validate", "--profile", "segmentation", "--backend", "fake"]
    )
    assert validate.exit_code == 0, validate.output
    payload = json.loads(validate.stdout)
    assert payload["aggregate"]["passed_cases"] == 20
    real = runner.invoke(app, ["benchmark", "run", "--profile", "pose"])
    assert real.exit_code == 8
    assert NPI_MODEL_NOT_AUTHORIZED in real.output


def test_n2a_tracked_tree_has_no_model_or_derived_image_artifacts(project_root: Path) -> None:
    tracked = subprocess.run(
        ["git", "-C", str(project_root), "ls-files"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    forbidden = (".pt", ".pth", ".ckpt", ".safetensors", ".onnx", ".engine", ".npy", ".npz")
    assert not [path for path in tracked if path.lower().endswith(forbidden)]
    generated_names = ("thumbnail", "cutout", "mask", "embedding", "skeleton")
    assert not [
        path
        for path in tracked
        if any(token in Path(path).stem.lower() for token in generated_names)
    ]


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(lambda: Coordinate(float("inf"), 1.0, 0.1, 0.1), id="pose-pixel-x"),
        pytest.param(lambda: Coordinate(1.0, 1.0, 0.1, float("-inf")), id="pose-normalized-y"),
        pytest.param(
            lambda: Keypoint("nose", "BODY", None, float("nan"), "VISIBLE"),
            id="pose-confidence",
        ),
        pytest.param(lambda: JointAngle(float("nan"), "DEFINED", 1.0), id="joint-angle"),
        pytest.param(
            lambda: replace(
                FakeSegmentationBackend().predict(
                    SegmentationInput("n2a-segmentation-02", 800, 600)
                ),
                confidence=float("nan"),
            ),
            id="segmentation-confidence",
        ),
    ],
)
def test_dtos_reject_non_finite_numbers_at_construction(factory) -> None:
    with pytest.raises(NonFiniteNumberError) as error:
        factory()
    assert error.value.error_code == NPI_NON_FINITE_NUMBER


@pytest.mark.parametrize(
    ("values", "error_type", "error_code"),
    [
        pytest.param(
            {"x": float("nan"), "y": 0.1, "width": 0.2, "height": 0.2},
            NonFiniteNumberError,
            NPI_NON_FINITE_NUMBER,
            id="bbox-x-nan",
        ),
        pytest.param(
            {"x": 0.1, "y": 0.1, "width": float("inf"), "height": 0.2},
            NonFiniteNumberError,
            NPI_NON_FINITE_NUMBER,
            id="bbox-width-infinity",
        ),
        pytest.param(
            {"x": 0.1, "y": 0.1, "width": 0.0, "height": 0.2},
            InvalidBoundingBoxError,
            NPI_INVALID_BOUNDING_BOX,
            id="bbox-width-zero",
        ),
        pytest.param(
            {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.0},
            InvalidBoundingBoxError,
            NPI_INVALID_BOUNDING_BOX,
            id="bbox-height-zero",
        ),
        pytest.param(
            {"x": 0.1, "y": 0.1, "width": -0.2, "height": 0.2},
            InvalidBoundingBoxError,
            NPI_INVALID_BOUNDING_BOX,
            id="bbox-negative-width",
        ),
        pytest.param(
            {"x": 0.8, "y": 0.1, "width": 0.3, "height": 0.2},
            InconsistentBoundingBoxError,
            NPI_INCONSISTENT_BOUNDING_BOX,
            id="bbox-x-overflow",
        ),
        pytest.param(
            {"x": 0.1, "y": 0.8, "width": 0.2, "height": 0.3},
            InconsistentBoundingBoxError,
            NPI_INCONSISTENT_BOUNDING_BOX,
            id="bbox-y-overflow",
        ),
    ],
)
def test_bbox_schema_dto_parity_matrix(values, error_type, error_code) -> None:
    document = _segmentation_document()
    document["bbox"].update(values)
    with pytest.raises(error_type) as schema_error:
        validate_document(document)
    with pytest.raises(error_type) as dto_error:
        NormalizedBoundingBox(**values)
    assert schema_error.value.error_code == error_code
    assert dto_error.value.error_code == error_code


def test_bbox_has_no_independent_derived_fields_and_properties_are_deterministic() -> None:
    box = NormalizedBoundingBox(0.1, 0.2, 0.3, 0.4)
    assert box.to_dict() == {"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}
    assert box.right == pytest.approx(0.4)
    assert box.bottom == pytest.approx(0.6)
    document = _segmentation_document()
    document["bbox"]["right"] = 0.4
    with pytest.raises(InvalidBoundingBoxError):
        validate_document(document)
    with pytest.raises(InvalidBoundingBoxError):
        validate_normalized_bbox_mapping(document["bbox"])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_strict_json_schema_and_measurement_boundaries_reject_non_finite_values(
    value: float,
) -> None:
    with pytest.raises(NonFiniteNumberError):
        strict_json_dumps({"value": value})
    pose = _pose_document()
    pose["people"][0]["keypoints"][0]["confidence"] = value
    with pytest.raises(NonFiniteNumberError) as schema_error:
        validate_document(pose)
    assert schema_error.value.error_code == NPI_NON_FINITE_NUMBER
    with pytest.raises(NonFiniteNumberError):
        Measurement(MeasurementStatus.MEASURED, value, "MiB", "probe", "synthetic-env")
    report = validate_profile(BenchmarkProfile.POSE, "fake").to_redacted_dict()
    report["aggregate"]["pass_rate"] = value
    with pytest.raises(NonFiniteNumberError):
        validate_document(report)


def test_measurement_attestation_matrix_is_closed_at_dto_construction() -> None:
    with pytest.raises(InvalidMeasurementAttestationError) as unknown:
        Measurement("UNKNOWN", None, None, None, None)  # type: ignore[arg-type]
    assert unknown.value.error_code == "NPI_INVALID_MEASUREMENT_ATTESTATION"
    with pytest.raises(InvalidMeasurementAttestationError):
        Measurement(MeasurementStatus.NOT_MEASURED, None, "MiB", None, None)
    with pytest.raises(InvalidMeasurementAttestationError):
        Measurement(
            MeasurementStatus.UNAVAILABLE, 1.0, None, None, None, "NPI_BACKEND_NOT_AVAILABLE"
        )
    with pytest.raises(InvalidMeasurementAttestationError):
        Measurement(
            MeasurementStatus.UNAVAILABLE, None, None, None, None, "NPI_INVALID_BENCHMARK_CASE"
        )
    with pytest.raises(InvalidMeasurementAttestationError):
        Measurement(MeasurementStatus.MEASURED, 1.0, None, "probe", "synthetic-env")
    measured = Measurement(MeasurementStatus.MEASURED, 1.0, "ms", "probe", "synthetic-env")
    unavailable = Measurement(
        MeasurementStatus.UNAVAILABLE,
        None,
        None,
        None,
        None,
        "NPI_BACKEND_NOT_AVAILABLE",
    )
    assert measured.to_redacted_dict()["reason_code"] is None
    assert unavailable.to_redacted_dict()["reason_code"] == "NPI_BACKEND_NOT_AVAILABLE"


def test_case_status_taxonomy_is_closed_for_dto_and_schema() -> None:
    case = validate_profile(BenchmarkProfile.POSE, "fake").cases[0]
    invalid_case_factories = (
        lambda: replace(
            case,
            status=BenchmarkCaseStatus.PASS,
            error_code=NPI_DETERMINISM_MISMATCH,
            error_category="DETERMINISM",
        ),
        lambda: replace(
            case, status=BenchmarkCaseStatus.FAIL, error_code=None, error_category=None
        ),
        lambda: replace(
            case, status=BenchmarkCaseStatus.ERROR, error_code=None, error_category=None
        ),
        lambda: replace(case, status="UNKNOWN", error_code=None, error_category=None),  # type: ignore[arg-type]
        lambda: replace(
            case,
            status=BenchmarkCaseStatus.ERROR,
            error_code="NPI_UNKNOWN",
            error_category="VALIDATION",
        ),
    )
    for factory in invalid_case_factories:
        with pytest.raises(BenchmarkValidationError):
            factory()
    report = validate_profile(BenchmarkProfile.POSE, "fake").to_redacted_dict()
    report["cases"][0]["status"] = "PASS"
    report["cases"][0]["error_code"] = NPI_DETERMINISM_MISMATCH
    report["cases"][0]["error_category"] = "DETERMINISM"
    with pytest.raises(SchemaValidationFailedError):
        validate_document(report)


@pytest.mark.parametrize(
    ("first", "vertex", "last"),
    [
        pytest.param(
            Coordinate(0.0, 0.0, 0.0, 0.0),
            Coordinate(0.0, 0.0, 0.0, 0.0),
            Coordinate(1.0, 0.0, 1.0, 0.0),
            id="first-vector-zero-length",
        ),
        pytest.param(
            Coordinate(1.0, 0.0, 1.0, 0.0),
            Coordinate(0.0, 0.0, 0.0, 0.0),
            Coordinate(0.0, 0.0, 0.0, 0.0),
            id="second-vector-zero-length",
        ),
        pytest.param(
            Coordinate(0.0, 0.0, 0.0, 0.0),
            Coordinate(0.0, 0.0, 0.0, 0.0),
            Coordinate(0.0, 0.0, 0.0, 0.0),
            id="all-points-coincident",
        ),
    ],
)
def test_joint_angle_zero_length_vectors_are_explicitly_undefined(
    first: Coordinate, vertex: Coordinate, last: Coordinate
) -> None:
    result = joint_angle(first, vertex, last)
    assert result.status == "UNDEFINED_ZERO_LENGTH"
    assert result.degrees is None
    assert result.confidence == 0.0
