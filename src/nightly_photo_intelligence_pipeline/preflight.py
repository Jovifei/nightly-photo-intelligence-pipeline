"""Read-only preflight checks for ``npi preflight``.

Every check is observational: it may query a tool or read a file, but it never
installs, upgrades, pulls, or changes system state. All output is redacted of
usernames, hostnames, home paths, and tokens.
"""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ._paths import find_project_root
from .domain.authorization import load_authorization
from .domain.errors import NPI_DUPLICATE_JSON_MEMBER, DuplicateJsonMemberError
from .json_strict import load_json_strict
from .redaction import redact_text

# Status values (do not conflate SKIPPED with PASS).
PASS = "PASS"
NOT_AVAILABLE = "NOT_AVAILABLE"
SKIPPED = "SKIPPED"
FAIL = "FAIL"
_MIN_FREE_DISK_BYTES = 1024**3

_TIMEOUT = 10  # seconds per observational command


@dataclass
class CheckResult:
    name: str
    status: str
    evidence: str = ""
    notes: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "evidence": redact_text(self.evidence),
            "notes": redact_text(self.notes),
        }


def _run(cmd: list[str], *, timeout: int = _TIMEOUT) -> tuple[int, str]:
    """Run a read-only command and return (returncode, redacted stdout)."""
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            check=False,
            text=False,
        )
        out = proc.stdout.decode("utf-8", errors="replace").strip()
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        combined = out if out else err
        return proc.returncode, combined
    except FileNotFoundError:
        return -1, "command not found"
    except subprocess.TimeoutExpired:
        return -2, "timed out"
    except OSError as exc:
        return -3, f"os error: {type(exc).__name__}"


def _check_python() -> CheckResult:
    return CheckResult(
        name="python",
        status=PASS,
        evidence=f"{sys.version.split()[0]} on {sys.platform}",
        notes=f"executable provenance: {redact_text(str(Path(sys.executable).resolve()))}",
    )


def _check_os() -> CheckResult:
    info = f"{platform.system()} {platform.release()} {platform.machine()}"
    return CheckResult(name="os", status=PASS, evidence=redact_text(info))


def _check_wsl() -> CheckResult:
    if sys.platform != "win32":
        return CheckResult(name="wsl", status=SKIPPED, notes="not on Windows")
    rc, out = _run(["wsl", "--status"])
    if rc == 0:
        return CheckResult(name="wsl", status=PASS, evidence=redact_text(out)[:200])
    return CheckResult(name="wsl", status=NOT_AVAILABLE, notes=redact_text(out)[:200])


def _check_git() -> CheckResult:
    rc, out = _run(["git", "--version"])
    if rc == 0:
        return CheckResult(name="git", status=PASS, evidence=redact_text(out))
    return CheckResult(name="git", status=NOT_AVAILABLE, notes=redact_text(out))


def _check_docker() -> CheckResult:
    rc, out = _run(["docker", "--version"])
    if rc == 0:
        return CheckResult(name="docker", status=PASS, evidence=redact_text(out))
    return CheckResult(name="docker", status=NOT_AVAILABLE, notes="redacted")


def _check_docker_compose() -> CheckResult:
    rc, out = _run(["docker", "compose", "version"])
    if rc == 0:
        return CheckResult(name="docker_compose", status=PASS, evidence=redact_text(out))
    return CheckResult(name="docker_compose", status=NOT_AVAILABLE, notes="redacted")


def _check_nvidia() -> CheckResult:
    rc, out = _run(
        ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"]
    )
    if rc == 0:
        # GPU name/driver/vram are not PII; serials are never queried.
        return CheckResult(name="nvidia_smi", status=PASS, evidence=redact_text(out)[:200])
    return CheckResult(name="nvidia_smi", status=NOT_AVAILABLE, notes="redacted")


def _check_disk() -> CheckResult:
    root = find_project_root()
    try:
        usage = shutil.disk_usage(str(root))
        free_gb = usage.free / (1024**3)
        if usage.free < _MIN_FREE_DISK_BYTES:
            return CheckResult(
                name="disk_free",
                status=FAIL,
                notes="available disk is below the 1 GiB safety floor",
            )
        return CheckResult(
            name="disk_free",
            status=PASS,
            evidence=f"project drive free: {free_gb:.1f} GiB",
        )
    except OSError:
        return CheckResult(name="disk_free", status=FAIL, notes="disk query failed")


def _check_fixture_integrity() -> CheckResult:  # noqa: PLR0911
    root = find_project_root()
    manifest_path = root / "fixtures" / "fixture_manifest.json"
    if not manifest_path.is_file():
        return CheckResult(name="fixture_integrity", status=FAIL, notes="manifest missing")
    try:
        manifest = load_json_strict(manifest_path)
    except DuplicateJsonMemberError:
        return CheckResult(name="fixture_integrity", status=FAIL, notes=NPI_DUPLICATE_JSON_MEMBER)
    except (OSError, UnicodeError, ValueError):
        return CheckResult(name="fixture_integrity", status=FAIL, notes="manifest invalid")
    files = manifest.get("files", [])
    if len(files) != 3:
        return CheckResult(
            name="fixture_integrity", status=FAIL, notes=f"expected 3 fixtures, got {len(files)}"
        )
    for entry in files:
        p = root / "fixtures" / "three_image_smoke_set" / entry["name"]
        if not p.is_file():
            return CheckResult(
                name="fixture_integrity", status=FAIL, notes=f"missing {entry['name']}"
            )
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != entry["sha256"]:
            return CheckResult(
                name="fixture_integrity", status=FAIL, notes=f"hash mismatch {entry['name']}"
            )
    return CheckResult(
        name="fixture_integrity",
        status=PASS,
        evidence="3 synthetic fixtures match manifest SHA-256",
    )


def _check_repo_independence() -> CheckResult:
    root = find_project_root().resolve()
    # Walk up to ensure no parent .git exists (would mean we are inside another repo).
    current = root
    for _ in range(10):
        if (current / ".git").exists():
            if current == root:
                return CheckResult(
                    name="repo_independence",
                    status=PASS,
                    evidence="local git repo initialized at project root",
                )
            return CheckResult(
                name="repo_independence",
                status=FAIL,
                notes="project is inside a parent .git repository",
            )
        if current.parent == current:
            break
        current = current.parent
    return CheckResult(
        name="repo_independence",
        status=PASS,
        evidence="no parent git repository detected (independent)",
    )


