"""Controlled adapter for the public N2B2 runtime revalidation command.

The adapter owns the admission order.  It validates quality and all source
bindings before probing the runtime, reserves one engineering lease exactly
once, and only then starts the runner subprocesses.  The subprocess worker is
the existing S3/S20 implementation; it is not another authorization path.
"""

from __future__ import annotations

import os
import platform
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from ..engineering.common import (
    EngineeringError,
    canonical,
    is_digest,
    require,
    sha256,
    strict_json,
)
from ..engineering.controlled_entry import (
    REQUIRED_FORBIDDEN_COUNTERS,
    ControlledExecutionPlan,
    path_plan_digest,
    run_controlled_execution,
)
from ..engineering.evidence import quality_matrix
from ..engineering.lease import validate_lease
from ..engineering.path_policy import checked_path, overlaps, recheck, validate_plan
from ..engineering.readiness import python_check
from ..engineering.source_identity import full_source_identity
from ..n2b1p_integrity import N2B1PRuntimeConfiguration, load_n2b1p_runtime_configuration
from . import worker_dispatch
from .runtime_identity_revalidation import snapshot_tree

IdentityProbe = Callable[[], Mapping[str, object]]
Execute = Callable[[], Mapping[str, Any]]
_LEASE_SCHEMA = "npi_synthetic_execution_lease_v2.schema.json"
_WORKER_MODULE = "nightly_photo_intelligence_pipeline.n2b2_synthetic.controlled_runtime_worker"
_WORKER_CALL = f"from {_WORKER_MODULE} import run_from_stdin; raise SystemExit(run_from_stdin())"
_LEDGER_DIR = "n2b2-controlled-execution-ledger"
_COUNTER_LABEL = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_TASK_RECEIPT = "approvals/owner_n2b2_ollama_runtime_identity_revalidation_20260906.yaml"
_TASK_RECEIPT_SCHEMA = "schemas/owner_n2b2_ollama_runtime_identity_revalidation_v1.schema.json"
_OWNER_LEASE_ANCHOR_SCHEMA = "schemas/npi_owner_execution_lease_anchor_v1.schema.json"
_OWNER_LEASE_ANCHOR_DIR = "owner-approvals"
_OWNER_LEASE_ANCHOR_FILE = "n2b2_synthetic_execution_lease_anchor.json"


@dataclass(frozen=True)
class _OwnerLeaseAnchor:
    path: Path
    data: bytes
    execution_lease_sha256: str


def _checked_dir(value: Path) -> Path:
    checked_path(Path(value), must_exist=True)
    return Path(value)


def _validate_file_syntax(path: Path) -> None:
    require(path.is_absolute(), "NPI_PATH_NOT_ABSOLUTE")
    require(".." not in path.parts, "NPI_PATH_TRAVERSAL")
    require(not str(path).startswith(("\\\\", "//")), "NPI_NETWORK_PATH_DENIED")
    require(
        all(":" not in part for part in path.parts[1:]),
        "NPI_ALTERNATE_STREAM_DENIED",
    )


def _regular_file(path: Path, *, nonempty: bool = True) -> tuple[Path, bytes]:
    candidate = Path(path)
    _validate_file_syntax(candidate)
    checked_path(candidate.parent, must_exist=True)
    try:
        info = candidate.lstat()
    except OSError as exc:
        raise EngineeringError("NPI_REQUIRED_FILE_MISSING") from exc
    require(
        stat.S_ISREG(info.st_mode)
        and info.st_nlink == 1
        and not (getattr(info, "st_file_attributes", 0) & 0x400),
        "NPI_REQUIRED_FILE_INVALID",
    )
    try:
        data = candidate.read_bytes()
    except OSError as exc:
        raise EngineeringError("NPI_REQUIRED_FILE_UNREADABLE") from exc
    require(not nonempty or bool(data), "NPI_REQUIRED_FILE_EMPTY")
    return candidate, data


def _file_fingerprint(path: Path) -> tuple[int, int, int, int, str]:
    candidate, data = _regular_file(path, nonempty=False)
    info = candidate.lstat()
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, sha256(data))


def _assert_file_fingerprint(
    fingerprints: Mapping[Path, tuple[int, int, int, int, str]],
) -> None:
    for path, expected in fingerprints.items():
        require(_file_fingerprint(path) == expected, "NPI_BOUND_FILE_CHANGED")


