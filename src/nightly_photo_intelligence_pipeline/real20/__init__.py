"""Bounded Real20 preparation and read-only evaluation entry points."""

from typing import Any

from .contracts import EXIF_ALLOWLIST, Real20Error
from .ledger_bootstrap import check_ledger_bootstrap
from .ledger_probe import load_probe_configuration, probe_status, require_probe_configuration
from .runtime_identity import RuntimeIdentity, validate_ledger_acl_probe, validate_runtime_identity

__all__ = [
    "EXIF_ALLOWLIST",
    "Real20Error",
    "check_ledger_bootstrap",
    "load_probe_configuration",
    "probe_status",
    "require_probe_configuration",
    "RuntimeIdentity",
    "validate_ledger_acl_probe",
    "validate_runtime_identity",
    "prepare_real20",
    "run_real20",
]


def __getattr__(name: str) -> Any:
    if name in {"prepare_real20", "run_real20"}:
        from .runner import prepare_real20, run_real20

        return prepare_real20 if name == "prepare_real20" else run_real20
    raise AttributeError(name)
