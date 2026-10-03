"""Bound cleanup capability contract for Real20 synthetic probe cleanup.

This module is code-only. It does not create identities, impersonate users,
modify ACLs, or execute cleanup. It validates the nonce/object/helper binding
that a separately authorized pre-opened-handle cleanup path must carry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .contracts import Real20Error

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CleanupCapability:
    """Nonce/object/helper-bound cleanup permission description."""

    capability_version: str
    probe_nonce_sha256: str
    probe_object_sha256: str
    cleanup_identity_sha256: str
    expires_at_utc: str


def _digest(value: object) -> None:
    if not isinstance(value, str) or _HEX64.fullmatch(value) is None:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_DIGEST_INVALID")


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_TIME_INVALID")
    return value.astimezone(UTC)


def validate_cleanup_capability(
    value: object,
    *,
    now: datetime,
    expected_probe_nonce_sha256: str,
    expected_probe_object_sha256: str,
    expected_cleanup_identity_sha256: str,
) -> CleanupCapability:
    """Validate an exact capability binding; expected bindings are mandatory."""

    current = _aware_utc(now)
    for expected in (
        expected_probe_nonce_sha256,
        expected_probe_object_sha256,
        expected_cleanup_identity_sha256,
    ):
        _digest(expected)

    if not isinstance(value, dict):
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_REQUIRED")
    if set(value) != {
        "capability_version",
        "probe_nonce_sha256",
        "probe_object_sha256",
        "cleanup_identity_sha256",
        "expires_at_utc",
    }:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_FIELDS_INVALID")
    for key in (
        "probe_nonce_sha256",
        "probe_object_sha256",
        "cleanup_identity_sha256",
    ):
        _digest(value[key])
    if value["capability_version"] != "npi-real20-cleanup-capability-v1":
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_VERSION_INVALID")
    if value["probe_nonce_sha256"] != expected_probe_nonce_sha256:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_NONCE_MISMATCH")
    if value["probe_object_sha256"] != expected_probe_object_sha256:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_OBJECT_MISMATCH")
    if value["cleanup_identity_sha256"] != expected_cleanup_identity_sha256:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_IDENTITY_MISMATCH")
    try:
        expiry = datetime.fromisoformat(value["expires_at_utc"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_TIME_INVALID") from exc
    if expiry.tzinfo is None or expiry.utcoffset() is None:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_TIME_INVALID")
    if not expiry.astimezone(UTC) > current:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_EXPIRED")
    return CleanupCapability(**value)