def _add_protected(protected: dict[str, Path], name: str, path: Path) -> None:
    normalized = os.path.normcase(os.path.abspath(str(path)))
    for existing in protected.values():
        existing_normalized = os.path.normcase(os.path.abspath(str(existing)))
        if normalized == existing_normalized:
            return
        require(not overlaps(path, existing), "NPI_PATH_PLAN_OVERLAP")
    protected[name] = path


def _check_disjoint(
    inputs: Mapping[str, Path], protected: Mapping[str, Path], outputs: Mapping[str, Path]
) -> None:
    roots = [*inputs.values(), *protected.values(), *outputs.values()]
    for index, left in enumerate(roots):
        for right in roots[index + 1 :]:
            if os.path.normcase(os.path.abspath(str(left))) == os.path.normcase(
                os.path.abspath(str(right))
            ):
                continue
            require(not overlaps(left, right), "NPI_PATH_PLAN_OVERLAP")


def _load_quality(path: Path) -> tuple[list[Mapping[str, Any]], dict[str, Any], bytes]:
    _, data = _regular_file(path)
    payload = strict_json(data)
    require(isinstance(payload, Mapping), "NPI_QUALITY_EVIDENCE_INVALID")
    records = payload.get("checks")
    require(
        isinstance(records, Sequence) and not isinstance(records, (str, bytes)),
        "NPI_QUALITY_EVIDENCE_INVALID",
    )
    checks = cast(Sequence[Mapping[str, Any]], records)
    require(all(isinstance(item, Mapping) for item in checks), "NPI_QUALITY_EVIDENCE_INVALID")
    version = (sys.version_info[0], sys.version_info[1], sys.version_info[2])
    support = python_check(version)
    matrix = quality_matrix(checks, python_supported=support["status"] == "PASS")
    require(matrix["complete"] is True, "NPI_QUALITY_INCOMPLETE")
    return list(checks), matrix, data


def _validate_lease_schema(project_root: Path, lease: Mapping[str, Any]) -> None:
    try:
        schema = strict_json((project_root / "schemas" / _LEASE_SCHEMA).read_bytes())
    except OSError as exc:
        raise EngineeringError("NPI_LEASE_SCHEMA_UNAVAILABLE") from exc
    errors = list(Draft202012Validator(schema).iter_errors(lease))
    require(not errors, "NPI_LEASE_SCHEMA_INVALID")


def _load_task_specific_receipt(project_root: Path) -> Mapping[str, object]:
    try:
        import yaml

        payload = yaml.safe_load((project_root / _TASK_RECEIPT).read_text(encoding="utf-8"))
        schema = strict_json((project_root / _TASK_RECEIPT_SCHEMA).read_bytes())
    except Exception as exc:
        raise EngineeringError("NPI_TASK_RECEIPT_INVALID") from exc
    require(isinstance(payload, Mapping), "NPI_TASK_RECEIPT_INVALID")
    require(
        not list(Draft202012Validator(schema).iter_errors(payload)),
        "NPI_TASK_RECEIPT_INVALID",
    )
    return cast(Mapping[str, object], payload)


def _load_owner_lease_anchor(project_root: Path, runtime_parent: Path) -> _OwnerLeaseAnchor:
    path = runtime_parent / _OWNER_LEASE_ANCHOR_DIR / _OWNER_LEASE_ANCHOR_FILE
    _, data = _regular_file(path)
    payload = strict_json(data)
    try:
        schema = strict_json((project_root / _OWNER_LEASE_ANCHOR_SCHEMA).read_bytes())
    except OSError as exc:
        raise EngineeringError("NPI_OWNER_LEASE_ANCHOR_SCHEMA_UNAVAILABLE") from exc
    require(isinstance(payload, Mapping), "NPI_OWNER_LEASE_ANCHOR_INVALID")
    require(
        not list(Draft202012Validator(schema).iter_errors(payload)),
        "NPI_OWNER_LEASE_ANCHOR_INVALID",
    )
    digest = payload.get("execution_lease_sha256")
    require(isinstance(digest, str) and is_digest(digest), "NPI_OWNER_LEASE_ANCHOR_INVALID")
    return _OwnerLeaseAnchor(path=path, data=data, execution_lease_sha256=digest)


