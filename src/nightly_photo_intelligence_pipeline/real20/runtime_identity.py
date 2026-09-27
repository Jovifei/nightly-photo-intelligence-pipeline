"""Versioned Real20 runtime identity and ledger-proof validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from ..engineering.common import canonical, sha256
from .contracts import Real20Error

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY_FIELDS = {"schema_version", "runtime_observation", "ledger_acl_probe"}
_PROBE_FIELDS = {
    "contract_version",
    "status",
    "inheritance_status",
    "cleanup_status",
    "runner_identity_sha256",
    "cleanup_identity_sha256",
    "ledger_policy_sha256",
    "probe_policy_sha256",
    "probe_object_sha256",
    "created_at_utc",
    "expires_at_utc",
}


@dataclass(frozen=True)
class RuntimeIdentity:
    """Validated runtime identity with separate live and Owner-bound domains."""

    control: dict[str, Any]
    observation: dict[str, Any]
    ledger_acl_probe: dict[str, Any] | None
    control_digest: str
    observation_digest: str


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Real20Error(code)


def _parse_utc(value: object, code: str) -> datetime:
    if not isinstance(value, str):
        raise Real20Error(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Real20Error(code) from exc
    _require(parsed.tzinfo is not None, code)
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
) -> dict[str, Any]:
    """Validate the finalized, redacted proof used for new admission."""

    _require(isinstance(value, dict), "REAL20_LEDGER_PROBE_OBJECT_REQUIRED")
    proof = cast(dict[str, Any], value)
    _require(set(proof) == _PROBE_FIELDS, "REAL20_LEDGER_PROBE_FIELDS_INVALID")
    _require(
        proof["contract_version"] == "npi-real20-ledger-acl-probe-v1",
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
    for key in (
        "runner_identity_sha256",
        "cleanup_identity_sha256",
        "ledger_policy_sha256",
        "probe_policy_sha256",
        "probe_object_sha256",
    ):
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
        value is None
        for value in (
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
            proof["probe_object_sha256"] == current_ledger_object_sha256,
            "REAL20_LEDGER_PROBE_OBJECT_MISMATCH",
        )
    created = _parse_utc(proof["created_at_utc"], "REAL20_LEDGER_PROBE_TIME_INVALID")
    expires = _parse_utc(proof["expires_at_utc"], "REAL20_LEDGER_PROBE_TIME_INVALID")
    current = now.astimezone(UTC)
    _require(created < expires and created <= current < expires, "REAL20_LEDGER_PROBE_STALE")
    return proof


def validate_runtime_identity(
    value: object,
    *,
    now: datetime,
    require_v2: bool = True,
    current_runner_identity_sha256: str | None = None,
    current_ledger_policy_sha256: str | None = None,
    current_ledger_object_sha256: str | None = None,
    require_live_binding: bool = False,
) -> RuntimeIdentity:
    """Validate v2 identity; legacy v1 is accepted only by low-level tests."""

    _require(isinstance(value, dict), "REAL20_RUNTIME_IDENTITY_OBJECT_REQUIRED")
    control = cast(dict[str, Any], value)
    if control.get("schema_version") != "2.0":
        if require_v2:
            raise Real20Error("REAL20_RUNTIME_IDENTITY_SCHEMA_INVALID")
        return RuntimeIdentity(
            control=control,
            observation=control,
            ledger_acl_probe=None,
            control_digest=sha256(canonical(control)),
            observation_digest=sha256(canonical(control)),
        )
    _require(set(control) == _IDENTITY_FIELDS, "REAL20_RUNTIME_IDENTITY_FIELDS_INVALID")
    observation = control["runtime_observation"]
    _require(isinstance(observation, dict), "REAL20_RUNTIME_OBSERVATION_INVALID")
    _require(
        set(observation) == {"models", "worker", "vision", "qwen"}
        and all(isinstance(observation[key], dict) for key in observation),
        "REAL20_RUNTIME_OBSERVATION_FIELDS_INVALID",
    )
    proof = validate_ledger_acl_probe(
        control["ledger_acl_probe"],
        now=now,
        current_runner_identity_sha256=current_runner_identity_sha256,
        current_ledger_policy_sha256=current_ledger_policy_sha256,
        current_ledger_object_sha256=current_ledger_object_sha256,
        require_live_binding=require_live_binding,
    )
    return RuntimeIdentity(
        control=control,
        observation=cast(dict[str, Any], observation),
        ledger_acl_probe=proof,
        control_digest=sha256(canonical(control)),
        observation_digest=sha256(canonical(observation)),
    )
