"""Append-only terminal records for one-shot Real20 credentials."""
from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from ..engineering.common import canonical, sha256, strict_json
from ..windows_bound_promotion import BoundDirectory

_SHA256 = re.compile(r"[0-9a-f]{64}")
_TERMINAL_PREFIX = "terminal-v1-"
_COMMIT_PREFIX = "terminal-commit-v1-"
_MAX_RECORD_BYTES = 16 * 1024


def _is_sha(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def _validate_evidence(status: object, evidence_status: object, evidence_sha: object) -> None:
    if status == "COMPLETE":
        valid = evidence_status == "PERSISTED" and _is_sha(evidence_sha)
    elif status == "FAILED":
        valid = (
            evidence_status == "PERSISTED" and _is_sha(evidence_sha)
        ) or (
            evidence_status in ("PERSISTENCE_FAILED", "RESERVATION_RECORD_FAILED")
            and evidence_sha is None
        )
    else:
        valid = False
    if not valid:
        raise ValueError("TERMINAL_EVIDENCE_INVALID")


def _valid_reservation(value: object, credential_sha: str) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "schema_version", "status", "credential_sha256", "bindings_sha256", "reserved_at_utc"
    }:
        return False
    if value.get("schema_version") != "npi-real20-consumption-v1" \
            or value.get("status") != "RESERVED" \
            or value.get("credential_sha256") != credential_sha \
            or not _is_sha(value.get("bindings_sha256")):
        return False
    try:
        timestamp = datetime.fromisoformat(value["reserved_at_utc"])
    except (TypeError, ValueError):
        return False
    return timestamp.tzinfo is not None and timestamp.utcoffset() == UTC.utcoffset(timestamp)


def _read(directory: BoundDirectory, name: str) -> tuple[bytes, dict[str, Any]]:
    with directory.open_file(name) as handle:
        data = handle.read_all(max_bytes=_MAX_RECORD_BYTES)
    value = strict_json(data)
    if not isinstance(value, dict) or canonical(value) != data:
        raise ValueError("TERMINAL_RECORD_INVALID")
    return data, value


def read_terminal_record(claim: BoundDirectory, credential_sha: str) -> dict[str, Any]:
    if not _is_sha(credential_sha):
        raise ValueError("TERMINAL_CREDENTIAL_INVALID")
    names = claim.list_names()
    records = sorted(name for name in names if name.startswith(_TERMINAL_PREFIX))
    commits = sorted(name for name in names if name.startswith(_COMMIT_PREFIX))
    if not commits:
        raise ValueError("TERMINAL_COMMIT_MISSING")
    if len(commits) != 1 or len(records) != 1:
        raise ValueError("TERMINAL_COMMIT_CONFLICT")
    commit_name = commits[0]
    record_name = records[0]
    record_bytes, record = _read(claim, record_name)
    _, commit = _read(claim, commit_name)
    record_sha = sha256(record_bytes)
    expected_commit = {
        "schema_version": "npi-real20-ledger-terminal-commit-v1",
        "credential_sha256": credential_sha,
        "record_name": record_name,
        "record_sha256": record_sha,
    }
    if commit != expected_commit or commit_name != _COMMIT_PREFIX + record_sha + ".json":
        raise ValueError("TERMINAL_COMMIT_INVALID")
    if record_name != _TERMINAL_PREFIX + record_sha + ".json":
        raise ValueError("TERMINAL_RECORD_HASH_INVALID")
    expected_fields = {
        "schema_version", "credential_sha256", "reservation_sha256", "status",
        "evidence_status", "evidence_sha256", "finished_at_utc",
    }
    if set(record) != expected_fields \
            or record.get("schema_version") != "npi-real20-ledger-terminal-v1" \
            or record.get("credential_sha256") != credential_sha:
        raise ValueError("TERMINAL_RECORD_INVALID")
    _validate_evidence(
        record.get("status"), record.get("evidence_status"), record.get("evidence_sha256")
    )
    reservation_sha = None
    reservation_valid = False
    if "reservation.json" in names:
        try:
            reservation_bytes, reservation = _read(claim, "reservation.json")
            reservation_sha = sha256(reservation_bytes)
            reservation_valid = _valid_reservation(reservation, credential_sha)
        except (OSError, ValueError):
            try:
                with claim.open_file("reservation.json") as handle:
                    reservation_sha = sha256(handle.read_all(max_bytes=_MAX_RECORD_BYTES))
            except OSError:
                pass
    if record.get("reservation_sha256") != reservation_sha:
        raise ValueError("TERMINAL_RESERVATION_HASH_MISMATCH")
    if record["evidence_status"] != "RESERVATION_RECORD_FAILED" and not reservation_valid:
        raise ValueError("TERMINAL_RESERVATION_INVALID")
    try:
        timestamp = datetime.fromisoformat(record["finished_at_utc"])
    except (TypeError, ValueError) as exc:
        raise ValueError("TERMINAL_TIMESTAMP_INVALID") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() != UTC.utcoffset(timestamp):
        raise ValueError("TERMINAL_TIMESTAMP_INVALID")
    return record


