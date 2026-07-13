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

from ._paths import find_project_root
from .domain.authorization import load_authorization
from .redaction import redact_text

# Status values (do not conflate SKIPPED with PASS).
PASS = "PASS"
NOT_AVAILABLE = "NOT_AVAILABLE"
SKIPPED = "SKIPPED"
FAIL = "FAIL"

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
        return CheckResult(
            name="disk_free",
            status=PASS,
            evidence=f"project drive free: {free_gb:.1f} GiB",
        )
    except OSError as exc:
        return CheckResult(name="disk_free", status=FAIL, notes=str(exc))


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
        return CheckResult(name="handoff_integrity", status=FAIL, notes="MANIFEST.sha256 missing")
    listed: dict[str, str] = {}
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            digest, rel = line.split("  ", 1)
        except ValueError:
            return CheckResult(
                name="handoff_integrity", status=FAIL, notes=f"bad manifest line: {line[:40]}"
            )
        listed[rel] = digest
    missing: list[str] = []
    mismatched: list[str] = []
    for rel, digest in listed.items():
        p = root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        if actual != digest:
            mismatched.append(rel)
    if missing or mismatched:
        return CheckResult(
            name="handoff_integrity",
            status=FAIL,
            notes=f"missing={len(missing)} mismatched={len(mismatched)}",
        )
    return CheckResult(
        name="handoff_integrity",
        status=PASS,
        evidence=f"{len(listed)} contract files intact (new N0 files allowed)",
    )


def _check_schema_version() -> CheckResult:
    root = find_project_root()
    catalog = root / "schemas" / "schema_catalog.json"
    if not catalog.is_file():
        return CheckResult(name="schema_version", status=NOT_AVAILABLE, notes="catalog missing")
    try:
        data = json.loads(catalog.read_text(encoding="utf-8"))
        return CheckResult(
            name="schema_version",
            status=PASS,
            evidence=f"catalog_version={data.get('catalog_version', 'unknown')}",
        )
    except json.JSONDecodeError as exc:
        return CheckResult(name="schema_version", status=FAIL, notes=str(exc))


def _check_authorization() -> CheckResult:
    try:
        auth = load_authorization()
        return CheckResult(
            name="authorization",
            status=PASS,
            evidence=(
                f"phase={auth.phase_id}/{auth.phase_status} "
                f"gate={auth.data_gate_id}/{auth.data_gate_status}"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        return CheckResult(name="authorization", status=FAIL, notes=str(exc))


def _check_source_runtime_separation() -> CheckResult:
    src = os.environ.get("NPI_SOURCE_ROOT")
    rt = os.environ.get("NPI_RUNTIME_ROOT")
    if not src or not rt:
        return CheckResult(
            name="source_runtime_separation",
            status=SKIPPED,
            notes="NPI_SOURCE_ROOT / NPI_RUNTIME_ROOT not set (configure before N1)",
        )
    from .domain.errors import NpiError
    from .ingest.source_guard import validate_roots

    try:
        validate_roots(Path(src), Path(rt))
        return CheckResult(
            name="source_runtime_separation", status=PASS, evidence="roots separated"
        )
    except NpiError as exc:
        return CheckResult(name="source_runtime_separation", status=FAIL, notes=exc.error_code)


_CHECKS: list[Callable[[], CheckResult]] = [
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
    _check_source_runtime_separation,
]


def run_preflight() -> list[CheckResult]:
    """Run all preflight checks and return their results."""
    return [check() for check in _CHECKS]


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