def _validate_task_specific_receipt(
    *,
    receipt: Mapping[str, object],
    review_bytes: bytes,
    state_bytes: bytes,
    old_identity: Mapping[str, object],
    current_identity: Mapping[str, object],
) -> None:
    try:
        review_text = review_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EngineeringError("NPI_REVIEW_ARTIFACT_INVALID") from exc
    from .runtime_identity_revalidation import (
        BASE_CANDIDATE,
        validate_revalidation_authorization,
    )

    try:
        validate_revalidation_authorization(
            receipt,
            review_sha256=sha256(review_bytes),
            review_text=review_text,
            project_state_sha256=sha256(state_bytes),
            project_state_n2b2="LOCKED",
            old_identity=old_identity,
            current_identity=current_identity,
            current_head=BASE_CANDIDATE,
        )
    except ValueError as exc:
        raise EngineeringError("NPI_TASK_RECEIPT_BINDING_INVALID") from exc


def _identity_record(identity: Any) -> dict[str, object]:
    values = {
        "model_name": getattr(identity, "model_name", None),
        "full_local_digest": getattr(identity, "full_local_digest", None),
        "size_bytes": getattr(identity, "size_bytes", None),
        "quantization_level": getattr(identity, "quantization_level", None),
        "capabilities": getattr(identity, "capabilities", None),
        "ollama_version": getattr(identity, "ollama_version", None),
    }
    require(
        isinstance(values["model_name"], str)
        and is_digest(values["full_local_digest"])
        and type(values["size_bytes"]) is int
        and values["size_bytes"] > 0
        and isinstance(values["quantization_level"], str)
        and isinstance(values["capabilities"], Sequence)
        and not isinstance(values["capabilities"], (str, bytes))
        and all(isinstance(item, str) and item for item in values["capabilities"])
        and isinstance(values["ollama_version"], str)
        and bool(values["ollama_version"]),
        "NPI_RUNTIME_IDENTITY_INVALID",
    )
    return cast(dict[str, object], values)


def _observation(label: str, identity: Mapping[str, object]) -> dict[str, object]:
    return {
        "checkpoint": label,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "identity": dict(identity),
    }


