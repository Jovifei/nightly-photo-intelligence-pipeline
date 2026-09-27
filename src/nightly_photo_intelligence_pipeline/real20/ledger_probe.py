"""Fail-closed control-plane entry points for the isolated ledger probe.

The native probe is intentionally unavailable until the Owner supplies the
probe root and separate cleanup identity in the approved runtime envelope. The
commands expose that boundary without guessing paths or touching the real
ledger, source, output, cache, ACLs, or system identities.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from ..engineering.common import strict_json
from .admission import control_bytes
from .contracts import Real20Error

_REQUIRED_PROBE_CONFIG = frozenset(
    {
        "real20_probe_root",
        "real20_runner_identity_sha256",
        "real20_cleanup_identity_sha256",
        "real20_ledger_policy_sha256",
    }
)


def load_probe_configuration(project_root: Path) -> dict[str, Any]:
    """Load the Owner-provisioned probe envelope or fail closed."""

    path = project_root / "approvals/n2b1p_runtime_configuration.json"
    try:
        value = strict_json(control_bytes(path))
    except Exception as exc:  # noqa: BLE001 - stable boundary error
        raise Real20Error("REAL20_LEDGER_PROBE_NOT_AVAILABLE") from exc
    if not isinstance(value, dict) or not _REQUIRED_PROBE_CONFIG.issubset(value):
        raise Real20Error("REAL20_LEDGER_PROBE_NOT_AVAILABLE")
    return cast(dict[str, Any], value)


def probe_status(project_root: Path) -> dict[str, str]:
    """Return a redacted readiness result without creating any probe object."""

    try:
        load_probe_configuration(project_root)
    except Real20Error as exc:
        return {"status": "NOT_AVAILABLE", "error_code": exc.code}
    return {"status": "READY", "error_code": "NONE"}


def require_probe_configuration(project_root: Path) -> dict[str, Any]:
    """Common guard for future native probe and cleanup implementations."""

    return load_probe_configuration(project_root)
