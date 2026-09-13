"""Fail-closed authorization primitives for one Owner-approved runtime revalidation."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import time
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

TASK = "N2B2_OLLAMA_RUNTIME_IDENTITY_REVALIDATION_20260906"
BASE_CANDIDATE = "d83f96271f754763d61cedcc314fc725c840c86f"
REVIEW_VERDICT = "INCONCLUSIVE"
REVIEW_BLOCKER = "N2B2_S20_RESUME_BINDING_MISMATCH: model_identity"
OLD_OLLAMA_VERSION = "0.32.15"
NEW_OLLAMA_VERSION = "0.33.3"
IDENTITY_FIELDS = (
    "model_name",
    "full_local_digest",
    "size_bytes",
    "quantization_level",
    "capabilities",
    "ollama_version",
)
BOUNDARY_FIELDS = (
    "real_photo",
    "real_exif",
    "g1_source",
    "sqlite",
    "real20",
    "app",
    "production_bundle",
    "model_download",
    "model_replacement",
)
CONSUMPTION_SCHEMA_VERSION = "n2b2-runtime-authorization-consumption-v1"
EVIDENCE_SCHEMA_VERSION = "n2b2-runtime-revalidation-evidence-v1"
LEASE_SCHEMA_VERSION = "n2b2-runtime-execution-lease-v1"
LEASE_TYPE = "OWNER_N2B2_SYNTHETIC_RUNTIME_EXECUTION_LEASE"
_HEX64 = set("0123456789abcdef")
_REPARSE_POINT = 0x400


class RevalidationGateError(ValueError):
    """Raised before any model call when this narrow authorization is invalid."""


@dataclass(frozen=True)
class TreeSnapshot:
    """Path-redactable release tree hash inventory."""

    entries: dict[str, str]

    @property
    def file_count(self) -> int:
        return len(self.entries)


@dataclass(frozen=True)
class RevalidationPermit:
    """Validated immutable inputs for the one authorized identity transition."""

    identity_diff_fields: tuple[str, ...]
    old_identity_sha256: str
    new_identity_sha256: str


@dataclass(frozen=True)
class OneShotReservation:
    """Durable external reservation for one receipt/candidate execution."""

    key: str
    record_path: Path
    receipt_sha256: str
    source_candidate: str


_ACTIVE_RESERVATION: ContextVar[OneShotReservation | None] = ContextVar(
    "n2b2_active_reservation", default=None
)


def _fail(detail: str) -> None:
    raise RevalidationGateError(f"N2B2_RUNTIME_IDENTITY_REVALIDATION_BLOCKED: {detail}")


def _is_hex(value: object, length: int) -> bool:
    return isinstance(value, str) and len(value) == length and set(value) <= _HEX64


def _nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _reject_reparse_ancestors(path: Path) -> None:
    """Reject links before any resolution, including Windows junctions."""

    current = Path(path)
    while True:
        try:
            info = current.lstat()
        except FileNotFoundError:
            if current.parent == current:
                return
            current = current.parent
            continue
        except OSError:
            _fail("path metadata is unavailable")
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & _REPARSE_POINT:
            _fail("path contains a reparse point")
        if current.parent == current:
            return
        current = current.parent


def _resolve_checked(path: Path, *, must_exist: bool) -> Path:
    candidate = Path(path)
    _reject_reparse_ancestors(candidate)
    try:
        resolved = candidate.resolve(strict=must_exist)
    except (OSError, RuntimeError):
        _fail("path cannot be resolved safely")
    _reject_reparse_ancestors(resolved)
    return resolved


def validate_external_path(path: Path, *, project_root: Path, must_exist: bool = True) -> Path:
    """Resolve one file or directory only after rejecting reparse ancestors."""

    resolved = _resolve_checked(path, must_exist=must_exist)
    project = _resolve_checked(project_root, must_exist=True)
    if _overlaps(resolved, project):
        _fail("path must be Git-external")
    return resolved


def validate_root_set(
    roots: Mapping[str, Path],
    *,
    project_root: Path,
    allow_missing: set[str] | frozenset[str] = frozenset(),
) -> dict[str, Path]:
    """Resolve a complete input/output/protected root set and reject overlap."""

    project = _resolve_checked(project_root, must_exist=True)
    resolved: dict[str, Path] = {}
    for name, value in roots.items():
        current = _resolve_checked(Path(value), must_exist=name not in allow_missing)
        if name != "project_root" and _overlaps(current, project):
            _fail(f"root overlaps Git project: {name}")
        if name not in allow_missing and not current.is_dir():
            _fail(f"root is not a directory: {name}")
        resolved[name] = current
    items = list(resolved.items())
    for index, (left_name, left) in enumerate(items):
        for right_name, right in items[index + 1 :]:
            if _overlaps(left, right):
                _fail(f"root overlap: {left_name} and {right_name}")
    return resolved


def canonical_identity(value: Mapping[str, object]) -> bytes:
    """Serialize only the Owner-bound identity fields in a stable form."""

    if set(value) != set(IDENTITY_FIELDS):
        _fail("identity fields are incomplete or broadened")
    model_name = value.get("model_name")
    digest = value.get("full_local_digest")
    size = value.get("size_bytes")
    quantization = value.get("quantization_level")
    version = value.get("ollama_version")
    capabilities = value.get("capabilities")
    if not (
        isinstance(model_name, str)
        and isinstance(digest, str)
        and len(digest) == 64
        and isinstance(size, int)
        and size > 0
        and isinstance(quantization, str)
        and isinstance(version, str)
        and isinstance(capabilities, Sequence)
        and not isinstance(capabilities, str)
        and all(isinstance(item, str) and item for item in capabilities)
    ):
        _fail("identity has invalid field types")
    capabilities = cast(Sequence[object], capabilities)
    normalized_capabilities = sorted({cast(str, item) for item in capabilities})
    normalized = {
        "model_name": model_name,
        "full_local_digest": digest,
        "size_bytes": size,
        "quantization_level": quantization,
        "capabilities": normalized_capabilities,
        "ollama_version": version,
    }
    return (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _identity_dict(value: Mapping[str, object]) -> dict[str, object]:
    payload = json.loads(canonical_identity(value).decode("utf-8"))
    if not isinstance(payload, dict):  # pragma: no cover - canonical JSON is an object
        _fail("canonical identity is not an object")
    return {str(key): item for key, item in payload.items()}


def _identity_sha256(value: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_identity(value)).hexdigest()


def _receipt_identity(value: Mapping[str, object]) -> dict[str, object]:
    """Validate a receipt identity without admitting any runtime-only field."""

    expected = set(IDENTITY_FIELDS) | {"canonical_identity_sha256"}
    if set(value) != expected:
        _fail("receipt identity fields are incomplete or broadened")
    identity = {field: value[field] for field in IDENTITY_FIELDS}
    expected_hash = value.get("canonical_identity_sha256")
    if not isinstance(expected_hash, str) or expected_hash != _identity_sha256(identity):
        _fail("receipt canonical identity hash does not match")
    return identity


def _overlaps(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        try:
            right.relative_to(left)
            return True
        except ValueError:
            return False


def validate_fresh_output(
    output: Path,
    *,
    project_root: Path,
    cache_root: Path,
    old_roots: Sequence[Path],
) -> Path:
    """Reject every existing, Git, cache, or historical-evidence output target."""

    names = {"project_root": project_root, "cache_root": cache_root}
    names.update({f"old_root_{index}": root for index, root in enumerate(old_roots)})
    names["output"] = output
    candidate = validate_root_set(names, project_root=project_root, allow_missing={"output"})[
        "output"
    ]
    if candidate.exists():
        _fail("new output directory must not already exist")
    return candidate


def snapshot_tree(root: Path) -> TreeSnapshot:
    """Hash a known external tree without writing to it."""

    resolved = _resolve_checked(root, must_exist=True)
    if not resolved.is_dir():
        _fail("snapshot root is unavailable or reparse")
    entries: dict[str, str] = {}
    for path in sorted(resolved.rglob("*")):
        _reject_reparse_ancestors(path)
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            _fail("snapshot tree contains non-regular file")
        if info.st_nlink != 1:
            _fail("snapshot tree contains hardlink")
        relative = path.relative_to(resolved).as_posix()
        entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return TreeSnapshot(entries=entries)


def _write_exclusive_json(path: Path, value: Mapping[str, object]) -> None:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError:
        _fail("authorization consumption record could not be created")


def _read_consumption_record(path: Path) -> dict[str, object]:
    _reject_reparse_ancestors(path)
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            _fail("authorization consumption record is not a unique regular file")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        _fail("authorization consumption record is invalid")
    if not isinstance(value, dict):
        _fail("authorization consumption record is invalid")
    return cast(dict[str, object], value)


def _replace_json(path: Path, value: Mapping[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    _reject_reparse_ancestors(path.parent)
    try:
        _write_exclusive_json(temporary, value)
        os.replace(temporary, path)
    except OSError:
        _fail("authorization consumption record could not be finalized")
    finally:
        if temporary.exists():
            temporary.unlink()


def _consumption_key(receipt_sha256: str, source_candidate: str) -> str:
    return hashlib.sha256(
        json.dumps(
            {"receipt_sha256": receipt_sha256, "source_candidate": source_candidate},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def reserve_one_shot_authorization(
    consumption_root: Path,
    *,
    project_root: Path,
    receipt_sha256: str,
    source_candidate: str,
) -> OneShotReservation:
    """Atomically reserve a receipt/candidate pair before any model call."""

    if not _is_hex(receipt_sha256, 64) or not _is_hex(source_candidate, 40):
        _fail("authorization consumption key is invalid")
    root = validate_root_set(
        {"project_root": project_root, "consumption_root": consumption_root},
        project_root=project_root,
        allow_missing={"consumption_root"},
    )["consumption_root"]
    root.mkdir(parents=True, exist_ok=True)
    _reject_reparse_ancestors(root)
    key = _consumption_key(receipt_sha256, source_candidate)
    reservation_dir = root / key
    try:
        reservation_dir.mkdir()
    except FileExistsError:
        _fail("authorization already consumed")
    except OSError:
        _fail("authorization consumption reservation failed")
    record_path = reservation_dir / "consumption.json"
    _write_exclusive_json(
        record_path,
        {
            "schema_version": CONSUMPTION_SCHEMA_VERSION,
            "key": key,
            "receipt_sha256": receipt_sha256,
            "source_candidate": source_candidate,
            "status": "STARTED",
            "started_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    return OneShotReservation(key, record_path, receipt_sha256, source_candidate)


def finalize_one_shot_authorization(
    reservation: OneShotReservation, *, status: Literal["COMPLETE", "FAILED"]
) -> dict[str, object]:
    """Persist the terminal state without ever releasing the reservation."""

    record = _read_consumption_record(reservation.record_path)
    if (
        record.get("schema_version") != CONSUMPTION_SCHEMA_VERSION
        or record.get("key") != reservation.key
        or record.get("receipt_sha256") != reservation.receipt_sha256
        or record.get("source_candidate") != reservation.source_candidate
        or record.get("status") != "STARTED"
    ):
        _fail("authorization consumption transition is invalid")
    record.update(
        {"status": status, "finished_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    )
    _replace_json(reservation.record_path, record)
    return record


def activate_one_shot_authorization(reservation: OneShotReservation) -> None:
    """Register a reservation for the CLI safety wrapper's terminal transition."""

    _ACTIVE_RESERVATION.set(reservation)


