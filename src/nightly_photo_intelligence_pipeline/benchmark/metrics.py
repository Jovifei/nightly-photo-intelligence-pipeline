"""Typed, attested benchmark DTOs for the synthetic-only N2A harness."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from typing import cast

from ..domain.errors import (
    NPI_BACKEND_NOT_AVAILABLE,
    NPI_DETERMINISM_MISMATCH,
    NPI_FAKE_BACKEND_PROVENANCE_MISMATCH,
    NPI_INCONSISTENT_BOUNDING_BOX,
    NPI_INTERNAL_BENCHMARK_ERROR,
    NPI_INVALID_BENCHMARK_CASE,
    NPI_INVALID_BOUNDING_BOX,
    NPI_INVALID_MEASUREMENT_ATTESTATION,
    NPI_INVALID_PROVENANCE,
    NPI_INVALID_SIDE_LABEL,
    NPI_MODEL_NOT_AUTHORIZED,
    NPI_NON_FINITE_NUMBER,
    NPI_SCHEMA_VALIDATION_FAILED,
    BenchmarkValidationError,
    InvalidMeasurementAttestationError,
)
from ..domain.numeric import require_finite_number


class MeasurementStatus(StrEnum):
    NOT_MEASURED = "NOT_MEASURED"
    MEASURED = "MEASURED"
    UNAVAILABLE = "UNAVAILABLE"


class BenchmarkCaseStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"


class BenchmarkErrorCategory(StrEnum):
    DETERMINISM = "DETERMINISM"
    VALIDATION = "VALIDATION"
    EXECUTION = "EXECUTION"


BENCHMARK_ERROR_CODES = frozenset(
    {
        NPI_MODEL_NOT_AUTHORIZED,
        NPI_BACKEND_NOT_AVAILABLE,
        NPI_INVALID_BENCHMARK_CASE,
        NPI_SCHEMA_VALIDATION_FAILED,
        NPI_DETERMINISM_MISMATCH,
        NPI_INVALID_PROVENANCE,
        NPI_INVALID_SIDE_LABEL,
        NPI_INVALID_MEASUREMENT_ATTESTATION,
        NPI_FAKE_BACKEND_PROVENANCE_MISMATCH,
        NPI_NON_FINITE_NUMBER,
        NPI_INVALID_BOUNDING_BOX,
        NPI_INCONSISTENT_BOUNDING_BOX,
        NPI_INTERNAL_BENCHMARK_ERROR,
    }
)
_FAILURE_CODES = frozenset({NPI_DETERMINISM_MISMATCH})
_EXECUTION_CODES = frozenset(
    {NPI_MODEL_NOT_AUTHORIZED, NPI_BACKEND_NOT_AVAILABLE, NPI_INTERNAL_BENCHMARK_ERROR}
)
_UNAVAILABLE_REASON_CODES = frozenset({NPI_MODEL_NOT_AUTHORIZED, NPI_BACKEND_NOT_AVAILABLE})


@dataclass(frozen=True)
class Measurement:
    status: MeasurementStatus
    value: float | None
    unit: str | None
    measurement_source: str | None
    environment_ref: str | None
    reason_code: str | None = None

    def __post_init__(self) -> None:
        try:
            status = MeasurementStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise InvalidMeasurementAttestationError(
                "measurement status is not authorized"
            ) from exc
        object.__setattr__(self, "status", status)
        if status == MeasurementStatus.MEASURED:
            if (
                self.value is None
                or not self.unit
                or not self.measurement_source
                or not self.environment_ref
                or self.reason_code is not None
            ):
                raise InvalidMeasurementAttestationError(
                    "MEASURED metric requires finite value, unit, source, and environment reference"
                )
            object.__setattr__(self, "value", require_finite_number(self.value))
        elif status == MeasurementStatus.NOT_MEASURED:
            if any(
                value is not None
                for value in (
                    self.value,
                    self.unit,
                    self.measurement_source,
                    self.environment_ref,
                    self.reason_code,
                )
            ):
                raise InvalidMeasurementAttestationError(
                    "NOT_MEASURED metric cannot contain measurement evidence"
                )
        elif (
            self.value is not None
            or self.unit is not None
            or self.measurement_source is not None
            or self.environment_ref is not None
            or self.reason_code not in _UNAVAILABLE_REASON_CODES
        ):
            raise InvalidMeasurementAttestationError(
                "UNAVAILABLE metric requires only a stable unavailable reason"
            )

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "value": self.value,
            "unit": self.unit,
            "measurement_source": self.measurement_source,
            "environment_ref": self.environment_ref,
            "reason_code": self.reason_code,
        }


def not_measured() -> Measurement:
    return Measurement(MeasurementStatus.NOT_MEASURED, None, None, None, None)


@dataclass(frozen=True)
class BenchmarkCaseResult:
    case_id: str
    profile: str
    backend_id: str
    backend_type: str
    synthetic: bool
    input_fixture_ref: str
    status: BenchmarkCaseStatus
    error_code: str | None
    error_category: BenchmarkErrorCategory | None
    processing_time: Measurement
    gpu_peak_memory: Measurement
    cpu_peak_memory: Measurement
    deterministic_rerun_match: bool
    schema_valid: bool
    provenance: dict[str, object]
    uncertainties: tuple[str, ...]
    output_summary: dict[str, object]

    def __post_init__(self) -> None:
        try:
            status = BenchmarkCaseStatus(self.status)
        except (TypeError, ValueError) as exc:
            raise BenchmarkValidationError("benchmark case status is not authorized") from exc
        if status == BenchmarkCaseStatus.PASS:
            if self.error_code is not None or self.error_category is not None:
                raise BenchmarkValidationError("PASS benchmark case cannot contain an error")
            object.__setattr__(self, "status", status)
            return
        if self.error_code not in BENCHMARK_ERROR_CODES:
            raise BenchmarkValidationError("benchmark case error code is not authorized")
        expected_category = error_category_for(self.error_code)
        category_value = self.error_category
        if category_value is None:
            raise BenchmarkValidationError("benchmark error category is required")
        try:
            category = BenchmarkErrorCategory(cast(str, category_value))
        except ValueError as exc:
            raise BenchmarkValidationError("benchmark error category is not authorized") from exc
        if category != expected_category:
            raise BenchmarkValidationError("benchmark error category does not match error code")
        if status == BenchmarkCaseStatus.FAIL and self.error_code not in _FAILURE_CODES:
            raise BenchmarkValidationError("FAIL benchmark case requires a business failure code")
        if status == BenchmarkCaseStatus.ERROR and self.error_code in _FAILURE_CODES:
            raise BenchmarkValidationError(
                "ERROR benchmark case requires an execution or validation code"
            )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "error_category", category)

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "profile": self.profile,
            "backend_id": self.backend_id,
            "backend_type": self.backend_type,
            "synthetic": self.synthetic,
            "input_fixture_ref": self.input_fixture_ref,
            "status": self.status,
            "error_code": self.error_code,
            "error_category": self.error_category,
            "processing_time": self.processing_time.to_redacted_dict(),
            "gpu_peak_memory": self.gpu_peak_memory.to_redacted_dict(),
            "cpu_peak_memory": self.cpu_peak_memory.to_redacted_dict(),
            "deterministic_rerun": {"count": 1, "match": self.deterministic_rerun_match},
            "schema_validation": {
                "valid": self.schema_valid,
                "error_code": None if self.schema_valid else "NPI_SCHEMA_VALIDATION_FAILED",
            },
            "provenance": self.provenance,
            "uncertainties": list(self.uncertainties),
            "output_summary": self.output_summary,
        }


@dataclass(frozen=True)
class BenchmarkAggregate:
    profile: str
    backend_identity: str
    cases: tuple[BenchmarkCaseResult, ...]

    def __post_init__(self) -> None:
        if len(self.cases) != 20:
            raise BenchmarkValidationError("N2A benchmark aggregate requires exactly 20 cases")

    def to_redacted_dict(self) -> dict[str, object]:
        statuses = Counter(case.status for case in self.cases)
        errors = Counter(case.error_code for case in self.cases if case.error_code is not None)
        measurements = (
            measurement.status
            for case in self.cases
            for measurement in (case.processing_time, case.gpu_peak_memory, case.cpu_peak_memory)
        )
        coverage = Counter(measurements)
        total = len(self.cases)
        return {
            "total_cases": total,
            "passed_cases": statuses[BenchmarkCaseStatus.PASS],
            "failed_cases": statuses[BenchmarkCaseStatus.FAIL],
            "error_cases": statuses[BenchmarkCaseStatus.ERROR],
            "pass_rate": require_finite_number(statuses[BenchmarkCaseStatus.PASS] / total),
            "failure_distribution": dict(sorted(errors.items())),
            "backend_identity": self.backend_identity,
            "deterministic_rerun_count": total,
            "deterministic_mismatch_count": sum(
                not case.deterministic_rerun_match for case in self.cases
            ),
            "schema_pass_count": sum(case.schema_valid for case in self.cases),
            "schema_fail_count": sum(not case.schema_valid for case in self.cases),
            "measurement_coverage": {
                "measured": coverage[MeasurementStatus.MEASURED],
                "not_measured": coverage[MeasurementStatus.NOT_MEASURED],
                "unavailable": coverage[MeasurementStatus.UNAVAILABLE],
            },
            "threshold_status": "NOT_CALIBRATED",
            "threshold_uncertainty": (
                "synthetic metadata validation does not calibrate real-model thresholds"
            ),
            "synthetic_only": True,
            "ready_for_real_benchmark": False,
            "authorization_status": "N2B_LOCKED",
            "no_artifact_attestation": True,
        }


def error_category_for(error_code: str) -> BenchmarkErrorCategory:
    if error_code == NPI_DETERMINISM_MISMATCH:
        return BenchmarkErrorCategory.DETERMINISM
    if error_code in _EXECUTION_CODES:
        return BenchmarkErrorCategory.EXECUTION
    return BenchmarkErrorCategory.VALIDATION
