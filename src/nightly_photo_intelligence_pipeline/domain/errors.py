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
NPI_SOURCE_RUNTIME_OVERLAP = "NPI_SOURCE_RUNTIME_OVERLAP"
NPI_SOURCE_SYMLINK_ESCAPE = "NPI_SOURCE_SYMLINK_ESCAPE"
NPI_SOURCE_CHANGED_DURING_READ = "NPI_SOURCE_CHANGED_DURING_READ"
NPI_UNSUPPORTED_MEDIA = "NPI_UNSUPPORTED_MEDIA"
NPI_DATABASE_ERROR = "NPI_DATABASE_ERROR"
NPI_SCHEMA_INVALID = "NPI_SCHEMA_INVALID"
NPI_HANDOFF_INTEGRITY_FAILED = "NPI_HANDOFF_INTEGRITY_FAILED"
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


class SourceRuntimeOverlapError(NpiError):
    error_code = NPI_SOURCE_RUNTIME_OVERLAP
    exit_code = ExitCode.SECURITY_BOUNDARY


class SourceSymlinkEscapeError(NpiError):
    error_code = NPI_SOURCE_SYMLINK_ESCAPE
    exit_code = ExitCode.SECURITY_BOUNDARY


class SourceChangedDuringReadError(NpiError):
    error_code = NPI_SOURCE_CHANGED_DURING_READ
    exit_code = ExitCode.SECURITY_BOUNDARY


class UnsupportedMediaError(NpiError):
    error_code = NPI_UNSUPPORTED_MEDIA
    exit_code = ExitCode.PARTIAL_FAILURE


class DatabaseError(NpiError):
    error_code = NPI_DATABASE_ERROR
    exit_code = ExitCode.DATABASE_ERROR


class SchemaInvalidError(NpiError):
    error_code = NPI_SCHEMA_INVALID
    exit_code = ExitCode.SCHEMA_CONFIG_ERROR


class HandoffIntegrityError(NpiError):
    error_code = NPI_HANDOFF_INTEGRITY_FAILED
    exit_code = ExitCode.INTEGRITY_FAILED


# Map error_code string -> ExitCode for callers that only have the string.
ERROR_CODE_TO_EXIT: dict[str, ExitCode] = {
    NPI_CLI_USAGE_ERROR: ExitCode.CLI_USAGE_ERROR,
    NPI_PREFLIGHT_UNSATISFIED: ExitCode.PREFLIGHT_UNSATISFIED,
    NPI_GATE_NOT_AUTHORIZED: ExitCode.GATE_NOT_AUTHORIZED,
    NPI_SOURCE_RUNTIME_OVERLAP: ExitCode.SECURITY_BOUNDARY,
    NPI_SOURCE_SYMLINK_ESCAPE: ExitCode.SECURITY_BOUNDARY,
    NPI_SOURCE_CHANGED_DURING_READ: ExitCode.SECURITY_BOUNDARY,
    NPI_UNSUPPORTED_MEDIA: ExitCode.PARTIAL_FAILURE,
    NPI_DATABASE_ERROR: ExitCode.DATABASE_ERROR,
    NPI_SCHEMA_INVALID: ExitCode.SCHEMA_CONFIG_ERROR,
    NPI_HANDOFF_INTEGRITY_FAILED: ExitCode.INTEGRITY_FAILED,
    NPI_INTERNAL_ERROR: ExitCode.INTERNAL_ERROR,
}


def exit_code_for(error_code: str) -> ExitCode:
    """Return the ExitCode for an error_code string, defaulting to INTERNAL_ERROR."""
    return ERROR_CODE_TO_EXIT.get(error_code, ExitCode.INTERNAL_ERROR)
