"""Bounded B-source network acquisition executor.

The executor never authorizes itself. It requires the exact-SHA post-review
admission and an external exact-payload absence record before it constructs a
network transport or opens the bound quarantine for mutation.
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import secrets
import ssl
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import SplitResult, urljoin, urlsplit

from jsonschema import (  # type: ignore[import-untyped]
    Draft202012Validator,
    FormatChecker,
)

from .domain.errors import GateNotAuthorizedError, NpiError
from .json_strict import load_json_strict
from .n2b1p_b_source_network import (
    POST_REVIEW_ADMISSION_STATUS,
    check_external_exact_sha_review_receipt,
    load_b_source_network_execution_binding,
)
from .windows_bound_promotion import (
    BoundDirectory,
    BoundStagingTransaction,
    bind_existing_directory,
)

_ALLOWED_DOMAIN = "download.pytorch.org"
_QUARANTINE_REF = "E_CLAUDE_ALLOW_DOWNLOAD/npi-n2b1p-b-source-quarantine-20260930-e9110783"
_QUARANTINE_IDENTITY = "ff0fc35900d4f60d906e8dbcc8d806e8d1360aee4290326049925353667f9000"
_EVIDENCE_PARENT = "npi-c2c-evidence-20260930"
_MISSING_PRECONDITION_FILENAME = "b-source-missing-payload-precondition-v1.json"
_MISSING_PRECONDITION_SCHEMA = "n2b1p_b_source_missing_payload_precondition_v1.schema.json"
_TRANSFER_SCHEMA = "n2b1p_b_source_transfer_manifest_v1.schema.json"
_RESULT_SCHEMA = "n2b1p_b_source_acquisition_result_v1.schema.json"
_LEGACY_RESULT_FILENAME = "b-source-network-acquisition-result-v1.json"
_LEASE_DIRNAME = "b-source-network-acquisition-one-shot-v1"
_RESERVATION_DIRNAME = "reservation-v1"
_RESERVATION_FILENAME = "reservation.json"
_TERMINAL_DIRNAME = "terminal-v1"
_TERMINAL_FILENAME = "terminal.json"
_LEASE_REF = f"E_CLAUDE_ALLOW_DOWNLOAD/{_EVIDENCE_PARENT}/{_LEASE_DIRNAME}"
_RESERVATION_REF = f"{_LEASE_REF}/{_RESERVATION_DIRNAME}/{_RESERVATION_FILENAME}"
_RESULT_REF = f"{_LEASE_REF}/{_TERMINAL_DIRNAME}/{_TERMINAL_FILENAME}"
_ONE_SHOT_STATE_UNCLAIMED = "UNCLAIMED"
_ONE_SHOT_STATE_CLAIMED = "CLAIMED"
_ONE_SHOT_STATE_INCOMPLETE = "INCOMPLETE_CLAIM"
_ONE_SHOT_STATE_COMPLETED = "COMPLETED"
_ONE_SHOT_TEST_HOOK: Callable[[str], None] | None = None
_QUARANTINE_LEAF = "npi-n2b1p-b-source-quarantine-20260930-e9110783"
_ROUTE_B_CACHE_LEAF = "npi-n2b1p-cache-v2-20260929"
_HISTORICAL_CACHE_LEAF = "npi-model-cache"
_CHUNK_BYTES = 1024 * 1024
_MAX_REDIRECTS = 3
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class BSourceAcquisitionError(RuntimeError):
    """Fail-closed acquisition error with a stable public code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    revision: str
    url: str
    filename: str
    byte_count: int
    sha256: str
    historical_transfer_manifest_sha256: str

    @classmethod
    def from_record(cls, record: Mapping[str, object]) -> ArtifactSpec:
        return cls(
            artifact_id=cast(str, record["id"]),
            revision=cast(str, record["revision"]),
            url=cast(str, record["url"]),
            filename=cast(str, record["filename"]),
            byte_count=cast(int, record["byte_count"]),
            sha256=cast(str, record["local_sha256"]),
            historical_transfer_manifest_sha256=cast(
                str,
                record["transfer_manifest_sha256"],
            ),
        )


class DownloadResponse(Protocol):
    @property
    def status(self) -> int: ...

    def getheader(self, name: str) -> str | None: ...

    def read(self, amount: int) -> bytes: ...

    def close(self) -> None: ...


class DownloadTransport(Protocol):
    def open(self, url: str) -> DownloadResponse: ...


class QuarantinePublisher(Protocol):
    def validate_initial_state(self) -> None: ...

    def publish(
        self,
        spec: ArtifactSpec,
        response: DownloadResponse,
        *,
        final_url: str,
        redirect_count: int,
        reviewed_head: str,
        reviewed_tree: str,
        completed_at_utc: str,
    ) -> dict[str, object]: ...


