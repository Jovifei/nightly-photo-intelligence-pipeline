"""Trusted fixed-path plan and execution authority for the Real20 control plane."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from ..engineering.common import strict_json
from ..n2b1p_integrity import load_n2b1p_runtime_configuration
from ..windows_bound_promotion import paths_overlap
from .contracts import Real20Error
from .identity import candidate_identity

LEDGER_LEAF = "real20-execution-ledger"
PROBE_ROOT_LEAF = "real20-ledger-acl-probe"
BOOTSTRAP_EVIDENCE_LEAF = "real20-control-plane-bootstrap.json"
AUTHORITY_LEAF = "real20_control_plane_authority.json"
_ALLOWED_OPERATIONS = (
    "BOOTSTRAP_FIXED_LEDGER_AND_PROBE_ROOTS",
    "RUN_SYNTHETIC_LEDGER_INHERITANCE_PROBE",
    "CLEAN_SYNTHETIC_PROBE_BY_PREOPENED_HANDLE",
)


@dataclass(frozen=True)
class Real20ControlPlanePlan:
    runtime_parent: Path
    work_root: Path
    cache_root: Path
    configuration_digest: str
    ledger_root: Path
    probe_root: Path
    bootstrap_evidence: Path


def load_control_plane_plan(project_root: Path) -> Real20ControlPlanePlan:
    """Derive every Real20 control-plane path from the strict N2B1P runtime config."""
    try:
        config = load_n2b1p_runtime_configuration(project_root.resolve())
    except Exception as exc:  # noqa: BLE001 - convert to stable Real20 boundary
        raise Real20Error("REAL20_RUNTIME_CONFIGURATION_UNAVAILABLE") from exc
    runtime_parent = config.runtime_parent
    ledger_root = runtime_parent / LEDGER_LEAF
    probe_root = runtime_parent / PROBE_ROOT_LEAF
    evidence = runtime_parent / BOOTSTRAP_EVIDENCE_LEAF
    try:
        invalid = (
            paths_overlap(ledger_root, config.work_root)
            or paths_overlap(probe_root, config.work_root)
            or paths_overlap(ledger_root, config.cache_root)
            or paths_overlap(probe_root, config.cache_root)
            or paths_overlap(ledger_root, probe_root)
        )
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_CONTROL_PLANE_PATH_INVALID") from exc
    if invalid:
        raise Real20Error("REAL20_CONTROL_PLANE_PATH_OVERLAP")
    return Real20ControlPlanePlan(
        runtime_parent=runtime_parent,
        work_root=config.work_root,
        cache_root=config.cache_root,
        configuration_digest=config.configuration_digest,
        ledger_root=ledger_root,
        probe_root=probe_root,
        bootstrap_evidence=evidence,
    )


def require_control_plane_execution_authority(
    project_root: Path, plan: Real20ControlPlanePlan
) -> dict[str, Any]:
    """Require an external Owner authority bound to the exact reviewed candidate."""
    from .admission import control_bytes

    path = plan.runtime_parent / "owner-approvals" / AUTHORITY_LEAF
    try:
        value = strict_json(control_bytes(path))
        identity = candidate_identity(project_root.resolve())
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_CONTROL_PLANE_AUTHORITY_REQUIRED") from exc
    required = {
        "schema_version",
        "status",
        "owner_id",
        "scope",
        "execution_authorized",
        "runtime_configuration_digest",
        "candidate_commit",
        "candidate_tree",
        "source_manifest_sha256",
        "allowed_operations",
        "production_n2b2",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise Real20Error("REAL20_CONTROL_PLANE_AUTHORITY_INVALID")
    authority = cast(dict[str, Any], value)
    if (
        authority["schema_version"] != "npi-real20-control-plane-authority-v1"
        or authority["status"] != "APPROVED"
        or authority["owner_id"] != "Jovi"
        or authority["scope"] != "R1_REAL20_CONTROL_PLANE_ONLY"
        or authority["execution_authorized"] is not True
        or authority["runtime_configuration_digest"] != plan.configuration_digest
        or authority["candidate_commit"] != identity["candidate_commit"]
        or authority["candidate_tree"] != identity["candidate_tree"]
        or authority["source_manifest_sha256"] != identity["source_manifest_sha256"]
        or authority["allowed_operations"] != list(_ALLOWED_OPERATIONS)
        or authority["production_n2b2"] != "LOCKED"
    ):
        raise Real20Error("REAL20_CONTROL_PLANE_AUTHORITY_INVALID")
    return authority
