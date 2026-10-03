"""Bounded Real20 preparation and read-only evaluation entry points."""

from typing import Any

from .contracts import EXIF_ALLOWLIST, Real20Error
from .ledger_bootstrap import bootstrap_control_plane, check_ledger_bootstrap
from .ledger_probe import (
    load_probe_configuration,
    probe_status,
    require_probe_configuration,
    run_ledger_probe,
)
from .runtime_identity import (
    RuntimeIdentity,
    assemble_runtime_identity_v3,
    validate_ledger_acl_probe,
    validate_runtime_identity,
)

__all__ = [
    "EXIF_ALLOWLIST",
    "Real20Error",
    "bootstrap_control_plane",
    "check_ledger_bootstrap",
    "load_probe_configuration",
    "probe_status",
    "require_probe_configuration",
    "run_ledger_probe",
    "RuntimeIdentity",
    "assemble_runtime_identity_v3",
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
