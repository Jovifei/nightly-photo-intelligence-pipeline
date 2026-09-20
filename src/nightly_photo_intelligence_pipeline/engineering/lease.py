"""Receipt-keyed one-shot consumption on an Owner-controlled local filesystem.

No SQLite, models, network, source-photo reads, permission changes or deletion.
The trusted receipt hash must come from a separate Owner decision. A self-hashed
DRAFT is NOT authorization. Reservation is keyed by the RECEIPT, not output path,
so changing output paths or code cannot reset the consumed allowance.

The integration adapter must validate all runtime/paths/source checks first,
reserve immediately before the first model load, and never release on failure.
A crash after mkdir leaves the receipt consumed. Missing/corrupt records fail
closed and need a separately approved replacement lease, not cleanup/retry.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .common import EngineeringError, canonical, is_digest, require, sha256, strict_json
from .path_policy import checked_path

REQUIRED_BINDINGS = {
    "candidate_commit",
    "candidate_tree",
    "source_manifest_sha256",
    "project_state_sha256",
    "candidate_review_sha256",
    "historical_review_sha256",
    "prior_s20_review_sha256",
    "quality_evidence_sha256",
    "runtime_identity_sha256",
    "s3_manifest_sha256",
    "s20_manifest_sha256",
    "model_cache_binding_sha256",
    "path_plan_sha256",
}
DENIED = {
    "real_photo",
    "real_exif",
    "g1_source",
    "sqlite_ingest",
    "app",
    "production_bundle",
    "model_download",
    "model_replacement",
    "project_state_mutation",
}


@dataclass(frozen=True)
class Permit:
    receipt_sha256: str
    receipt: bytes
    bindings_sha256: str


@dataclass(frozen=True)
class Reservation:
    directory: Path
    receipt_sha256: str
    record_sha256: str


def _timestamp(value: object) -> datetime:
    require(isinstance(value, str), "NPI_LEASE_TIME_INVALID")
    assert isinstance(value, str)
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise EngineeringError("NPI_LEASE_TIME_INVALID") from exc
    require(date.tzinfo is not None and date.utcoffset() is not None, "NPI_LEASE_TIME_INVALID")
    return date.astimezone(UTC)


def validate_lease(
    data: bytes, *, trusted_receipt_sha256: str, observed_bindings: Mapping[str, str], now: datetime
) -> Permit:
    require(is_digest(trusted_receipt_sha256), "NPI_OWNER_ANCHOR_REQUIRED")
    require(sha256(data) == trusted_receipt_sha256, "NPI_LEASE_DIGEST_MISMATCH")
    receipt = strict_json(data)
    fields = {
        "schema_version",
        "status",
        "owner_id",
        "purpose",
        "not_before_utc",
        "expires_at_utc",
        "bindings",
        "boundaries",
        "max_fresh_s3_runs",
        "max_fresh_s20_runs",
        "production_unlock",
    }
    require(isinstance(receipt, dict) and set(receipt) == fields, "NPI_LEASE_SCHEMA_INVALID")
    require(
        receipt["schema_version"] == "npi-synthetic-execution-lease-v3"
        and receipt["status"] == "APPROVED"
        and receipt["owner_id"] == "Jovi"
        and receipt["purpose"] == "SYNTHETIC_S3_S20_ENGINEERING_VALIDATION",
        "NPI_LEASE_NOT_APPROVED",
    )
    for field in ("max_fresh_s3_runs", "max_fresh_s20_runs"):
        require(type(receipt[field]) is int and receipt[field] == 1, "NPI_LEASE_SCOPE_INVALID")
    boundaries = receipt["boundaries"]
    require(
        isinstance(boundaries, dict)
        and set(boundaries) == DENIED
        and all(value is False for value in boundaries.values())
        and receipt["production_unlock"] is False,
        "NPI_LEASE_SCOPE_INVALID",
    )
    bindings = receipt["bindings"]
    require(
        isinstance(bindings, dict)
        and set(bindings) == REQUIRED_BINDINGS
        and set(observed_bindings) == REQUIRED_BINDINGS,
        "NPI_LEASE_BINDING_INVALID",
    )
    for name, value in bindings.items():
        length = 40 if name in ("candidate_commit", "candidate_tree") else 64
        require(
            is_digest(value, length) and observed_bindings[name] == value,
            "NPI_LEASE_BINDING_MISMATCH",
        )
    require(now.tzinfo is not None and now.utcoffset() is not None, "NPI_LEASE_TIME_INVALID")
    start, end = _timestamp(receipt["not_before_utc"]), _timestamp(receipt["expires_at_utc"])
    require(start < end and start <= now.astimezone(UTC) < end, "NPI_LEASE_OUTSIDE_WINDOW")
    return Permit(trusted_receipt_sha256, data, sha256(canonical(bindings)))


def _exclusive_json(path: Path, value: object) -> bytes:
    data = canonical(value)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    if os.name != "nt":
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return data


def reserve(
    ledger_root: Path, permit: Permit, *, observed_bindings: Mapping[str, str], now: datetime
) -> Reservation:
    """Revalidate at the reservation boundary; duplicate and crashed claims never retry."""
    validated = validate_lease(
        permit.receipt,
        trusted_receipt_sha256=permit.receipt_sha256,
        observed_bindings=observed_bindings,
        now=now,
    )
    require(validated == permit, "NPI_PERMIT_CHANGED")
    checked_path(ledger_root, must_exist=True)
    target = ledger_root / permit.receipt_sha256
    try:
        # Atomic on the supported local filesystem. Never remove a failed claim.
        target.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise EngineeringError("NPI_LEASE_ALREADY_CONSUMED") from exc
    record = {
        "schema_version": "npi-lease-consumption-v1",
        "status": "RESERVED",
        "receipt_sha256": permit.receipt_sha256,
        "bindings_sha256": permit.bindings_sha256,
        "reserved_at_utc": now.astimezone(UTC).isoformat(),
    }
    data = _exclusive_json(target / "reservation.json", record)
    return Reservation(target, permit.receipt_sha256, sha256(data))


def finish(reservation: Reservation, *, outcome: str, evidence_sha256: str, now: datetime) -> None:
    """Write one terminal record. Failures consume the same allowance as successes."""
    require(outcome in ("COMPLETE", "FAILED"), "NPI_LEASE_TERMINAL_INVALID")
    require(is_digest(evidence_sha256), "NPI_EVIDENCE_ANCHOR_INVALID")
    require(now.tzinfo is not None, "NPI_LEASE_TIME_INVALID")
    checked_path(reservation.directory, must_exist=True)
    path = reservation.directory / "reservation.json"
    info = path.lstat()
    require(
        not path.is_symlink()
        and info.st_nlink == 1
        and not (getattr(info, "st_file_attributes", 0) & 0x400),
        "NPI_LEASE_RECORD_INVALID",
    )
    require(sha256(path.read_bytes()) == reservation.record_sha256, "NPI_LEASE_RECORD_CHANGED")
    try:
        _exclusive_json(
            reservation.directory / "terminal.json",
            {
                "schema_version": "npi-lease-consumption-v1",
                "status": outcome,
                "receipt_sha256": reservation.receipt_sha256,
                "reservation_sha256": reservation.record_sha256,
                "evidence_sha256": evidence_sha256,
                "finished_at_utc": now.astimezone(UTC).isoformat(),
            },
        )
    except FileExistsError as exc:
        raise EngineeringError("NPI_LEASE_ALREADY_FINALIZED") from exc