def finalize_active_one_shot_authorization(
    *, status: Literal["COMPLETE", "FAILED"]
) -> dict[str, object] | None:
    reservation = _ACTIVE_RESERVATION.get()
    if reservation is None:
        return None
    return finalize_one_shot_authorization(reservation, status=status)


def clear_active_one_shot_authorization() -> None:
    _ACTIVE_RESERVATION.set(None)


def _git_bytes(root: Path, *args: str) -> bytes:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        _fail("Git tree binding is unavailable")
    if result.returncode != 0:
        _fail("Git tree binding is unavailable")
    return result.stdout


def git_tree_binding(project_root: Path) -> dict[str, object]:
    """Bind the complete clean committed Git tree, not a selected source list."""

    root = _resolve_checked(project_root, must_exist=True)
    if _git_bytes(root, "status", "--porcelain=v1", "--untracked-files=all") != b"":
        _fail("Git tree binding requires a clean worktree")
    head = _git_bytes(root, "rev-parse", "HEAD").decode("ascii").strip()
    tree = _git_bytes(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    listing = _git_bytes(root, "ls-tree", "--full-tree", "-r", "-z", "HEAD")
    if not _is_hex(head, 40) or not _is_hex(tree, 40) or not listing.endswith(b"\0"):
        _fail("Git tree binding is invalid")
    return {
        "schema_version": "n2b2-git-tree-binding-v1",
        "git_head": head,
        "git_tree": tree,
        "tree_sha256": hashlib.sha256(listing).hexdigest(),
        "file_count": listing.count(b"\0"),
    }


def build_revalidation_evidence(
    *,
    candidate: str,
    tree: Mapping[str, object],
    identities: Sequence[Mapping[str, object]],
    commands: Sequence[Mapping[str, object]],
    artifacts: Mapping[str, object],
    resume: Mapping[str, object],
    forbidden_counters: Mapping[str, object],
) -> dict[str, object]:
    """Build a versioned evidence DTO from actual observations only."""

    if not _is_hex(candidate, 40):
        _fail("evidence candidate binding is invalid")
    file_count = tree.get("file_count")
    if (
        tree.get("schema_version") != "n2b2-git-tree-binding-v1"
        or tree.get("git_head") != candidate
        or not _is_hex(tree.get("git_tree"), 40)
        or not _is_hex(tree.get("tree_sha256"), 64)
        or not isinstance(file_count, int)
        or isinstance(file_count, bool)
        or file_count <= 0
    ):
        _fail("evidence Git tree binding is invalid")
    if not identities:
        _fail("identity observations are required")
    normalized_identities = [_identity_dict(identity) for identity in identities]
    if not commands:
        _fail("command evidence is required")
    normalized_commands: list[dict[str, object]] = []
    for command in commands:
        if (
            not isinstance(command.get("name"), str)
            or not isinstance(command.get("status"), str)
            or type(command.get("exit_code")) is not int
        ):
            _fail("command evidence is invalid")
        normalized_commands.append(dict(command))
    if not artifacts or any(not _is_hex(value, 64) for value in artifacts.values()):
        _fail("artifact hash evidence is invalid")
    required_resume = {"status", "exit_code", "added", "changed", "removed"}
    if (
        set(resume) < required_resume
        or type(resume.get("exit_code")) is not int
        or any(not _nonnegative_int(resume.get(name)) for name in required_resume - {"status"})
    ):
        _fail("resume evidence is incomplete")
    if any(type(value) is not int or value < 0 for value in forbidden_counters.values()):
        _fail("forbidden counter evidence is invalid")
    return {
        "schema_version": EVIDENCE_SCHEMA_VERSION,
        "candidate": candidate,
        "git_tree": dict(tree),
        "identity_observations": normalized_identities,
        "commands": normalized_commands,
        "artifacts": dict(artifacts),
        "resume": dict(resume),
        "forbidden_counters": dict(forbidden_counters),
        "counter_evidence": "DECLARED_BY_RUNNER_NOT_INDEPENDENT_OS_TELEMETRY",
    }


def validate_source_bound_execution_lease(
    lease: Mapping[str, object],
    *,
    lease_sha256: str,
    current_head: str,
    current_tree: Mapping[str, object],
    project_state_sha256: str,
    project_state_n2b2: str,
    old_identity: Mapping[str, object],
    current_identity: Mapping[str, object] | None,
    review_sha256: str,
    review_text: str,
) -> None:
    """Require a fresh Owner lease bound to the exact code tree before execution."""

    required = {
        "schema_version",
        "receipt_type",
        "status",
        "owner_id",
        "issued_at_utc",
        "task",
        "receipt_id",
        "external_review_sha256",
        "accepted_verdict",
        "accepted_blocker",
        "old_identity",
        "authorized_identity",
        "source_candidate",
        "source_git_tree",
        "source_tree_sha256",
        "source_tree_file_count",
        "project_state_sha256",
        "project_state_n2b2",
        "production_unlock",
        "boundaries",
        "max_fresh_s3_runs",
        "max_fresh_s20_runs",
        "mandatory_external_review",
    }
    if set(lease) != required or not _is_hex(lease_sha256, 64):
        _fail("source-bound execution lease fields are incomplete")
    if (
        lease.get("schema_version") != LEASE_SCHEMA_VERSION
        or lease.get("receipt_type") != LEASE_TYPE
        or lease.get("status") != "APPROVED"
        or lease.get("owner_id") != "Jovi"
        or not isinstance(lease.get("issued_at_utc"), str)
        or not isinstance(lease.get("task"), str)
        or not isinstance(lease.get("receipt_id"), str)
        or not lease.get("receipt_id")
        or lease.get("external_review_sha256") != review_sha256
        or lease.get("accepted_verdict") != REVIEW_VERDICT
        or lease.get("accepted_blocker") != REVIEW_BLOCKER
        or project_state_n2b2 != "LOCKED"
        or lease.get("production_unlock") is not False
        or lease.get("max_fresh_s3_runs") != 1
        or lease.get("max_fresh_s20_runs") != 1
        or lease.get("mandatory_external_review") is not True
    ):
        _fail("source-bound execution lease does not match current state")
    if lease.get("source_candidate") != current_head:
        _fail("source candidate binding does not match current HEAD")
    if (
        lease.get("source_git_tree") != current_tree.get("git_tree")
        or lease.get("source_tree_sha256") != current_tree.get("tree_sha256")
        or lease.get("source_tree_file_count") != current_tree.get("file_count")
    ):
        _fail("source tree binding does not match current tree")
    if (
        lease.get("project_state_sha256") != project_state_sha256
        or lease.get("project_state_n2b2") != project_state_n2b2
    ):
        _fail("source-bound execution lease state binding does not match")
    boundaries = lease.get("boundaries")
    if not isinstance(boundaries, Mapping) or set(boundaries) != set(BOUNDARY_FIELDS):
        _fail("source-bound execution lease boundaries are incomplete")
    boundaries = cast(Mapping[str, object], boundaries)
    if any(boundaries.get(field) is not False for field in BOUNDARY_FIELDS):
        _fail("source-bound execution lease broadens a forbidden boundary")
    if REVIEW_VERDICT not in review_text or REVIEW_BLOCKER not in review_text:
        _fail("source-bound execution lease review binding is invalid")
    old_bound = lease.get("old_identity")
    new_bound = lease.get("authorized_identity")
    if not isinstance(old_bound, Mapping) or not isinstance(new_bound, Mapping):
        _fail("source-bound execution lease identity binding is invalid")
    old_bound = cast(Mapping[str, object], old_bound)
    new_bound = cast(Mapping[str, object], new_bound)
    old_bound_identity = _receipt_identity(old_bound)
    new_bound_identity = _receipt_identity(new_bound)
    if canonical_identity(old_bound_identity) != canonical_identity(old_identity):
        _fail("source-bound execution lease identity binding does not match")
    old = _identity_dict(old_identity)
    authorized = _identity_dict(new_bound_identity)
    if (
        old["model_name"] != "qwen3.5:9b"
        or old["quantization_level"] != "Q4_K_M"
        or "vision" not in cast(list[object], old["capabilities"])
        or old["ollama_version"] != OLD_OLLAMA_VERSION
        or authorized["ollama_version"] != NEW_OLLAMA_VERSION
    ):
        _fail("source-bound execution lease identity transition is invalid")
    if tuple(field for field in IDENTITY_FIELDS if old[field] != authorized[field]) != (
        "ollama_version",
    ):
        _fail("source-bound execution lease identity drift is broader than Ollama version")
    if current_identity is None:
        return
    if canonical_identity(new_bound_identity) != canonical_identity(current_identity):
        _fail("source-bound execution lease identity binding does not match")
    current = _identity_dict(current_identity)
    if current["ollama_version"] != NEW_OLLAMA_VERSION or tuple(
        field for field in IDENTITY_FIELDS if old[field] != current[field]
    ) != ("ollama_version",):
        _fail("source-bound execution lease identity drift is broader than Ollama version")


def assert_identity_stable(before: Mapping[str, object], after: Mapping[str, object]) -> None:
    """Require byte-equivalent canonical current identities across checkpoints."""

    if canonical_identity(before) != canonical_identity(after):
        _fail("current Ollama identity changed during revalidation")


def validate_revalidation_authorization(
    receipt: Mapping[str, object],
    *,
    review_sha256: str,
    review_text: str,
    project_state_sha256: str,
    project_state_n2b2: str,
    old_identity: Mapping[str, object],
    current_identity: Mapping[str, object],
    current_head: str,
) -> RevalidationPermit:
    """Validate the single accepted review and the exact 0.32.15 -> 0.33.3 transition."""

    required = {
        "schema_version",
        "receipt_type",
        "status",
        "owner_id",
        "issued_at_utc",
        "task",
        "base_candidate",
        "external_review_sha256",
        "accepted_verdict",
        "accepted_blocker",
        "old_identity",
        "authorized_identity",
        "project_state_sha256",
        "project_state_n2b2",
        "production_unlock",
        "boundaries",
        "max_fresh_s3_runs",
        "max_fresh_s20_runs",
        "new_output_required",
        "old_evidence_mutation",
        "mandatory_external_review",
    }
    if set(receipt) != required:
        _fail("receipt fields are incomplete or broadened")
    if (
        receipt.get("schema_version") != "1.0"
        or receipt.get("receipt_type") != "OWNER_N2B2_OLLAMA_RUNTIME_IDENTITY_REVALIDATION"
        or receipt.get("status") != "APPROVED"
        or receipt.get("owner_id") != "Jovi"
        or not isinstance(receipt.get("issued_at_utc"), str)
        or receipt.get("task") != TASK
        or receipt.get("base_candidate") != BASE_CANDIDATE
        or current_head != BASE_CANDIDATE
        or receipt.get("external_review_sha256") != review_sha256
        or receipt.get("accepted_verdict") != REVIEW_VERDICT
        or receipt.get("accepted_blocker") != REVIEW_BLOCKER
        or receipt.get("project_state_sha256") != project_state_sha256
        or receipt.get("project_state_n2b2") != project_state_n2b2
        or project_state_n2b2 != "LOCKED"
        or receipt.get("production_unlock") is not False
        or receipt.get("max_fresh_s3_runs") != 1
        or receipt.get("max_fresh_s20_runs") != 1
        or receipt.get("new_output_required") is not True
        or receipt.get("old_evidence_mutation") is not False
        or receipt.get("mandatory_external_review") is not True
    ):
        _fail("receipt binding does not match the one-shot authorization")
    if REVIEW_VERDICT not in review_text or REVIEW_BLOCKER not in review_text:
        _fail("review does not contain the accepted verdict and blocker")
    boundaries = receipt.get("boundaries")
    if not isinstance(boundaries, Mapping) or set(boundaries) != set(BOUNDARY_FIELDS):
        _fail("receipt boundaries are incomplete")
    boundaries = cast(Mapping[str, object], boundaries)
    if any(boundaries.get(field) is not False for field in BOUNDARY_FIELDS):
        _fail("receipt broadens a forbidden boundary")
    expected_old_raw = receipt.get("old_identity")
    expected_new_raw = receipt.get("authorized_identity")
    if not isinstance(expected_old_raw, Mapping) or not isinstance(expected_new_raw, Mapping):
        _fail("receipt identity records are invalid")
    expected_old = cast(Mapping[str, object], expected_old_raw)
    expected_new = cast(Mapping[str, object], expected_new_raw)
    receipt_old = _receipt_identity(expected_old)
    receipt_new = _receipt_identity(expected_new)
    if canonical_identity(receipt_old) != canonical_identity(old_identity):
        _fail("historical model identity does not match receipt")
    if canonical_identity(receipt_new) != canonical_identity(current_identity):
        _fail("current model identity does not match receipt")
    old = _identity_dict(old_identity)
    current = _identity_dict(current_identity)
    if (
        old["model_name"] != "qwen3.5:9b"
        or old["quantization_level"] != "Q4_K_M"
        or "vision" not in cast(list[object], old["capabilities"])
        or old["ollama_version"] != OLD_OLLAMA_VERSION
        or current["ollama_version"] != NEW_OLLAMA_VERSION
    ):
        _fail("model identity is outside the Owner-approved transition")
    changes = tuple(field for field in IDENTITY_FIELDS if old[field] != current[field])
    if changes != ("ollama_version",):
        _fail("model artifact drift is not limited to Ollama version")
    return RevalidationPermit(
        identity_diff_fields=changes,
        old_identity_sha256=_identity_sha256(old_identity),
        new_identity_sha256=_identity_sha256(current_identity),
    )