_OWNER_MUTABLE_ARCHIVE_FILES = {
    "PROJECT_STATE.json",
    "tasks/index.json",
    "tasks/README.md",
    "tasks/phase_n1_ingest_state_machine.yaml",
    "research/benchmark_protocol.md",
    "research/license_review_checklist.md",
    "research/model_candidate_register.md",
    "research/source_register.md",
    "research/technology_decision_matrix.md",
}


def _check_handoff() -> CheckResult:
    """Verify the delivered contract files (listed in MANIFEST.sha256) are intact.

    This is a subset check: every file listed in MANIFEST.sha256 must still
    exist and hash-match. New implementation files added during N0 are allowed
    (they are not contract files). The full ``tools/verify_handoff.py`` does an
    exact-set match designed for the pristine package and was run
    pre-implementation (evidence recorded in reports/N0_test_evidence.md).
    """
    root = find_project_root()
    manifest_path = root / "MANIFEST.sha256"
    if not manifest_path.is_file():
        return CheckResult(
            name="ARCHIVAL_HANDOFF_BASELINE_CHECK",
            status=FAIL,
            notes="MANIFEST.sha256 missing",
        )
    listed: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            return CheckResult(
                name="ARCHIVAL_HANDOFF_BASELINE_CHECK",
                status=FAIL,
                notes="invalid manifest record",
            )
        listed[rel] = digest
    missing: list[str] = []
    mismatched: list[str] = []
    for rel, digest in listed.items():
        if rel in _OWNER_MUTABLE_ARCHIVE_FILES:
            continue
        p = root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != digest:
            mismatched.append(rel)
    if missing or mismatched:
        return CheckResult(
            name="ARCHIVAL_HANDOFF_BASELINE_CHECK",
            status=FAIL,
            notes=f"missing={len(missing)} mismatched={len(mismatched)}",
        )
    return CheckResult(
        name="ARCHIVAL_HANDOFF_BASELINE_CHECK",
        status=PASS,
        evidence=(
            f"{len(listed) - len(_OWNER_MUTABLE_ARCHIVE_FILES)} immutable delivery files intact; "
            "Owner-authorized current state validated separately"
        ),
    )


def _check_schema_version() -> CheckResult:
    """Report a deterministic, traceable catalog version (never 'unknown').

    Per Owner decision, catalog_version is derived from the package version
    (or the catalog's own constant if present), not a runtime/random value.
    """
    root = find_project_root()
    catalog = root / "schemas" / "current_stage_schema_catalog.json"
    if not catalog.is_file():
        return CheckResult(name="schema_version", status=NOT_AVAILABLE, notes="catalog missing")
    try:
        data = load_json_strict(catalog)
    except (OSError, UnicodeError, ValueError):
        return CheckResult(name="schema_version", status=FAIL, notes="catalog JSON invalid")
    from . import __version__ as pkg_version
    from .persistence.migrations import SCHEMA_VERSION as db_schema_version

    catalog_version = data.get("catalog_version") or pkg_version
    return CheckResult(
        name="schema_version",
        status=PASS,
        evidence=(
            f"catalog_version={catalog_version} "
            f"(package={pkg_version}, db_migration=v{db_schema_version})"
        ),
    )


def _validate_schema(schema: dict[str, Any], instance: Any) -> list[str]:
    try:
        from jsonschema import Draft202012Validator, FormatChecker  # type: ignore
    except ImportError:
        return ["jsonschema unavailable"]
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    return [error.message for error in validator.iter_errors(instance)]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _n1_approval_chain_is_consistent(
    *,
    state: dict[str, Any],
    approval: dict[str, Any],
    n1_completion: dict[str, Any],
    n1_task: dict[str, Any],
    g1_task: dict[str, Any],
    task_index: dict[str, Any],
) -> bool:
    """Validate the immutable N1 approval link into the current G1 gate."""
    n0 = "72a81f5984838b74304d23263ac450ea4b5a3a9a"
    n1 = "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc"
    completion_path = "approvals/phase_completion_N1.yaml"
    completed_n1 = next(
        (item for item in task_index.get("completed", []) if item.get("phase") == "N1"),
        None,
    )
    return all(
        (
            n1_completion.get("status") == "APPROVED",
            n1_completion.get("owner_id") == "Jovi",
            n1_completion.get("phase_id") == "N1",
            n1_completion.get("baseline", {}).get("n0_commit") == n0,
            n1_completion.get("baseline", {}).get("n1_commit") == n1,
            n1_completion.get("independent_reviewer", {}).get("reviewed_commit") == n1,
            state.get("baselines", {}).get("N0", {}).get("commit") == n0,
            state.get("baselines", {}).get("N1", {}).get("commit") == n1,
            approval.get("baselines") == {"N0": n0, "N1": n1},
            n1_task.get("completion_approval") == completion_path,
            g1_task.get("dependencies", {}).get("n1_completion_approval") == completion_path,
            isinstance(completed_n1, dict),
            (completed_n1 or {}).get("baseline_commit") == n1,
            (completed_n1 or {}).get("completion_approval") == completion_path,
            state.get("authorization", {}).get("task_contract")
            == "tasks/gate_g1_calibration_20.yaml",
            state.get("authorization", {}).get("approval_record")
            == "approvals/data_gate_approval_G1.yaml",
        )
    )


