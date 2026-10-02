"""Bounded N2B1P recovery admission primitives.

This module intentionally separates recovery-action admission from the
steady-state CACHE_HIT verification performed by preflight/handoff.
It does not mutate cache state and does not replace the steady-state gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecoveryAdmission:
    """Evidence required before a recovery promotion action may start."""

    capability: str
    artifact_id: str
    quarantine_run_id: str
    runtime_configuration_digest: str
    cache_root_identity: str


def validate_recovery_admission(
    admission: RecoveryAdmission,
    *,
    expected_capability: str,
    expected_runtime_configuration_digest: str,
    expected_cache_root_identity: str,
) -> None:
    """Fail closed before recovery promotion.

    This validation deliberately does not check CACHE_HIT. CACHE_HIT is a
    postcondition enforced by the existing steady-state verification path.
    """

    if admission.capability != expected_capability:
        raise ValueError("N2B1P recovery capability mismatch")
    if admission.runtime_configuration_digest != expected_runtime_configuration_digest:
        raise ValueError("N2B1P recovery runtime binding mismatch")
    if admission.cache_root_identity != expected_cache_root_identity:
        raise ValueError("N2B1P recovery cache identity mismatch")
    if not admission.artifact_id or not admission.quarantine_run_id:
        raise ValueError("N2B1P recovery artifact binding missing")


def ensure_existing_root(path: Path) -> None:
    """Reject missing roots without creating remediation side effects."""

    if not path.exists():
        raise FileNotFoundError("N2B1P recovery root missing")
