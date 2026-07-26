"""Typed errors, stable exit codes, and redaction constants.

Exit codes are the public CLI contract (see docs/11_cli_contract.md and
config/error_taxonomy.yaml). They must never change silently.
"""

from __future__ import annotations

from enum import IntEnum


class ExitCode(IntEnum):
    """Stable CLI exit codes. Public contract - do not renumber."""

    SUCCESS = 0
    CLI_USAGE_ERROR = 2
    PREFLIGHT_UNSATISFIED = 3
    SECURITY_BOUNDARY = 4
    SCHEMA_CONFIG_ERROR = 5
    DATABASE_ERROR = 6
    PARTIAL_FAILURE = 7
    GATE_NOT_AUTHORIZED = 8
    INTEGRITY_FAILED = 9
    INTERNAL_ERROR = 10


# Error code string constants (match config/error_taxonomy.yaml exactly).
NPI_CLI_USAGE_ERROR = "NPI_CLI_USAGE_ERROR"
NPI_PREFLIGHT_UNSATISFIED = "NPI_PREFLIGHT_UNSATISFIED"
NPI_GATE_NOT_AUTHORIZED = "NPI_GATE_NOT_AUTHORIZED"
NPI_MODEL_NOT_AUTHORIZED = "NPI_MODEL_NOT_AUTHORIZED"
NPI_BACKEND_NOT_AVAILABLE = "NPI_BACKEND_NOT_AVAILABLE"
NPI_INVALID_BENCHMARK_CASE = "NPI_INVALID_BENCHMARK_CASE"
NPI_SCHEMA_VALIDATION_FAILED = "NPI_SCHEMA_VALIDATION_FAILED"
NPI_DETERMINISM_MISMATCH = "NPI_DETERMINISM_MISMATCH"
NPI_INVALID_PROVENANCE = "NPI_INVALID_PROVENANCE"
NPI_INVALID_SIDE_LABEL = "NPI_INVALID_SIDE_LABEL"
NPI_INVALID_MEASUREMENT_ATTESTATION = "NPI_INVALID_MEASUREMENT_ATTESTATION"
NPI_FAKE_BACKEND_PROVENANCE_MISMATCH = "NPI_FAKE_BACKEND_PROVENANCE_MISMATCH"
NPI_NON_FINITE_NUMBER = "NPI_NON_FINITE_NUMBER"
NPI_INVALID_BOUNDING_BOX = "NPI_INVALID_BOUNDING_BOX"
NPI_INCONSISTENT_BOUNDING_BOX = "NPI_INCONSISTENT_BOUNDING_BOX"
NPI_INTERNAL_BENCHMARK_ERROR = "NPI_INTERNAL_BENCHMARK_ERROR"
NPI_SOURCE_RUNTIME_OVERLAP = "NPI_SOURCE_RUNTIME_OVERLAP"
NPI_SOURCE_SYMLINK_ESCAPE = "NPI_SOURCE_SYMLINK_ESCAPE"
NPI_SOURCE_CHANGED_DURING_READ = "NPI_SOURCE_CHANGED_DURING_READ"
NPI_SOURCE_READ_ONLY_NOT_VERIFIED = "NPI_SOURCE_READ_ONLY_NOT_VERIFIED"
NPI_RUNTIME_POLICY_INVALID = "NPI_RUNTIME_POLICY_INVALID"
NPI_UNSUPPORTED_MEDIA = "NPI_UNSUPPORTED_MEDIA"
NPI_DATABASE_ERROR = "NPI_DATABASE_ERROR"
NPI_STAGE_CLAIM_CONFLICT = "NPI_STAGE_CLAIM_CONFLICT"
NPI_LEASE_LOST = "NPI_LEASE_LOST"
NPI_RETRY_EXHAUSTED = "NPI_RETRY_EXHAUSTED"
NPI_RUN_INTERRUPTED = "NPI_RUN_INTERRUPTED"
NPI_SCHEMA_INVALID = "NPI_SCHEMA_INVALID"
NPI_HANDOFF_INTEGRITY_FAILED = "NPI_HANDOFF_INTEGRITY_FAILED"
NPI_DUPLICATE_JSON_MEMBER = "NPI_DUPLICATE_JSON_MEMBER"
NPI_ARTIFACT_FILENAME_MISMATCH = "NPI_ARTIFACT_FILENAME_MISMATCH"
NPI_ARTIFACT_SIZE_LIMIT_EXCEEDED = "NPI_ARTIFACT_SIZE_LIMIT_EXCEEDED"
NPI_OWNER_SIZE_LIMIT_REQUIRED = "NPI_OWNER_SIZE_LIMIT_REQUIRED"
NPI_INVALID_OWNER_SIZE_LIMIT = "NPI_INVALID_OWNER_SIZE_LIMIT"
NPI_ARTIFACT_REVISION_MISMATCH = "NPI_ARTIFACT_REVISION_MISMATCH"
NPI_OFFICIAL_ARTIFACT_HASH_MISMATCH = "NPI_OFFICIAL_ARTIFACT_HASH_MISMATCH"
NPI_QUARANTINE_APPROVAL_EXPIRED = "NPI_QUARANTINE_APPROVAL_EXPIRED"
NPI_QUARANTINE_APPROVAL_NOT_YET_VALID = "NPI_QUARANTINE_APPROVAL_NOT_YET_VALID"
NPI_QUARANTINE_APPROVAL_TIME_RANGE_INVALID = "NPI_QUARANTINE_APPROVAL_TIME_RANGE_INVALID"
NPI_QUARANTINE_APPROVAL_STATE_MISMATCH = "NPI_QUARANTINE_APPROVAL_STATE_MISMATCH"
NPI_QUARANTINE_RIGHTS_NOT_QUALIFIED = "NPI_QUARANTINE_RIGHTS_NOT_QUALIFIED"
NPI_QUARANTINE_APPROVAL_SCHEMA_INVALID = "NPI_QUARANTINE_APPROVAL_SCHEMA_INVALID"
NPI_QUALIFICATION_SNAPSHOT_SCHEMA_INVALID = "NPI_QUALIFICATION_SNAPSHOT_SCHEMA_INVALID"
NPI_PROJECT_STATE_SCHEMA_INVALID = "NPI_PROJECT_STATE_SCHEMA_INVALID"
NPI_UNSUPPORTED_DOCUMENT_SCHEMA_VERSION = "NPI_UNSUPPORTED_DOCUMENT_SCHEMA_VERSION"
NPI_CANDIDATE_FILENAME_URL_MISMATCH = "NPI_CANDIDATE_FILENAME_URL_MISMATCH"
NPI_CANDIDATE_FINAL_URL_FILENAME_MISMATCH = "NPI_CANDIDATE_FINAL_URL_FILENAME_MISMATCH"
NPI_CANDIDATE_MODEL_CONFIGURATION_REVISION_MISMATCH = (
    "NPI_CANDIDATE_MODEL_CONFIGURATION_REVISION_MISMATCH"
)
NPI_CANDIDATE_EVIDENCE_URL_REQUIRED = "NPI_CANDIDATE_EVIDENCE_URL_REQUIRED"
NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED = "NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED"
NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH = "NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH"
NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING = "NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING"
NPI_CANDIDATE_LICENSE_EVIDENCE_INSUFFICIENT = "NPI_CANDIDATE_LICENSE_EVIDENCE_INSUFFICIENT"
NPI_INTERNAL_ERROR = "NPI_INTERNAL_ERROR"


