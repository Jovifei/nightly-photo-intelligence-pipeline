"""Controlled future synthetic execution entry; no model is imported here."""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from .common import EngineeringError, canonical, is_digest, require, sha256, strict_json
from .evidence import quality_matrix, validate_identity_observations, validate_resume_evidence
from .lease import Reservation, finish, reserve, validate_lease
from .path_policy import overlaps, recheck, validate_plan
from .readiness import python_check
from .source_identity import full_source_identity

# Absence is not zero. These are callback declarations, not OS measurements.
REQUIRED_FORBIDDEN_COUNTERS = frozenset(
    {
        "real_photo_read_count",
        "real_exif_read_count",
        "g1_source_access",
        "sqlite_write_count",
        "app_write_count",
        "production_bundle_count",
        "model_download_bytes",
    }
)
_EVIDENCE_LABEL = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")


@dataclass(frozen=True)
class ControlledExecutionPlan:
    """Immutable admission inputs supplied by a future synthetic runner."""

    project_root: Path
    ledger_root: Path
    lease: bytes
    trusted_receipt_sha256: str
    inputs: Mapping[str, Path]
    outputs: Mapping[str, Path]
    protected: Mapping[str, Path]
    observed_bindings: Mapping[str, str]


def path_plan_digest(
    *,
    inputs: Mapping[str, Path],
    outputs: Mapping[str, Path],
    protected: Mapping[str, Path],
) -> str:
    """Return the stable binding for the complete path plan, not one output."""

    payload = {
        name: {label: str(Path(value)) for label, value in paths.items()}
        for name, paths in (
            ("inputs", inputs),
            ("outputs", outputs),
            ("protected", protected),
        )
    }
    return sha256(canonical(payload))


def _bind_operational_roots(plan: ControlledExecutionPlan) -> None:
    """Bind the actual reservation destination to the Owner-bound path plan.

    Do not resolve aliases here: validate_plan must still see and reject links.
    A caller cannot reset a consumed allowance by selecting another ledger while
    leaving the signed path-plan digest unchanged.
    """
    require(
        plan.protected.get("ledger_root") == plan.ledger_root,
        "NPI_LEDGER_ROOT_BINDING_MISMATCH",
    )
    require(
        plan.protected.get("project_root") == plan.project_root,
        "NPI_PROJECT_ROOT_BINDING_MISMATCH",
    )
    blockers = [*plan.inputs.values()]
    blockers.extend(path for name, path in plan.protected.items() if name != "ledger_root")
    require(
        all(not overlaps(plan.ledger_root, path) for path in blockers),
        "NPI_LEDGER_ROOT_OVERLAP",
    )


