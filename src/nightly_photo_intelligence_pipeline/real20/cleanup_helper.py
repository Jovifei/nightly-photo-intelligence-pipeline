"""Restricted cleanup helper for a Real20 synthetic probe.

The helper accepts only an already-open directory handle (or its bound wrapper)
plus capability data. It has no path-opening or traversal API.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..engineering.common import canonical, sha256
from ..windows_bound_promotion import BoundDirectory, adopt_preopened_directory
from .cleanup_capability import validate_cleanup_capability
from .contracts import Real20Error

_HELPER_CONTRACT = {
    "contract_version": "npi-real20-preopened-cleanup-helper-v1",
    "scope": "ONE_SYNTHETIC_PROBE_OBJECT",
    "path_opening": False,
    "recursive_cleanup": False,
    "acl_change": False,
}


def cleanup_helper_identity_sha256() -> str:
    """Stable helper-contract fingerprint used by the cleanup capability."""
    return sha256(canonical(_HELPER_CONTRACT))


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Real20Error(code)


def cleanup_preopened_probe(
    probe: BoundDirectory,
    capability: object,
    *,
    expected_probe_nonce_sha256: str,
    now: datetime,
) -> dict[str, str]:
    """Delete only the exact synthetic probe represented by an already-open handle."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_TIME_INVALID")
    probe._verify()
    helper_identity = cleanup_helper_identity_sha256()
    validated = validate_cleanup_capability(
        capability,
        now=now,
        expected_probe_nonce_sha256=expected_probe_nonce_sha256,
        expected_probe_object_sha256=probe.identity.digest,
        expected_cleanup_identity_sha256=helper_identity,
    )
    expected_names = {
        "reservation.json",
        f"terminal-v1-{validated.probe_nonce_sha256}.json",
    }
    _require(probe.list_names() == expected_names, "REAL20_CLEANUP_HELPER_CONTENT_MISMATCH")

    for name in sorted(expected_names):
        with probe.open_file_for_cleanup(name) as handle:
            handle.delete_owned()
    _require(not probe.list_names(), "REAL20_CLEANUP_HELPER_NOT_EMPTY")
    probe.delete_owned_empty()
    return {
        "schema_version": "npi-real20-cleanup-proof-v1",
        "cleanup_status": "CLEANUP_PASS",
        "probe_nonce_sha256": validated.probe_nonce_sha256,
        "probe_object_sha256": validated.probe_object_sha256,
        "cleanup_identity_sha256": helper_identity,
        "cleaned_at_utc": now.astimezone(UTC).isoformat(),
    }


def cleanup_inherited_probe_handle(
    handle: int,
    capability: object,
    *,
    expected_probe_nonce_sha256: str,
    now: datetime,
) -> dict[str, str]:
    """Adopt and consume one inherited handle; never opens a filesystem path."""
    if not isinstance(capability, dict):
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_REQUIRED")
    object_digest = capability.get("probe_object_sha256")
    if not isinstance(object_digest, str):
        raise Real20Error("REAL20_CLEANUP_CAPABILITY_DIGEST_INVALID")
    with adopt_preopened_directory(
        handle,
        expected_identity_sha256=object_digest,
        writable=True,
        security_check=True,
    ) as probe:
        return cleanup_preopened_probe(
            probe,
            capability,
            expected_probe_nonce_sha256=expected_probe_nonce_sha256,
            now=now,
        )