# Redaction tokens (match config/error_taxonomy.yaml redaction block).
REDACT_PATH = "<SOURCE_ROOT>/<RELATIVE_OR_HASHED_NAME>"
REDACT_HOSTNAME = "<HOST_REDACTED>"
REDACT_USERNAME = "<USER_REDACTED>"
REDACT_TOKEN = "<SECRET_REDACTED>"


class NpiError(Exception):
    """Base class for all NPI domain errors.

    Carries a stable ``error_code`` string and the matching ``exit_code``.
    Messages must already be redacted before construction; this class does not
    mutate the message further.
    """

    error_code: str = NPI_INTERNAL_ERROR
    exit_code: ExitCode = ExitCode.INTERNAL_ERROR

    def __init__(self, message: str, *, error_code: str | None = None) -> None:
        super().__init__(message)
        if error_code is not None:
            self.error_code = error_code


class CliUsageError(NpiError):
    error_code = NPI_CLI_USAGE_ERROR
    exit_code = ExitCode.CLI_USAGE_ERROR


class PreflightUnsatisfiedError(NpiError):
    """Preflight found missing capabilities but made no system changes."""

    error_code = NPI_PREFLIGHT_UNSATISFIED
    exit_code = ExitCode.PREFLIGHT_UNSATISFIED