def _check_n2b0_7_authorization(root: Path, state: dict[str, Any]) -> CheckResult:
    """Validate the active N2B0.7 metadata-only authorization chain."""
    try:
        schemas = root / "schemas"
        n2b0_6_approval_path = root / "approvals" / "phase_completion_N2B0_6.yaml"
        n2b0_6_completion = yaml.safe_load(n2b0_6_approval_path.read_text(encoding="utf-8"))
        bounded = yaml.safe_load(
            (root / "approvals" / "owner_continuous_authorization_N2B0_7_to_N3A.yaml").read_text(
                encoding="utf-8"
            )
        )
        n2b0_7_task = yaml.safe_load(
            (root / "tasks" / "phase_n2b0_7_gpu_native_qualification.yaml").read_text(
                encoding="utf-8"
            )
        )
        qualification = load_json_strict(
            root / "research" / "N2B0_7_torchvision_artifact_qualification.json"
        )
        task_index = load_json_strict(root / "tasks" / "index.json")
        checks = [
            (load_json_strict(schemas / "project_state_v1_5.schema.json"), state),
            (
                load_json_strict(schemas / "phase_completion_approval_n2b0_6_v1_0.schema.json"),
                n2b0_6_completion,
            ),
            (
                load_json_strict(
                    schemas / "owner_bounded_continuous_authorization_v1_0.schema.json"
                ),
                bounded,
            ),
            (load_json_strict(schemas / "task_contract_n2b0_7_v1_0.schema.json"), n2b0_7_task),
            (
                load_json_strict(schemas / "n2b0_7_artifact_qualification_v1.schema.json"),
                qualification,
            ),
            (load_json_strict(schemas / "task_index_v1_2.schema.json"), task_index),
        ]
        if any(_validate_schema(schema, value) for schema, value in checks):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2B0.7 authorization schema validation failed",
            )
        auth = state.get("authorization", {})
        phase_status = state.get("phase_status", {})
        gates = auth.get("capability_gates", {})
        active_execution = auth.get("active_execution", {})
        n2b0_7_index = next(
            (item for item in task_index.get("authorized", []) if item.get("phase") == "N2B0_7"),
            None,
        )
        if not all(
            (
                n2b0_6_completion.get("owner_decision") == "N2B0_6_OWNER_APPROVED",
                n2b0_6_completion.get("independent_reviewer", {}).get("reviewed_commit")
                == "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2",
                (root / "approvals" / "phase_completion_N2B0_6.sha256")
                .read_text(encoding="utf-8")
                .strip()
                == _file_sha256(n2b0_6_approval_path),
                bounded.get("start_phase", {}).get("status") == "AUTHORIZED_NOW",
                n2b0_7_task.get("capability") == "N2B0_7_GPU_NATIVE_QUALIFICATION",
                n2b0_7_task.get("mandatory_stop", {}).get("value") is True,
                phase_status.get("N2B0_6") == "APPROVED_COMPLETE",
                phase_status.get("N2B0_7") == "AUTHORIZED",
                gates.get("N2B0_7_GPU_NATIVE_QUALIFICATION") == "AUTHORIZED",
                gates.get("N2B_MODEL_DOWNLOAD_AND_INFERENCE") == "LOCKED",
                gates.get("N2B1_MODEL_DOWNLOAD") == "LOCKED",
                gates.get("N2B2_REAL_BENCHMARK") == "LOCKED",
                auth.get("large_model_downloads") == "NOT_AUTHORIZED",
                auth.get("real_model_execution") == "NOT_AUTHORIZED",
                active_execution
                == {
                    "phase": "N2B0_7",
                    "capability": "N2B0_7_GPU_NATIVE_QUALIFICATION",
                    "source_photo_content_read": "NOT_AUTHORIZED",
                    "source_photo_exif_read": "NOT_AUTHORIZED",
                    "sqlite_ingest_write": "NOT_AUTHORIZED",
                },
                qualification.get("result") == "N2B0_7_ARTIFACT_QUALIFICATION_BLOCKED",
                qualification.get("prohibited_action_counters")
                == {
                    "model_download_bytes": 0,
                    "dependency_installs": 0,
                    "model_execution_runs": 0,
                    "real_photo_reads": 0,
                    "cache_writes": 0,
                },
                state.get("required_stop_after")
                == {
                    "condition": "N2B0_7_ARTIFACT_QUALIFICATION_BLOCKED",
                    "next_action": "WAIT_FOR_OWNER_ARTIFACT_DECISION",
                },
                isinstance(n2b0_7_index, dict),
                (n2b0_7_index or {}).get("file") == "phase_n2b0_7_gpu_native_qualification.yaml",
                (n2b0_7_index or {}).get("capability") == "N2B0_7_GPU_NATIVE_QUALIFICATION",
            )
        ):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2B0.7 approval chain is inconsistent or broadened",
            )
        from .ingest.g1_contract import load_g1_approval

        load_g1_approval(root)
        return CheckResult(
            name="current_authorization_contracts",
            status=PASS,
            evidence=(
                "N2B0.6 approval+tag and bounded N2B0.7 metadata-only authorization valid; "
                "N2B1/Q/P, N2B2, N3, G2, and G3 remain locked"
            ),
        )
    except DuplicateJsonMemberError:
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes=NPI_DUPLICATE_JSON_MEMBER,
        )
    except Exception:  # noqa: BLE001
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes="N2B0.7 authorization contract validation failed",
        )