def _bind_static_inputs(
    plan: ControlledExecutionPlan, source: Mapping[str, Any], path_digest: str
) -> None:
    state = plan.project_root / "PROJECT_STATE.json"
    state_bytes = state.read_bytes()
    payload = strict_json(state_bytes)
    phase_status = payload.get("phase_status") if isinstance(payload, Mapping) else None
    require(
        isinstance(phase_status, Mapping) and phase_status.get("N2B2") == "LOCKED",
        "NPI_PROJECT_STATE_BOUNDARY_VIOLATION",
    )
    expected = {
        "candidate_commit": source["candidate_commit"],
        "candidate_tree": source["candidate_tree"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "project_state_sha256": sha256(state_bytes),
        "path_plan_sha256": path_digest,
    }
    for name, value in expected.items():
        require(plan.observed_bindings.get(name) == value, "NPI_SOURCE_BINDING_MISMATCH")


def _validate_callback_evidence(
    result: Mapping[str, Any], *, identity: Mapping[str, object]
) -> dict[str, Any]:
    quality_records = result.get("quality_records")
    require(
        isinstance(quality_records, Sequence)
        and not isinstance(quality_records, (str, bytes))
        and all(isinstance(item, Mapping) for item in quality_records),
        "NPI_QUALITY_RECORD_INCOMPLETE",
    )
    quality = quality_matrix(
        cast(Sequence[Mapping[str, Any]], quality_records), python_supported=True
    )
    require(quality["complete"] is True, "NPI_QUALITY_INCOMPLETE")

    observations = result.get("identity_observations")
    require(
        isinstance(observations, Sequence)
        and not isinstance(observations, (str, bytes))
        and all(isinstance(item, Mapping) for item in observations),
        "NPI_IDENTITY_OBSERVATIONS_INCOMPLETE",
    )
    identity_sha = validate_identity_observations(
        cast(Sequence[Mapping[str, Any]], observations), identity
    )

    resume = result.get("resume")
    if not isinstance(resume, Mapping):
        raise EngineeringError("NPI_RESUME_EVIDENCE_INVALID")
    resume = cast(Mapping[str, Any], resume)
    exit_code = resume.get("exit_code")
    resume_status = resume.get("resume_status")
    before = resume.get("before")
    after = resume.get("after")
    if not (
        type(exit_code) is int
        and isinstance(resume_status, str)
        and isinstance(before, Mapping)
        and isinstance(after, Mapping)
    ):
        raise EngineeringError("NPI_RESUME_EVIDENCE_INVALID")
    resume_evidence = validate_resume_evidence(
        exit_code=exit_code,
        resume_status=resume_status,
        before=cast(Mapping[str, str], before),
        after=cast(Mapping[str, str], after),
        model_load_count=resume.get("model_load_count"),
    )

    artifacts = result.get("artifacts")
    if not (
        isinstance(artifacts, Mapping)
        and bool(artifacts)
        and all(
            isinstance(key, str) and _EVIDENCE_LABEL.fullmatch(key) is not None and is_digest(value)
            for key, value in artifacts.items()
        )
    ):
        raise EngineeringError("NPI_ARTIFACT_EVIDENCE_INVALID")
    artifacts = cast(Mapping[str, object], artifacts)
    # Never synthesize missing observations, and never accept a nonzero
    # forbidden action as a successfully completed controlled execution.
    counters = result.get("forbidden_counters")
    if not (
        isinstance(counters, Mapping)
        and REQUIRED_FORBIDDEN_COUNTERS.issubset(counters)
        and all(
            isinstance(key, str)
            and _EVIDENCE_LABEL.fullmatch(key) is not None
            and type(value) is int
            and value >= 0
            for key, value in counters.items()
        )
    ):
        raise EngineeringError("NPI_COUNTER_EVIDENCE_INVALID")
    counters = cast(Mapping[str, int], counters)
    require(all(value == 0 for value in counters.values()), "NPI_FORBIDDEN_ACTION_RECORDED")
    return {
        "quality_matrix": quality,
        "identity_observations_sha256": identity_sha,
        "resume": resume_evidence,
        "artifacts": dict(artifacts),
        "forbidden_counters": dict(counters),
    }


def run_controlled_execution(
    plan: ControlledExecutionPlan,
    *,
    now: datetime,
    identity_probe: Callable[[], Mapping[str, object]],
    execute: Callable[[], Mapping[str, Any]],
    evidence_sink: Callable[[Mapping[str, Any]], None] | None = None,
    post_execute_check: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Admit one source-bound synthetic run and consume its lease exactly once.

    ``execute`` is the only model-runner callback and is unreachable until every
    admission check and the durable reservation have succeeded. This function
    validates evidence returned by that callback; it does not manufacture it.
    """

    version = (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    support = python_check(version)
    require(support["status"] == "PASS", "NPI_UNSUPPORTED_PYTHON")

    _bind_operational_roots(plan)
    source = full_source_identity(plan.project_root)
    checked_paths = validate_plan(
        inputs=plan.inputs, outputs=plan.outputs, protected=plan.protected
    )
    require(bool(checked_paths), "NPI_PATH_PLAN_INCOMPLETE")
    path_digest = path_plan_digest(
        inputs=plan.inputs, outputs=plan.outputs, protected=plan.protected
    )
    _bind_static_inputs(plan, source, path_digest)

    permit = validate_lease(
        plan.lease,
        trusted_receipt_sha256=plan.trusted_receipt_sha256,
        observed_bindings=plan.observed_bindings,
        now=now,
    )
    identity = identity_probe()
    runtime_identity_sha = sha256(canonical(identity))
    require(
        plan.observed_bindings.get("runtime_identity_sha256") == runtime_identity_sha,
        "NPI_RUNTIME_IDENTITY_BINDING_MISMATCH",
    )

    reservation: Reservation | None = None
    try:
        recheck(checked_paths)
        reservation = reserve(
            plan.ledger_root,
            permit,
            observed_bindings=plan.observed_bindings,
            now=now,
        )
        callback_result = execute()
        require(isinstance(callback_result, Mapping), "NPI_CALLBACK_RESULT_INVALID")
        if post_execute_check is not None:
            post_execute_check()
        evidence = _validate_callback_evidence(callback_result, identity=identity)
        evidence.update(
            {
                "schema_version": "npi-controlled-execution-evidence-v1",
                "candidate_commit": source["candidate_commit"],
                "candidate_tree": source["candidate_tree"],
                "source_manifest_sha256": source["source_manifest_sha256"],
                "path_plan_sha256": path_digest,
                "runtime_identity_sha256": runtime_identity_sha,
                "execution_lease_sha256": plan.trusted_receipt_sha256,
            }
        )
        supplemental = callback_result.get("supplemental_evidence")
        if supplemental is not None:
            require(isinstance(supplemental, Mapping), "NPI_SUPPLEMENTAL_EVIDENCE_INVALID")
            evidence["supplemental_evidence"] = dict(supplemental)
        evidence_sha = sha256(canonical(evidence))
        if post_execute_check is not None:
            post_execute_check()
        if evidence_sink is not None:
            evidence_sink(evidence)
        finish(reservation, outcome="COMPLETE", evidence_sha256=evidence_sha, now=now)
        return {
            "result": "CONTROLLED_EXECUTION_COMPLETE",
            "evidence": evidence,
            "evidence_sha256": evidence_sha,
        }
    except Exception as exc:
        if reservation is not None:
            failure = {
                "schema_version": "npi-controlled-execution-evidence-v1",
                "result": "CONTROLLED_EXECUTION_FAILED",
                "error_type": type(exc).__name__,
            }
            finish(
                reservation,
                outcome="FAILED",
                evidence_sha256=sha256(canonical(failure)),
                now=now,
            )
        raise
