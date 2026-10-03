"""Trusted fixed-path bootstrap for the Real20 ledger/probe control plane."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..engineering.common import canonical, sha256, strict_json
from ..windows_bound_promotion import BoundDirectory, bind_existing_directory
from .contracts import Real20Error
from .control_plane import (
    BOOTSTRAP_EVIDENCE_LEAF,
    LEDGER_LEAF,
    PROBE_ROOT_LEAF,
    Real20ControlPlanePlan,
    load_control_plane_plan,
    require_control_plane_execution_authority,
)

_BOOTSTRAP_FIELDS = {
    "schema_version",
    "status",
    "runtime_configuration_digest",
    "ledger_object_sha256",
    "probe_root_object_sha256",
    "ledger_policy_sha256",
    "probe_policy_sha256",
}


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Real20Error(code)


def _evidence_payload(
    plan: Real20ControlPlanePlan,
    ledger: BoundDirectory,
    probe: BoundDirectory,
) -> dict[str, str]:
    ledger._verify()
    probe._verify()
    ledger_policy = ledger.security_policy_digest()
    probe_policy = probe.security_policy_digest()
    _require(ledger_policy == probe_policy, "REAL20_LEDGER_PROBE_POLICY_MISMATCH")
    return {
        "schema_version": "npi-real20-control-plane-bootstrap-v1",
        "status": "BOOTSTRAP_BOUND",
        "runtime_configuration_digest": plan.configuration_digest,
        "ledger_object_sha256": ledger.identity.digest,
        "probe_root_object_sha256": probe.identity.digest,
        "ledger_policy_sha256": ledger_policy,
        "probe_policy_sha256": probe_policy,
    }


def _validate_bootstrap_evidence(
    value: object,
    plan: Real20ControlPlanePlan,
    ledger: BoundDirectory,
    probe: BoundDirectory,
) -> dict[str, str]:
    _require(isinstance(value, dict), "REAL20_BOOTSTRAP_EVIDENCE_INVALID")
    _require(set(value) == _BOOTSTRAP_FIELDS, "REAL20_BOOTSTRAP_EVIDENCE_INVALID")
    expected = _evidence_payload(plan, ledger, probe)
    _require(value == expected, "REAL20_BOOTSTRAP_EVIDENCE_MISMATCH")
    return expected


def _read_evidence(parent: BoundDirectory) -> object:
    try:
        with parent.open_file(BOOTSTRAP_EVIDENCE_LEAF) as handle:
            return strict_json(handle.read_all(max_bytes=64 * 1024))
    except FileNotFoundError as exc:
        raise Real20Error("REAL20_BOOTSTRAP_EVIDENCE_MISSING") from exc
    except Real20Error:
        raise
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_BOOTSTRAP_EVIDENCE_INVALID") from exc


def bootstrap_control_plane(project_root: Path) -> dict[str, Any]:
    """Create only the fixed ledger/probe roots after separate Owner authority."""
    plan = load_control_plane_plan(project_root)
    require_control_plane_execution_authority(project_root, plan)

    try:
        with bind_existing_directory(
            plan.runtime_parent, writable=True, security_check=True
        ) as parent:
            names = parent.list_names()
            present = {
                LEDGER_LEAF: LEDGER_LEAF in names,
                PROBE_ROOT_LEAF: PROBE_ROOT_LEAF in names,
                BOOTSTRAP_EVIDENCE_LEAF: BOOTSTRAP_EVIDENCE_LEAF in names,
            }
            if any(present.values()):
                if not all(present.values()):
                    raise Real20Error("REAL20_BOOTSTRAP_PARTIAL_STATE")
                with (
                    parent.open_directory(LEDGER_LEAF, writable=False) as ledger,
                    parent.open_directory(PROBE_ROOT_LEAF, writable=False) as probe,
                ):
                    evidence = _validate_bootstrap_evidence(
                        _read_evidence(parent), plan, ledger, probe
                    )
                return {
                    "status": "BOOTSTRAP_ALREADY_BOUND",
                    "evidence_sha256": sha256(canonical(evidence)),
                    **evidence,
                }

            ledger = parent.create_directory(LEDGER_LEAF)
            probe = parent.create_directory(PROBE_ROOT_LEAF)
            try:
                evidence = _evidence_payload(plan, ledger, probe)
                payload = canonical(evidence)
                with parent.create_file(BOOTSTRAP_EVIDENCE_LEAF) as handle:
                    handle.write(payload)
                    handle.flush()
                with parent.open_file(BOOTSTRAP_EVIDENCE_LEAF) as handle:
                    if handle.read_all(max_bytes=len(payload)) != payload:
                        raise Real20Error("REAL20_BOOTSTRAP_EVIDENCE_WRITE_FAILED")
                return {
                    "status": "BOOTSTRAP_CREATED",
                    "evidence_sha256": sha256(payload),
                    **evidence,
                }
            finally:
                probe.close()
                ledger.close()
    except Real20Error:
        raise
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_BOOTSTRAP_NATIVE_UNAVAILABLE") from exc


def check_ledger_bootstrap(project_root: Path) -> dict[str, str]:
    """Read-only exact-object check; never creates or repairs anything."""
    try:
        plan = load_control_plane_plan(project_root)
        with bind_existing_directory(
            plan.runtime_parent, writable=False, security_check=True
        ) as parent:
            with (
                parent.open_directory(LEDGER_LEAF, writable=False) as ledger,
                parent.open_directory(PROBE_ROOT_LEAF, writable=False) as probe,
            ):
                evidence = _validate_bootstrap_evidence(
                    _read_evidence(parent), plan, ledger, probe
                )
        return {
            "status": "READY_EXISTING_CONTROL_PLANE",
            "error_code": "NONE",
            "evidence_sha256": sha256(canonical(evidence)),
        }
    except FileNotFoundError:
        return {
            "status": "OWNER_BOOTSTRAP_REQUIRED",
            "error_code": "REAL20_CONTROL_PLANE_OBJECT_MISSING",
        }
    except Real20Error as exc:
        return {"status": "NOT_READY", "error_code": exc.code}
    except Exception:
        return {
            "status": "NOT_READY",
            "error_code": "REAL20_BOOTSTRAP_NATIVE_UNAVAILABLE",
        }


__all__ = [
    "LEDGER_LEAF",
    "PROBE_ROOT_LEAF",
    "bootstrap_control_plane",
    "check_ledger_bootstrap",
]