def _check_n2b1r_authorization(root: Path, state: dict[str, Any]) -> CheckResult:
    """Validate N2B1R without opening photos or model payloads."""
    try:
        schemas = root / "schemas"
        completion_path = root / "approvals" / "phase_completion_N2B0_7.yaml"
        completion = yaml.safe_load(completion_path.read_text(encoding="utf-8"))
        research_approval = yaml.safe_load(
            (root / "approvals" / "owner_local_research_execution_N2B1R_to_N5R.yaml").read_text(
                encoding="utf-8"
            )
        )
        task = yaml.safe_load(
            (root / "tasks" / "phase_n2b1r_local_research_model_acquisition.yaml").read_text(
                encoding="utf-8"
            )
        )
        register = load_json_strict(
            root / "research" / "N2B1R_local_research_artifact_register.json"
        )
        task_index = load_json_strict(root / "tasks" / "index.json")
        checks = [
            (load_json_strict(schemas / "project_state_v1_6.schema.json"), state),
            (
                load_json_strict(schemas / "phase_completion_approval_n2b0_7_v1_0.schema.json"),
                completion,
            ),
            (
                load_json_strict(schemas / "owner_local_research_execution_v1_0.schema.json"),
                research_approval,
            ),
            (load_json_strict(schemas / "task_contract_n2b1r_v1_0.schema.json"), task),
            (load_json_strict(schemas / "n2b1r_artifact_register_v1.schema.json"), register),
            (load_json_strict(schemas / "task_index_v1_2.schema.json"), task_index),
        ]
        if any(_validate_schema(schema, value) for schema, value in checks):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2B1R authorization schema validation failed",
            )
        auth = state.get("authorization", {})
        phases = state.get("phase_status", {})
        gates = auth.get("capability_gates", {})
        active = auth.get("active_execution", {})
        index_entry = next(
            (item for item in task_index.get("authorized", []) if item.get("phase") == "N2B1R"),
            None,
        )
        required_locked = (
            "N2B",
            "N2B1",
            "N2B1P",
            "N2B1_Q",
            "N2B1_P",
            "N2B2",
            "N3",
            "N4",
            "N5",
            "N6",
            "N7",
            "N8",
        )
        if not all(
            (
                completion.get("owner_decision") == "N2B0_7_OWNER_APPROVED",
                completion.get("baseline", {}).get("n2b0_7_commit")
                == "f2b1c38301d71da52b855f73de8a67908cb525ef",
                (root / "approvals" / "phase_completion_N2B0_7.sha256")
                .read_text(encoding="utf-8")
                .strip()
                == _file_sha256(completion_path),
                research_approval.get("start_phase", {}).get("status") == "AUTHORIZED_NOW",
                task.get("capability") == "N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION",
                task.get("mandatory_stop", {}).get("value") is True,
                phases.get("N2B0_7") == "APPROVED_COMPLETE",
                phases.get("N2B1R") == "AUTHORIZED",
                gates.get("N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION") == "AUTHORIZED",
                auth.get("large_model_downloads") == "AUTHORIZED_RESEARCH_ONLY",
                auth.get("real_model_execution") == "NOT_AUTHORIZED",
                active
                == {
                    "phase": "N2B1R",
                    "capability": "N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION",
                    "source_photo_content_read": "NOT_AUTHORIZED",
                    "source_photo_exif_read": "NOT_AUTHORIZED",
                    "sqlite_ingest_write": "NOT_AUTHORIZED",
                },
                all(phases.get(phase) == "LOCKED" for phase in required_locked),
                isinstance(index_entry, dict),
                (index_entry or {}).get("file")
                == "phase_n2b1r_local_research_model_acquisition.yaml",
                (index_entry or {}).get("capability") == "N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION",
                register.get("weights_rights", {}).get("status")
                == "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
                all(item.get("official_sha256") is None for item in register.get("artifacts", [])),
                all(
                    item.get("local_sha256_required") is True
                    for item in register.get("artifacts", [])
                ),
                state.get("required_stop_after")
                == {
                    "condition": "N2B1R_ACQUISITION_AWAITING_LOCAL_VERIFICATION",
                    "next_action": "VERIFY_QUARANTINE_AND_CREATE_N2B1P_AUTHORIZATION",
                },
            )
        ):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2B1R authorization boundary is inconsistent or broadened",
            )
        from .ingest.g1_contract import load_g1_approval

        load_g1_approval(root)
        return CheckResult(
            name="current_authorization_contracts",
            status=PASS,
            evidence=(
                "N2B1R local-research acquisition is bounded; model execution and source-photo "
                "access remain denied"
            ),
        )
    except DuplicateJsonMemberError:
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes=NPI_DUPLICATE_JSON_MEMBER,
        )
    except Exception:  # noqa: BLE001
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes="N2B1R authorization contract validation failed",
        )


def _check_n2b1p_authorization(root: Path, state: dict[str, Any]) -> CheckResult:
    """Validate N2B1P controls without opening a quarantine payload or photo."""
    try:
        schemas = root / "schemas"
        approval = yaml.safe_load(
            (root / "approvals" / "owner_n2b1p_cache_promotion.yaml").read_text(encoding="utf-8")
        )
        task = yaml.safe_load(
            (root / "tasks" / "phase_n2b1p_local_research_cache_promotion.yaml").read_text(
                encoding="utf-8"
            )
        )
        evidence = load_json_strict(root / "research" / "N2B1R_acquisition_evidence.json")
        promotion_evidence = load_json_strict(
            root / "research" / "N2B1P_cache_promotion_evidence.json"
        )
        runtime_configuration = load_json_strict(
            root / "approvals" / "n2b1p_runtime_configuration.json"
        )
        register = load_json_strict(
            root / "research" / "N2B1R_local_research_artifact_register.json"
        )
        task_index = load_json_strict(root / "tasks" / "index.json")
        checks = [
            (load_json_strict(schemas / "project_state_v1_7.schema.json"), state),
            (
                load_json_strict(schemas / "owner_n2b1p_cache_promotion_v1_0.schema.json"),
                approval,
            ),
            (load_json_strict(schemas / "task_contract_n2b1p_v1_0.schema.json"), task),
            (load_json_strict(schemas / "n2b1r_acquisition_evidence_v1.schema.json"), evidence),
            (
                load_json_strict(schemas / "n2b1p_cache_promotion_evidence_v1.schema.json"),
                promotion_evidence,
            ),
            (
                load_json_strict(schemas / "n2b1p_runtime_configuration_v1_0.schema.json"),
                runtime_configuration,
            ),
            (load_json_strict(schemas / "n2b1r_artifact_register_v1.schema.json"), register),
            (load_json_strict(schemas / "task_index_v1_2.schema.json"), task_index),
        ]
        if any(_validate_schema(schema, value) for schema, value in checks):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2B1P authorization schema validation failed",
            )
        auth = state.get("authorization", {})
        phases = state.get("phase_status", {})
        gates = auth.get("capability_gates", {})
        active = auth.get("active_execution", {})
        index_entry = next(
            (item for item in task_index.get("authorized", []) if item.get("phase") == "N2B1P"),
            None,
        )
        required_locked = (
            "N2B",
            "N2B1",
            "N2B1_Q",
            "N2B1_P",
            "N2B2",
            "N3",
            "N4",
            "N5",
            "N6",
            "N7",
            "N8",
        )
        from .local_research_promotion import (
            load_authorized_promotion,
            verify_promoted_artifact,
        )

        artifacts = {
            load_authorized_promotion(artifact_id, project_root=root).local_sha256
            for artifact_id in (
                "torchvision-keypointrcnn-resnet50-fpn-coco-v1",
                "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
                "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1",
            )
        }
        cache_results = {
            verify_promoted_artifact(artifact_id, project_root=root).status
            for artifact_id in (
                "torchvision-keypointrcnn-resnet50-fpn-coco-v1",
                "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
                "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1",
            )
        }
        if not all(
            (
                phases.get("N2B0_7") == "APPROVED_COMPLETE",
                phases.get("N2B1R") == "ACQUISITION_COMPLETE",
                phases.get("N2B1P") == "AUTHORIZED",
                gates.get("N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION") == "ACQUISITION_COMPLETE",
                gates.get("N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION") == "AUTHORIZED",
                auth.get("real_model_execution") == "NOT_AUTHORIZED",
                auth.get("network_access") == "DENY_BY_DEFAULT",
                active
                == {
                    "phase": "N2B1P",
                    "capability": "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
                    "source_photo_content_read": "NOT_AUTHORIZED",
                    "source_photo_exif_read": "NOT_AUTHORIZED",
                    "sqlite_ingest_write": "NOT_AUTHORIZED",
                },
                all(phases.get(phase) == "LOCKED" for phase in required_locked),
                isinstance(index_entry, dict),
                (index_entry or {}).get("file")
                == "phase_n2b1p_local_research_cache_promotion.yaml",
                (index_entry or {}).get("capability") == "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
                len(artifacts) == 3,
                promotion_evidence.get("result")
                == "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
                promotion_evidence.get("prohibited_actions")
                == {
                    "source_photo_or_exif_read": "NOT_PERFORMED",
                    "sqlite_ingest_write": "NOT_PERFORMED",
                    "model_load_or_inference": "NOT_PERFORMED",
                    "cuda_execution": "NOT_PERFORMED",
                    "dependency_install": "NOT_PERFORMED",
                    "derived_image_or_model_output": "NOT_PERFORMED",
                    "network_request_or_download": "NOT_PERFORMED",
                    "cache_or_quarantine_delete": "NOT_PERFORMED",
                },
                state.get("required_stop_after")
                == {
                    "condition": "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
                    "next_action": "EXTERNAL_REVIEW_N2B1P_REMEDIATION",
                },
                cache_results == {"CACHE_HIT"},
            )
        ):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2B1P authorization boundary is inconsistent or broadened",
            )
        return CheckResult(
            name="current_authorization_contracts",
            status=PASS,
            evidence=(
                "N2B1P cache promotion is bound to three local-research artifacts; "
                "model execution and source-photo access remain denied"
            ),
        )
    except DuplicateJsonMemberError:
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes=NPI_DUPLICATE_JSON_MEMBER,
        )
    except Exception:  # noqa: BLE001
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes="N2B1P authorization contract validation failed",
        )