@dataclass
class _HttpResponseHandle:
    response: http.client.HTTPResponse
    connection: http.client.HTTPSConnection

    @property
    def status(self) -> int:
        return int(self.response.status)

    def getheader(self, name: str) -> str | None:
        return self.response.getheader(name)

    def read(self, amount: int) -> bytes:
        return self.response.read(amount)

    def close(self) -> None:
        try:
            self.response.close()
        finally:
            self.connection.close()


class StdlibHttpsTransport:
    """HTTPS-only transport with no automatic redirects or proxy fallback."""

    def open(self, url: str) -> DownloadResponse:
        parsed = _validate_bound_url(url)
        host = cast(str, parsed.hostname)
        connection = http.client.HTTPSConnection(
            host,
            443,
            timeout=60,
            context=ssl.create_default_context(),
        )
        try:
            connection.request(
                "GET",
                parsed.path,
                headers={
                    "Accept": "application/octet-stream",
                    "User-Agent": "npi-b-source-reacquisition/1",
                },
            )
            return _HttpResponseHandle(connection.getresponse(), connection)
        except (OSError, TimeoutError, http.client.HTTPException, ssl.SSLError):
            connection.close()
            raise


def _validate_bound_url(
    url: str,
    filename: str | None = None,
) -> SplitResult:
    try:
        parsed = urlsplit(url)
    except ValueError as exc:
        raise BSourceAcquisitionError("NPI_B_SOURCE_URL_REJECTED") from exc
    expected_path = None if filename is None else f"/models/{filename}"
    valid = (
        parsed.scheme == "https"
        and parsed.hostname == _ALLOWED_DOMAIN
        and parsed.port is None
        and parsed.username is None
        and parsed.password is None
        and parsed.query == ""
        and parsed.fragment == ""
        and parsed.path.startswith("/models/")
        and (expected_path is None or parsed.path == expected_path)
    )
    if not valid:
        raise BSourceAcquisitionError("NPI_B_SOURCE_URL_REJECTED")
    return parsed


