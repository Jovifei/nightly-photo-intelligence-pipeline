"""Fail-closed, code-only control-plane checks for Route B cache recovery.

This module validates versioned DRAFT contracts and historical bindings.  It
does not create roots, inspect external objects, copy payloads, install
packages, use the network, or load any model/runtime component.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import yaml
from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from .domain.errors import GateNotAuthorizedError, PreflightUnsatisfiedError
from .json_strict import load_json_strict

ROUTE_B_STATUS = "ROUTE_B_CONTROL_PLANE_READY"
PY312_STATUS = "PY312_TOOLING_CONTROL_PLANE_READY"
NOT_AUTHORIZED = "NOT_AUTHORIZED"

_ARTIFACT_IDS = {
    "torchvision-keypointrcnn-resnet50-fpn-coco-v1",
    "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
    "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1",
}


def _schema(project_root: Path, name: str) -> Mapping[str, object]:
    value = load_json_strict(project_root / "schemas" / name)
    if not isinstance(value, Mapping):
        raise GateNotAuthorizedError(f"schema is not an object: {name}")
    return cast(Mapping[str, object], value)


def _validate(schema: Mapping[str, object], value: object, label: str) -> None:
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: list(error.path),
    )
    if errors:
        raise GateNotAuthorizedError(f"{label} schema invalid")


def _yaml(project_root: Path, relative: str) -> Mapping[str, object]:
    try:
        value = yaml.safe_load((project_root / relative).read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise GateNotAuthorizedError(f"control document unavailable: {relative}") from exc
    if not isinstance(value, Mapping):
        raise GateNotAuthorizedError(f"control document is not an object: {relative}")
    return cast(Mapping[str, object], value)


def _json(project_root: Path, relative: str) -> Mapping[str, object]:
    value = load_json_strict(project_root / relative)
    if not isinstance(value, Mapping):
        raise GateNotAuthorizedError(f"control document is not an object: {relative}")
    return cast(Mapping[str, object], value)


def _historical_artifacts(project_root: Path) -> dict[str, dict[str, object]]:
    register = _json(project_root, "research/N2B1R_local_research_artifact_register.json")
    promotion = _json(project_root, "research/N2B1P_cache_promotion_evidence.json")
    register_items = register.get("artifacts")
    promotion_items = promotion.get("artifacts")
    if not isinstance(register_items, list) or not isinstance(promotion_items, list):
        raise GateNotAuthorizedError("historical artifact records are invalid")
    registers = {
        str(item["id"]): item
        for item in register_items
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    promoted = {
        str(item["id"]): item
        for item in promotion_items
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    if set(registers) != _ARTIFACT_IDS or set(promoted) != _ARTIFACT_IDS:
        raise GateNotAuthorizedError("historical artifact set is not exactly three items")
    result: dict[str, dict[str, object]] = {}
    for artifact_id in sorted(_ARTIFACT_IDS):
        register_item = registers[artifact_id]
        promoted_item = promoted[artifact_id]
        result[artifact_id] = {
            "id": artifact_id,
            "revision": register_item.get("revision"),
            "filename": register_item.get("filename"),
            "byte_count": promoted_item.get("byte_count"),
            "local_sha256": promoted_item.get("local_sha256"),
            "transfer_manifest_sha256": promoted_item.get("transfer_manifest_sha256"),
        }
    return result


def validate_reprovision_document(
    document: Mapping[str, object],
    *,
    historical_configuration_digest: str,
    historical_cache_root_identity: str,
    historical_artifacts: Mapping[str, Mapping[str, object]],
) -> None:
    """Validate immutable historical bindings without touching external roots."""
    superseded = document.get("superseded_runtime_configuration")
    if not isinstance(superseded, Mapping):
        raise GateNotAuthorizedError("Route B superseded runtime binding is missing")
    if superseded.get("configuration_digest") != historical_configuration_digest:
        raise GateNotAuthorizedError("Route B superseded configuration digest mismatch")
    if superseded.get("cache_root_identity") != historical_cache_root_identity:
        raise GateNotAuthorizedError("Route B superseded cache identity mismatch")
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise GateNotAuthorizedError("Route B artifact set must contain exactly three items")
    actual = {str(item.get("id")): item for item in artifacts if isinstance(item, Mapping)}
    if set(actual) != _ARTIFACT_IDS:
        raise GateNotAuthorizedError("Route B artifact IDs do not match the historical set")
    for artifact_id, expected in historical_artifacts.items():
        item = actual[artifact_id]
        for field in (
            "revision",
            "filename",
            "byte_count",
            "local_sha256",
            "transfer_manifest_sha256",
        ):
            if item.get(field) != expected.get(field):
                raise GateNotAuthorizedError(f"Route B historical binding mismatch: {field}")
    authorities = document.get("authorities")
    if not isinstance(authorities, Mapping):
        raise GateNotAuthorizedError("Route B authorities are missing")
    b_cache = authorities.get("b_cache")
    b_source = authorities.get("b_source")
    if not isinstance(b_cache, Mapping) or not isinstance(b_source, Mapping):
        raise GateNotAuthorizedError("Route B authorities are invalid")
    if b_cache.get("network_access") != "DENY" or b_cache.get("status") != NOT_AUTHORIZED:
        raise GateNotAuthorizedError("B-cache authority is not fail-closed")
    if b_source.get("status") != NOT_AUTHORIZED:
        raise GateNotAuthorizedError("B-source authority is not separate and unauthorized")


def validate_successor_runtime_binding(
    document: Mapping[str, object], runtime: Mapping[str, object]
) -> None:
    """Bind the successor task's digest and object identity to its runtime draft."""
    successor = document.get("successor_runtime_configuration")
    if not isinstance(successor, Mapping):
        raise GateNotAuthorizedError("Route B successor runtime binding is missing")
    for field in ("configuration_digest", "cache_root_identity"):
        if successor.get(field) != runtime.get(field):
            raise GateNotAuthorizedError(f"Route B successor runtime {field} mismatch")
    if runtime.get("status") != "DRAFT_NOT_AUTHORIZED":
        raise GateNotAuthorizedError("Route B successor runtime is executable")
    if runtime.get("configuration_digest") != "0" * 64:
        raise GateNotAuthorizedError("Route B successor runtime digest is not a DRAFT placeholder")
    if runtime.get("cache_root_identity") != "0" * 64:
        raise GateNotAuthorizedError("Route B successor cache identity is not a DRAFT placeholder")