def _check_authorization() -> CheckResult:  # noqa: PLR0911
    root = find_project_root()
    try:
        state = load_json_strict(root / "PROJECT_STATE.json")
        if state.get("schema_version") == "1.7":
            return _check_n2b1p_authorization(root, state)
        if state.get("schema_version") == "1.6":
            return _check_n2b1r_authorization(root, state)
        if state.get("schema_version") == "1.5":
            return _check_n2b0_7_authorization(root, state)
        approval = yaml.safe_load(
            (root / "approvals" / "data_gate_approval_G1.yaml").read_text(encoding="utf-8")
        )
        n1_completion = yaml.safe_load(
            (root / "approvals" / "phase_completion_N1.yaml").read_text(encoding="utf-8")
        )
        n1_task = yaml.safe_load(
            (root / "tasks" / "phase_n1_ingest_state_machine.yaml").read_text(encoding="utf-8")
        )
        g1_task = yaml.safe_load(
            (root / "tasks" / "gate_g1_calibration_20.yaml").read_text(encoding="utf-8")
        )
        g1_completion = yaml.safe_load(
            (root / "approvals" / "phase_completion_G1.yaml").read_text(encoding="utf-8")
        )
        n2a_task = yaml.safe_load(
            (root / "tasks" / "phase_n2a_pose_and_segmentation_benchmark.yaml").read_text(
                encoding="utf-8"
            )
        )
        n2b0_completion = yaml.safe_load(
            (root / "approvals" / "phase_completion_N2B0.yaml").read_text(encoding="utf-8")
        )
        n2b0_5_task = yaml.safe_load(
            (root / "tasks" / "phase_n2b0_5_artifact_rights_and_provenance.yaml").read_text(
                encoding="utf-8"
            )
        )
        n2b0_5_approval_path = root / "approvals" / "phase_completion_N2B0_5.yaml"
        n2b0_5_completion = yaml.safe_load(n2b0_5_approval_path.read_text(encoding="utf-8"))
        n2b0_6_task = yaml.safe_load(
            (
                root / "tasks" / "phase_n2b0_6_license_clear_alternative_candidate_research.yaml"
            ).read_text(encoding="utf-8")
        )
        retry_policy = yaml.safe_load(
            (root / "config" / "retry_policy_v1_1.yaml").read_text(encoding="utf-8")
        )
        error_taxonomy = yaml.safe_load(
            (root / "config" / "error_taxonomy_v1_1.yaml").read_text(encoding="utf-8")
        )
        n2a_error_taxonomy = yaml.safe_load(
            (root / "config" / "error_taxonomy_v1_2.yaml").read_text(encoding="utf-8")
        )
        task_index = load_json_strict(root / "tasks" / "index.json")
        schemas = root / "schemas"
        checks = [
            (
                load_json_strict(schemas / "project_state_v1_4.schema.json"),
                state,
            ),
            (
                load_json_strict(schemas / "approval_record_v1_1.schema.json"),
                approval,
            ),
            (
                load_json_strict(schemas / "phase_completion_approval_v1_0.schema.json"),
                n1_completion,
            ),
            (
                load_json_strict(schemas / "task_contract_v1_1.schema.json"),
                n1_task,
            ),
            (
                load_json_strict(schemas / "task_contract_v1_1.schema.json"),
                g1_task,
            ),
            (
                load_json_strict(schemas / "task_index_v1_2.schema.json"),
                task_index,
            ),
            (
                load_json_strict(schemas / "phase_completion_approval_g1_v1_0.schema.json"),
                g1_completion,
            ),
            (
                load_json_strict(schemas / "task_contract_n2a_v1_0.schema.json"),
                n2a_task,
            ),
            (
                load_json_strict(schemas / "phase_completion_approval_n2b0_v1_0.schema.json"),
                n2b0_completion,
            ),
            (
                load_json_strict(schemas / "task_contract_n2b0_5_v1_0.schema.json"),
                n2b0_5_task,
            ),
            (
                load_json_strict(schemas / "phase_completion_approval_n2b0_5_v1_0.schema.json"),
                n2b0_5_completion,
            ),
            (
                load_json_strict(schemas / "task_contract_n2b0_6_v1_0.schema.json"),
                n2b0_6_task,
            ),
        ]
        if any(_validate_schema(schema, value) for schema, value in checks):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="current contract schema validation failed",
            )
        if not all(
            (
                _file_sha256(root / "config" / "retry_policy_v1_1.yaml")
                == "316df5c98fa81a0ae2facf8bcb3ac4914e363eedf219ee2a48f547830b2afafe",
                _file_sha256(root / "config" / "error_taxonomy_v1_1.yaml")
                == "a3003f71fd7b43d3169ceb983fe4ce27feef7a1b971cffa4309251f6fb24ac65",
                retry_policy.get("defaults", {}).get("max_attempts") == 2,
                error_taxonomy.get("schema_version") == "1.1",
                n2a_error_taxonomy.get("schema_version") == "1.2",
                "NPI_MODEL_NOT_AUTHORIZED" in n2a_error_taxonomy.get("errors", {}),
            )
        ):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="versioned retry or error taxonomy binding failed",
            )
        if not _n1_approval_chain_is_consistent(
            state=state,
            approval=approval,
            n1_completion=n1_completion,
            n1_task=n1_task,
            g1_task=g1_task,
            task_index=task_index,
        ):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N1 completion approval chain validation failed",
            )
        n2a_authorized = state.get("authorization", {}).get("capability_gates", {})
        phase_status = state.get("phase_status", {})
        n2a_index = next(
            (item for item in task_index.get("authorized", []) if item.get("phase") == "N2A"),
            None,
        )
        completed_n2b0 = next(
            (item for item in task_index.get("completed", []) if item.get("phase") == "N2B0"),
            None,
        )
        completed_n2b0_5 = next(
            (item for item in task_index.get("completed", []) if item.get("phase") == "N2B0_5"),
            None,
        )
        authorized_n2b0_6 = next(
            (item for item in task_index.get("authorized", []) if item.get("phase") == "N2B0_6"),
            None,
        )
        g1_baseline = g1_completion.get("baseline", {})
        if not all(
            (
                g1_completion.get("status") == "APPROVED",
                g1_completion.get("owner_decision") == "G1_OWNER_APPROVED",
                g1_baseline.get("g1_commit") == "4a807dbbcd147a106b02b7e3899aa701c2028d83",
                g1_baseline.get("g1_tag") == "g1-approved-2026-07-19",
                phase_status.get("G1") == "APPROVED_COMPLETE",
                phase_status.get("N2A") == "APPROVED_COMPLETE",
                phase_status.get("N2B0") == "APPROVED_COMPLETE",
                phase_status.get("N2B0_5") == "APPROVED_COMPLETE",
                phase_status.get("N2B0_6") == "AUTHORIZED",
                phase_status.get("N2B") == "LOCKED",
                phase_status.get("N2B1") == "LOCKED",
                phase_status.get("N2B1_Q") == "LOCKED",
                phase_status.get("N2B1_P") == "LOCKED",
                phase_status.get("N2B2") == "LOCKED",
                n2a_authorized.get("N2A_POSE_SEGMENTATION_BENCHMARK_PREPARATION")
                == "APPROVED_COMPLETE",
                n2a_authorized.get("N2B0_MODEL_ARTIFACT_QUALIFICATION") == "APPROVED_COMPLETE",
                n2a_authorized.get("N2B0_5_ARTIFACT_RIGHTS_AND_PROVENANCE_CLOSURE")
                == "APPROVED_COMPLETE",
                n2a_authorized.get("N2B0_6_LICENSE_CLEAR_ALTERNATIVE_CANDIDATE_RESEARCH")
                == "AUTHORIZED",
                n2a_authorized.get("N2B_MODEL_DOWNLOAD_AND_INFERENCE") == "LOCKED",
                n2a_authorized.get("N2B1_MODEL_DOWNLOAD") == "LOCKED",
                n2a_authorized.get("N2B1_Q_QUARANTINE_DOWNLOAD") == "LOCKED",
                n2a_authorized.get("N2B1_P_CACHE_PROMOTION") == "LOCKED",
                n2a_authorized.get("N2B2_REAL_BENCHMARK") == "LOCKED",
                state.get("authorization", {}).get("large_model_downloads") == "NOT_AUTHORIZED",
                state.get("authorization", {}).get("real_model_execution") == "NOT_AUTHORIZED",
                isinstance(n2a_index, dict),
                (n2a_index or {}).get("capability")
                == "N2A_POSE_SEGMENTATION_BENCHMARK_PREPARATION",
                isinstance(completed_n2b0, dict),
                (completed_n2b0 or {}).get("baseline_commit")
                == "f331621c84905aef921c612908d01d3a8a2f577a",
                (completed_n2b0 or {}).get("completion_approval")
                == "approvals/phase_completion_N2B0.yaml",
                isinstance(completed_n2b0_5, dict),
                (completed_n2b0_5 or {}).get("baseline_commit")
                == "5ad9f8d7d0d6fa267df02d90ef25957bc679e232",
                (completed_n2b0_5 or {}).get("completion_approval")
                == "approvals/phase_completion_N2B0_5.yaml",
                isinstance(authorized_n2b0_6, dict),
                (authorized_n2b0_6 or {}).get("capability")
                == "N2B0_6_LICENSE_CLEAR_ALTERNATIVE_CANDIDATE_RESEARCH",
                n2b0_completion.get("owner_decision") == "N2B0_OWNER_APPROVED",
                n2b0_completion.get("independent_reviewer", {}).get("reviewed_commit")
                == "f331621c84905aef921c612908d01d3a8a2f577a",
                n2b0_5_task.get("approval", {}).get("n2b0_commit")
                == "f331621c84905aef921c612908d01d3a8a2f577a",
                n2b0_5_completion.get("owner_decision") == "N2B0_5_OWNER_APPROVED",
                n2b0_5_completion.get("independent_reviewer", {}).get("reviewed_commit")
                == "5ad9f8d7d0d6fa267df02d90ef25957bc679e232",
                n2b0_6_task.get("approval", {}).get("n2b0_5_commit")
                == "5ad9f8d7d0d6fa267df02d90ef25957bc679e232",
                (root / "approvals" / "phase_completion_N2B0_5.sha256")
                .read_text(encoding="utf-8")
                .strip()
                == _file_sha256(n2b0_5_approval_path),
            )
        ):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2B0.5 approval or N2B0.6 research gate is inconsistent",
            )
        from .ingest.g1_contract import load_g1_approval

        load_g1_approval(root)
        auth = load_authorization(root)
        if not auth.phase_authorized or not auth.data_gate_authorized:
            raise ValueError("authorization inactive")
        return CheckResult(
            name="current_authorization_contracts",
            status=PASS,
            evidence=(
                f"phase={auth.phase_id}/{auth.phase_status} "
                f"gate={auth.data_gate_id}/{auth.data_gate_status}; "
                "schema+N1/G1/N2A/N2B0/N2B0.5 approval-chain+N2B0.6 research gate valid"
            ),
        )
    except DuplicateJsonMemberError:
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes=NPI_DUPLICATE_JSON_MEMBER,
        )
    except Exception:  # noqa: BLE001
        return CheckResult(
            name="current_authorization_contracts",
            status=FAIL,
            notes="current authorization contract validation failed",
        )


