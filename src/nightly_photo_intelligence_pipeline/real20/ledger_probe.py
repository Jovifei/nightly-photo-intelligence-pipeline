"""Synthetic Real20 ledger inheritance probe with bounded cleanup."""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from ..engineering.common import canonical, sha256, strict_json
from ..windows_bound_promotion import (
    BoundDirectory,
    bind_existing_directory,
    current_process_identity_sha256,
)
from .cleanup_helper import cleanup_helper_identity_sha256, cleanup_inherited_probe_handle
from .contracts import Real20Error
from .control_plane import (
    LEDGER_LEAF,
    PROBE_ROOT_LEAF,
    load_control_plane_plan,
    require_control_plane_execution_authority,
)
from .ledger_bootstrap import check_ledger_bootstrap

_DIR_FORBIDDEN = (0x00000040, 0x00010000, 0x00040000, 0x00080000)
_FILE_FORBIDDEN = (0x00000002, 0x00010000, 0x00040000, 0x00080000)
_FILE_APPEND_DATA = 0x00000004


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Real20Error(code)


def load_probe_configuration(project_root: Path) -> dict[str, Any]:
    """Return only the fixed plan derived from the strict N2B1P runtime config."""
    plan = load_control_plane_plan(project_root)
    return {
        "runtime_configuration_digest": plan.configuration_digest,
        "ledger_leaf": LEDGER_LEAF,
        "probe_root_leaf": PROBE_ROOT_LEAF,
    }


def require_probe_configuration(project_root: Path) -> dict[str, Any]:
    return load_probe_configuration(project_root)


def probe_status(project_root: Path) -> dict[str, str]:
    """Report code/control-plane readiness without creating a synthetic claim."""
    try:
        plan = load_control_plane_plan(project_root)
        bootstrap = check_ledger_bootstrap(project_root)
    except Real20Error as exc:
        return {"status": "NOT_AVAILABLE", "error_code": exc.code}
    if bootstrap.get("status") != "READY_EXISTING_CONTROL_PLANE":
        return {
            "status": "NOT_AVAILABLE",
            "error_code": bootstrap.get("error_code", "REAL20_CONTROL_PLANE_NOT_READY"),
        }
    try:
        require_control_plane_execution_authority(project_root, plan)
    except Real20Error as exc:
        return {"status": "NOT_AUTHORIZED", "error_code": exc.code}
    return {"status": "READY", "error_code": "NONE"}


def _check_directory_rights(directory: BoundDirectory) -> None:
    directory._verify()
    for right in _DIR_FORBIDDEN:
        result = directory.access_check(right)
        _require(
            result.granted is False and result.win32_error is None,
            "REAL20_LEDGER_PROBE_DIRECTORY_RIGHTS_INVALID",
        )


def _check_file_rights(handle: Any) -> None:
    for right in _FILE_FORBIDDEN:
        result = handle.access_check(right)
        _require(
            result.granted is False and result.win32_error is None,
            "REAL20_LEDGER_PROBE_FILE_RIGHTS_INVALID",
        )
    append = handle.access_check(_FILE_APPEND_DATA)
    _require(
        append.granted is True and append.win32_error is None,
        "REAL20_LEDGER_PROBE_APPEND_RIGHT_REQUIRED",
    )


def _probe_payload(kind: str, nonce_sha256: str) -> bytes:
    return canonical(
        {
            "schema_version": "npi-real20-ledger-probe-object-v1",
            "kind": kind,
            "probe_nonce_sha256": nonce_sha256,
        }
    )