class GateNotAuthorizedError(NpiError):
    error_code = NPI_GATE_NOT_AUTHORIZED
    exit_code = ExitCode.GATE_NOT_AUTHORIZED


class ModelNotAuthorizedError(NpiError):
    """Model download or inference is outside the currently approved gate."""

    error_code = NPI_MODEL_NOT_AUTHORIZED
    exit_code = ExitCode.GATE_NOT_AUTHORIZED


class BackendNotAvailableError(NpiError):
    error_code = NPI_BACKEND_NOT_AVAILABLE
    exit_code = ExitCode.GATE_NOT_AUTHORIZED


class BenchmarkValidationError(NpiError):
    error_code = NPI_INVALID_BENCHMARK_CASE
    exit_code = ExitCode.SCHEMA_CONFIG_ERROR


class SchemaValidationFailedError(BenchmarkValidationError):
    error_code = NPI_SCHEMA_VALIDATION_FAILED


class DeterminismMismatchError(NpiError):
    error_code = NPI_DETERMINISM_MISMATCH
    exit_code = ExitCode.PARTIAL_FAILURE


class InvalidProvenanceError(BenchmarkValidationError):
    error_code = NPI_INVALID_PROVENANCE


class InvalidSideLabelError(BenchmarkValidationError):
    error_code = NPI_INVALID_SIDE_LABEL


class InvalidMeasurementAttestationError(BenchmarkValidationError):
    error_code = NPI_INVALID_MEASUREMENT_ATTESTATION


class FakeBackendProvenanceMismatchError(BenchmarkValidationError):
    error_code = NPI_FAKE_BACKEND_PROVENANCE_MISMATCH


class NonFiniteNumberError(BenchmarkValidationError):
    """A public numeric contract received NaN, Infinity, or -Infinity."""

    error_code = NPI_NON_FINITE_NUMBER


class InvalidBoundingBoxError(BenchmarkValidationError):
    error_code = NPI_INVALID_BOUNDING_BOX


class InconsistentBoundingBoxError(BenchmarkValidationError):
    error_code = NPI_INCONSISTENT_BOUNDING_BOX


class InternalBenchmarkError(NpiError):
    error_code = NPI_INTERNAL_BENCHMARK_ERROR
    exit_code = ExitCode.INTERNAL_ERROR


class SourceRuntimeOverlapError(NpiError):
    error_code = NPI_SOURCE_RUNTIME_OVERLAP
    exit_code = ExitCode.SECURITY_BOUNDARY


class SourceSymlinkEscapeError(NpiError):
    error_code = NPI_SOURCE_SYMLINK_ESCAPE
    exit_code = ExitCode.SECURITY_BOUNDARY


class SourceChangedDuringReadError(NpiError):
    error_code = NPI_SOURCE_CHANGED_DURING_READ
    exit_code = ExitCode.SECURITY_BOUNDARY


class SourceReadOnlyNotVerifiedError(NpiError):
    error_code = NPI_SOURCE_READ_ONLY_NOT_VERIFIED
    exit_code = ExitCode.SECURITY_BOUNDARY


class RuntimePolicyError(NpiError):
    error_code = NPI_RUNTIME_POLICY_INVALID
    exit_code = ExitCode.SECURITY_BOUNDARY


class UnsupportedMediaError(NpiError):
    error_code = NPI_UNSUPPORTED_MEDIA
    exit_code = ExitCode.PARTIAL_FAILURE


class DatabaseError(NpiError):
    error_code = NPI_DATABASE_ERROR
    exit_code = ExitCode.DATABASE_ERROR


class StageClaimConflictError(DatabaseError):
    error_code = NPI_STAGE_CLAIM_CONFLICT


class LeaseLostError(DatabaseError):
    error_code = NPI_LEASE_LOST