def append_terminal_record(
    ledger: BoundDirectory,
    claim: BoundDirectory,
    credential_sha: str,
    *,
    status: str,
    evidence_sha: str | None,
    evidence_status: str,
) -> dict[str, Any]:
    if not _is_sha(credential_sha):
        raise ValueError("TERMINAL_BINDING_INVALID")
    _validate_evidence(status, evidence_status, evidence_sha)
    claim_name = claim.identity.final_path.rsplit("\\", 1)[-1]
    if claim._root is not ledger or claim._closed or claim_name != credential_sha \
            or not ledger._append_only or not claim._append_only:
        raise ValueError("TERMINAL_LEDGER_HANDLE_INVALID")
    names = claim.list_names()
    if any(name.startswith((_TERMINAL_PREFIX, _COMMIT_PREFIX)) for name in names):
        raise ValueError("TERMINAL_ALREADY_STARTED")
    reservation_sha = None
    try:
        reservation_bytes, reservation = _read(claim, "reservation.json")
        if not _valid_reservation(reservation, credential_sha):
            raise ValueError("TERMINAL_RESERVATION_INVALID")
        reservation_sha = sha256(reservation_bytes)
    except (OSError, ValueError) as exc:
        if status != "FAILED" or evidence_status != "RESERVATION_RECORD_FAILED":
            raise ValueError("TERMINAL_RESERVATION_INVALID") from exc
        if "reservation.json" in names:
            try:
                with claim.open_file("reservation.json") as handle:
                    reservation_sha = sha256(handle.read_all(max_bytes=_MAX_RECORD_BYTES))
            except OSError:
                pass
    record = {
        "schema_version": "npi-real20-ledger-terminal-v1",
        "credential_sha256": credential_sha,
        "reservation_sha256": reservation_sha,
        "status": status,
        "evidence_status": evidence_status,
        "evidence_sha256": evidence_sha,
        "finished_at_utc": datetime.now(UTC).isoformat(),
    }
    record_bytes = canonical(record)
    record_sha = sha256(record_bytes)
    record_name = _TERMINAL_PREFIX + record_sha + ".json"
    commit = {
        "schema_version": "npi-real20-ledger-terminal-commit-v1",
        "credential_sha256": credential_sha,
        "record_name": record_name,
        "record_sha256": record_sha,
    }
    with claim.create_file(record_name) as handle:
        handle.write(record_bytes)
        handle.flush()
    commit_bytes = canonical(commit)
    with claim.create_file(_COMMIT_PREFIX + record_sha + ".json") as handle:
        handle.write(commit_bytes)
        handle.flush()
    claim.close()
    with ledger.open_directory(credential_sha, writable=True) as reopened:
        verified = read_terminal_record(reopened, credential_sha)
    if verified != record:
        raise ValueError("TERMINAL_REOPEN_MISMATCH")
    return verified