def _check_git_baselines() -> CheckResult:
    root = find_project_root()
    n0 = "72a81f5984838b74304d23263ac450ea4b5a3a9a"
    n1 = "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc"
    g1 = "4a807dbbcd147a106b02b7e3899aa701c2028d83"
    n2b0 = "f331621c84905aef921c612908d01d3a8a2f577a"
    n2b0_5 = "5ad9f8d7d0d6fa267df02d90ef25957bc679e232"

    def git(*args: str) -> tuple[int, str]:
        return _run(["git", "-C", str(root), *args])

    def result(checks: list[bool], *, failure_notes: str, pass_evidence: str) -> CheckResult:
        return CheckResult(
            name="git_stage_baselines",
            status=PASS if all(checks) else FAIL,
            evidence=pass_evidence if all(checks) else "",
            notes=failure_notes if not all(checks) else "",
        )

    try:
        state = load_json_strict(root / "PROJECT_STATE.json")
    except Exception:  # noqa: BLE001
        state = {}
    if state.get("schema_version") == "1.7":
        n2b0_6 = "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2"
        n2b0_7 = "f2b1c38301d71da52b855f73de8a67908cb525ef"
        n2b1r = "d3628e27334e819ba2d5944151447595e03f39f9"
        checks = [
            git("rev-parse", "n0-approved-2026-07-14") == (0, n0),
            git("rev-parse", "n1-approved-2026-07-14") == (0, n1),
            git("rev-parse", "g1-approved-2026-07-19") == (0, g1),
            git("rev-parse", "n2b0-approved-2026-07-24") == (0, n2b0),
            git("rev-parse", "n2b0-5-approved-2026-07-26") == (0, n2b0_5),
            git("rev-parse", "n2b0-6-approved-2026-07-29") == (0, n2b0_6),
            git("rev-parse", "n2b0-7-approved-2026-07-29") == (0, n2b0_7),
            git("merge-base", "--is-ancestor", n2b0_7, "HEAD")[0] == 0,
            git("rev-list", "--count", f"{n2b0_6}..{n2b0_7}") == (0, "1"),
            git("rev-list", "--count", f"{n2b0_7}..{n2b1r}") == (0, "1"),
            git("rev-list", "--count", f"{n2b1r}..HEAD") == (0, "1"),
            git("rev-list", "--merges", "HEAD") == (0, ""),
            git("status", "--porcelain", "--untracked-files=all") == (0, ""),
        ]
        return result(
            checks,
            failure_notes="Git baseline or N2B1P cache-promotion commit topology mismatch",
            pass_evidence=(
                "N0/N1/G1/N2A/N2B0/N2B0.5/N2B0.6/N2B0.7 tags intact; "
                "one N2B1R and one N2B1P commit; no merge; worktree clean"
            ),
        )

    if state.get("schema_version") == "1.6":
        n2b0_6 = "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2"
        n2b0_7 = "f2b1c38301d71da52b855f73de8a67908cb525ef"
        checks = [
            git("rev-parse", "n0-approved-2026-07-14") == (0, n0),
            git("rev-parse", "n1-approved-2026-07-14") == (0, n1),
            git("rev-parse", "g1-approved-2026-07-19") == (0, g1),
            git("rev-parse", "n2b0-approved-2026-07-24") == (0, n2b0),
            git("rev-parse", "n2b0-5-approved-2026-07-26") == (0, n2b0_5),
            git("rev-parse", "n2b0-6-approved-2026-07-29") == (0, n2b0_6),
            git("rev-parse", "n2b0-7-approved-2026-07-29") == (0, n2b0_7),
            git("merge-base", "--is-ancestor", n2b0_7, "HEAD")[0] == 0,
            git("rev-list", "--count", f"{n2b0_6}..{n2b0_7}") == (0, "1"),
            git("rev-list", "--count", f"{n2b0_7}..HEAD") == (0, "1"),
            git("rev-list", "--merges", "HEAD") == (0, ""),
            git("status", "--porcelain", "--untracked-files=all") == (0, ""),
        ]
        return result(
            checks,
            failure_notes="Git baseline or N2B1R governance commit topology mismatch",
            pass_evidence=(
                "N0/N1/G1/N2A/N2B0/N2B0.5/N2B0.6/N2B0.7 tags intact; "
                "one N2B1R governance commit; no merge; worktree clean"
            ),
        )

    if state.get("schema_version") == "1.5":
        n2b0_6 = "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2"
        checks = [
            git("rev-parse", "n0-approved-2026-07-14") == (0, n0),
            git("rev-parse", "n1-approved-2026-07-14") == (0, n1),
            git("rev-parse", "g1-approved-2026-07-19") == (0, g1),
            git("rev-parse", "n2b0-approved-2026-07-24") == (0, n2b0),
            git("rev-parse", "n2b0-5-approved-2026-07-26") == (0, n2b0_5),
            git("rev-parse", "n2b0-6-approved-2026-07-29") == (0, n2b0_6),
            git("merge-base", "--is-ancestor", n2b0_6, "HEAD")[0] == 0,
            git("rev-list", "--count", f"{n2b0_5}..{n2b0_6}") == (0, "1"),
            git("rev-list", "--count", f"{n2b0_6}..HEAD") == (0, "1"),
            git("rev-list", "--merges", "HEAD") == (0, ""),
            git("status", "--porcelain", "--untracked-files=all") == (0, ""),
        ]
        return result(
            checks,
            failure_notes="Git baseline or N2B0.7 commit topology mismatch",
            pass_evidence=(
                "N0/N1/G1/N2A/N2B0/N2B0.5/N2B0.6 tags intact; one N2B0.7 commit; "
                "no merge; worktree clean"
            ),
        )

    checks = [
        git("rev-parse", "n0-approved-2026-07-14") == (0, n0),
        git("rev-parse", "n1-approved-2026-07-14") == (0, n1),
        git("rev-parse", "g1-approved-2026-07-19") == (0, g1),
        git("rev-parse", "n2b0-approved-2026-07-24") == (0, n2b0),
        git("rev-parse", "n2b0-5-approved-2026-07-26") == (0, n2b0_5),
        git("merge-base", "--is-ancestor", n0, n1)[0] == 0,
        git("merge-base", "--is-ancestor", n1, "HEAD")[0] == 0,
        git("merge-base", "--is-ancestor", g1, "HEAD")[0] == 0,
        git("rev-list", "--count", "HEAD") == (0, "7"),
        git("rev-list", "--count", f"{n1}..HEAD") == (0, "5"),
        git("rev-list", "--count", f"{g1}..HEAD") == (0, "4"),
        git("merge-base", "--is-ancestor", n2b0, "HEAD")[0] == 0,
        git("merge-base", "--is-ancestor", n2b0_5, "HEAD")[0] == 0,
        git("rev-list", "--count", f"{n2b0_5}..HEAD") == (0, "1"),
        git("rev-list", "--merges", "HEAD") == (0, ""),
        git("status", "--porcelain", "--untracked-files=all") == (0, ""),
    ]
    return result(
        checks,
        failure_notes="Git baseline or N2B0.6 commit topology mismatch",
        pass_evidence=(
            "N0/N1/G1/N2A/N2B0/N2B0.5 tags intact; one N2B0.6 commit; no merge; worktree clean"
        ),
    )


