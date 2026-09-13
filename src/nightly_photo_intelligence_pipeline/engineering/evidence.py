"""Validate recorded evidence, never manufacture missing command observations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from .common import EngineeringError, canonical, is_digest, require, sha256

REQUIRED_QUALITY = {
    "pytest",
    "contract_integrity",
    "schema_validation",
    "sensitive_scan",
    "ruff_check",
    "ruff_format",
    "mypy",
}


def quality_matrix(
    records: Sequence[Mapping[str, Any]], *, python_supported: bool
) -> dict[str, Any]:
    names: set[str] = set()
    output: list[dict[str, Any]] = []
    for record in records:
        required = {
            "name",
            "command",
            "tool_version",
            "started_at_utc",
            "ended_at_utc",
            "exit_code",
            "status",
            "stdout_sha256",
            "stderr_sha256",
            "skipped_count",
        }
        require(set(record) == required, "NPI_QUALITY_RECORD_INCOMPLETE")
        name = record["name"]
        require(isinstance(name, str) and name not in names, "NPI_QUALITY_DUPLICATE_CHECK")
        names.add(name)
        command = record["command"]
        require(
            isinstance(command, list)
            and bool(command)
            and all(isinstance(arg, str) and arg for arg in command),
            "NPI_QUALITY_COMMAND_MISSING",
        )
        require(
            isinstance(record["tool_version"], str) and bool(record["tool_version"]),
            "NPI_QUALITY_VERSION_MISSING",
        )
        require(
            is_digest(record["stdout_sha256"]) and is_digest(record["stderr_sha256"]),
            "NPI_QUALITY_LOG_ANCHOR_MISSING",
        )
        try:
            start = datetime.fromisoformat(record["started_at_utc"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(record["ended_at_utc"].replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise EngineeringError("NPI_QUALITY_TIME_INVALID") from exc
        require(
            start.tzinfo is not None and end.tzinfo is not None and start <= end,
            "NPI_QUALITY_TIME_INVALID",
        )
        status, code = record["status"], record["exit_code"]
        require(
            status in ("PASS", "FAIL", "NOT_AVAILABLE", "SKIPPED"), "NPI_QUALITY_STATUS_INVALID"
        )
        require(code is None or type(code) is int, "NPI_QUALITY_EXIT_CODE_INVALID")
        skips = record["skipped_count"]
        require(type(skips) is int and skips >= 0, "NPI_QUALITY_SKIP_COUNT_INVALID")
        require(status != "PASS" or (code == 0 and skips == 0), "NPI_QUALITY_FALSE_PASS")
        output.append(dict(record))
    require(names == REQUIRED_QUALITY, "NPI_QUALITY_CHECK_SET_MISMATCH")
    complete = python_supported is True and all(item["status"] == "PASS" for item in output)
    return {
        "schema_version": "npi-quality-matrix-v2",
        "checks": output,
        "python_supported": python_supported,
        "complete": complete,
        "result": "QUALITY_COMPLETE" if complete else "QUALITY_INCOMPLETE",
        "execution_authorized": False,
        "independent_review_verdict": "NOT_ISSUED",
    }


def validate_identity_observations(
    observations: Sequence[Mapping[str, Any]], expected_identity: Mapping[str, Any]
) -> str:
    """Exactly five time-stamped snapshots; no counted but unchecked second query."""
    labels = ("preflight", "before_s3", "before_s20", "before_resume", "after_resume")
    require(len(observations) == 5, "NPI_IDENTITY_OBSERVATIONS_INCOMPLETE")
    expected = canonical(expected_identity)
    last_time: datetime | None = None
    for label, item in zip(labels, observations, strict=True):
        require(
            set(item) == {"checkpoint", "observed_at_utc", "identity"}
            and item["checkpoint"] == label,
            "NPI_IDENTITY_OBSERVATION_INVALID",
        )
        require(canonical(item["identity"]) == expected, "NPI_RUNTIME_IDENTITY_DRIFT")
        try:
            when = datetime.fromisoformat(item["observed_at_utc"].replace("Z", "+00:00"))
        except (ValueError, AttributeError) as exc:
            raise EngineeringError("NPI_IDENTITY_TIME_INVALID") from exc
        require(
            when.tzinfo is not None and (last_time is None or when >= last_time),
            "NPI_IDENTITY_TIME_INVALID",
        )
        last_time = when
    return sha256(canonical(list(observations)))


def validate_resume_evidence(
    *,
    exit_code: int,
    resume_status: str,
    before: Mapping[str, str],
    after: Mapping[str, str],
    model_load_count: int | None,
) -> dict[str, Any]:
    require(type(exit_code) is int and exit_code == 0, "NPI_LIVE_RESUME_NOT_SUCCESSFUL")
    require(resume_status == "ALREADY_COMPLETE_VERIFIED", "NPI_LIVE_RESUME_STATUS_INVALID")
    require(
        bool(before) and all(isinstance(k, str) and is_digest(v) for k, v in before.items()),
        "NPI_RESUME_INVENTORY_INVALID",
    )
    require(dict(before) == dict(after), "NPI_RESUME_ARTIFACTS_CHANGED")
    require(
        type(model_load_count) is int and model_load_count == 0, "NPI_RESUME_LOAD_NOT_PROVEN_ZERO"
    )
    return {
        "exit_code": 0,
        "resume_status": resume_status,
        "file_count": len(before),
        "added": 0,
        "changed": 0,
        "removed": 0,
        "model_load_count": 0,
        "inventory_sha256": sha256(canonical(dict(before))),
    }
