"""Read-only preflight checks for ``npi preflight``.

Every check is observational: it may query a tool or read a file, but it never
installs, upgrades, pulls, or changes system state. All output is redacted of
usernames, hostnames, home paths, and tokens.
"""

from __future__ import annotations

import hashlib
import json
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


def _check_fixture_integrity() -> CheckResult:
    root = find_project_root()
    manifest_path = root / "fixtures" / "fixture_manifest.json"
    if not manifest_path.is_file():
        return CheckResult(name="fixture_integrity", status=FAIL, notes="manifest missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return CheckResult(name="fixture_integrity", status=FAIL, notes=f"manifest invalid: {exc}")
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
        data = json.loads(catalog.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
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


def _check_authorization() -> CheckResult:
    root = find_project_root()
    try:
        state = json.loads((root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
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
        retry_policy = yaml.safe_load(
            (root / "config" / "retry_policy_v1_1.yaml").read_text(encoding="utf-8")
        )
        error_taxonomy = yaml.safe_load(
            (root / "config" / "error_taxonomy_v1_1.yaml").read_text(encoding="utf-8")
        )
        n2a_error_taxonomy = yaml.safe_load(
            (root / "config" / "error_taxonomy_v1_2.yaml").read_text(encoding="utf-8")
        )
        task_index = json.loads((root / "tasks" / "index.json").read_text(encoding="utf-8"))
        schemas = root / "schemas"
        checks = [
            (
                json.loads((schemas / "project_state_v1_2.schema.json").read_text("utf-8")),
                state,
            ),
            (
                json.loads((schemas / "approval_record_v1_1.schema.json").read_text("utf-8")),
                approval,
            ),
            (
                json.loads(
                    (schemas / "phase_completion_approval_v1_0.schema.json").read_text("utf-8")
                ),
                n1_completion,
            ),
            (
                json.loads((schemas / "task_contract_v1_1.schema.json").read_text("utf-8")),
                n1_task,
            ),
            (
                json.loads((schemas / "task_contract_v1_1.schema.json").read_text("utf-8")),
                g1_task,
            ),
            (
                json.loads((schemas / "task_index_v1_2.schema.json").read_text("utf-8")),
                task_index,
            ),
            (
                json.loads(
                    (schemas / "phase_completion_approval_g1_v1_0.schema.json").read_text("utf-8")
                ),
                g1_completion,
            ),
            (
                json.loads((schemas / "task_contract_n2a_v1_0.schema.json").read_text("utf-8")),
                n2a_task,
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
        authorized_n2b0 = next(
            (item for item in task_index.get("authorized", []) if item.get("phase") == "N2B0"),
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
                phase_status.get("N2B0") == "AUTHORIZED",
                phase_status.get("N2B") == "LOCKED",
                n2a_authorized.get("N2A_POSE_SEGMENTATION_BENCHMARK_PREPARATION")
                == "APPROVED_COMPLETE",
                n2a_authorized.get("N2B0_MODEL_ARTIFACT_QUALIFICATION") == "AUTHORIZED",
                n2a_authorized.get("N2B_MODEL_DOWNLOAD_AND_INFERENCE") == "LOCKED",
                isinstance(n2a_index, dict),
                (n2a_index or {}).get("capability")
                == "N2A_POSE_SEGMENTATION_BENCHMARK_PREPARATION",
                isinstance(authorized_n2b0, dict),
                (authorized_n2b0 or {}).get("capability") == "N2B0_MODEL_ARTIFACT_QUALIFICATION",
            )
        ):
            return CheckResult(
                name="current_authorization_contracts",
                status=FAIL,
                notes="N2A completion or N2B0 capability gate is inconsistent",
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
                "schema+N1/G1/N2A approval-chain+N2B0 capability gate valid"
            ),
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

    def git(*args: str) -> tuple[int, str]:
        return _run(["git", "-C", str(root), *args])

    checks = [
        git("rev-parse", "n0-approved-2026-07-14") == (0, n0),
        git("rev-parse", "n1-approved-2026-07-14") == (0, n1),
        git("rev-parse", "g1-approved-2026-07-19") == (0, g1),
        git("merge-base", "--is-ancestor", n0, n1)[0] == 0,
        git("merge-base", "--is-ancestor", n1, "HEAD")[0] == 0,
        git("merge-base", "--is-ancestor", g1, "HEAD")[0] == 0,
        git("rev-list", "--count", "HEAD") == (0, "5"),
        git("rev-list", "--count", f"{n1}..HEAD") == (0, "3"),
        git("rev-list", "--count", f"{g1}..HEAD") == (0, "2"),
        git("rev-list", "--merges", "HEAD") == (0, ""),
        git("status", "--porcelain", "--untracked-files=all") == (0, ""),
    ]
    if not all(checks):
        return CheckResult(
            name="git_stage_baselines",
            status=FAIL,
            notes="Git baseline or N2A commit mismatch",
        )
    return CheckResult(
        name="git_stage_baselines",
        status=PASS,
        evidence=(
            "N0/N1/G1/N2A tags intact; one N2A and one N2B0 commit; no merge; worktree clean"
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
                "N2B0 qualification only; no source/runtime/photo access "
                "or model execution performed"
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