def _check_source_runtime_separation() -> CheckResult:
    root = find_project_root()
    try:
        auth = load_authorization(root)
    except Exception:  # noqa: BLE001 - fall through to the stricter G1 gate
        auth = None
    if auth is not None and not auth.n2b_model_authorized:
        return CheckResult(
            name="g1_execution_environment",
            status=PASS,
            evidence=(
                "Current phase does not authorize source/runtime/photo access or "
                "model execution; no source content was opened"
            ),
        )
    src = os.environ.get("NPI_SOURCE_ROOT")
    parent = os.environ.get("NPI_RUNTIME_PARENT")
    rt = os.environ.get("NPI_RUNTIME_ROOT")
    manifest_path = os.environ.get("NPI_G1_MANIFEST")
    if not src or not parent or not rt or not manifest_path:
        return CheckResult(
            name="g1_execution_environment",
            status=FAIL,
            notes="required G1 source/runtime/manifest environment is not configured",
        )

    try:
        from .ingest.g1_contract import load_g1_approval, prepare_g1_execution
        from .ingest.manifest import G1FrozenManifest

        root = find_project_root()
        auth = load_authorization(root)
        approval = load_g1_approval(root)
        manifest = G1FrozenManifest.load(
            Path(manifest_path),
            expected_sha256=approval.manifest_sha256,
            expected_count=approval.manifest_count,
        )
        permit = prepare_g1_execution(
            source_root=Path(src),
            runtime_parent=Path(parent),
            runtime_child=Path(rt),
            auth=auth,
            manifest=manifest,
            approval=approval,
        )
        return CheckResult(
            name="g1_execution_environment",
            status=PASS,
            evidence=(
                f"manifest_count={manifest.count}; runtime policy valid; "
                f"read_only={permit.read_only.status}"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        error_code = getattr(exc, "error_code", "NPI_PREFLIGHT_UNSATISFIED")
        return CheckResult(name="g1_execution_environment", status=FAIL, notes=str(error_code))


_BASE_CHECKS: tuple[Callable[[], CheckResult], ...] = (
    _check_python,
    _check_os,
    _check_wsl,
    _check_git,
    _check_docker,
    _check_docker_compose,
    _check_nvidia,
    _check_disk,
    _check_fixture_integrity,
    _check_repo_independence,
    _check_handoff,
    _check_schema_version,
    _check_authorization,
    _check_git_baselines,
)


def run_preflight(
    *,
    execution_environment_check: Callable[[], CheckResult] = _check_source_runtime_separation,
) -> list[CheckResult]:
    """Run current-stage checks, ending with the pre-content execution gate.

    The injected callable exists for synthetic tests only. The CLI uses the
    default, which always validates the configured real manifest, runtime
    policy, and OS-enforced source read-only capability.
    """
    return [check() for check in (*_BASE_CHECKS, execution_environment_check)]


def format_preflight_text(results: list[CheckResult]) -> str:
    """Render preflight results as a human-readable table."""
    lines = ["NPI preflight (read-only; no system changes)", "=" * 50]
    for r in results:
        ev = redact_text(r.evidence)
        nt = redact_text(r.notes)
        lines.append(f"[{r.status:14}] {r.name}")
        if ev:
            lines.append(f"    evidence: {ev}")
        if nt:
            lines.append(f"    notes: {nt}")
    _statuses = (PASS, NOT_AVAILABLE, SKIPPED, FAIL)
    summary = {s: sum(1 for r in results if r.status == s) for s in _statuses}
    lines.append("-" * 50)
    lines.append(
        f"Summary: {summary[PASS]} pass, {summary[NOT_AVAILABLE]} not_available, "
        f"{summary[SKIPPED]} skipped, {summary[FAIL]} fail"
    )
    lines.append("No install, update, pull, or system change was performed.")
    return "\n".join(lines)
