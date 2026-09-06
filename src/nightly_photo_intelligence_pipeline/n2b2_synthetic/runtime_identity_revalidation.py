"""Fail-closed authorization primitives for one Owner-approved runtime revalidation."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

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


def _fail(detail: str) -> None:
    raise RevalidationGateError(f"N2B2_RUNTIME_IDENTITY_REVALIDATION_BLOCKED: {detail}")


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

    candidate = output.resolve(strict=False)
    protected = (project_root.resolve(strict=True), cache_root.resolve(strict=True), *old_roots)
    if any(_overlaps(candidate, root.resolve(strict=True)) for root in protected):
        _fail("new output overlaps Git, cache, or historical evidence")
    if candidate.exists():
        _fail("new output directory must not already exist")
    return candidate


def snapshot_tree(root: Path) -> TreeSnapshot:
    """Hash a known external tree without writing to it."""

    resolved = root.resolve(strict=True)
    if not resolved.is_dir() or resolved.is_symlink():
        _fail("snapshot root is unavailable or reparse")
    entries: dict[str, str] = {}
    for path in sorted(resolved.rglob("*")):
        if path.is_dir():
            if path.is_symlink():
                _fail("snapshot tree contains reparse directory")
            continue
        if path.is_symlink() or not path.is_file():
            _fail("snapshot tree contains non-regular file")
        relative = path.relative_to(resolved).as_posix()
        entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return TreeSnapshot(entries=entries)


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
