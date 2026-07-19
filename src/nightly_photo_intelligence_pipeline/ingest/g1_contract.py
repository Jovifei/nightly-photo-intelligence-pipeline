"""G1 approval, runtime policy, and pre-content-read execution permit."""

from __future__ import annotations

import hashlib
import ntpath
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from ..domain.authorization import AuthorizationSnapshot
from ..domain.errors import GateNotAuthorizedError, RuntimePolicyError
from .manifest import G1FrozenManifest
from .read_only_capability import (
    ProbeFunction,
    ReadOnlyCapabilityResult,
    _windows_probe,
    verify_source_read_only_capability,
)
from .source_guard import is_reparse_point, strict_realpath, validate_roots

N0_BASELINE = "72a81f5984838b74304d23263ac450ea4b5a3a9a"
N1_BASELINE = "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc"
MANIFEST_SHA256 = "29eee5fdb8e16c85649752501c4b722d2b4d071950c8a989add040e895a75c47"
SOURCE_ROOT_FINGERPRINT_SHA256 = "a80ad1f4c5c193211c80fa2b765ec7108a865da22a145bb9238183a617ef4d0a"
RUNTIME_PARENT_FINGERPRINT_SHA256 = (
    "4fff1e32b19b8b0eca0d509d1a83a6e402600986fd7db90620c8086d6c014cf0"
)
RETRY_POLICY_SHA256 = "316df5c98fa81a0ae2facf8bcb3ac4914e363eedf219ee2a48f547830b2afafe"
ERROR_TAXONOMY_SHA256 = "a3003f71fd7b43d3169ceb983fe4ce27feef7a1b971cffa4309251f6fb24ac65"
G1_HISTORICAL_BINDINGS = {
    "project_state_sha256": "d6a70d095141e75a8848e7d68f4cc93285a86fb4866bc6c361ab597fdcb82762",
    "n1_task_sha256": "17c8fba29d229c2507f3fb2eacb01d1c22ee0bf930250754fb213d15f94a8c61",
    "g1_task_sha256": "e173ab85c68f72c0c8c801a1c1f2e8274b9a0a9454011aa90b3dd58bef5df7dc",
    "task_index_sha256": "67db817def7f9471aa45e5a8915cb0a52dfd25b346ec88037b66e3936772eb1c",
    "retry_policy_sha256": RETRY_POLICY_SHA256,
    "error_taxonomy_sha256": ERROR_TAXONOMY_SHA256,
}


@dataclass(frozen=True)
class G1Approval:
    manifest_sha256: str
    manifest_count: int
    source_root_fingerprint_sha256: str
    runtime_parent_fingerprint_sha256: str
    n0_baseline: str
    n1_baseline: str
    expires_at: datetime


@dataclass(frozen=True)
class G1ExecutionPermit:
    manifest_sha256: str
    source_root_fingerprint_sha256: str
    runtime_child_fingerprint_sha256: str
    read_only: ReadOnlyCapabilityResult

    def require_valid(self, manifest: G1FrozenManifest) -> None:
        if self.manifest_sha256 != manifest.sha256:
            raise GateNotAuthorizedError("G1 execution permit manifest mismatch")
        self.read_only.require_verified()