def _historical_runtime(project_root: Path) -> tuple[str, str]:
    runtime = _json(project_root, "approvals/n2b1p_runtime_configuration.json")
    digest = runtime.get("configuration_digest")
    identity = runtime.get("cache_root_identity")
    if not isinstance(digest, str) or not isinstance(identity, str):
        raise GateNotAuthorizedError("historical runtime binding is invalid")
    return digest, identity


def load_reprovision_control_plane(project_root: Path) -> dict[str, object]:
    """Strict-load Route B DRAFT controls and return redacted validation facts."""
    task = _yaml(project_root, "tasks/phase_n2b1p_cache_reprovision_v1.yaml")
    approval = _yaml(project_root, "approvals/owner_n2b1p_cache_reprovision_v1.DRAFT.yaml")
    runtime = _json(project_root, "approvals/n2b1p_reprovision_runtime_configuration.DRAFT.json")
    _validate(_schema(project_root, "n2b1p_cache_reprovision_v1.schema.json"), task, "Route B task")
    _validate(
        _schema(project_root, "owner_n2b1p_cache_reprovision_v1.schema.json"),
        approval,
        "Route B approval",
    )
    _validate(
        _schema(project_root, "n2b1p_reprovision_runtime_configuration_v1.schema.json"),
        runtime,
        "Route B runtime",
    )
    validate_successor_runtime_binding(task, runtime)
    historical_digest, historical_identity = _historical_runtime(project_root)
    historical_artifacts = _historical_artifacts(project_root)
    validate_reprovision_document(
        task,
        historical_configuration_digest=historical_digest,
        historical_cache_root_identity=historical_identity,
        historical_artifacts=historical_artifacts,
    )
    if (
        task.get("status") != "DRAFT_NOT_AUTHORIZED"
        or approval.get("status") != "DRAFT_NOT_AUTHORIZED"
    ):
        raise GateNotAuthorizedError("Route B DRAFT controls must remain non-executable")
    return {
        "task_status": task["status"],
        "approval_status": approval["status"],
        "runtime_status": runtime["status"],
        "execution_authority": NOT_AUTHORIZED,
        "historical_artifact_count": len(historical_artifacts),
        "network_access": "DENY",
    }