def _open_final_response(
    transport: DownloadTransport,
    spec: ArtifactSpec,
    request_counter: list[int],
) -> tuple[DownloadResponse, str, int]:
    current = spec.url
    visited = {current}
    for redirect_count in range(_MAX_REDIRECTS + 1):
        _validate_bound_url(current, spec.filename)
        request_counter[0] += 1
        try:
            response = transport.open(current)
        except (OSError, TimeoutError, http.client.HTTPException) as exc:
            raise BSourceAcquisitionError("NPI_B_SOURCE_NETWORK_IO_ERROR") from exc
        if response.status in _REDIRECT_STATUSES:
            location = response.getheader("Location")
            response.close()
            if not location:
                raise BSourceAcquisitionError("NPI_B_SOURCE_REDIRECT_REJECTED")
            target = urljoin(current, location)
            _validate_bound_url(target, spec.filename)
            if target in visited or redirect_count >= _MAX_REDIRECTS:
                raise BSourceAcquisitionError("NPI_B_SOURCE_REDIRECT_REJECTED")
            visited.add(target)
            current = target
            continue
        if response.status != 200:
            response.close()
            raise BSourceAcquisitionError("NPI_B_SOURCE_HTTP_STATUS_REJECTED")
        content_length = response.getheader("Content-Length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError as exc:
                response.close()
                raise BSourceAcquisitionError("NPI_B_SOURCE_CONTENT_LENGTH_REJECTED") from exc
            if declared != spec.byte_count:
                response.close()
                raise BSourceAcquisitionError("NPI_B_SOURCE_CONTENT_LENGTH_REJECTED")
        return response, current, redirect_count
    raise BSourceAcquisitionError("NPI_B_SOURCE_REDIRECT_REJECTED")


def _stream_response(
    response: DownloadResponse,
    spec: ArtifactSpec,
    write_chunk: Callable[[bytes], None],
) -> tuple[str, int]:
    digest = hashlib.sha256()
    observed = 0
    while True:
        chunk = response.read(_CHUNK_BYTES)
        if not chunk:
            break
        next_size = observed + len(chunk)
        if next_size > spec.byte_count:
            raise BSourceAcquisitionError("NPI_B_SOURCE_STREAM_TOO_LONG")
        write_chunk(chunk)
        digest.update(chunk)
        observed = next_size
    if observed != spec.byte_count:
        raise BSourceAcquisitionError("NPI_B_SOURCE_STREAM_TOO_SHORT")
    observed_sha256 = digest.hexdigest()
    if observed_sha256 != spec.sha256:
        raise BSourceAcquisitionError("NPI_B_SOURCE_SHA256_MISMATCH")
    return observed_sha256, observed


def _canonical_json_bytes(value: Mapping[str, object]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _load_schema(
    project_root: Path,
    filename: str,
) -> Mapping[str, object]:
    value = load_json_strict(project_root / "schemas" / filename)
    if not isinstance(value, Mapping):
        raise BSourceAcquisitionError("NPI_B_SOURCE_SCHEMA_INVALID")
    Draft202012Validator.check_schema(value)
    return cast(Mapping[str, object], value)


def _validate_document(
    project_root: Path,
    filename: str,
    value: Mapping[str, object],
) -> None:
    errors = list(
        Draft202012Validator(
            _load_schema(project_root, filename),
            format_checker=FormatChecker(),
        ).iter_errors(value)
    )
    if errors:
        raise BSourceAcquisitionError("NPI_B_SOURCE_EVIDENCE_SCHEMA_INVALID")


def _fixed_download_path(*parts: str) -> Path:
    suffix = chr(92).join(("Claude_allow", "Download", *parts))
    return Path("E:" + chr(92) + suffix)


def _resolve_evidence_parent() -> Path:
    if os.name != "nt":
        raise BSourceAcquisitionError("NPI_B_SOURCE_WINDOWS_PATH_REQUIRED")
    try:
        return _fixed_download_path(_EVIDENCE_PARENT).resolve(strict=True)
    except OSError as exc:
        raise BSourceAcquisitionError("NPI_B_SOURCE_EVIDENCE_PARENT_UNAVAILABLE") from exc


def _resolve_bound_quarantine_path() -> Path:
    """Return the fixed lexical path; handle binding must see every reparse point."""
    if os.name != "nt":
        raise BSourceAcquisitionError("NPI_B_SOURCE_WINDOWS_PATH_REQUIRED")
    return _fixed_download_path(_QUARANTINE_LEAF)


def _approved_download_parent_path() -> Path:
    return _fixed_download_path()


def _route_b_cache_path() -> Path:
    return _fixed_download_path(_ROUTE_B_CACHE_LEAF)


def _historical_cache_path() -> Path:
    return _fixed_download_path(_HISTORICAL_CACHE_LEAF)


def _handle_paths_overlap(left: str, right: str) -> bool:
    first = left.rstrip(chr(92)).casefold()
    second = right.rstrip(chr(92)).casefold()
    separator = chr(92)
    return (
        first == second
        or first.startswith(second + separator)
        or second.startswith(first + separator)
    )


def load_missing_payload_precondition(
    project_root: Path,
    evidence_path: Path,
    *,
    reviewed_head: str,
) -> dict[str, object]:
    try:
        resolved = evidence_path.resolve(strict=True)
        root = project_root.resolve(strict=True)
    except OSError as exc:
        raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_UNAVAILABLE") from exc
    if evidence_path.is_symlink() or not evidence_path.is_file():
        raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_UNAVAILABLE")
    try:
        resolved.relative_to(root)
    except ValueError:
        pass
    else:
        raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_INSIDE_GIT")
    if resolved.name != _MISSING_PRECONDITION_FILENAME:
        raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_PATH_REJECTED")
    if os.name == "nt":
        if resolved.parent != _resolve_evidence_parent():
            raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_PATH_REJECTED")
    elif resolved.parent.name != _EVIDENCE_PARENT:
        raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_PATH_REJECTED")
    value = load_json_strict(resolved)
    if not isinstance(value, Mapping):
        raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_INVALID")
    record = cast(dict[str, object], value)
    _validate_document(
        project_root,
        _MISSING_PRECONDITION_SCHEMA,
        record,
    )
    if record.get("reviewed_head") != reviewed_head:
        raise BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_STALE")
    return record


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class WindowsBoundQuarantinePublisher:
    """Handle-bound exclusive staging and atomic publication."""

    def __init__(
        self,
        project_root: Path,
        quarantine_path: Path,
        expected_identity: str,
    ) -> None:
        self.project_root = project_root
        self.quarantine_path = quarantine_path
        self.expected_identity = expected_identity
        self._completed: set[str] = set()

    def _validate_bound_root(self, root: BoundDirectory) -> None:
        with bind_existing_directory(
            _approved_download_parent_path(),
            writable=False,
        ) as approved_parent:
            expected_final = (
                approved_parent.identity.final_path.rstrip(chr(92))
                + chr(92)
                + _QUARANTINE_LEAF.casefold()
            )
            if (
                root.identity.volume_serial_number != approved_parent.identity.volume_serial_number
                or root.identity.final_path.casefold() != expected_final
            ):
                raise BSourceAcquisitionError("NPI_B_SOURCE_QUARANTINE_LOCATION_MISMATCH")
        if root.identity.digest != self.expected_identity:
            raise BSourceAcquisitionError("NPI_B_SOURCE_QUARANTINE_IDENTITY_MISMATCH")
        for cache_path, required in (
            (_route_b_cache_path(), True),
            (_historical_cache_path(), False),
        ):
            try:
                cache_root = bind_existing_directory(cache_path, writable=False)
            except FileNotFoundError as exc:
                if required:
                    raise BSourceAcquisitionError(
                        "NPI_B_SOURCE_CACHE_BOUNDARY_UNAVAILABLE"
                    ) from exc
                continue
            with cache_root:
                if _handle_paths_overlap(
                    root.identity.final_path,
                    cache_root.identity.final_path,
                ):
                    raise BSourceAcquisitionError("NPI_B_SOURCE_QUARANTINE_CACHE_OVERLAP")

    def validate_initial_state(self) -> None:
        with bind_existing_directory(
            self.quarantine_path,
            writable=True,
        ) as root:
            self._validate_bound_root(root)
            if root.list_names():
                raise BSourceAcquisitionError("NPI_B_SOURCE_QUARANTINE_NOT_EMPTY")

    def publish(
        self,
        spec: ArtifactSpec,
        response: DownloadResponse,
        *,
        final_url: str,
        redirect_count: int,
        reviewed_head: str,
        reviewed_tree: str,
        completed_at_utc: str,
    ) -> dict[str, object]:
        with bind_existing_directory(
            self.quarantine_path,
            writable=True,
        ) as root:
            self._validate_bound_root(root)
            if root.list_names() != self._completed:
                raise BSourceAcquisitionError("NPI_B_SOURCE_QUARANTINE_UNEXPECTED_STATE")
            with BoundStagingTransaction.create(root) as transaction:
                with transaction.create_file(spec.filename) as payload:
                    observed_sha256, observed_bytes = _stream_response(
                        response,
                        spec,
                        payload.write,
                    )
                    payload.flush()
                with transaction.staging.open_file(spec.filename) as staged:
                    staged_sha256, staged_bytes = staged.sha256_and_size()
                if (
                    staged_sha256 != spec.sha256
                    or staged_bytes != spec.byte_count
                    or staged_sha256 != observed_sha256
                    or staged_bytes != observed_bytes
                ):
                    raise BSourceAcquisitionError("NPI_B_SOURCE_STAGED_REREAD_MISMATCH")
                manifest = {
                    "schema_version": "1.0",
                    "evidence_type": ("B_SOURCE_NETWORK_TRANSFER_MANIFEST_V1"),
                    "status": "PUBLISHED_VERIFIED",
                    "artifact_id": spec.artifact_id,
                    "revision": spec.revision,
                    "filename": spec.filename,
                    "requested_url": spec.url,
                    "final_url": final_url,
                    "final_domain": _ALLOWED_DOMAIN,
                    "redirect_count": redirect_count,
                    "response_status": 200,
                    "expected_byte_count": spec.byte_count,
                    "observed_byte_count": observed_bytes,
                    "expected_sha256": spec.sha256,
                    "observed_sha256": observed_sha256,
                    "historical_transfer_manifest_sha256": (
                        spec.historical_transfer_manifest_sha256
                    ),
                    "quarantine_root_ref": _QUARANTINE_REF,
                    "quarantine_root_identity_sha256": (self.expected_identity),
                    "reviewed_head": reviewed_head,
                    "reviewed_tree": reviewed_tree,
                    "completed_at_utc": completed_at_utc,
                }
                _validate_document(
                    self.project_root,
                    _TRANSFER_SCHEMA,
                    manifest,
                )
                manifest_bytes = _canonical_json_bytes(manifest)
                manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
                with transaction.create_file("transfer_manifest.json") as target:
                    target.write(manifest_bytes)
                    target.flush()
                try:
                    transaction.publish(spec.sha256)
                except FileExistsError as exc:
                    raise BSourceAcquisitionError("NPI_B_SOURCE_ATOMIC_PUBLISH_CONFLICT") from exc
                with root.open_directory(
                    spec.sha256,
                    writable=False,
                ) as published:
                    with published.open_file(spec.filename) as payload:
                        final_sha256, final_bytes = payload.sha256_and_size()
                    with published.open_file("transfer_manifest.json") as manifest_file:
                        final_manifest = manifest_file.read_all(max_bytes=128 * 1024)
                if (
                    final_sha256 != spec.sha256
                    or final_bytes != spec.byte_count
                    or hashlib.sha256(final_manifest).hexdigest() != manifest_sha256
                ):
                    raise BSourceAcquisitionError("NPI_B_SOURCE_PUBLISHED_REREAD_MISMATCH")
            self._completed.add(spec.sha256)
            return {
                "artifact_id": spec.artifact_id,
                "status": "PUBLISHED_VERIFIED",
                "filename": spec.filename,
                "requested_url": spec.url,
                "final_url": final_url,
                "redirect_count": redirect_count,
                "response_status": 200,
                "observed_byte_count": spec.byte_count,
                "observed_sha256": spec.sha256,
                "transfer_manifest_sha256": manifest_sha256,
            }


def _terminal_result(
    project_root: Path,
    *,
    status: str,
    failure_code: str | None,
    reviewed_head: str,
    reviewed_tree: str,
    quarantine_identity: str,
    network_request_count: int,
    artifact_results: list[dict[str, object]],
    one_shot_state: str = _ONE_SHOT_STATE_UNCLAIMED,
) -> dict[str, object]:
    success = status == "B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW"
    result: dict[str, object] = {
        "schema_version": "1.0",
        "evidence_type": ("B_SOURCE_NETWORK_ACQUISITION_RESULT_V1"),
        "status": status,
        "failure_code": failure_code,
        "reviewed_head": reviewed_head,
        "reviewed_tree": reviewed_tree,
        "quarantine_root_ref": _QUARANTINE_REF,
        "quarantine_root_identity_sha256": quarantine_identity,
        "network_request_count": network_request_count,
        "artifact_results": artifact_results,
        "one_shot_state": one_shot_state,
        "terminal": True,
        "retry_authorized": False,
        "cache_promotion": "NOT_AUTHORIZED",
        "model_cuda_photo_exif_sqlite_real20": "NOT_AUTHORIZED",
        "mandatory_stop": (
            "EXTERNAL_REVIEW_B_SOURCE_BYTES_READY"
            if success
            else "EXTERNAL_REVIEW_B_SOURCE_ACQUISITION_FAILURE"
        ),
    }
    _validate_document(project_root, _RESULT_SCHEMA, result)
    return result


def _execution_specs(binding: Mapping[str, object]) -> tuple[ArtifactSpec, ...]:
    records = binding.get("artifacts")
    if not isinstance(records, list):
        raise BSourceAcquisitionError("NPI_B_SOURCE_EXECUTION_BINDING_INVALID")
    specs: list[ArtifactSpec] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise BSourceAcquisitionError("NPI_B_SOURCE_EXECUTION_BINDING_INVALID")
        specs.append(ArtifactSpec.from_record(record))
    if len(specs) != 3:
        raise BSourceAcquisitionError("NPI_B_SOURCE_EXECUTION_BINDING_INVALID")
    return tuple(specs)


def _binding_identity(binding: Mapping[str, object]) -> str:
    value = binding.get("quarantine_root_identity_sha256")
    if not isinstance(value, str):
        raise BSourceAcquisitionError("NPI_B_SOURCE_EXECUTION_BINDING_INVALID")
    return value


def _failure_code(exc: Exception, fallback: str) -> str:
    if isinstance(exc, BSourceAcquisitionError):
        return exc.code
    if isinstance(exc, NpiError):
        return exc.error_code
    return fallback


def _emit_one_shot_test_hook(stage: str) -> None:
    hook = _ONE_SHOT_TEST_HOOK
    if hook is not None:
        hook(stage)


def _atomic_publish_json_record(
    root: BoundDirectory,
    *,
    final_name: str,
    payload_name: str,
    record: Mapping[str, object],
) -> str:
    payload = _canonical_json_bytes(record)
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    with BoundStagingTransaction.create(root) as transaction:
        with transaction.create_file(payload_name) as target:
            target.write(payload)
            target.flush()
        with transaction.staging.open_file(payload_name) as staged:
            staged_bytes = staged.read_all(max_bytes=128 * 1024)
        if staged_bytes != payload:
            raise BSourceAcquisitionError("NPI_B_SOURCE_ONE_SHOT_STAGED_REREAD_MISMATCH")
        transaction.publish(final_name)
    return payload_sha256


def _read_published_json_record(
    lease: BoundDirectory,
    *,
    directory_name: str,
    payload_name: str,
) -> dict[str, object] | None:
    try:
        record_dir = lease.open_directory(directory_name, writable=False)
    except FileNotFoundError:
        return None
    with record_dir:
        if record_dir.list_names() != {payload_name}:
            raise BSourceAcquisitionError("NPI_B_SOURCE_ONE_SHOT_RECORD_INVALID")
        with record_dir.open_file(payload_name) as record_file:
            raw = record_file.read_all(max_bytes=128 * 1024)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise BSourceAcquisitionError("NPI_B_SOURCE_ONE_SHOT_RECORD_INVALID") from exc
    if not isinstance(value, dict):
        raise BSourceAcquisitionError("NPI_B_SOURCE_ONE_SHOT_RECORD_INVALID")
    return cast(dict[str, object], value)


def _reservation_is_structurally_valid(record: Mapping[str, object]) -> bool:
    nonce = record.get("nonce")
    lease_identity = record.get("lease_identity_sha256")
    return (
        record.get("schema_version") == "1.0"
        and record.get("evidence_type") == "B_SOURCE_NETWORK_ONE_SHOT_RESERVATION_V1"
        and record.get("status") == _ONE_SHOT_STATE_CLAIMED
        and isinstance(record.get("reviewed_head"), str)
        and isinstance(record.get("reviewed_tree"), str)
        and isinstance(nonce, str)
        and len(nonce) == 32
        and all(character in "0123456789abcdef" for character in nonce)
        and isinstance(lease_identity, str)
        and len(lease_identity) == 64
        and record.get("retry_authorized") is False
    )


def _classify_existing_one_shot_lease(lease: BoundDirectory) -> str:
    try:
        reservation = _read_published_json_record(
            lease,
            directory_name=_RESERVATION_DIRNAME,
            payload_name=_RESERVATION_FILENAME,
        )
    except BSourceAcquisitionError:
        return _ONE_SHOT_STATE_INCOMPLETE
    if reservation is None or not _reservation_is_structurally_valid(reservation):
        return _ONE_SHOT_STATE_INCOMPLETE
    try:
        terminal = _read_published_json_record(
            lease,
            directory_name=_TERMINAL_DIRNAME,
            payload_name=_TERMINAL_FILENAME,
        )
    except BSourceAcquisitionError:
        return _ONE_SHOT_STATE_INCOMPLETE
    if terminal is None:
        return _ONE_SHOT_STATE_CLAIMED
    if (
        terminal.get("terminal") is True
        and terminal.get("retry_authorized") is False
        and terminal.get("one_shot_state") == _ONE_SHOT_STATE_COMPLETED
    ):
        return _ONE_SHOT_STATE_COMPLETED
    return _ONE_SHOT_STATE_INCOMPLETE


def _one_shot_state_error(state: str) -> str:
    if state == _ONE_SHOT_STATE_COMPLETED:
        return "NPI_B_SOURCE_ONE_SHOT_COMPLETED"
    if state == _ONE_SHOT_STATE_CLAIMED:
        return "NPI_B_SOURCE_ONE_SHOT_CLAIMED"
    return "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"


def _one_shot_state_from_error(code: str) -> str:
    if code == "NPI_B_SOURCE_ONE_SHOT_COMPLETED":
        return _ONE_SHOT_STATE_COMPLETED
    if code == "NPI_B_SOURCE_ONE_SHOT_CLAIMED":
        return _ONE_SHOT_STATE_CLAIMED
    if code == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM":
        return _ONE_SHOT_STATE_INCOMPLETE
    return _ONE_SHOT_STATE_UNCLAIMED


@dataclass(frozen=True)
class OneShotExecutionClaim:
    """Immutable lease identity and nonce for one reviewed acquisition attempt."""

    project_root: Path
    reviewed_head: str
    reviewed_tree: str
    evidence_parent_path: Path
    lease_identity_sha256: str
    nonce: str

    @classmethod
    def claim(
        cls,
        project_root: Path,
        reviewed_head: str,
        reviewed_tree: str,
    ) -> OneShotExecutionClaim:
        if os.name != "nt":
            raise BSourceAcquisitionError("NPI_B_SOURCE_WINDOWS_PATH_REQUIRED")
        evidence_parent_path = _fixed_download_path(_EVIDENCE_PARENT)
        with bind_existing_directory(evidence_parent_path, writable=True) as evidence_parent:
            names = evidence_parent.list_names()
            if _LEGACY_RESULT_FILENAME in names:
                raise BSourceAcquisitionError("NPI_B_SOURCE_ONE_SHOT_COMPLETED")
            if _LEASE_DIRNAME in names:
                with evidence_parent.open_directory(
                    _LEASE_DIRNAME,
                    writable=False,
                ) as existing_lease:
                    state = _classify_existing_one_shot_lease(existing_lease)
                raise BSourceAcquisitionError(_one_shot_state_error(state))
            try:
                lease = evidence_parent.create_directory(_LEASE_DIRNAME)
            except NpiError as exc:
                try:
                    with evidence_parent.open_directory(
                        _LEASE_DIRNAME,
                        writable=False,
                    ) as existing_lease:
                        state = _classify_existing_one_shot_lease(existing_lease)
                except (FileNotFoundError, NpiError):
                    raise BSourceAcquisitionError(
                        "NPI_B_SOURCE_ONE_SHOT_CLAIM_DENIED"
                    ) from exc
                raise BSourceAcquisitionError(_one_shot_state_error(state)) from exc

            lease_identity_sha256 = lease.identity.digest
            nonce = secrets.token_hex(16)
            reservation: dict[str, object] = {
                "schema_version": "1.0",
                "evidence_type": "B_SOURCE_NETWORK_ONE_SHOT_RESERVATION_V1",
                "status": _ONE_SHOT_STATE_CLAIMED,
                "reviewed_head": reviewed_head,
                "reviewed_tree": reviewed_tree,
                "lease_identity_sha256": lease_identity_sha256,
                "nonce": nonce,
                "retry_authorized": False,
            }
            try:
                _emit_one_shot_test_hook("after_lease_create_before_reservation")
                _atomic_publish_json_record(
                    lease,
                    final_name=_RESERVATION_DIRNAME,
                    payload_name=_RESERVATION_FILENAME,
                    record=reservation,
                )
            finally:
                lease.close()
            _emit_one_shot_test_hook("after_reservation_publish_before_transport")
        return cls(
            project_root=project_root,
            reviewed_head=reviewed_head,
            reviewed_tree=reviewed_tree,
            evidence_parent_path=evidence_parent_path,
            lease_identity_sha256=lease_identity_sha256,
            nonce=nonce,
        )

    def persist_terminal(self, result: Mapping[str, object]) -> dict[str, str]:
        completed = dict(result)
        completed["one_shot_state"] = _ONE_SHOT_STATE_COMPLETED
        _validate_document(self.project_root, _RESULT_SCHEMA, completed)
        try:
            with bind_existing_directory(
                self.evidence_parent_path,
                writable=True,
            ) as evidence_parent:
                if _LEASE_DIRNAME not in evidence_parent.list_names():
                    raise BSourceAcquisitionError(
                        "NPI_B_SOURCE_ONE_SHOT_LEASE_MISSING"
                    )
                lease = evidence_parent.open_directory(
                    _LEASE_DIRNAME,
                    writable=True,
                )
                try:
                    if lease.identity.digest != self.lease_identity_sha256:
                        raise BSourceAcquisitionError(
                            "NPI_B_SOURCE_ONE_SHOT_LEASE_IDENTITY_MISMATCH"
                        )
                    reservation = _read_published_json_record(
                        lease,
                        directory_name=_RESERVATION_DIRNAME,
                        payload_name=_RESERVATION_FILENAME,
                    )
                    if reservation is None or not _reservation_is_structurally_valid(
                        reservation
                    ):
                        raise BSourceAcquisitionError(
                            "NPI_B_SOURCE_ONE_SHOT_RESERVATION_INVALID"
                        )
                    if (
                        reservation.get("reviewed_head") != self.reviewed_head
                        or reservation.get("reviewed_tree") != self.reviewed_tree
                        or reservation.get("lease_identity_sha256")
                        != self.lease_identity_sha256
                        or reservation.get("nonce") != self.nonce
                    ):
                        raise BSourceAcquisitionError(
                            "NPI_B_SOURCE_ONE_SHOT_RESERVATION_INVALID"
                        )
                    state = _classify_existing_one_shot_lease(lease)
                    if state == _ONE_SHOT_STATE_COMPLETED:
                        raise BSourceAcquisitionError(
                            "NPI_B_SOURCE_ONE_SHOT_COMPLETED"
                        )
                    if state != _ONE_SHOT_STATE_CLAIMED:
                        raise BSourceAcquisitionError(
                            "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
                        )
                    _emit_one_shot_test_hook(
                        "after_reservation_validation_before_terminal"
                    )
                    terminal_sha256 = _atomic_publish_json_record(
                        lease,
                        final_name=_TERMINAL_DIRNAME,
                        payload_name=_TERMINAL_FILENAME,
                        record=completed,
                    )
                finally:
                    lease.close()
        except BSourceAcquisitionError:
            raise
        except NpiError as exc:
            raise BSourceAcquisitionError(
                "NPI_B_SOURCE_TERMINAL_PERSIST_FAILED"
            ) from exc
        return {
            "one_shot_lease_ref": _LEASE_REF,
            "reservation_evidence_ref": _RESERVATION_REF,
            "terminal_evidence_ref": _RESULT_REF,
            "terminal_evidence_sha256": terminal_sha256,
        }


def claim_one_shot_execution(
    project_root: Path,
    reviewed_head: str,
    reviewed_tree: str,
) -> OneShotExecutionClaim:
    """Claim the immutable one-shot lease before transport construction."""
    return OneShotExecutionClaim.claim(project_root, reviewed_head, reviewed_tree)


def _finish_claimed_result(
    claim: OneShotExecutionClaim,
    result: dict[str, object],
) -> dict[str, object]:
    completed = {**result, "one_shot_state": _ONE_SHOT_STATE_COMPLETED}
    return {**completed, **claim.persist_terminal(completed)}


def run_b_source_network_acquisition(
    project_root: Path,
    review_receipt_path: Path,
    missing_payload_evidence_path: Path,
    *,
    transport: DownloadTransport | None = None,
    publisher: QuarantinePublisher | None = None,
    clock: Callable[[], str] = _utc_now,
) -> dict[str, object]:
    """Execute only after exact review and absence evidence."""

    admission = check_external_exact_sha_review_receipt(
        project_root,
        review_receipt_path,
    )
    if admission.get("status") != POST_REVIEW_ADMISSION_STATUS:
        return _terminal_result(
            project_root,
            status="B_SOURCE_NETWORK_ACQUISITION_BLOCKED",
            failure_code=("NPI_B_SOURCE_EXACT_SHA_ADMISSION_REQUIRED"),
            reviewed_head="UNBOUND",
            reviewed_tree="UNBOUND",
            quarantine_identity="UNBOUND",
            network_request_count=0,
            artifact_results=[],
        )
    reviewed_head = cast(str, admission["reviewed_head"])
    reviewed_tree = cast(str, admission["reviewed_tree"])
    quarantine_identity = "UNBOUND"
    try:
        load_missing_payload_precondition(
            project_root,
            missing_payload_evidence_path,
            reviewed_head=reviewed_head,
        )
        binding = load_b_source_network_execution_binding(project_root)
        specs = _execution_specs(binding)
        quarantine_identity = _binding_identity(binding)
        if binding.get("quarantine_root_ref") != _QUARANTINE_REF:
            raise BSourceAcquisitionError("NPI_B_SOURCE_QUARANTINE_BINDING_MISMATCH")
        active_publisher = publisher
        if active_publisher is None:
            active_publisher = WindowsBoundQuarantinePublisher(
                project_root,
                _resolve_bound_quarantine_path(),
                quarantine_identity,
            )
        active_publisher.validate_initial_state()
    except (
        BSourceAcquisitionError,
        GateNotAuthorizedError,
        NpiError,
        OSError,
        ValueError,
    ) as exc:
        code = _failure_code(exc, "NPI_B_SOURCE_PRE_REQUEST_GATE_FAILED")
        return _terminal_result(
            project_root,
            status="B_SOURCE_NETWORK_ACQUISITION_BLOCKED",
            failure_code=code,
            reviewed_head=reviewed_head,
            reviewed_tree=reviewed_tree,
            quarantine_identity=quarantine_identity,
            network_request_count=0,
            artifact_results=[],
        )

    try:
        execution_claim = claim_one_shot_execution(
            project_root,
            reviewed_head,
            reviewed_tree,
        )
    except (
        BSourceAcquisitionError,
        GateNotAuthorizedError,
        NpiError,
        OSError,
        ValueError,
    ) as exc:
        failure_code = _failure_code(
            exc,
            "NPI_B_SOURCE_ONE_SHOT_CLAIM_FAILED",
        )
        return _terminal_result(
            project_root,
            status="B_SOURCE_NETWORK_ACQUISITION_BLOCKED",
            failure_code=failure_code,
            reviewed_head=reviewed_head,
            reviewed_tree=reviewed_tree,
            quarantine_identity=quarantine_identity,
            network_request_count=0,
            artifact_results=[],
            one_shot_state=_one_shot_state_from_error(failure_code),
        )

    active_transport = transport or StdlibHttpsTransport()
    request_counter = [0]
    artifact_results: list[dict[str, object]] = []
    for spec in specs:
        response: DownloadResponse | None = None
        try:
            response, final_url, redirect_count = _open_final_response(
                active_transport,
                spec,
                request_counter,
            )
            artifact_results.append(
                active_publisher.publish(
                    spec,
                    response,
                    final_url=final_url,
                    redirect_count=redirect_count,
                    reviewed_head=reviewed_head,
                    reviewed_tree=reviewed_tree,
                    completed_at_utc=clock(),
                )
            )
        except (
            BSourceAcquisitionError,
            GateNotAuthorizedError,
            NpiError,
            OSError,
            ValueError,
        ) as exc:
            code = _failure_code(exc, "NPI_B_SOURCE_ACQUISITION_FAILED")
            return _finish_claimed_result(
                execution_claim,
                _terminal_result(
                    project_root,
                    status="B_SOURCE_NETWORK_ACQUISITION_FAILED",
                    failure_code=code,
                    reviewed_head=reviewed_head,
                    reviewed_tree=reviewed_tree,
                    quarantine_identity=quarantine_identity,
                    network_request_count=request_counter[0],
                    artifact_results=artifact_results,
                    one_shot_state=_ONE_SHOT_STATE_CLAIMED,
                ),
            )
        finally:
            if response is not None:
                response.close()
    return _finish_claimed_result(
        execution_claim,
        _terminal_result(
            project_root,
            status="B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW",
            failure_code=None,
            reviewed_head=reviewed_head,
            reviewed_tree=reviewed_tree,
            quarantine_identity=quarantine_identity,
            network_request_count=request_counter[0],
            artifact_results=artifact_results,
            one_shot_state=_ONE_SHOT_STATE_CLAIMED,
        ),
    )


__all__ = [
    "ArtifactSpec",
    "BSourceAcquisitionError",
    "DownloadResponse",
    "DownloadTransport",
    "QuarantinePublisher",
    "StdlibHttpsTransport",
    "WindowsBoundQuarantinePublisher",
    "OneShotExecutionClaim",
    "claim_one_shot_execution",
    "load_missing_payload_precondition",
    "run_b_source_network_acquisition",
]