class RetryExhaustedError(DatabaseError):
    error_code = NPI_RETRY_EXHAUSTED


class SchemaInvalidError(NpiError):
    error_code = NPI_SCHEMA_INVALID
    exit_code = ExitCode.SCHEMA_CONFIG_ERROR


class QuarantineApprovalSchemaInvalidError(SchemaInvalidError):
    """The fixed N2B1-Q approval schema rejects the raw document."""

    error_code = NPI_QUARANTINE_APPROVAL_SCHEMA_INVALID


class QualificationSnapshotSchemaInvalidError(SchemaInvalidError):
    """The fixed qualification-snapshot schema rejects the raw document."""

    error_code = NPI_QUALIFICATION_SNAPSHOT_SCHEMA_INVALID


class ProjectStateSchemaInvalidError(SchemaInvalidError):
    """The fixed project-state schema rejects the raw document."""

    error_code = NPI_PROJECT_STATE_SCHEMA_INVALID


class UnsupportedDocumentSchemaVersionError(SchemaInvalidError):
    """A raw future document claims no catalog-listed schema version."""

    error_code = NPI_UNSUPPORTED_DOCUMENT_SCHEMA_VERSION


class HandoffIntegrityError(NpiError):
    error_code = NPI_HANDOFF_INTEGRITY_FAILED
    exit_code = ExitCode.INTEGRITY_FAILED


class DuplicateJsonMemberError(NpiError):
    """A security-sensitive JSON document repeats one object member."""

    error_code = NPI_DUPLICATE_JSON_MEMBER
    exit_code = ExitCode.SCHEMA_CONFIG_ERROR

    def __init__(self, member: str) -> None:
        super().__init__(f"duplicate JSON member rejected: {member!r}")


class ArtifactFilenameMismatchError(GateNotAuthorizedError):
    """The final response URL does not bind to the approved artifact filename."""

    error_code = NPI_ARTIFACT_FILENAME_MISMATCH


class ArtifactSizeLimitExceededError(GateNotAuthorizedError):
    """Transport metadata exceeds the Owner's approved artifact byte ceiling."""

    error_code = NPI_ARTIFACT_SIZE_LIMIT_EXCEEDED


class OwnerSizeLimitRequiredError(GateNotAuthorizedError):
    """A future quarantine action lacks the Owner's explicit byte ceiling."""

    error_code = NPI_OWNER_SIZE_LIMIT_REQUIRED


class InvalidOwnerSizeLimitError(GateNotAuthorizedError):
    """A supplied Owner byte ceiling is not a positive integer."""

    error_code = NPI_INVALID_OWNER_SIZE_LIMIT


class ArtifactRevisionMismatchError(GateNotAuthorizedError):
    """Approval revision evidence does not exactly bind to its snapshot."""

    error_code = NPI_ARTIFACT_REVISION_MISMATCH


class OfficialArtifactHashMismatchError(GateNotAuthorizedError):
    """Approval expected hash does not exactly bind to its snapshot."""

    error_code = NPI_OFFICIAL_ARTIFACT_HASH_MISMATCH


class QuarantineApprovalExpiredError(GateNotAuthorizedError):
    """A future N2B1-Q approval is expired at the supplied deterministic time."""

    error_code = NPI_QUARANTINE_APPROVAL_EXPIRED


class QuarantineApprovalNotYetValidError(GateNotAuthorizedError):
    """A future N2B1-Q approval is not active at the supplied time."""

    error_code = NPI_QUARANTINE_APPROVAL_NOT_YET_VALID


class QuarantineApprovalTimeRangeInvalidError(GateNotAuthorizedError):
    """A future approval's issued/not-before/expiry ordering is invalid."""

    error_code = NPI_QUARANTINE_APPROVAL_TIME_RANGE_INVALID


class QuarantineApprovalStateMismatchError(GateNotAuthorizedError):
    """Approval bindings do not match the supplied current state or snapshot."""

    error_code = NPI_QUARANTINE_APPROVAL_STATE_MISMATCH


class QuarantineRightsNotQualifiedError(GateNotAuthorizedError):
    """A future N2B1-Q approval has not closed its artifact-rights gates."""

    error_code = NPI_QUARANTINE_RIGHTS_NOT_QUALIFIED


