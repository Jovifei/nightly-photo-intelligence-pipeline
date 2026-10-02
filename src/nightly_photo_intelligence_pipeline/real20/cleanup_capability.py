"""Bound cleanup capability contract for Real20 synthetic probe cleanup.

This module is code-only. It does not create identities, impersonate users,
modify ACLs, or execute cleanup. It validates the capability description that
may be supplied by an already-authorized runtime path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from .contracts import Real20Error

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class CleanupCapability:
    """Nonce/object-bound cleanup permission description."""

    capability_version: str
    probe_nonce_sha256: str
    probe_object_sha256: str
    cleanup_identity_sha256: str
    expires_at_utc: str


def validate_cleanup_capability(
    value: object,
    *,
    now: datetime,
    expected_probe_object_sha256: str | None = None,
    expected_cleanup_identity_sha256: str | None = None,
) -> CleanupCapability:
    """Fail closed on malformed or stale cleanup capability data."""

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
        if not isinstance(value[key], str) or _HEX64.fullmatch(value[key]) is None:
            raise Real20Error("REAL20_CLEANUP_CAPABILITY_DIGEST_INVALID")
    if value["capability_version"] != "npi-real20-cleanup-capability-v1":
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_VERSION_INVALID")
    if expected_probe_object_sha256 is not None and value["probe_object_sha256"] != expected_probe_object_sha256:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_OBJECT_MISMATCH")
    if expected_cleanup_identity_sha256 is not None and value["cleanup_identity_sha256"] != expected_cleanup_identity_sha256:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_IDENTITY_MISMATCH")
    try:
        expiry = datetime.fromisoformat(value["expires_at_utc"].replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_TIME_INVALID") from exc
    if expiry.tzinfo is None or not expiry.astimezone(UTC) > now.astimezone(UTC):
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_EXPIRED")
    return CleanupCapability(**value)
