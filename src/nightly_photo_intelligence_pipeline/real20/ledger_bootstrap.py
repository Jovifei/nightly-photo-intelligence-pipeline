"""Read-only readiness checks for the fixed Real20 ledger bootstrap boundary."""

from __future__ import annotations

from pathlib import Path

from ..engineering.common import strict_json
from ..ingest.source_guard import is_reparse_point
from ..windows_bound_promotion import bind_existing_directory
from .admission import control_bytes, protect_consumption
from .contracts import Real20Error
from .ledger_probe import load_probe_configuration

LEDGER_LEAF = "real20-execution-ledger"


def _runtime_parent(project_root: Path) -> Path:
    config_path = project_root / "approvals/n2b1p_runtime_configuration.json"
    value = strict_json(control_bytes(config_path))
    if not isinstance(value, dict) or not isinstance(value.get("runtime_parent"), str):
        raise Real20Error("REAL20_RUNTIME_CONFIGURATION_UNAVAILABLE")
    runtime = Path(value["runtime_parent"])
    if not runtime.is_absolute():
        raise Real20Error("REAL20_RUNTIME_CONFIGURATION_UNAVAILABLE")
    return runtime


def _ledger_path(project_root: Path) -> Path:
    return _runtime_parent(project_root) / LEDGER_LEAF


def _verify_ledger_policy(ledger: Path) -> None:
    """Observe the existing append-only policy without changing it."""

    with bind_existing_directory(
        ledger, writable=True, append_only=True, security_check=True
    ) as bound:
        protect_consumption(bound)


def check_ledger_bootstrap(project_root: Path) -> dict[str, str]:
    """Return a redacted readiness result; never creates or repairs anything."""

    project_root = project_root.resolve()
    try:
        ledger = _ledger_path(project_root)
    except Exception:
        return {
            "status": "OWNER_PREPROVISION_REQUIRED",
            "error_code": "REAL20_RUNTIME_CONFIGURATION_UNAVAILABLE",
        }

    if not ledger.is_dir():
        return {
            "status": "OWNER_PREPROVISION_REQUIRED",
            "error_code": "REAL20_LEDGER_ROOT_MISSING",
        }
    if is_reparse_point(ledger):
        return {"status": "UNSAFE_OR_REPARSE_OBJECT", "error_code": "REAL20_REPARSE_PATH_DENIED"}

    try:
        _verify_ledger_policy(ledger)
    except Exception:
        return {"status": "OBJECT_OR_POLICY_MISMATCH", "error_code": "REAL20_LEDGER_POLICY_INVALID"}

    try:
        load_probe_configuration(project_root)
    except Real20Error as exc:
        return {"status": "PROBE_CONFIGURATION_NOT_AVAILABLE", "error_code": exc.code}
    return {"status": "READY_EXISTING_LEDGER", "error_code": "NONE"}


__all__ = ["LEDGER_LEAF", "check_ledger_bootstrap"]
