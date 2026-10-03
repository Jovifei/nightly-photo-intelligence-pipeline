"""Versioned Real20 runtime identity and ledger-proof validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from ..engineering.common import canonical, sha256
from .cleanup_capability import CleanupCapability, validate_cleanup_capability
from .contracts import Real20Error

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_V2_FIELDS = {"schema_version", "runtime_observation", "ledger_acl_probe"}
_IDENTITY_V3_FIELDS = {
    "schema_version",
    "runtime_observation",
    "ledger_acl_probe",
    "cleanup_capability",
}
_PROBE_V1_FIELDS = {
    "contract_version",
    "status",
    "inheritance_status",
    "cleanup_status",
    "runner_identity_sha256",
    "cleanup_identity_sha256",
    "ledger_policy_sha256",
    "probe_policy_sha256",
    "probe_object_sha256",
    "ledger_object_sha256",
    "created_at_utc",
    "expires_at_utc",
}
_PROBE_V2_FIELDS = _PROBE_V1_FIELDS | {"probe_nonce_sha256"}


@dataclass(frozen=True)
class RuntimeIdentity:
    """Validated runtime identity with separate live and Owner-bound domains."""

    control: dict[str, Any]
    observation: dict[str, Any]
    ledger_acl_probe: dict[str, Any] | None
    cleanup_capability: CleanupCapability | None
    control_digest: str
    observation_digest: str


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Real20Error(code)


def _aware_utc(value: datetime, code: str) -> datetime:
    _require(value.tzinfo is not None and value.utcoffset() is not None, code)
    return value.astimezone(UTC)


def _parse_utc(value: object, code: str) -> datetime:
    if not isinstance(value, str):
        raise Real20Error(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Real20Error(code) from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None, code)
    return parsed.astimezone(UTC)


def _digest(value: object, code: str = "REAL20_LEDGER_PROBE_DIGEST_INVALID") -> None:
    _require(isinstance(value, str) and _HEX64.fullmatch(value) is not None, code)


def validate_ledger_acl_probe(
    value: object,
    *,
    now: datetime,
    current_runner_identity_sha256: str | None = None,
    current_ledger_policy_sha256: str | None = None,
    current_ledger_object_sha256: str | None = None,
    require_live_binding: bool = False,
    require_nonce_binding: bool = False,
) -> dict[str, Any]:
    """Validate the finalized, redacted proof used for new admission."""

    current = _aware_utc(now, "REAL20_LEDGER_PROBE_TIME_INVALID")
    _require(isinstance(value, dict), "REAL20_LEDGER_PROBE_OBJECT_REQUIRED")
    proof = cast(dict[str, Any], value)
    expected_fields = _PROBE_V2_FIELDS if require_nonce_binding else _PROBE_V1_FIELDS
    _require(set(proof) == expected_fields, "REAL20_LEDGER_PROBE_FIELDS_INVALID")
    _require(
        proof["contract_version"]
        == (
            "npi-real20-ledger-acl-probe-v2"
            if require_nonce_binding
            else "npi-real20-ledger-acl-probe-v1"
        ),
        "REAL20_LEDGER_PROBE_CONTRACT_INVALID",
    )
    _require(
        proof["status"] == "ADMISSION_ELIGIBLE",
        "REAL20_LEDGER_PROBE_NOT_ADMISSION_ELIGIBLE",
    )
    _require(
        proof["inheritance_status"] == "PROBE_PASS",
        "REAL20_LEDGER_PROBE_NOT_VERIFIED",
    )
    _require(
        proof["cleanup_status"] == "CLEANUP_PASS",
        "REAL20_LEDGER_PROBE_CLEANUP_NOT_VERIFIED",
    )
    digest_fields = [
        "runner_identity_sha256",
        "cleanup_identity_sha256",
        "ledger_policy_sha256",
        "probe_policy_sha256",
        "probe_object_sha256",
        "ledger_object_sha256",
    ]
    if require_nonce_binding:
        digest_fields.append("probe_nonce_sha256")
    for key in digest_fields:
        _digest(proof[key])
    _require(
        proof["runner_identity_sha256"] != proof["cleanup_identity_sha256"],
        "REAL20_LEDGER_PROBE_IDENTITIES_NOT_DISTINCT",
    )
    _require(
        proof["ledger_policy_sha256"] == proof["probe_policy_sha256"],
        "REAL20_LEDGER_PROBE_POLICY_MISMATCH",
    )
    if require_live_binding and any(
        item is None
        for item in (
            current_runner_identity_sha256,
            current_ledger_policy_sha256,
            current_ledger_object_sha256,
        )
    ):
        raise Real20Error("REAL20_LEDGER_PROBE_LIVE_ATTESTATION_UNAVAILABLE")
    if current_runner_identity_sha256 is not None:
        _require(
            proof["runner_identity_sha256"] == current_runner_identity_sha256,
            "REAL20_LEDGER_PROBE_RUNNER_IDENTITY_MISMATCH",
        )
    if current_ledger_policy_sha256 is not None:
        _require(
            proof["ledger_policy_sha256"] == current_ledger_policy_sha256,
            "REAL20_LEDGER_PROBE_LIVE_POLICY_MISMATCH",
        )
    if current_ledger_object_sha256 is not None:
        _require(
            proof["ledger_object_sha256"] == current_ledger_object_sha256,
            "REAL20_LEDGER_PROBE_OBJECT_MISMATCH",
        )
    created = _parse_utc(proof["created_at_utc"], "REAL20_LEDGER_PROBE_TIME_INVALID")
    expires = _parse_utc(proof["expires_at_utc"], "REAL20_LEDGER_PROBE_TIME_INVALID")
    _require(created < expires and created <= current < expires, "REAL20_LEDGER_PROBE_STALE")
    return proof


def _observation(control: dict[str, Any]) -> dict[str, Any]:
    observation = control["runtime_observation"]
    _require(isinstance(observation, dict), "REAL20_RUNTIME_OBSERVATION_INVALID")
    _require(
        set(observation) == {"models", "worker", "vision", "qwen"}
        and all(isinstance(observation[key], dict) for key in observation),
        "REAL20_RUNTIME_OBSERVATION_FIELDS_INVALID",
    )
    return cast(dict[str, Any], observation)


def validate_runtime_identity(
    value: object,
    *,
    now: datetime,
    require_v2: bool = True,
    require_v3: bool = False,
    current_runner_identity_sha256: str | None = None,
    current_ledger_policy_sha256: str | None = None,
    current_ledger_object_sha256: str | None = None,
    require_live_binding: bool = False,
) -> RuntimeIdentity:
    """Validate v2/v3 identity; production admission may require v3 explicitly."""

    current = _aware_utc(now, "REAL20_RUNTIME_IDENTITY_TIME_INVALID")
    _require(isinstance(value, dict), "REAL20_RUNTIME_IDENTITY_OBJECT_REQUIRED")
    control = cast(dict[str, Any], value)
    version = control.get("schema_version")

    if version == "3.0":
        _require(set(control) == _IDENTITY_V3_FIELDS, "REAL20_RUNTIME_IDENTITY_FIELDS_INVALID")
        observation = _observation(control)
        proof = validate_ledger_acl_probe(
            control["ledger_acl_probe"],
            now=current,
            current_runner_identity_sha256=current_runner_identity_sha256,
            current_ledger_policy_sha256=current_ledger_policy_sha256,
            current_ledger_object_sha256=current_ledger_object_sha256,
            require_live_binding=require_live_binding,
            require_nonce_binding=True,
        )
        cleanup = validate_cleanup_capability(
            control["cleanup_capability"],
            now=current,
            expected_probe_nonce_sha256=proof["probe_nonce_sha256"],
            expected_probe_object_sha256=proof["probe_object_sha256"],
            expected_cleanup_identity_sha256=proof["cleanup_identity_sha256"],
        )
        return RuntimeIdentity(
            control=control,
            observation=observation,
            ledger_acl_probe=proof,
            cleanup_capability=cleanup,
            control_digest=sha256(canonical(control)),
            observation_digest=sha256(canonical(observation)),
        )

    if version == "2.0":
        if require_v3:
            raise Real20Error("REAL20_RUNTIME_IDENTITY_V3_REQUIRED")
        _require(set(control) == _IDENTITY_V2_FIELDS, "REAL20_RUNTIME_IDENTITY_FIELDS_INVALID")
        observation = _observation(control)
        proof = validate_ledger_acl_probe(
            control["ledger_acl_probe"],
            now=current,
            current_runner_identity_sha256=current_runner_identity_sha256,
            current_ledger_policy_sha256=current_ledger_policy_sha256,
            current_ledger_object_sha256=current_ledger_object_sha256,
            require_live_binding=require_live_binding,
        )
        return RuntimeIdentity(
            control=control,
            observation=observation,
            ledger_acl_probe=proof,
            cleanup_capability=None,
            control_digest=sha256(canonical(control)),
            observation_digest=sha256(canonical(observation)),
        )

    if require_v3:
        raise Real20Error("REAL20_RUNTIME_IDENTITY_V3_REQUIRED")
    if require_v2:
        raise Real20Error("REAL20_RUNTIME_IDENTITY_SCHEMA_INVALID")
    return RuntimeIdentity(
        control=control,
        observation=control,
        ledger_acl_probe=None,
        cleanup_capability=None,
        control_digest=sha256(canonical(control)),
        observation_digest=sha256(canonical(control)),
    )


def assemble_runtime_identity_v3(
    runtime_observation: object,
    probe_result: object,
    *,
    now: datetime,
) -> RuntimeIdentity:
    """Assemble v3 only from a successful, cleanup-bound synthetic probe result."""
    current = _aware_utc(now, "REAL20_RUNTIME_IDENTITY_TIME_INVALID")
    _require(
        isinstance(runtime_observation, dict),
        "REAL20_RUNTIME_OBSERVATION_INVALID",
    )
    _require(isinstance(probe_result, dict), "REAL20_LEDGER_PROBE_RESULT_INVALID")
    result = cast(dict[str, Any], probe_result)
    _require(
        set(result)
        == {
            "schema_version",
            "status",
            "ledger_acl_probe",
            "cleanup_capability",
            "cleanup_proof",
        },
        "REAL20_LEDGER_PROBE_RESULT_INVALID",
    )
    _require(
        result["schema_version"] == "npi-real20-ledger-probe-result-v2"
        and result["status"] == "ADMISSION_ELIGIBLE",
        "REAL20_LEDGER_PROBE_NOT_ADMISSION_ELIGIBLE",
    )
    cleanup_proof = result["cleanup_proof"]
    _require(isinstance(cleanup_proof, dict), "REAL20_CLEANUP_PROOF_INVALID")
    cleanup = cast(dict[str, Any], cleanup_proof)
    _require(
        set(cleanup)
        == {
            "schema_version",
            "cleanup_status",
            "probe_nonce_sha256",
            "probe_object_sha256",
            "cleanup_identity_sha256",
            "cleaned_at_utc",
        },
        "REAL20_CLEANUP_PROOF_INVALID",
    )
    _require(
        cleanup["schema_version"] == "npi-real20-cleanup-proof-v1"
        and cleanup["cleanup_status"] == "CLEANUP_PASS",
        "REAL20_CLEANUP_PROOF_INVALID",
    )
    proof = result["ledger_acl_probe"]
    _require(isinstance(proof, dict), "REAL20_LEDGER_PROBE_OBJECT_REQUIRED")
    proof_map = cast(dict[str, Any], proof)
    for field in (
        "probe_nonce_sha256",
        "probe_object_sha256",
        "cleanup_identity_sha256",
    ):
        _require(cleanup.get(field) == proof_map.get(field), "REAL20_CLEANUP_PROOF_BINDING_MISMATCH")
    cleaned_at = _parse_utc(cleanup["cleaned_at_utc"], "REAL20_CLEANUP_PROOF_TIME_INVALID")
    created_at = _parse_utc(proof_map.get("created_at_utc"), "REAL20_LEDGER_PROBE_TIME_INVALID")
    expires_at = _parse_utc(proof_map.get("expires_at_utc"), "REAL20_LEDGER_PROBE_TIME_INVALID")
    _require(
        created_at <= cleaned_at <= current < expires_at,
        "REAL20_CLEANUP_PROOF_TIME_INVALID",
    )
    control = {
        "schema_version": "3.0",
        "runtime_observation": runtime_observation,
        "ledger_acl_probe": proof,
        "cleanup_capability": result["cleanup_capability"],
    }
    return validate_runtime_identity(control, now=current, require_v3=True)
