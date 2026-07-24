"""Pure, fail-closed policy checks for future N2B1/N2B2 artifact work.

N2B0.5 is not a download stage.  These helpers deliberately inspect only
caller-supplied metadata and policy objects; they perform no network, file,
archive, cache, or model operation.  A future stage must pass this policy
before it is allowed to introduce an I/O implementation.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, NoReturn, cast
from urllib.parse import unquote, urlparse, urlsplit

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from .domain.errors import (
    ArtifactFilenameMismatchError,
    ArtifactRevisionMismatchError,
    ArtifactSizeLimitExceededError,
    DuplicateJsonMemberError,
    GateNotAuthorizedError,
    InvalidOwnerSizeLimitError,
    OfficialArtifactHashMismatchError,
    OwnerSizeLimitRequiredError,
    ProjectStateSchemaInvalidError,
    QualificationSnapshotSchemaInvalidError,
    QuarantineApprovalExpiredError,
    QuarantineApprovalNotYetValidError,
    QuarantineApprovalSchemaInvalidError,
    QuarantineApprovalStateMismatchError,
    QuarantineApprovalTimeRangeInvalidError,
    QuarantineRightsNotQualifiedError,
    UnsupportedDocumentSchemaVersionError,
)
from .json_strict import loads_json_strict

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_RFC3339_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T.+(?:Z|[+-]\d{2}:\d{2})$")
_SAFE_ARCHIVE_SUFFIXES = frozenset({".json", ".pdiparams", ".pdmodel", ".txt", ".yaml", ".yml"})
_REVISION_KINDS = frozenset(
    {"GIT_COMMIT", "GIT_TAG", "RELEASE_ASSET_VERSION", "OBJECT_VERSION", "CHECKPOINT_REVISION"}
)
_FLOATING_REVISION_VALUES = frozenset({"LATEST", "MAIN", "MASTER", "FLOATING_URL"})
_NON_REVISION_MARKERS = frozenset({"ETAG", "LAST-MODIFIED", "LASTMODIFIED", "CONTENT-LENGTH"})
_RIGHTS_STATUS_FIELDS = (
    "code_license_status",
    "weights_license_status",
    "commercial_use_status",
    "artifact_identity_status",
    "immutable_revision_status",
    "official_hash_status",
    "ready_for_quarantine_download",
)
_SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas"
_SCHEMA_CATALOG = _SCHEMA_ROOT / "current_stage_schema_catalog.json"
_FIXED_SCHEMA_FILES: dict[str, dict[str, str]] = {
    "approval": {"1.0": "n2b1_quarantine_approval_v1_0.schema.json"},
    "qualification_snapshot": {"1.0": "model_artifact_qualification_snapshot_v1.schema.json"},
    "project_state": {
        "1.2": "project_state_v1_2.schema.json",
        "1.3": "project_state_v1_3.schema.json",
    },
}

__all__ = [
    "ArchiveEntry",
    "ArtifactRevisionEvidence",
    "TransportMetadata",
    "ValidatedN2B1QuarantineApproval",
    "ValidatedQuarantineRequest",
    "ValidatedTransportMetadata",
    "require_cache_promotion_authorized",
    "require_pth_quarantine_operation",
    "require_real_model_execution_authorized",
    "validate_n2b1_quarantine_request",
    "validate_zip_entries",
]


def _deny() -> NoReturn:
    """Raise a stable, payload-free denial for all artifact policy failures."""

    raise GateNotAuthorizedError("model artifact action is not authorized")


def _mapping(value: object) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _deny()
    return cast(Mapping[str, Any], value)


def _authorized(state: Mapping[str, object], phase: str, capability: str) -> bool:
    phase_status = _mapping(state.get("phase_status"))
    authorization = _mapping(state.get("authorization"))
    gates = _mapping(authorization.get("capability_gates"))
    return phase_status.get(phase) == "AUTHORIZED" and gates.get(capability) == "AUTHORIZED"


def _approved_for_stage(
    approval: Mapping[str, object] | None, artifact_id: str, stage: str
) -> bool:
    if approval is None or not isinstance(approval, Mapping):
        return False
    return (
        approval.get("status") == "APPROVED"
        and approval.get("artifact_id") == artifact_id
        and approval.get("stage") == stage
    )


def _is_positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_safe_filename(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    normalized = unicodedata.normalize("NFC", value)
    return (
        normalized not in {".", ".."}
        and "/" not in normalized
        and "\\" not in normalized
        and "\x00" not in normalized
        and not any(unicodedata.category(character) == "Cc" for character in normalized)
    )


def _is_nonblank_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_owner_max_bytes(owner_max_bytes: object) -> int:
    if owner_max_bytes is None:
        raise OwnerSizeLimitRequiredError("Owner size limit is required")
    if not _is_positive_integer(owner_max_bytes):
        raise InvalidOwnerSizeLimitError("Owner size limit is invalid")
    return cast(int, owner_max_bytes)


def _require_final_filename(*, final_url: str, expected_artifact_filename: str | None) -> None:
    if not _is_safe_filename(expected_artifact_filename):
        raise ArtifactFilenameMismatchError("final artifact filename does not match approval")
    parsed = urlparse(final_url)
    encoded_basename = parsed.path.rsplit("/", 1)[-1]
    try:
        basename = unicodedata.normalize("NFC", unquote(encoded_basename, errors="strict"))
    except UnicodeDecodeError:
        raise ArtifactFilenameMismatchError(
            "final artifact filename does not match approval"
        ) from None
    expected = unicodedata.normalize("NFC", cast(str, expected_artifact_filename))
    if not _is_safe_filename(basename) or basename != expected:
        raise ArtifactFilenameMismatchError("final artifact filename does not match approval")


def _validate_candidate_rights(candidate: Mapping[str, object]) -> None:
    """Require verified weights rights, commercial grant, revision, and SHA-256.

    Code-license information, HTTP metadata, ETag, and Last-Modified are not
    inputs to this decision and cannot compensate for a missing weights grant
    or immutable artifact identity.
    """

    weights_license = candidate.get("weights_license")
    commercial = candidate.get("commercial_use_status")
    revision = candidate.get("artifact_revision")
    expected_sha256 = candidate.get("expected_sha256")
    if not isinstance(weights_license, str) or not weights_license.strip():
        _deny()
    if weights_license.strip().upper() == "UNKNOWN":
        _deny()
    if commercial != "PERMITTED":
        _deny()
    if not isinstance(revision, str) or not revision.strip() or "UNKNOWN" in revision.upper():
        _deny()
    if not isinstance(expected_sha256, str) or not _SHA256.fullmatch(expected_sha256):
        _deny()


def _canonical_json_digest(value: Mapping[str, object]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _strict_document(payload: bytes) -> Mapping[str, object]:
    if not isinstance(payload, bytes):
        _deny()
    try:
        document = loads_json_strict(payload)
    except DuplicateJsonMemberError:
        raise
    except (UnicodeDecodeError, ValueError):
        _deny()
    return _mapping(document)


def _raise_schema_error(document_kind: str) -> NoReturn:
    if document_kind == "approval":
        raise QuarantineApprovalSchemaInvalidError("quarantine approval schema is invalid")
    if document_kind == "qualification_snapshot":
        raise QualificationSnapshotSchemaInvalidError("qualification snapshot schema is invalid")
    if document_kind == "project_state":
        raise ProjectStateSchemaInvalidError("project state schema is invalid")
    _deny()


def _schema_version(document: Mapping[str, object], document_kind: str) -> str:
    version = document.get("schema_version")
    if not isinstance(version, str) or version not in _FIXED_SCHEMA_FILES[document_kind]:
        raise UnsupportedDocumentSchemaVersionError("document schema version is not supported")
    return version


@cache
def _fixed_schema_validator(document_kind: str, version: str) -> Draft202012Validator:
    """Load a catalog-listed local Schema; callers cannot select its path or bytes."""

    filename = _FIXED_SCHEMA_FILES[document_kind].get(version)
    if filename is None:
        raise UnsupportedDocumentSchemaVersionError("document schema version is not supported")
    try:
        catalog = _mapping(loads_json_strict(_SCHEMA_CATALOG.read_bytes()))
        schemas = catalog.get("schemas")
        if not isinstance(schemas, list) or not any(
            isinstance(entry, Mapping) and entry.get("file") == filename for entry in schemas
        ):
            _raise_schema_error(document_kind)
        schema = _mapping(loads_json_strict((_SCHEMA_ROOT / filename).read_bytes()))
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except UnsupportedDocumentSchemaVersionError:
        raise
    except (OSError, UnicodeError, ValueError, DuplicateJsonMemberError):
        _raise_schema_error(document_kind)


def _validate_document_schema(document: Mapping[str, object], document_kind: str) -> None:
    version = _schema_version(document, document_kind)
    if list(_fixed_schema_validator(document_kind, version).iter_errors(document)):
        _raise_schema_error(document_kind)
    timestamp_fields = ("issued_at", "not_before", "expires_at")
    if document_kind == "approval" and not all(
        _is_rfc3339_timestamp(document[field]) for field in timestamp_fields
    ):
        _raise_schema_error(document_kind)


def _is_rfc3339_timestamp(value: object) -> bool:
    if not isinstance(value, str) or _RFC3339_TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


def _parse_timestamp(value: object) -> datetime:
    if not isinstance(value, str):
        _deny()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _deny()
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _deny()
    return parsed.astimezone(UTC)


def _canonical_domain(domain: object) -> str:
    if (
        not isinstance(domain, str)
        or not domain
        or any(character.isspace() for character in domain)
    ):
        _deny()
    try:
        parsed = urlsplit(f"https://{domain}")
        port = parsed.port
    except ValueError:
        _deny()
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.hostname is None
        or port is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        _deny()
    hostname = parsed.hostname
    try:
        canonical = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        _deny()
    if hostname != canonical or hostname.endswith(".") or canonical != canonical.casefold():
        _deny()
    return canonical


def _domain_from_https_url(url: object) -> str:
    if not isinstance(url, str):
        _deny()
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        _deny()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.hostname is None
        or port is not None
    ):
        _deny()
    hostname = parsed.hostname
    try:
        canonical = hostname.encode("idna").decode("ascii")
    except UnicodeError:
        _deny()
    if hostname != canonical or hostname.endswith("."):
        _deny()
    return canonical.casefold()


@dataclass(frozen=True)
class TransportMetadata:
    """Actual final-response metadata; it contains no approval-derived inputs."""

    artifact_id: str
    request_url: str
    redirect_chain: tuple[str, ...]
    redirect_count: int
    final_url: str
    http_status: int
    content_length_bytes: int
    content_type: str | None
    etag: str | None
    last_modified: str | None
    quarantine_destination_fingerprint: str


@dataclass(frozen=True)
class ArtifactRevisionEvidence:
    """Closed immutable-revision evidence from an official HTTPS source."""

    kind: str
    value: str
    source_url: str


@dataclass(frozen=True)
class ValidatedN2B1QuarantineApproval:
    """Immutable metadata output, never an authorization credential."""

    approval_id: str
    artifact_id: str
    expected_artifact_filename: str
    official_request_url: str
    allowed_request_domains: tuple[str, ...]
    allowed_final_domains: tuple[str, ...]
    redirect_limit: int
    expected_size_bytes: int
    owner_max_bytes: int
    quarantine_destination_fingerprint: str
    artifact_revision: ArtifactRevisionEvidence
    expected_sha256: str
    rights_snapshot_digest: str
    project_state_digest: str
    n2b0_5_baseline_sha: str
    issued_at: datetime
    not_before: datetime
    expires_at: datetime
    owner_decision_reference: str


@dataclass(frozen=True)
class ValidatedTransportMetadata:
    """Immutable metadata output, never an authorization credential."""

    artifact_id: str
    request_url: str
    final_url: str
    request_domain: str
    final_domain: str
    redirect_chain: tuple[str, ...]
    content_length_bytes: int
    content_type: str | None
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True)
class ValidatedQuarantineRequest:
    """Metadata-only result; it never authorizes or initiates an action."""

    approval: ValidatedN2B1QuarantineApproval
    transport: ValidatedTransportMetadata


def _validated_artifact_revision(
    value: object, *, official_request_url: str
) -> ArtifactRevisionEvidence:
    revision = _mapping(value)
    if set(revision) != {"kind", "value", "source_url"}:
        _deny()
    kind = revision.get("kind")
    evidence_value = revision.get("value")
    source_url = revision.get("source_url")
    if not isinstance(kind, str) or kind not in _REVISION_KINDS:
        _deny()
    if (
        not isinstance(evidence_value, str)
        or evidence_value != evidence_value.strip()
        or not evidence_value
    ):
        _deny()
    normalized = evidence_value.upper()
    if (
        normalized in _FLOATING_REVISION_VALUES
        or any(marker in normalized for marker in _NON_REVISION_MARKERS)
        or "://" in evidence_value
        or _DATE_ONLY.fullmatch(evidence_value) is not None
        or (kind == "GIT_COMMIT" and _GIT_COMMIT.fullmatch(evidence_value) is None)
    ):
        _deny()
    if not isinstance(source_url, str) or (
        _domain_from_https_url(source_url) != _domain_from_https_url(official_request_url)
    ):
        _deny()
    return ArtifactRevisionEvidence(kind=kind, value=evidence_value, source_url=source_url)


def _validated_official_sha256(
    value: object, *, source_url: object, official_request_url: str
) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _deny()
    if not isinstance(source_url, str) or (
        _domain_from_https_url(source_url) != _domain_from_https_url(official_request_url)
    ):
        _deny()
    return value


def _validated_approval(approval: Mapping[str, object]) -> ValidatedN2B1QuarantineApproval:
    if not all(
        _is_nonblank_text(approval.get(field))
        for field in ("approval_id", "owner", "owner_decision_reference", "artifact_id")
    ):
        _deny()
    if approval.get("revoked") is not False:
        _deny()
    if not _is_safe_filename(approval.get("expected_artifact_filename")):
        _deny()
    expected_size = approval["expected_size_bytes"]
    owner_max = approval["owner_max_bytes"]
    redirect_limit = approval["redirect_limit"]
    if not _is_positive_integer(expected_size) or not _is_positive_integer(owner_max):
        _deny()
    if cast(int, expected_size) > cast(int, owner_max):
        raise ArtifactSizeLimitExceededError("artifact exceeds Owner size limit")
    if (
        not isinstance(redirect_limit, int)
        or isinstance(redirect_limit, bool)
        or redirect_limit < 0
    ):
        _deny()
    official_request_url = cast(str, approval["official_request_url"])
    _domain_from_https_url(official_request_url)
    artifact_revision = _validated_artifact_revision(
        approval["artifact_revision"], official_request_url=official_request_url
    )
    expected_sha256 = _validated_official_sha256(
        approval["expected_sha256"],
        source_url=artifact_revision.source_url,
        official_request_url=official_request_url,
    )
    request_domains = tuple(
        _canonical_domain(item) for item in cast(list[object], approval["allowed_request_domains"])
    )
    final_domains = tuple(
        _canonical_domain(item) for item in cast(list[object], approval["allowed_final_domains"])
    )
    if len(set(request_domains)) != len(request_domains) or len(set(final_domains)) != len(
        final_domains
    ):
        _deny()
    return ValidatedN2B1QuarantineApproval(
        approval_id=cast(str, approval["approval_id"]),
        artifact_id=cast(str, approval["artifact_id"]),
        expected_artifact_filename=cast(str, approval["expected_artifact_filename"]),
        official_request_url=official_request_url,
        allowed_request_domains=request_domains,
        allowed_final_domains=final_domains,
        redirect_limit=redirect_limit,
        expected_size_bytes=cast(int, expected_size),
        owner_max_bytes=cast(int, owner_max),
        quarantine_destination_fingerprint=cast(
            str, approval["quarantine_destination_fingerprint"]
        ),
        artifact_revision=artifact_revision,
        expected_sha256=expected_sha256,
        rights_snapshot_digest=cast(str, approval["rights_snapshot_digest"]),
        project_state_digest=cast(str, approval["project_state_digest"]),
        n2b0_5_baseline_sha=cast(str, approval["n2b0_5_baseline_sha"]),
        issued_at=_parse_timestamp(approval["issued_at"]),
        not_before=_parse_timestamp(approval["not_before"]),
        expires_at=_parse_timestamp(approval["expires_at"]),
        owner_decision_reference=cast(str, approval["owner_decision_reference"]),
    )


def _require_rights_snapshot(
    approval: Mapping[str, object], qualification_snapshot: Mapping[str, object]
) -> None:
    if qualification_snapshot.get("artifact_id") != approval.get("artifact_id"):
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    if (
        qualification_snapshot.get("expected_artifact_filename")
        != approval.get("expected_artifact_filename")
        or qualification_snapshot.get("official_request_url")
        != approval.get("official_request_url")
        or qualification_snapshot.get("n2b0_5_baseline_sha") != approval.get("n2b0_5_baseline_sha")
    ):
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    if _canonical_json_digest(qualification_snapshot) != approval.get("rights_snapshot_digest"):
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    if qualification_snapshot.get("qualification_status") != "QUALIFIED":
        raise QuarantineRightsNotQualifiedError("quarantine rights are not qualified")
    if any(qualification_snapshot.get(field) != "PASS" for field in _RIGHTS_STATUS_FIELDS):
        raise QuarantineRightsNotQualifiedError("quarantine rights are not qualified")
    if any(
        approval.get(field) != qualification_snapshot.get(field) for field in _RIGHTS_STATUS_FIELDS
    ):
        raise QuarantineRightsNotQualifiedError("quarantine rights are not qualified")
    snapshot_revision = _validated_artifact_revision(
        qualification_snapshot["artifact_revision"],
        official_request_url=cast(str, qualification_snapshot["official_request_url"]),
    )
    snapshot_sha256 = _validated_official_sha256(
        qualification_snapshot["official_artifact_sha256"],
        source_url=qualification_snapshot["official_sha256_source_url"],
        official_request_url=cast(str, qualification_snapshot["official_request_url"]),
    )
    if approval.get("artifact_revision") != qualification_snapshot.get("artifact_revision"):
        raise ArtifactRevisionMismatchError(
            "artifact revision does not match qualification snapshot"
        )
    if approval.get("expected_sha256") != qualification_snapshot.get("official_artifact_sha256"):
        raise OfficialArtifactHashMismatchError(
            "artifact hash does not match qualification snapshot"
        )
    if (
        approval.get("artifact_revision")
        != {
            "kind": snapshot_revision.kind,
            "value": snapshot_revision.value,
            "source_url": snapshot_revision.source_url,
        }
        or approval.get("expected_sha256") != snapshot_sha256
    ):
        _deny()


def _require_state_and_capability(
    approval: ValidatedN2B1QuarantineApproval, project_state: Mapping[str, object]
) -> None:
    if _canonical_json_digest(project_state) != approval.project_state_digest:
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    if project_state.get("n2b0_5_baseline_sha") != approval.n2b0_5_baseline_sha:
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    baselines = _mapping(project_state.get("baselines"))
    n2b0_5 = _mapping(baselines.get("N2B0_5"))
    if n2b0_5.get("commit") != approval.n2b0_5_baseline_sha:
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    data_scope = _mapping(project_state.get("data_scope"))
    authorization = _mapping(project_state.get("authorization"))
    if (
        data_scope.get("max_assets") != 20
        or authorization.get("large_model_downloads") != "AUTHORIZED"
        or not _authorized(project_state, "N2B1_Q", "N2B1_Q_QUARANTINE_DOWNLOAD")
    ):
        _deny()


def _require_active_approval(approval: ValidatedN2B1QuarantineApproval, now: datetime) -> None:
    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
        _deny()
    instant = now.astimezone(UTC)
    if not approval.issued_at <= approval.not_before < approval.expires_at:
        raise QuarantineApprovalTimeRangeInvalidError("quarantine approval time range is invalid")
    if instant >= approval.expires_at:
        raise QuarantineApprovalExpiredError("quarantine approval is expired")
    if instant < approval.not_before:
        raise QuarantineApprovalNotYetValidError("quarantine approval is not yet valid")


def _validated_transport(
    approval: ValidatedN2B1QuarantineApproval, actual: TransportMetadata
) -> ValidatedTransportMetadata:
    if not isinstance(actual, TransportMetadata):
        _deny()
    if actual.artifact_id != approval.artifact_id:
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    if actual.request_url != approval.official_request_url:
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    if actual.quarantine_destination_fingerprint != approval.quarantine_destination_fingerprint:
        raise QuarantineApprovalStateMismatchError("quarantine approval state does not match")
    if not isinstance(actual.redirect_count, int) or isinstance(actual.redirect_count, bool):
        _deny()
    if (
        actual.redirect_count != len(actual.redirect_chain)
        or actual.redirect_count > approval.redirect_limit
    ):
        _deny()
    if actual.redirect_count == 0 and actual.final_url != actual.request_url:
        _deny()
    if actual.redirect_count > 0 and actual.redirect_chain[-1] != actual.final_url:
        _deny()
    if actual.http_status != 200:
        _deny()
    if not all(
        value is None or isinstance(value, str)
        for value in (actual.content_type, actual.etag, actual.last_modified)
    ):
        _deny()
    request_domain = _domain_from_https_url(actual.request_url)
    final_domain = _domain_from_https_url(actual.final_url)
    if (
        request_domain not in approval.allowed_request_domains
        or final_domain not in approval.allowed_final_domains
    ):
        _deny()
    for redirect_url in actual.redirect_chain:
        if _domain_from_https_url(redirect_url) not in approval.allowed_final_domains:
            _deny()
    _require_final_filename(
        final_url=actual.final_url,
        expected_artifact_filename=approval.expected_artifact_filename,
    )
    if not _is_positive_integer(actual.content_length_bytes):
        _deny()
    if actual.content_length_bytes > approval.owner_max_bytes:
        raise ArtifactSizeLimitExceededError("artifact exceeds Owner size limit")
    if actual.content_length_bytes != approval.expected_size_bytes:
        _deny()
    return ValidatedTransportMetadata(
        artifact_id=actual.artifact_id,
        request_url=actual.request_url,
        final_url=actual.final_url,
        request_domain=request_domain,
        final_domain=final_domain,
        redirect_chain=actual.redirect_chain,
        content_length_bytes=actual.content_length_bytes,
        content_type=actual.content_type,
        etag=actual.etag,
        last_modified=actual.last_modified,
    )


def validate_n2b1_quarantine_request(
    *,
    approval_document_bytes: bytes,
    qualification_snapshot_document_bytes: bytes,
    project_state_document_bytes: bytes,
    transport_metadata: TransportMetadata,
    now: datetime,
) -> ValidatedQuarantineRequest:
    """Validate one future N2B1-Q request without performing any I/O action.

    All approval-derived expectations remain private to this composition. The
    returned frozen values are output only: later actions must independently
    revalidate raw documents and cannot accept this result as a credential.
    """

    approval_document = _strict_document(approval_document_bytes)
    _validate_document_schema(approval_document, "approval")
    qualification_snapshot = _strict_document(qualification_snapshot_document_bytes)
    _validate_document_schema(qualification_snapshot, "qualification_snapshot")
    project_state = _strict_document(project_state_document_bytes)
    _validate_document_schema(project_state, "project_state")
    approval = _validated_approval(approval_document)
    _require_rights_snapshot(approval_document, qualification_snapshot)
    _require_state_and_capability(approval, project_state)
    _require_active_approval(approval, now)
    transport = _validated_transport(approval, transport_metadata)
    return ValidatedQuarantineRequest(approval=approval, transport=transport)


def require_cache_promotion_authorized(
    *,
    state: Mapping[str, object],
    artifact_id: str,
    expected_sha256: str,
    local_sha256: str | None,
    owner_approval: Mapping[str, object] | None,
) -> None:
    """Require a matching local hash plus a second N2B1-P approval."""

    if (
        not _SHA256.fullmatch(expected_sha256)
        or local_sha256 != expected_sha256
        or not _authorized(state, "N2B1_P", "N2B1_P_CACHE_PROMOTION")
        or not _approved_for_stage(owner_approval, artifact_id, "N2B1_P")
    ):
        _deny()


def require_real_model_execution_authorized(
    *,
    state: Mapping[str, object],
    artifact_id: str,
    owner_approval: Mapping[str, object] | None,
) -> None:
    """Keep cache promotion distinct from actual model execution."""

    authorization = _mapping(state.get("authorization"))
    if (
        authorization.get("real_model_execution") != "AUTHORIZED"
        or not _authorized(state, "N2B2", "N2B2_REAL_BENCHMARK")
        or not _approved_for_stage(owner_approval, artifact_id, "N2B2")
    ):
        _deny()


@dataclass(frozen=True)
class ArchiveEntry:
    """Metadata-only representation of a future ZIP entry."""

    name: str
    size_bytes: int
    is_symlink: bool = False


def validate_zip_entries(
    entries: Sequence[ArchiveEntry],
    *,
    max_entries: int,
    max_expanded_bytes: int,
) -> None:
    """Reject unsafe archive metadata without opening or extracting an archive."""

    if len(entries) > max_entries or max_entries < 1 or max_expanded_bytes < 1:
        _deny()
    total = 0
    for entry in entries:
        posix = PurePosixPath(entry.name)
        windows = PureWindowsPath(entry.name)
        if (
            not entry.name
            or posix.is_absolute()
            or windows.is_absolute()
            or windows.drive
            or ".." in posix.parts
            or ".." in windows.parts
            or entry.is_symlink
            or not isinstance(entry.size_bytes, int)
            or isinstance(entry.size_bytes, bool)
            or entry.size_bytes < 0
        ):
            _deny()
        if not entry.name.endswith("/") and posix.suffix.lower() not in _SAFE_ARCHIVE_SUFFIXES:
            _deny()
        total += entry.size_bytes
        if total > max_expanded_bytes:
            _deny()


def require_pth_quarantine_operation(operation: str) -> None:
    """Permit only metadata/byte hashing; never call ``torch.load`` in quarantine."""

    if operation != "byte_hash_and_metadata":
        _deny()