def validate_owner_provisioned_root(
    attestation: Mapping[str, object], *, expected_identity: str
) -> None:
    """Validate a future Owner root attestation without opening that root."""
    required = {
        "status": "OWNER_PREPROVISIONED",
        "empty": True,
        "non_reparse": True,
        "outside_runtime": True,
        "outside_source": True,
        "outside_quarantine": True,
    }
    if any(attestation.get(key) != value for key, value in required.items()):
        raise GateNotAuthorizedError("Route B Owner root attestation is not eligible")
    identity = attestation.get("object_identity_sha256")
    if identity != expected_identity:
        raise GateNotAuthorizedError("Route B Owner root identity is invalid")


def validate_b_source_record(
    record: Mapping[str, object],
    *,
    historical_artifacts: Mapping[str, Mapping[str, object]],
) -> None:
    """Require a future immutable B-source record before B-cache can run."""
    if record.get("status") != "B_SOURCE_BYTES_READY":
        raise GateNotAuthorizedError("B-source evidence is not ready")
    if record.get("source_mode") not in {
        "LOCAL_OWNER_IDENTIFIED",
        "NETWORK_REACQUISITION_SEPARATE_APPROVAL",
    }:
        raise GateNotAuthorizedError("B-source evidence mode is invalid")
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 3:
        raise GateNotAuthorizedError("B-source evidence must bind exactly three artifacts")
    actual = {str(item.get("id")): item for item in artifacts if isinstance(item, Mapping)}
    if set(actual) != _ARTIFACT_IDS:
        raise GateNotAuthorizedError("B-source artifact IDs do not match history")
    for artifact_id, expected in historical_artifacts.items():
        item = actual[artifact_id]
        for field in (
            "revision",
            "filename",
            "byte_count",
            "local_sha256",
            "transfer_manifest_sha256",
        ):
            if item.get(field) != expected.get(field):
                raise GateNotAuthorizedError(f"B-source historical binding mismatch: {field}")


def check_reprovision_control_plane(project_root: Path) -> dict[str, object]:
    try:
        facts = load_reprovision_control_plane(project_root)
    except (GateNotAuthorizedError, PreflightUnsatisfiedError, OSError, ValueError) as exc:
        return {"status": "ROUTE_B_CONTROL_PLANE_INVALID", "error_code": type(exc).__name__}
    return {"status": ROUTE_B_STATUS, **facts}


def check_python312_tooling_control_plane(project_root: Path) -> dict[str, object]:
    try:
        task = _yaml(project_root, "tasks/tooling_python312_quality_environment_v1.yaml")
        approval = _yaml(
            project_root, "approvals/owner_python312_quality_environment_v1.DRAFT.yaml"
        )
        _validate(
            _schema(project_root, "python312_tooling_contract_v1.schema.json"),
            task,
            "Python 3.12 task",
        )
        _validate(
            _schema(project_root, "owner_python312_quality_environment_v1.schema.json"),
            approval,
            "Python 3.12 approval",
        )
        pins = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
        dependencies = list(pins["project"]["dependencies"])
        dev = list(pins["project"]["optional-dependencies"]["dev"])
        expected = sorted(dependencies + dev)
        package_items = task.get("packages")
        if not isinstance(package_items, list) or not all(
            isinstance(item, Mapping) for item in package_items
        ):
            raise GateNotAuthorizedError("Python 3.12 package pins are invalid")
        declared = sorted(
            f"{item['name']}=={item['version']}"
            for item in cast(list[Mapping[str, object]], package_items)
        )
        if expected != declared:
            raise GateNotAuthorizedError("Python 3.12 pins differ from pyproject.toml")
        return {
            "status": PY312_STATUS,
            "approval_status": approval["status"],
            "execution_authority": NOT_AUTHORIZED,
            "installation": NOT_AUTHORIZED,
            "network_access": "DENY",
        }
    except (GateNotAuthorizedError, OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        return {"status": "PY312_TOOLING_CONTROL_PLANE_INVALID", "error_code": type(exc).__name__}


__all__ = [
    "check_python312_tooling_control_plane",
    "check_reprovision_control_plane",
    "load_reprovision_control_plane",
    "validate_b_source_record",
    "validate_owner_provisioned_root",
    "validate_reprovision_document",
    "validate_successor_runtime_binding",
]