def path_fingerprint(path: Path) -> str:
    """Legacy source-root fingerprint retained for the approved G1 binding."""
    resolved = str(Path(path).resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()


def runtime_parent_fingerprint(path: Path) -> str:
    """Canonical Windows spelling used for the approved runtime parent only."""
    normalized = ntpath.normcase(ntpath.normpath(str(Path(path)))).replace("\\", "/")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_g1_approval(project_root: Path, *, now: datetime | None = None) -> G1Approval:
    path = project_root / "approvals" / "data_gate_approval_G1.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError):
        raise GateNotAuthorizedError("G1 approval cannot be parsed") from None
    if not isinstance(data, dict):
        raise GateNotAuthorizedError("G1 approval has invalid structure")
    if data.get("status") != "APPROVED" or data.get("owner") != "Jovi":
        raise GateNotAuthorizedError("G1 approval status or owner mismatch")
    if data.get("scope") != "G1_CALIBRATION_20_REMEDIATION":
        raise GateNotAuthorizedError("G1 approval scope mismatch")
    if data.get("max_assets") != 20 or data.get("manifest_count") != 20:
        raise GateNotAuthorizedError("G1 approval asset cap mismatch")
    if data.get("manifest_sha256") != MANIFEST_SHA256:
        raise GateNotAuthorizedError("G1 approval manifest binding mismatch")
    baselines = data.get("baselines") or {}
    if baselines != {"N0": N0_BASELINE, "N1": N1_BASELINE}:
        raise GateNotAuthorizedError("G1 approval baseline mismatch")
    try:
        expires_at = datetime.fromisoformat(str(data["expires_at"]))
    except (KeyError, TypeError, ValueError):
        raise GateNotAuthorizedError("G1 approval expiry is invalid") from None
    reference_now = now or datetime.now().astimezone()
    if expires_at.tzinfo is None or reference_now >= expires_at:
        raise GateNotAuthorizedError("G1 approval is expired")

    required_exclusions = {
        "21st_or_off_manifest_asset",
        "n2_through_n8",
        "pose",
        "segmentation",
        "vlm",
        "embedding",
        "model_downloads",
        "cloud_processing",
        "openclaw",
        "system_configuration_changes",
        "main_app_changes",
        "git_push_merge_release",
    }
    if not required_exclusions.issubset(set(data.get("explicit_exclusions") or [])):
        raise GateNotAuthorizedError("G1 approval exclusions incomplete")
    current_bindings = {
        "project_state_sha256": _sha256(project_root / "PROJECT_STATE.json"),
        "n1_task_sha256": _sha256(project_root / "tasks" / "phase_n1_ingest_state_machine.yaml"),
        "g1_task_sha256": _sha256(project_root / "tasks" / "gate_g1_calibration_20.yaml"),
        "task_index_sha256": _sha256(project_root / "tasks" / "index.json"),
        "retry_policy_sha256": _sha256(project_root / "config" / "retry_policy_v1_1.yaml"),
        "error_taxonomy_sha256": _sha256(project_root / "config" / "error_taxonomy_v1_1.yaml"),
    }
    state_version = "1.1"
    try:
        import json

        state_version = json.loads((project_root / "PROJECT_STATE.json").read_text("utf-8")).get(
            "schema_version", "1.1"
        )
    except (OSError, UnicodeError, ValueError):
        pass
    if state_version == "1.2":
        valid_bindings: tuple[dict[str, str], ...] = (G1_HISTORICAL_BINDINGS, current_bindings)
    else:
        valid_bindings = (current_bindings,)
    if data.get("bindings") not in valid_bindings:
        raise GateNotAuthorizedError("G1 approval mutable-state binding mismatch")
    source_policy = data.get("source_policy") or {}
    runtime_policy = data.get("runtime_policy") or {}
    if source_policy.get("root_fingerprint_sha256") != SOURCE_ROOT_FINGERPRINT_SHA256:
        raise GateNotAuthorizedError("G1 approval source binding mismatch")
    if runtime_policy.get("parent_fingerprint_sha256") != RUNTIME_PARENT_FINGERPRINT_SHA256:
        raise GateNotAuthorizedError("G1 approval runtime binding mismatch")
    if state_version != "1.2" and current_bindings["retry_policy_sha256"] != RETRY_POLICY_SHA256:
        raise GateNotAuthorizedError("G1 retry policy binding mismatch")
    if (
        state_version != "1.2"
        and current_bindings["error_taxonomy_sha256"] != ERROR_TAXONOMY_SHA256
    ):
        raise GateNotAuthorizedError("G1 error taxonomy binding mismatch")
    return G1Approval(
        manifest_sha256=str(data["manifest_sha256"]),
        manifest_count=int(data["manifest_count"]),
        source_root_fingerprint_sha256=str(source_policy.get("root_fingerprint_sha256", "")),
        runtime_parent_fingerprint_sha256=str(runtime_policy.get("parent_fingerprint_sha256", "")),
        n0_baseline=str(baselines["N0"]),
        n1_baseline=str(baselines["N1"]),
        expires_at=expires_at,
    )


def validate_runtime_child(
    *,
    source_root: Path,
    runtime_parent: Path,
    runtime_child: Path,
    approval: G1Approval,
) -> None:
    parent = Path(runtime_parent)
    child = Path(runtime_child)
    if runtime_parent_fingerprint(parent) != approval.runtime_parent_fingerprint_sha256:
        raise RuntimePolicyError("runtime parent fingerprint mismatch")
    if not parent.is_dir() or not child.is_dir():
        raise RuntimePolicyError("runtime parent or child is unavailable")
    ancestor_chain = [*reversed(parent.parents), parent]
    if any(component.exists() and is_reparse_point(component) for component in ancestor_chain):
        raise RuntimePolicyError("runtime parent ancestry contains a reparse point")
    if is_reparse_point(child):
        raise RuntimePolicyError("runtime path contains a reparse point")
    parent_real = strict_realpath(parent)
    child_real = strict_realpath(child)
    try:
        relative = child_real.relative_to(parent_real)
    except ValueError:
        raise RuntimePolicyError("runtime child is outside approved parent") from None
    if not relative.parts:
        raise RuntimePolicyError("runtime child must be distinct from parent")
    cursor = parent
    for part in relative.parts:
        cursor = cursor / part
        if cursor.exists() and is_reparse_point(cursor):
            raise RuntimePolicyError("runtime child path contains a reparse point")
    validate_roots(source_root, child)


def validate_g1_execution_contract(
    *,
    source_root: Path,
    runtime_parent: Path,
    runtime_child: Path,
    auth: AuthorizationSnapshot,
    manifest: G1FrozenManifest,
    approval: G1Approval,
) -> None:
    if auth.phase_id != "N1" or not auth.phase_authorized:
        raise GateNotAuthorizedError("G1 requires the approved N1 capability baseline")
    if auth.data_gate_id != "G1_CALIBRATION_20" or not auth.data_gate_authorized:
        raise GateNotAuthorizedError("G1 data gate is not authorized")
    if auth.n0_baseline_commit != N0_BASELINE or auth.n1_baseline_commit != N1_BASELINE:
        raise GateNotAuthorizedError("G1 authorization baseline mismatch")
    if auth.max_assets != 20 or auth.real_photo_access != "AUTHORIZED":
        raise GateNotAuthorizedError("G1 authorization scope mismatch")
    if auth.exif_real_data_read != "AUTHORIZED_NON_SENSITIVE_ONLY":
        raise GateNotAuthorizedError("G1 EXIF authorization mismatch")
    if manifest.sha256.lower() != approval.manifest_sha256.lower():
        raise GateNotAuthorizedError("G1 manifest SHA-256 mismatch")
    if manifest.count != approval.manifest_count or manifest.count != 20:
        raise GateNotAuthorizedError("G1 manifest count mismatch")
    if path_fingerprint(source_root) != approval.source_root_fingerprint_sha256:
        raise GateNotAuthorizedError("G1 source root fingerprint mismatch")
    validate_runtime_child(
        source_root=source_root,
        runtime_parent=runtime_parent,
        runtime_child=runtime_child,
        approval=approval,
    )


def prepare_g1_execution(
    *,
    source_root: Path,
    runtime_parent: Path,
    runtime_child: Path,
    auth: AuthorizationSnapshot,
    manifest: G1FrozenManifest,
    approval: G1Approval,
    probe: ProbeFunction = _windows_probe,
) -> G1ExecutionPermit:
    """Complete every non-content gate before returning an ingest permit."""
    validate_g1_execution_contract(
        source_root=source_root,
        runtime_parent=runtime_parent,
        runtime_child=runtime_child,
        auth=auth,
        manifest=manifest,
        approval=approval,
    )
    authorized = [source_root / entry.relative_path for entry in manifest.entries]
    read_only = verify_source_read_only_capability(source_root, authorized, probe=probe)
    read_only.require_verified()
    return G1ExecutionPermit(
        manifest_sha256=manifest.sha256,
        source_root_fingerprint_sha256=path_fingerprint(source_root),
        runtime_child_fingerprint_sha256=path_fingerprint(runtime_child),
        read_only=read_only,
    )