def run_ledger_probe(
    project_root: Path,
    *,
    now: datetime | None = None,
    nonce_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Create, validate and clean one fixed-scope synthetic probe."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None or current.utcoffset() is None:
        raise Real20Error("REAL20_LEDGER_PROBE_TIME_INVALID")
    current = current.astimezone(UTC)
    plan = load_control_plane_plan(project_root)
    require_control_plane_execution_authority(project_root, plan)
    bootstrap = check_ledger_bootstrap(project_root)
    _require(
        bootstrap.get("status") == "READY_EXISTING_CONTROL_PLANE",
        "REAL20_CONTROL_PLANE_NOT_READY",
    )

    nonce = nonce_bytes if nonce_bytes is not None else secrets.token_bytes(32)
    _require(isinstance(nonce, bytes) and len(nonce) >= 16, "REAL20_LEDGER_PROBE_NONCE_INVALID")
    nonce_sha256 = sha256(nonce)
    probe_name = "probe-" + nonce_sha256[:32]
    helper_identity = cleanup_helper_identity_sha256()
    created_at = current
    expires_at = current + timedelta(minutes=20)

    try:
        with (
            bind_existing_directory(
                plan.ledger_root,
                writable=True,
                append_only=True,
                security_check=True,
            ) as ledger,
            bind_existing_directory(
                plan.probe_root,
                writable=True,
                append_only=True,
                security_check=True,
            ) as probe_root,
        ):
            from .admission import protect_consumption

            protect_consumption(ledger)
            ledger_policy = ledger.security_policy_digest()
            probe_policy = probe_root.security_policy_digest()
            _require(ledger_policy == probe_policy, "REAL20_LEDGER_PROBE_POLICY_MISMATCH")
            runner_identity = current_process_identity_sha256()
            ledger_object = ledger.identity.digest

            with probe_root.create_directory(probe_name) as claim:
                _check_directory_rights(claim)
                probe_object = claim.identity.digest
                with claim.create_file("reservation.json") as reservation:
                    _check_file_rights(reservation)
                    reservation.write(_probe_payload("RESERVATION", nonce_sha256))
                    reservation.flush()
                terminal_name = f"terminal-v1-{nonce_sha256}.json"
                with claim.create_file(terminal_name) as terminal:
                    _check_file_rights(terminal)
                    terminal.write(_probe_payload("TERMINAL", nonce_sha256))
                    terminal.flush()

        capability = {
            "capability_version": "npi-real20-cleanup-capability-v1",
            "probe_nonce_sha256": nonce_sha256,
            "probe_object_sha256": probe_object,
            "cleanup_identity_sha256": helper_identity,
            "expires_at_utc": expires_at.isoformat(),
        }

        cleanup_error: Real20Error | None = None
        cleanup_proof: dict[str, str] | None = None
        try:
            with bind_existing_directory(
                plan.probe_root, writable=True, security_check=True
            ) as mutable_probe_root:
                cleanup_handle = mutable_probe_root.open_directory(probe_name, writable=True)
                inherited_handle, inherited_identity = cleanup_handle.release_for_inheritance()
                _require(
                    inherited_identity == probe_object,
                    "REAL20_CLEANUP_CAPABILITY_OBJECT_MISMATCH",
                )
                cleanup_proof = cleanup_inherited_probe_handle(
                    inherited_handle,
                    capability,
                    expected_probe_nonce_sha256=nonce_sha256,
                    now=current,
                )
        except Real20Error as exc:
            cleanup_error = exc
        except Exception as exc:  # noqa: BLE001
            cleanup_error = Real20Error("REAL20_LEDGER_PROBE_CLEANUP_NOT_VERIFIED")

        if cleanup_error is not None:
            return {
                "schema_version": "npi-real20-ledger-probe-result-v2",
                "status": "NOT_ADMISSION_ELIGIBLE",
                "inheritance_status": "PROBE_PASS",
                "cleanup_status": "CLEANUP_FAILED",
                "error_code": cleanup_error.code,
                "probe_nonce_sha256": nonce_sha256,
                "probe_object_sha256": probe_object,
                "ledger_object_sha256": ledger_object,
                "runner_identity_sha256": runner_identity,
                "cleanup_identity_sha256": helper_identity,
                "ledger_policy_sha256": ledger_policy,
                "probe_policy_sha256": probe_policy,
            }

        _require(cleanup_proof is not None, "REAL20_LEDGER_PROBE_CLEANUP_NOT_VERIFIED")
        proof = {
            "contract_version": "npi-real20-ledger-acl-probe-v2",
            "status": "ADMISSION_ELIGIBLE",
            "inheritance_status": "PROBE_PASS",
            "cleanup_status": "CLEANUP_PASS",
            "probe_nonce_sha256": nonce_sha256,
            "runner_identity_sha256": runner_identity,
            "cleanup_identity_sha256": helper_identity,
            "ledger_policy_sha256": ledger_policy,
            "probe_policy_sha256": probe_policy,
            "probe_object_sha256": probe_object,
            "ledger_object_sha256": ledger_object,
            "created_at_utc": created_at.isoformat(),
            "expires_at_utc": expires_at.isoformat(),
        }
        return {
            "schema_version": "npi-real20-ledger-probe-result-v2",
            "status": "ADMISSION_ELIGIBLE",
            "ledger_acl_probe": proof,
            "cleanup_capability": capability,
            "cleanup_proof": cleanup_proof,
        }
    except Real20Error:
        raise
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_LEDGER_PROBE_NATIVE_UNAVAILABLE") from exc


def run_inherited_cleanup_from_environment(
    project_root: Path,
    *,
    now: datetime | None = None,
) -> dict[str, str]:
    """Restricted helper entry: inherited handle + capability only, never a path."""
    current = now or datetime.now(UTC)
    plan = load_control_plane_plan(project_root)
    require_control_plane_execution_authority(project_root, plan)
    raw_handle = os.environ.get("NPI_REAL20_CLEANUP_HANDLE")
    raw_capability = os.environ.get("NPI_REAL20_CLEANUP_CAPABILITY_JSON")
    nonce_sha256 = os.environ.get("NPI_REAL20_PROBE_NONCE_SHA256")
    if raw_handle is None or raw_capability is None or nonce_sha256 is None:
        raise Real20Error("REAL20_CLEANUP_HELPER_INHERITED_HANDLE_REQUIRED")
    try:
        handle = int(raw_handle, 10)
        capability = strict_json(raw_capability.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_CLEANUP_HELPER_INPUT_INVALID") from exc
    from .cleanup_helper import cleanup_inherited_probe_handle

    return cleanup_inherited_probe_handle(
        handle,
        capability,
        expected_probe_nonce_sha256=nonce_sha256,
        now=current,
    )
