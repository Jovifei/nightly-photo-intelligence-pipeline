#!/usr/bin/env python3
"""Validate whether the current B-source control packet is eligible for review.

This read-only check covers Git lineage, tracked manifests, schemas, and packet
authority bindings. It does not validate cache/runtime readiness or execute the
full handoff verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = str(ROOT / "src")
if SOURCE_ROOT not in sys.path:
    sys.path.insert(0, SOURCE_ROOT)
from nightly_photo_intelligence_pipeline.git_governance import (  # noqa: E402
    linear_history_findings,
)
from nightly_photo_intelligence_pipeline.json_strict import loads_json_strict  # noqa: E402
from nightly_photo_intelligence_pipeline.n2b1p_integrity import (  # noqa: E402
    canonical_json_bytes,
    sha256_bytes,
)

TASK_PATH = "tasks/phase_n2b1p_b_source_network_reacquisition_v1.yaml"
BASELINE_APPROVAL_PATH = "approvals/phase_completion_N2B1P.yaml"
BASELINE_SCHEMA_PATH = "schemas/phase_completion_n2b1p_v1_0.schema.json"
PROJECT_STATE_PATH = "PROJECT_STATE.json"
PROJECT_STATE_SCHEMA_PATH = "schemas/project_state_v1_7.schema.json"
# The completion record was written after the approved candidate commit. Pin
# its raw bytes so the self-declared immutable flag is not its only trust anchor.
BASELINE_APPROVAL_SHA256 = "d57215a5ba8357eaddc58d398d0d3f8d840e4b4b172a19c8aa3f8847bea2aa65"
TASK_ID = "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
CAPABILITY = "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
REVIEW_SCOPE = "B_SOURCE_NETWORK_REACQUISITION_V1_CONTROL_PACKET_ONLY"
CONTROL_PACKET_CLASS = "CONTROL_PLANE_ONLY"
KNOWN_CHANGE_CATEGORIES = frozenset(
    {
        "task_contract",
        "owner_approval",
        "schema",
        "tests",
        "governance_tool",
        "control_plane_code",
        "manifest",
        "todo_status",
        "task_tracking",
    }
)
SHA1_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ReviewEligibilityError(ValueError):
    """Raised when the exact current tree is not eligible for external review."""


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ReviewEligibilityError("duplicate YAML member")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git command failed"
        raise ReviewEligibilityError(f"git {args[0]} failed: {detail}")
    return result.stdout.strip()


def _safe_file(root: Path, relative: object) -> Path:
    if not isinstance(relative, str):
        raise ReviewEligibilityError("packet file reference must be a repository-relative path")
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise ReviewEligibilityError(f"unsafe repository file reference: {relative!r}")
    candidate = root.joinpath(*rel.parts)
    if candidate.is_symlink():
        raise ReviewEligibilityError(f"packet file must not be a symlink: {relative}")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as exc:
        raise ReviewEligibilityError(
            f"packet file is missing or outside the repository: {relative}"
        ) from exc
    if not resolved.is_file():
        raise ReviewEligibilityError(f"packet reference is not a regular file: {relative}")
    return resolved


def _load_yaml(root: Path, relative: object) -> dict[str, Any]:
    path = _safe_file(root, relative)
    try:
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeySafeLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise ReviewEligibilityError(f"invalid YAML document: {relative}") from exc
    if not isinstance(value, dict):
        raise ReviewEligibilityError(f"YAML document must contain an object: {relative}")
    return value


def _load_json(root: Path, relative: object) -> dict[str, Any]:
    path = _safe_file(root, relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReviewEligibilityError(f"invalid JSON document: {relative}") from exc
    if not isinstance(value, dict):
        raise ReviewEligibilityError(f"JSON document must contain an object: {relative}")
    return value


def _load_json_strict(root: Path, relative: str) -> dict[str, Any]:
    path = _safe_file(root, relative)
    try:
        value = loads_json_strict(path.read_bytes())
    except Exception as exc:
        raise ReviewEligibilityError(f"invalid strict JSON document: {relative}") from exc
    if not isinstance(value, dict):
        raise ReviewEligibilityError(f"JSON document must contain an object: {relative}")
    return value


def _validate_document(document: object, schema: dict[str, Any], label: str) -> None:
    try:
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
            key=lambda error: list(error.absolute_path),
        )
    except Exception as exc:  # jsonschema exposes several schema error classes
        raise ReviewEligibilityError(
            f"invalid JSON Schema for {label}: {type(exc).__name__}"
        ) from exc
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise ReviewEligibilityError(
            f"{label} schema validation failed at {location}: {first.message}"
        )


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_manifest(path: Path) -> dict[str, str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ReviewEligibilityError(f"manifest is unavailable: {path.name}") from exc
    result: dict[str, str] = {}
    for line in lines:
        if not line:
            continue
        if "  " not in line:
            raise ReviewEligibilityError(f"malformed manifest row in {path.name}")
        digest, relative = line.split("  ", 1)
        if not SHA256_PATTERN.fullmatch(digest) or not relative or relative in result:
            raise ReviewEligibilityError(f"invalid or duplicate manifest row in {path.name}")
        result[relative] = digest
    return result


def _tracked_regular_files(root: Path) -> set[str]:
    staged = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--stage", "-z"],
        check=False,
        capture_output=True,
    )
    if staged.returncode != 0:
        raise ReviewEligibilityError("cannot enumerate tracked files")
    tracked: set[str] = set()
    for entry in staged.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_path = entry.split(b"\t", 1)
            mode, _object_id, stage = metadata.decode("ascii").split()
            relative = raw_path.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ReviewEligibilityError("invalid Git index entry") from exc
        if stage != "0" or mode not in {"100644", "100755"}:
            raise ReviewEligibilityError(f"tracked path is not a regular stage-0 file: {relative}")
        tracked.add(relative)
    return tracked


def _verify_one_manifest(root: Path, manifest_path: str, expected_paths: set[str]) -> None:
    manifest = _read_manifest(_safe_file(root, manifest_path))
    if set(manifest) != expected_paths:
        raise ReviewEligibilityError(f"{manifest_path} does not bind the exact tracked file set")
    mismatches: list[str] = []
    for relative, expected_sha256 in manifest.items():
        path = _safe_file(root, relative)
        if _sha256_bytes(path.read_bytes()) != expected_sha256:
            mismatches.append(relative)
    if mismatches:
        raise ReviewEligibilityError(
            f"{manifest_path} hash mismatch: {', '.join(sorted(mismatches))}"
        )


def _verify_manifests(root: Path) -> None:
    tracked = _tracked_regular_files(root)
    root_manifest = "MANIFEST.sha256"
    overlay_manifest = "review_tools/MANIFEST.sha256"
    if root_manifest not in tracked or overlay_manifest not in tracked:
        raise ReviewEligibilityError("root and review_tools manifests must both be tracked")
    _verify_one_manifest(root, root_manifest, tracked - {root_manifest})
    overlay_paths = {path for path in tracked if path.startswith("review_tools/")}
    _verify_one_manifest(root, overlay_manifest, overlay_paths - {overlay_manifest})


def _verify_linear_history(root: Path, baseline_commit: str) -> tuple[str, str]:
    if not SHA1_PATTERN.fullmatch(baseline_commit):
        raise ReviewEligibilityError("immutable N2B1P baseline commit is not a full Git SHA")
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}")
    tree = _git(root, "rev-parse", f"{head}^{{tree}}")
    findings = linear_history_findings(root, baseline_commit, head)
    if findings:
        raise ReviewEligibilityError(findings[0])
    return head, tree


def _change_category(relative: str) -> str | None:
    if relative in {"MANIFEST.sha256", "review_tools/MANIFEST.sha256"}:
        return "manifest"
    if relative == TASK_PATH:
        return "task_contract"
    if relative in {OWNER_PATH, RUNTIME_PATH}:
        return "owner_approval"
    if relative.startswith("schemas/"):
        return "schema"
    if relative.startswith("tests/"):
        return "tests"
    if relative == "tasks/todo.md":
        return "todo_status"
    if relative in {"tasks/index.json", "tasks/lessons.md"}:
        return "task_tracking"
    if relative.startswith("review_tools/") or relative in {
        "tools/verify_review_candidate.py",
        "tools/verify_handoff.py",
        "src/nightly_photo_intelligence_pipeline/git_governance.py",
        "src/nightly_photo_intelligence_pipeline/preflight.py",
    }:
        return "governance_tool"
    if relative in {
        "src/nightly_photo_intelligence_pipeline/n2b1p_b_source_network.py",
        "src/nightly_photo_intelligence_pipeline/cli.py",
    }:
        return "control_plane_code"
    return None


def _verify_review_change_scope(
    root: Path, baseline_commit: str, metadata: Mapping[str, object]
) -> None:
    declared = metadata.get("allowed_change_categories")
    if not isinstance(declared, list) or set(declared) != KNOWN_CHANGE_CATEGORIES:
        raise ReviewEligibilityError("review change categories are not the closed approved set")
    introductions = [
        item
        for item in _git(root, "log", "--diff-filter=A", "--format=%H", "--", TASK_PATH).splitlines()
        if item
    ]
    if len(introductions) != 1:
        raise ReviewEligibilityError("active review task must have exactly one introduction commit")
    introduction = introductions[0]
    if linear_history_findings(root, baseline_commit, introduction):
        raise ReviewEligibilityError("task introduction is outside immutable linear ancestry")
    parent = _git(root, "rev-parse", f"{introduction}^")
    rows = _git(root, "diff", "--name-status", "--find-renames", f"{parent}..HEAD").splitlines()
    if not rows:
        raise ReviewEligibilityError("review candidate range has no changes")
    for row in rows:
        parts = row.split("\t")
        if len(parts) != 2 or parts[0] not in {"A", "M"}:
            raise ReviewEligibilityError("review candidate contains a delete or rename")
        relative = parts[1]
        category = _change_category(relative)
        if category is None or category not in declared:
            raise ReviewEligibilityError(
                f"review change path is outside the declared control-packet scope: {relative}"
            )


def _verify_project_state(root: Path, baseline: dict[str, Any]) -> None:
    state_path = _safe_file(root, PROJECT_STATE_PATH)
    try:
        state_bytes = state_path.read_bytes()
        state = loads_json_strict(state_bytes)
    except Exception as exc:
        raise ReviewEligibilityError("invalid strict JSON document: PROJECT_STATE.json") from exc
    if not isinstance(state, dict):
        raise ReviewEligibilityError("PROJECT_STATE.json must contain an object")
    state_schema = _load_json(root, PROJECT_STATE_SCHEMA_PATH)
    _validate_document(state, state_schema, "PROJECT_STATE")

    expected_sha256 = baseline.get("project_state_sha256")
    if (
        not isinstance(expected_sha256, str)
        or not SHA256_PATTERN.fullmatch(expected_sha256)
        or _sha256_bytes(state_bytes) != expected_sha256
    ):
        raise ReviewEligibilityError(
            "PROJECT_STATE SHA-256 differs from the N2B1P approval baseline"
        )

    authorization = state.get("authorization")
    active_execution = (
        authorization.get("active_execution") if isinstance(authorization, dict) else None
    )
    capability_gates = (
        authorization.get("capability_gates") if isinstance(authorization, dict) else None
    )
    data_scope = state.get("data_scope")
    phase_status = state.get("phase_status")
    if (
        not isinstance(active_execution, dict)
        or active_execution.get("phase") != "N2B1P"
        or active_execution.get("capability") != "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION"
        or active_execution.get("source_photo_content_read") != "NOT_AUTHORIZED"
        or active_execution.get("source_photo_exif_read") != "NOT_AUTHORIZED"
        or active_execution.get("sqlite_ingest_write") != "NOT_AUTHORIZED"
        or not isinstance(authorization, dict)
        or authorization.get("network_access") != "DENY_BY_DEFAULT"
        or authorization.get("git_remote_write") != "NOT_AUTHORIZED"
        or authorization.get("real_model_execution") != "NOT_AUTHORIZED"
        or not isinstance(capability_gates, dict)
        or capability_gates.get("N2B2_REAL_BENCHMARK") != "LOCKED"
        or not isinstance(data_scope, dict)
        or data_scope.get("N2B2_REAL_BENCHMARK") != "LOCKED"
        or not isinstance(phase_status, dict)
        or phase_status.get("N2B2") != "LOCKED"
    ):
        raise ReviewEligibilityError("PROJECT_STATE contains a changed N2B1P or N2B2 lock")


def _verify_packet(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    task = _load_yaml(root, TASK_PATH)
    metadata = task.get("review_candidate")
    if not isinstance(metadata, dict):
        raise ReviewEligibilityError("active task has no review_candidate metadata")
    fixed_metadata = {
        "status": "REVIEW_CANDIDATE",
        "task_id": TASK_ID,
        "review_scope": REVIEW_SCOPE,
        "class": CONTROL_PACKET_CLASS,
        "baseline_approval_ref": BASELINE_APPROVAL_PATH,
        "immutable_baseline_ref": BASELINE_APPROVAL_PATH,
        "external_exact_sha_review_required": True,
        "execution_before_review": False,
    }
    for key, expected in fixed_metadata.items():
        if metadata.get(key) != expected:
            raise ReviewEligibilityError(
                f"review_candidate.{key} is not bound to the approved scope"
            )
    categories = metadata.get("allowed_change_categories")
    if (
        not isinstance(categories, list)
        or not categories
        or not all(isinstance(item, str) and item for item in categories)
        or len(categories) != len(KNOWN_CHANGE_CATEGORIES)
        or set(categories) != KNOWN_CHANGE_CATEGORIES
    ):
        raise ReviewEligibilityError("review_candidate allowed change categories are invalid")
    phase = task.get("phase")
    if not isinstance(phase, dict) or phase.get("id") != "N2B1P":
        raise ReviewEligibilityError("active task is not bound to phase N2B1P")
    if task.get("capability") != CAPABILITY:
        raise ReviewEligibilityError("active task capability does not match the review candidate")

    task_schema = _load_json(root, metadata.get("task_schema_ref"))
    _validate_document(task, task_schema, "active task")
    owner_path = metadata.get("owner_approval_ref")
    if owner_path != task.get("approval_ref"):
        raise ReviewEligibilityError("owner approval reference does not match the active task")
    owner = _load_yaml(root, owner_path)
    owner_schema = _load_json(root, metadata.get("owner_approval_schema_ref"))
    _validate_document(owner, owner_schema, "owner approval")

    runtime_path = metadata.get("runtime_configuration_ref")
    task_runtime = task.get("runtime_configuration")
    if not isinstance(task_runtime, dict) or task_runtime.get("path") != runtime_path:
        raise ReviewEligibilityError("runtime configuration reference does not match the task")
    runtime = _load_json(root, runtime_path)
    runtime_schema = _load_json(root, metadata.get("runtime_configuration_schema_ref"))
    _validate_document(runtime, runtime_schema, "runtime configuration")
    digest = runtime.get("configuration_digest")
    if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
        raise ReviewEligibilityError("runtime configuration digest is invalid")
    runtime_payload = {
        key: value for key, value in runtime.items() if key != "configuration_digest"
    }
    if sha256_bytes(canonical_json_bytes(runtime_payload)) != digest:
        raise ReviewEligibilityError("runtime configuration digest does not match its content")
    if task_runtime.get("configuration_digest") != digest:
        raise ReviewEligibilityError("runtime configuration digest is not bound by the task")
    if owner.get("runtime_configuration_ref") != runtime_path:
        raise ReviewEligibilityError("owner approval runtime reference does not match the task")
    if owner.get("runtime_configuration_digest") != digest:
        raise ReviewEligibilityError("owner approval runtime digest does not match the task")
    if owner.get("contract_ref") != TASK_PATH:
        raise ReviewEligibilityError(
            "owner approval contract reference does not match the active task"
        )

    if task.get("status") != "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW":
        raise ReviewEligibilityError("active task is not a locked pre-execution review packet")
    if owner.get("status") != "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW":
        raise ReviewEligibilityError("owner approval is not awaiting the required external review")
    if task.get("owner_authorized") is not True or owner.get("owner_authorized") is not True:
        raise ReviewEligibilityError("owner authorization record is missing")
    if task.get("execution_status") != "NOT_RUN" or owner.get("execution_status") != "NOT_RUN":
        raise ReviewEligibilityError("packet execution status is not NOT_RUN")
    if task.get("execution_authority") != "NOT_AUTHORIZED":
        raise ReviewEligibilityError("active task grants execution authority")
    if owner.get("execution_authority") != "NOT_AUTHORIZED":
        raise ReviewEligibilityError("owner approval grants execution authority")
    if runtime.get("execution_authority") != "NOT_AUTHORIZED":
        raise ReviewEligibilityError("runtime configuration grants execution authority")
    if owner.get("network_access") != "DENY":
        raise ReviewEligibilityError("owner approval network access is not denied")
    if runtime.get("network_access") != "DENY":
        raise ReviewEligibilityError("runtime network access is not denied")
    network_policy = task.get("network_policy")
    if not isinstance(network_policy, dict) or network_policy.get("access") != "DENY":
        raise ReviewEligibilityError("task network access is not denied")
    if task.get("network_download_before_external_review") is not False:
        raise ReviewEligibilityError("task allows download before external review")
    if runtime.get("download_before_external_review") is not False:
        raise ReviewEligibilityError("runtime allows download before external review")

    baseline_path = metadata.get("baseline_approval_ref")
    baseline_file = _safe_file(root, baseline_path)
    if _sha256_bytes(baseline_file.read_bytes()) != BASELINE_APPROVAL_SHA256:
        raise ReviewEligibilityError("N2B1P baseline approval digest is not trusted")
    baseline_approval = _load_yaml(root, baseline_path)
    baseline_schema = _load_json(root, BASELINE_SCHEMA_PATH)
    _validate_document(baseline_approval, baseline_schema, "immutable N2B1P baseline approval")
    if (
        baseline_approval.get("status") != "APPROVED"
        or baseline_approval.get("phase_id") != "N2B1P"
    ):
        raise ReviewEligibilityError("N2B1P baseline approval is not an approved N2B1P record")
    baseline = baseline_approval.get("baseline")
    if not isinstance(baseline, dict) or baseline.get("immutable") is not True:
        raise ReviewEligibilityError("N2B1P baseline is not marked immutable")
    baseline_commit = baseline.get("candidate_commit")
    if not isinstance(baseline_commit, str) or not SHA1_PATTERN.fullmatch(baseline_commit):
        raise ReviewEligibilityError("N2B1P immutable baseline commit is invalid")
    _verify_project_state(root, baseline)
    return task, owner, runtime, baseline_commit


def validate_review_candidate(root: Path = ROOT) -> None:
    """Raise ReviewEligibilityError unless HEAD is a clean, reviewable packet."""

    resolved_root = root.resolve(strict=True)
    if not (resolved_root / ".git").exists():
        raise ReviewEligibilityError("candidate root is not a Git working tree")
    status = _git(resolved_root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise ReviewEligibilityError("working tree must be clean for exact-SHA review")
    task, _owner, _runtime, baseline_commit = _verify_packet(resolved_root)
    head, _tree = _verify_linear_history(resolved_root, baseline_commit)
    metadata = task.get("review_candidate")
    if not isinstance(metadata, Mapping):
        raise ReviewEligibilityError("review candidate metadata is missing")
    _verify_review_change_scope(resolved_root, baseline_commit, metadata)
    _verify_manifests(resolved_root)
    check = subprocess.run(
        ["git", "-C", str(resolved_root), "diff", "--check", f"{baseline_commit}...{head}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check.returncode != 0 or check.stdout.strip() or check.stderr.strip():
        detail = check.stdout.strip() or check.stderr.strip() or "whitespace check failed"
        raise ReviewEligibilityError(f"diff --check failed: {detail}")
    if _git(resolved_root, "rev-parse", "HEAD") != head:
        raise ReviewEligibilityError("HEAD changed during review-eligibility validation")
    if _git(resolved_root, "status", "--porcelain", "--untracked-files=all"):
        raise ReviewEligibilityError("working tree changed during review-eligibility validation")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="candidate Git worktree")
    args = parser.parse_args(argv)
    try:
        validate_review_candidate(args.root)
    except ReviewEligibilityError as exc:
        print(f"REVIEW_ELIGIBILITY=FAIL: {exc}", file=sys.stderr)
        return 1
    print("REVIEW_ELIGIBILITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