# Map error_code string -> ExitCode for callers that only have the string.
ERROR_CODE_TO_EXIT: dict[str, ExitCode] = {
    NPI_CLI_USAGE_ERROR: ExitCode.CLI_USAGE_ERROR,
    NPI_PREFLIGHT_UNSATISFIED: ExitCode.PREFLIGHT_UNSATISFIED,
    NPI_GATE_NOT_AUTHORIZED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_MODEL_NOT_AUTHORIZED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_BACKEND_NOT_AVAILABLE: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_INVALID_BENCHMARK_CASE: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_SCHEMA_VALIDATION_FAILED: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_DETERMINISM_MISMATCH: ExitCode.PARTIAL_FAILURE,
    NPI_INVALID_PROVENANCE: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_INVALID_SIDE_LABEL: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_INVALID_MEASUREMENT_ATTESTATION: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_FAKE_BACKEND_PROVENANCE_MISMATCH: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_NON_FINITE_NUMBER: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_INVALID_BOUNDING_BOX: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_INCONSISTENT_BOUNDING_BOX: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_INTERNAL_BENCHMARK_ERROR: ExitCode.INTERNAL_ERROR,
    NPI_SOURCE_RUNTIME_OVERLAP: ExitCode.SECURITY_BOUNDARY,
    NPI_SOURCE_SYMLINK_ESCAPE: ExitCode.SECURITY_BOUNDARY,
    NPI_SOURCE_CHANGED_DURING_READ: ExitCode.SECURITY_BOUNDARY,
    NPI_SOURCE_READ_ONLY_NOT_VERIFIED: ExitCode.SECURITY_BOUNDARY,
    NPI_RUNTIME_POLICY_INVALID: ExitCode.SECURITY_BOUNDARY,
    NPI_UNSUPPORTED_MEDIA: ExitCode.PARTIAL_FAILURE,
    NPI_DATABASE_ERROR: ExitCode.DATABASE_ERROR,
    NPI_STAGE_CLAIM_CONFLICT: ExitCode.DATABASE_ERROR,
    NPI_LEASE_LOST: ExitCode.DATABASE_ERROR,
    NPI_RETRY_EXHAUSTED: ExitCode.DATABASE_ERROR,
    NPI_RUN_INTERRUPTED: ExitCode.DATABASE_ERROR,
    NPI_SCHEMA_INVALID: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_HANDOFF_INTEGRITY_FAILED: ExitCode.INTEGRITY_FAILED,
    NPI_DUPLICATE_JSON_MEMBER: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_ARTIFACT_FILENAME_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_ARTIFACT_SIZE_LIMIT_EXCEEDED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_OWNER_SIZE_LIMIT_REQUIRED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_INVALID_OWNER_SIZE_LIMIT: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_ARTIFACT_REVISION_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_OFFICIAL_ARTIFACT_HASH_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_QUARANTINE_APPROVAL_EXPIRED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_QUARANTINE_APPROVAL_NOT_YET_VALID: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_QUARANTINE_APPROVAL_TIME_RANGE_INVALID: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_QUARANTINE_APPROVAL_STATE_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_QUARANTINE_RIGHTS_NOT_QUALIFIED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_QUARANTINE_APPROVAL_SCHEMA_INVALID: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_QUALIFICATION_SNAPSHOT_SCHEMA_INVALID: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_PROJECT_STATE_SCHEMA_INVALID: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_UNSUPPORTED_DOCUMENT_SCHEMA_VERSION: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_CANDIDATE_FILENAME_URL_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_CANDIDATE_FINAL_URL_FILENAME_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_CANDIDATE_MODEL_CONFIGURATION_REVISION_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_CANDIDATE_EVIDENCE_URL_REQUIRED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_CANDIDATE_LICENSE_EVIDENCE_INSUFFICIENT: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_INTERNAL_ERROR: ExitCode.INTERNAL_ERROR,
}


def exit_code_for(error_code: str) -> ExitCode:
    """Return the ExitCode for an error_code string, defaulting to INTERNAL_ERROR."""
    return ERROR_CODE_TO_EXIT.get(error_code, ExitCode.INTERNAL_ERROR)
