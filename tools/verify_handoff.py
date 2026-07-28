#!/usr/bin/env python3
"""Verify the current governed NPI handoff without performing any work.

The repository began as an N0 archival package.  That historical package is
not an executable authority after Owner-approved phase transitions.  This
verifier binds the checked-in current-stage documents and every tracked file
to ``MANIFEST.sha256``.  It never downloads, installs, opens source photos,
or changes repository state.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CURRENT_PHASE = "N2B0_7"
CURRENT_TASK = "tasks/phase_n2b0_7_gpu_native_qualification.yaml"
CURRENT_CAPABILITY = "N2B0_7_GPU_NATIVE_QUALIFICATION"

errors: list[str] = []
passes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def ok(message: str) -> None:
    passes.append(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON member: {key}")
        value[key] = item
    return value


def load_json(rel: str) -> Any:
    try:
        return json.loads(
            (ROOT / rel).read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except Exception as exc:  # noqa: BLE001 - report rather than crash
        fail(f"{rel}: cannot strict-parse JSON: {type(exc).__name__}")
        return {}


def load_yaml(rel: str) -> Any:
    try:
        import yaml

        return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report rather than crash
        fail(f"{rel}: cannot parse YAML: {type(exc).__name__}")
        return {}


def git(*args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, type(exc).__name__
    return result.returncode, result.stdout.strip()


def check_required_files() -> None:
    required = [
        "MASTER_EXECUTION_CONTRACT.md",
        "AGENTS.md",
        "PROJECT_STATE.json",
        CURRENT_TASK,
        "tasks/index.json",
        "MANIFEST.sha256",
        "research/N2B0_7_torchvision_artifact_qualification.json",
        "approvals/phase_completion_N2B0_6.yaml",
        "approvals/phase_completion_N2B0_6.sha256",
        "approvals/owner_continuous_authorization_N2B0_7_to_N3A.yaml",
        "reports/N2B0_7_owner_decision_packet.md",
        "tools/verify_handoff.py",
    ]
    missing = [rel for rel in required if not (ROOT / rel).is_file()]
    if missing:
        fail("missing required current-stage files: " + ", ".join(missing))
    else:
        ok("required current-stage files exist")


def check_current_authorization() -> None:
    state = load_json("PROJECT_STATE.json")
    task = load_yaml(CURRENT_TASK)
    index = load_json("tasks/index.json")
    qualification = load_json("research/N2B0_7_torchvision_artifact_qualification.json")
    if not all(isinstance(value, dict) for value in (state, task, index, qualification)):
        return
    phase_status = state.get("phase_status", {})
    auth = state.get("authorization", {})
    gates = auth.get("capability_gates", {}) if isinstance(auth, dict) else {}
    active_execution = auth.get("active_execution", {}) if isinstance(auth, dict) else {}
    authorized = index.get("authorized", [])
    current_index = next(
        (
            entry
            for entry in authorized
            if isinstance(entry, dict) and entry.get("phase") == CURRENT_PHASE
        ),
        None,
    )
    locked = ("N2B", "N2B1", "N2B1_Q", "N2B1_P", "N2B2", "N3", "N4", "N5", "N6", "N7", "N8")
    valid = all(
        (
            state.get("schema_version") == "1.5",
            auth.get("phase") == {"id": "N1", "status": "APPROVED_COMPLETE"},
            auth.get("data_gate") == {"id": "G1_CALIBRATION_20", "status": "AUTHORIZED"},
            phase_status.get(CURRENT_PHASE) == "AUTHORIZED",
            task.get("phase", {}).get("id") == CURRENT_PHASE,
            task.get("phase", {}).get("status") == "AUTHORIZED",
            task.get("capability") == CURRENT_CAPABILITY,
            task.get("mandatory_stop", {}).get("value") is True,
            task.get("data_gate", {}).get("allowed_assets")
            == "official source, license, release, wheel-index, and environment metadata only; no real photo reads",
            gates.get(CURRENT_CAPABILITY) == "AUTHORIZED",
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
            all(phase_status.get(phase) == "LOCKED" for phase in locked),
            isinstance(current_index, dict),
            current_index.get("file") == Path(CURRENT_TASK).name,
            current_index.get("capability") == CURRENT_CAPABILITY,
            (ROOT / "approvals" / "phase_completion_N2B0_6.yaml").is_file(),
            (ROOT / "approvals" / "phase_completion_N2B0_6.sha256").is_file(),
        )
    )
    if not valid:
        fail("current N2B0.7 authorization boundary is inconsistent or broadened")
    else:
        ok("N2B0.7 fail-closed qualification is coherent; model/photo stages remain locked")


def check_baselines() -> None:
    expected = {
        "n0-approved-2026-07-14": "72a81f5984838b74304d23263ac450ea4b5a3a9a",
        "n1-approved-2026-07-14": "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc",
        "g1-approved-2026-07-19": "4a807dbbcd147a106b02b7e3899aa701c2028d83",
        "n2a-approved-2026-07-22": "f79d2df504622ff82aa5e53d1486310bbea9985a",
        "n2b0-approved-2026-07-24": "f331621c84905aef921c612908d01d3a8a2f577a",
        "n2b0-5-approved-2026-07-26": "5ad9f8d7d0d6fa267df02d90ef25957bc679e232",
        "n2b0-6-approved-2026-07-29": "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2",
    }
    mismatched = [tag for tag, commit in expected.items() if git("rev-parse", tag) != (0, commit)]
    if mismatched:
        fail("immutable baseline tag mismatch: " + ", ".join(mismatched))
        return
    if git("merge-base", "--is-ancestor", expected["n2b0-5-approved-2026-07-26"], "HEAD")[0] != 0:
        fail("N2B0.5 approved baseline is not an ancestor of HEAD")
    elif git("rev-list", "--merges", "HEAD") != (0, ""):
        fail("current candidate contains a merge commit")
    else:
        ok("N0/N1/G1/N2A/N2B0/N2B0.5 approved tags and ancestry are intact")


def check_manifest() -> None:
    path = ROOT / "MANIFEST.sha256"
    listed: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or rel in listed:
                raise ValueError("invalid digest or duplicate path")
            listed[rel] = digest
    except (OSError, ValueError) as exc:
        fail(f"MANIFEST.sha256 is invalid: {type(exc).__name__}")
        return
    rc, tracked_text = git("ls-files")
    if rc != 0:
        fail("cannot enumerate tracked files")
        return
    tracked = {rel for rel in tracked_text.splitlines() if rel and rel != "MANIFEST.sha256"}
    if set(listed) != tracked:
        fail("MANIFEST.sha256 does not bind exactly the tracked current-stage file set")
        return
    mismatches = [rel for rel, digest in listed.items() if sha256(ROOT / rel) != digest]
    if mismatches:
        fail("MANIFEST.sha256 hash mismatch: " + ", ".join(sorted(mismatches)))
        return
    if git("status", "--porcelain", "--untracked-files=all") != (0, ""):
        fail("worktree is not clean")
        return
    ok("MANIFEST.sha256 binds every tracked current-stage file; worktree is clean")


def check_n2b0_6_completion_hash() -> None:
    approval = ROOT / "approvals" / "phase_completion_N2B0_6.yaml"
    digest = ROOT / "approvals" / "phase_completion_N2B0_6.sha256"
    try:
        expected = digest.read_text(encoding="utf-8").strip()
    except OSError:
        fail("N2B0.6 completion approval digest is absent")
        return
    if not re.fullmatch(r"[0-9a-f]{64}", expected) or expected != sha256(approval):
        fail("N2B0.6 completion approval digest mismatch")
        return
    ok("N2B0.6 completion approval is bound by its local SHA-256")


def check_sensitive_paths() -> None:
    rc, tracked_text = git("ls-files")
    if rc != 0:
        fail("cannot inspect tracked paths for sensitive content")
        return
    forbidden_suffixes = (".db", ".sqlite", ".sqlite3", ".pth", ".pt", ".onnx", ".safetensors")
    # These source files contain the detection expressions themselves, not
    # user data.  They are still covered by the exact manifest and review.
    pattern_source_files = {
        "src/nightly_photo_intelligence_pipeline/redaction.py",
        "tools/sensitive_file_scan.py",
        "tools/verify_handoff.py",
    }
    violations: list[str] = []
    for rel in (line for line in tracked_text.splitlines() if line):
        lower = rel.casefold()
        if lower.endswith(forbidden_suffixes):
            violations.append(rel)
            continue
        if rel in pattern_source_files:
            continue
        try:
            content = (ROOT / rel).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if re.search(r"(?i)(?:[a-z]:\\\\users\\\\(?!<|owner(?:\\\\|$))|/home/(?!<))", content):
            violations.append(rel)
    if violations:
        fail("tracked sensitive path or model artifact: " + ", ".join(sorted(set(violations))))
    else:
        ok("no tracked model artifacts or likely personal absolute paths")


def archival_n0_notice() -> int:
    print("N0_ARCHIVAL_SUPERSEDED")
    print("The original N0-only verifier cannot validate a governed N2B0.7 tree.")
    print("Use `python tools/verify_handoff.py` for the current N2B0.7 integrity gate.")
    return 8


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print("CURRENT_STAGE_HANDOFF_VERIFIER")
        print("Verifies the governed N2B0.7 tracked-file, baseline, and authorization chain.")
        return 0
    if len(sys.argv) == 2 and sys.argv[1] == "--archival-n0":
        return archival_n0_notice()
    if len(sys.argv) != 1:
        print("usage: verify_handoff.py [--archival-n0]", file=sys.stderr)
        return 2

    check_required_files()
    check_current_authorization()
    check_baselines()
    check_manifest()
    check_n2b0_6_completion_hash()
    check_sensitive_paths()
    print("NPI current-stage handoff verification")
    print("======================================")
    for message in passes:
        print(f"PASS: {message}")
    for message in errors:
        print(f"FAIL: {message}")
    print(f"Summary: {len(passes)} pass, {len(errors)} fail")
    if errors:
        print("HANDOFF_INVALID: current-stage work must not continue")
        return 1
    print("HANDOFF_VALID: N2B0.7 metadata-only qualification only; follow-on stages remain locked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