def _write_exclusive_json(path: Path, value: object) -> None:
    data = canonical(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as exc:
        raise EngineeringError("NPI_EVIDENCE_WRITE_FAILED") from exc


def _run_worker(
    *, project_root: Path, mode: str, configuration: Mapping[str, object]
) -> tuple[dict[str, Any], dict[str, Any]]:
    envelope = worker_dispatch.issue(configuration, mode)
    command = [Path(sys.executable).name, "-c", _WORKER_CALL, "--mode", mode]
    try:
        completed = subprocess.run(
            [sys.executable, "-c", _WORKER_CALL, "--mode", mode],
            cwd=str(project_root),
            input=canonical(envelope),
            capture_output=True,
            check=False,
            timeout=24 * 60 * 60,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EngineeringError("NPI_RUNNER_PROCESS_UNAVAILABLE") from exc
    record = {
        "name": f"n2b2_{mode}",
        "command": command,
        "tool_version": platform.python_version(),
        "exit_code": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "stdout_sha256": sha256(completed.stdout),
        "stderr_sha256": sha256(completed.stderr),
    }
    require(completed.returncode == 0, "NPI_RUNNER_PROCESS_FAILED")
    payload = strict_json(completed.stdout)
    require(isinstance(payload, Mapping), "NPI_RUNNER_EVIDENCE_INVALID")
    return cast(dict[str, Any], payload), record


def _combine_counters(*values: object) -> dict[str, int]:
    total: dict[str, int] = {}
    for value in values:
        require(isinstance(value, Mapping), "NPI_COUNTER_EVIDENCE_INVALID")
        counters = cast(Mapping[str, object], value)
        require(
            REQUIRED_FORBIDDEN_COUNTERS.issubset(counters),
            "NPI_COUNTER_EVIDENCE_INVALID",
        )
        for name, count in counters.items():
            require(
                isinstance(name, str) and _COUNTER_LABEL.fullmatch(name) is not None,
                "NPI_COUNTER_EVIDENCE_INVALID",
            )
            require(type(count) is int and count >= 0, "NPI_COUNTER_EVIDENCE_INVALID")
            total[name] = total.get(name, 0) + cast(int, count)
    require(REQUIRED_FORBIDDEN_COUNTERS.issubset(total), "NPI_COUNTER_EVIDENCE_INVALID")
    return total


def _hash_artifacts(paths: Mapping[str, Path]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, path in paths.items():
        _, data = _regular_file(path)
        result[name] = sha256(data)
    return result


def _validate_supplemental(value: Mapping[str, Any]) -> None:
    commands = value.get("commands")
    require(
        isinstance(commands, Sequence)
        and not isinstance(commands, (str, bytes))
        and len(commands) == 2
        and all(isinstance(item, Mapping) for item in commands),
        "NPI_COMMAND_EVIDENCE_INVALID",
    )
    required = {
        "name",
        "command",
        "tool_version",
        "exit_code",
        "status",
        "stdout_sha256",
        "stderr_sha256",
    }
    command_items = cast(Sequence[Mapping[str, Any]], commands)
    for item in command_items:
        require(set(item) == required, "NPI_COMMAND_EVIDENCE_INVALID")
        require(
            isinstance(item["command"], list)
            and bool(item["command"])
            and all(isinstance(arg, str) and arg for arg in item["command"])
            and isinstance(item["tool_version"], str)
            and bool(item["tool_version"])
            and type(item["exit_code"]) is int
            and item["exit_code"] == 0
            and item["status"] == "PASS"
            and is_digest(item["stdout_sha256"])
            and is_digest(item["stderr_sha256"]),
            "NPI_COMMAND_EVIDENCE_INVALID",
        )


def _default_execute(
    *,
    project_root: Path,
    runtime: N2B1PRuntimeConfiguration,
    source: Mapping[str, Any],
    inputs: Mapping[str, Path],
    outputs: Mapping[str, Path],
    quality_records: Sequence[Mapping[str, Any]],
    file_fingerprints: Mapping[Path, tuple[int, int, int, int, str]],
    identity_observations: list[dict[str, object]],
    prior_review: Path,
    ledger_root: Path,
    receipt_sha256: str,
    bindings_sha256: str,
) -> Execute:
    def execute() -> Mapping[str, Any]:
        _assert_file_fingerprint(file_fingerprints)
        before = {
            name: snapshot_tree(path).entries
            for name, path in {
                "old_s3": inputs["old_s3"],
                "old_s20": inputs["old_s20"],
                "s3_manifest": inputs["s3_manifest"],
                "s20_manifest": inputs["s20_manifest"],
                "baseline_manifest": inputs["baseline_manifest"],
            }.items()
        }
        configuration = {
            "project_root": str(project_root),
            "cache_root": str(runtime.cache_root),
            "s3_manifest_dir": str(inputs["s3_manifest"]),
            "s20_manifest_dir": str(inputs["s20_manifest"]),
            "baseline_manifest_dir": str(inputs["baseline_manifest"]),
            "s3_out": str(outputs["s3_out"]),
            "s20_out": str(outputs["s20_out"]),
            "prior_s20_review_record": str(prior_review),
            "reviewed_commit": str(source["candidate_commit"]),
            "candidate_tree": str(source["candidate_tree"]),
            "source_manifest_sha256": str(source["source_manifest_sha256"]),
            "s3_manifest_sha256": sha256(
                (inputs["s3_manifest"] / "fixture_manifest.json").read_bytes()
            ),
            "s20_manifest_sha256": sha256(
                (inputs["s20_manifest"] / "fixture_manifest.json").read_bytes()
            ),
            "runtime_identity_sha256": sha256(canonical(identity_observations[0]["identity"])),
            "ledger_root": str(ledger_root),
            "reservation_dir": str(ledger_root / receipt_sha256),
            "receipt_sha256": receipt_sha256,
            "bindings_sha256": bindings_sha256,
        }
        fresh_payload, fresh_command = _run_worker(
            project_root=project_root, mode="fresh", configuration=configuration
        )
        fresh_observations = fresh_payload.get("identity_observations")
        require(
            isinstance(fresh_observations, Sequence)
            and not isinstance(fresh_observations, (str, bytes))
            and len(fresh_observations) == 2
            and all(isinstance(item, Mapping) for item in fresh_observations),
            "NPI_IDENTITY_OBSERVATIONS_INCOMPLETE",
        )
        identity_observations.extend(cast(Sequence[dict[str, object]], fresh_observations))

        resume_payload, resume_command = _run_worker(
            project_root=project_root, mode="resume", configuration=configuration
        )
        resume_observations = resume_payload.get("identity_observations")
        require(
            isinstance(resume_observations, Sequence)
            and not isinstance(resume_observations, (str, bytes))
            and len(resume_observations) == 2
            and all(isinstance(item, Mapping) for item in resume_observations),
            "NPI_IDENTITY_OBSERVATIONS_INCOMPLETE",
        )
        identity_observations.extend(cast(Sequence[dict[str, object]], resume_observations))

        after = {
            name: snapshot_tree(path).entries
            for name, path in {
                "old_s3": inputs["old_s3"],
                "old_s20": inputs["old_s20"],
                "s3_manifest": inputs["s3_manifest"],
                "s20_manifest": inputs["s20_manifest"],
                "baseline_manifest": inputs["baseline_manifest"],
            }.items()
        }
        require(before == after, "NPI_PROTECTED_EVIDENCE_CHANGED")
        resume_value = resume_payload.get("resume")
        require(isinstance(resume_value, Mapping), "NPI_RESUME_EVIDENCE_INVALID")
        resume = cast(Mapping[str, Any], resume_value)
        resume_evidence = {
            "exit_code": resume_command["exit_code"],
            "resume_status": resume.get("resume_status"),
            "before": resume_payload.get("before"),
            "after": resume_payload.get("after"),
            "model_load_count": resume.get("model_load_count"),
        }
        artifacts = _hash_artifacts(
            {
                "s3_summary": outputs["s3_out"] / "validation_summary.json",
                "s20_summary": outputs["s20_out"] / "validation_summary.json",
                "s20_checkpoint": outputs["s20_out"] / "checkpoint.json",
                "s20_runtime_metrics": outputs["s20_out"] / "runtime_metrics.json",
                "s20_checksums": outputs["s20_out"] / "CHECKSUMS.sha256",
            }
        )
        counters = _combine_counters(
            fresh_payload.get("s3_hard_counts"),
            fresh_payload.get("s20_hard_counts"),
        )
        commands = [fresh_command, resume_command]
        supplemental = {
            "commands": commands,
            "runner_python": platform.python_version(),
            "counter_evidence": "DECLARED_BY_EXISTING_RUNNERS_NOT_INDEPENDENT_OS_TELEMETRY",
            "protected_evidence_unchanged": True,
        }
        _validate_supplemental(supplemental)
        runner_evidence = {
            "schema_version": "npi-controlled-runner-evidence-v1",
            "commands": commands,
            "identity_observations": list(identity_observations),
            "resume": resume_evidence,
            "artifacts": artifacts,
            "forbidden_counters": counters,
        }
        runner_path = outputs["evidence_out"] / "runner_execution_evidence.json"
        _write_exclusive_json(runner_path, runner_evidence)
        artifacts["runner_evidence"] = _file_fingerprint(runner_path)[4]
        return {
            "quality_records": list(quality_records),
            "identity_observations": list(identity_observations),
            "resume": resume_evidence,
            "artifacts": artifacts,
            "forbidden_counters": counters,
            "supplemental_evidence": supplemental,
        }

    return execute


def run_controlled_runtime_revalidation(
    *,
    project_root: Path,
    review_artifact: Path,
    execution_lease: Path,
    quality_evidence: Path,
    prior_s20_review_record: Path,
    old_s3_runtime: Path,
    old_s20_runtime: Path,
    s3_manifest_dir: Path,
    s20_manifest_dir: Path,
    baseline_manifest_dir: Path,
    s3_out: Path,
    s20_out: Path,
    evidence_out: Path,
    identity_probe: IdentityProbe | None = None,
    execute: Execute | None = None,
    runtime: N2B1PRuntimeConfiguration | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run one source-bound controlled revalidation; no lease means no runner."""

    root = Path(project_root)
    checked_path(root, must_exist=True)
    runtime_configuration = runtime or load_n2b1p_runtime_configuration(root)
    runtime_parent = _checked_dir(runtime_configuration.runtime_parent)
    cache_root = _checked_dir(runtime_configuration.cache_root)
    ledger_root = runtime_parent / _LEDGER_DIR

    inputs = {
        "old_s3": _checked_dir(old_s3_runtime),
        "old_s20": _checked_dir(old_s20_runtime),
        "s3_manifest": _checked_dir(s3_manifest_dir),
        "s20_manifest": _checked_dir(s20_manifest_dir),
        "baseline_manifest": _checked_dir(baseline_manifest_dir),
    }
    outputs = {
        "s3_out": Path(s3_out),
        "s20_out": Path(s20_out),
        "evidence_out": Path(evidence_out),
    }
    for path in outputs.values():
        checked_path(path, must_exist=False)
    require(
        all(not overlaps(root, path) for path in [*inputs.values(), cache_root]),
        "NPI_PROJECT_ROOT_BOUNDARY",
    )
    require(not overlaps(root, ledger_root), "NPI_PROJECT_ROOT_BOUNDARY")

    protected: dict[str, Path] = {"project_root": root, "ledger_root": ledger_root}
    _add_protected(protected, "cache_root", cache_root)
    owner_anchor_root = runtime_parent / _OWNER_LEASE_ANCHOR_DIR
    _add_protected(protected, "owner_anchor_root", owner_anchor_root)
    for label, path in (
        ("review_root", Path(review_artifact).parent),
        ("lease_root", Path(execution_lease).parent),
        ("quality_root", Path(quality_evidence).parent),
        ("prior_review_root", Path(prior_s20_review_record).parent),
    ):
        _add_protected(protected, label, path)
    _checked_dir(ledger_root.parent)
    _check_disjoint(inputs, protected, outputs)

    review_path, review_bytes = _regular_file(Path(review_artifact))
    lease_path, lease_bytes = _regular_file(Path(execution_lease))
    owner_anchor = _load_owner_lease_anchor(root, runtime_parent)
    execution_lease_sha256 = owner_anchor.execution_lease_sha256
    require(
        sha256(lease_bytes) == execution_lease_sha256,
        "NPI_OWNER_LEASE_ANCHOR_MISMATCH",
    )
    quality_path = Path(quality_evidence)
    quality_records, _, quality_bytes = _load_quality(quality_path)
    prior_path, prior_bytes = _regular_file(Path(prior_s20_review_record))
    prior_payload = strict_json(prior_bytes)
    require(isinstance(prior_payload, Mapping), "NPI_PRIOR_REVIEW_INVALID")
    reviewed_commit = prior_payload.get("reviewed_commit")
    require(
        isinstance(reviewed_commit, str) and len(reviewed_commit) == 40, "NPI_PRIOR_REVIEW_INVALID"
    )
    require(bool(review_bytes), "NPI_REVIEW_ARTIFACT_EMPTY")
    from .legacy_s20_binding import validate_legacy_s20_binding

    # Reject stale or mismatched historical inputs before ledger creation or S3.
    validate_legacy_s20_binding(root, prior_path, inputs["s20_manifest"] / "fixture_manifest.json")
    task_receipt_path = root / _TASK_RECEIPT
    task_receipt_schema_path = root / _TASK_RECEIPT_SCHEMA
    task_receipt = _load_task_specific_receipt(root)
    old_identity_path = inputs["old_s20"] / "ollama_identity.json"
    _, old_identity_bytes = _regular_file(old_identity_path)
    old_identity_payload = strict_json(old_identity_bytes)
    require(isinstance(old_identity_payload, Mapping), "NPI_OLD_IDENTITY_INVALID")
    old_identity = cast(Mapping[str, object], old_identity_payload)

    state_path, state_bytes = _regular_file(root / "PROJECT_STATE.json")
    state_payload = strict_json(state_bytes)
    state_object = (
        cast(Mapping[str, Any], state_payload) if isinstance(state_payload, Mapping) else {}
    )
    phase_status = state_object.get("phase_status")
    require(
        isinstance(phase_status, Mapping) and phase_status.get("N2B2") == "LOCKED",
        "NPI_PROJECT_STATE_BOUNDARY_VIOLATION",
    )
    source = full_source_identity(root)
    manifest_paths = {
        "s3_manifest_sha256": inputs["s3_manifest"] / "fixture_manifest.json",
        "s20_manifest_sha256": inputs["s20_manifest"] / "fixture_manifest.json",
    }
    manifest_bytes = {name: _regular_file(path)[1] for name, path in manifest_paths.items()}
    path_digest = path_plan_digest(inputs=inputs, outputs=outputs, protected=protected)
    source_bindings = {
        "candidate_commit": cast(str, source["candidate_commit"]),
        "candidate_tree": cast(str, source["candidate_tree"]),
        "source_manifest_sha256": cast(str, source["source_manifest_sha256"]),
        "project_state_sha256": sha256(state_bytes),
        "runtime_identity_sha256": "",
        "s3_manifest_sha256": sha256(manifest_bytes["s3_manifest_sha256"]),
        "s20_manifest_sha256": sha256(manifest_bytes["s20_manifest_sha256"]),
        "model_cache_binding_sha256": runtime_configuration.cache_root_identity,
        "path_plan_sha256": path_digest,
    }
    lease_payload = cast(Mapping[str, Any], strict_json(lease_bytes))
    _validate_lease_schema(root, lease_payload)
    lease_bindings_value = lease_payload.get("bindings")
    require(isinstance(lease_bindings_value, Mapping), "NPI_LEASE_BINDING_INVALID")
    lease_bindings = cast(Mapping[str, Any], lease_bindings_value)
    runtime_identity_value = lease_bindings.get("runtime_identity_sha256")
    require(isinstance(runtime_identity_value, str), "NPI_LEASE_BINDING_INVALID")
    runtime_identity_sha = cast(str, runtime_identity_value)
    source_bindings["runtime_identity_sha256"] = runtime_identity_sha
    timestamp = now or datetime.now(UTC)
    validate_lease(
        lease_bytes,
        trusted_receipt_sha256=execution_lease_sha256,
        observed_bindings=source_bindings,
        now=timestamp,
    )

    if ledger_root.exists():
        _checked_dir(ledger_root)
    else:
        try:
            ledger_root.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise EngineeringError("NPI_LEDGER_ROOT_UNAVAILABLE") from exc
        _checked_dir(ledger_root)

    checked_paths = validate_plan(inputs=inputs, outputs=outputs, protected=protected)
    _check_disjoint(inputs, protected, outputs)
    file_fingerprints = {
        path: _file_fingerprint(path)
        for path in (
            review_path,
            lease_path,
            quality_path,
            prior_path,
            state_path,
            old_identity_path,
            task_receipt_path,
            task_receipt_schema_path,
            owner_anchor.path,
            *manifest_paths.values(),
        )
    }
    plan = ControlledExecutionPlan(
        project_root=root,
        ledger_root=ledger_root,
        lease=lease_bytes,
        trusted_receipt_sha256=execution_lease_sha256,
        inputs=inputs,
        outputs=outputs,
        protected=protected,
        observed_bindings=source_bindings,
    )
    observations: list[dict[str, object]] = []
    client: Any = None

    def default_probe() -> Mapping[str, object]:
        nonlocal client
        if client is None:
            from .ollama_client import OllamaClient

            client = OllamaClient()
        observed = _identity_record(client.verify_identity())
        return observed

    probe = identity_probe or default_probe
    runner = execute or _default_execute(
        project_root=root,
        runtime=runtime_configuration,
        source=source,
        inputs=inputs,
        outputs=outputs,
        quality_records=quality_records,
        file_fingerprints=file_fingerprints,
        identity_observations=observations,
        prior_review=prior_path,
        ledger_root=ledger_root,
        receipt_sha256=execution_lease_sha256,
        bindings_sha256=sha256(canonical(source_bindings)),
    )

    def guarded_execute() -> Mapping[str, Any]:
        _assert_file_fingerprint(file_fingerprints)
        result = runner()
        require(isinstance(result, Mapping), "NPI_CALLBACK_RESULT_INVALID")
        return result

    def post_execute_check() -> None:
        _assert_file_fingerprint(file_fingerprints)
        recheck({name: item for name, item in checked_paths.items() if item.existed})

    def guarded_probe() -> Mapping[str, object]:
        observed = probe()
        _assert_file_fingerprint(file_fingerprints)
        _validate_task_specific_receipt(
            receipt=task_receipt,
            review_bytes=review_bytes,
            state_bytes=state_bytes,
            old_identity=old_identity,
            current_identity=observed,
        )
        observations.append(_observation("preflight", observed))
        return observed

    def sink(evidence: Mapping[str, Any]) -> None:
        _write_exclusive_json(
            outputs["evidence_out"] / "controlled_execution_evidence.json", evidence
        )

    result = run_controlled_execution(
        plan,
        now=timestamp,
        identity_probe=guarded_probe,
        execute=guarded_execute,
        evidence_sink=sink,
        post_execute_check=post_execute_check,
    )
    return {
        **result,
        "quality_evidence_sha256": sha256(quality_bytes),
        "review_artifact_sha256": sha256(review_bytes),
        "execution_lease_sha256": execution_lease_sha256,
    }
