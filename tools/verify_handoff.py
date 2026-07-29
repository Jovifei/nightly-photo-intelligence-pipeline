#!/usr/bin/env python3
"""Verify the current N2B1R governed handoff without performing work.

This verifier never opens a source photo, sends a network request, installs a
wheel, or writes repository/runtime state.  It binds the exact local-research
authorization, the immutable approved baselines, and every tracked file.
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
CURRENT_PHASE = "N2B1R"
CURRENT_TASK = "tasks/phase_n2b1r_local_research_model_acquisition.yaml"
CURRENT_CAPABILITY = "N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION"

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
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def load_json(rel: str) -> Any:
    try:
        return json.loads(
            (ROOT / rel).read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except Exception as exc:  # noqa: BLE001 - verifier must report instead of crash
        fail(f"{rel}: cannot strict-parse JSON: {type(exc).__name__}")
        return {}


def load_yaml(rel: str) -> Any:
    try:
        import yaml

        return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - verifier must report instead of crash
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


def _validate(schema_rel: str, value: object) -> bool:
    try:
        from jsonschema import Draft202012Validator, FormatChecker

        schema = load_json(schema_rel)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        return not list(validator.iter_errors(value))
    except Exception:  # noqa: BLE001 - a schema failure is a verification failure
        return False


def check_required_files() -> None:
    required = (
        "MASTER_EXECUTION_CONTRACT.md",
        "AGENTS.md",
        "PROJECT_STATE.json",
        CURRENT_TASK,
        "tasks/index.json",
        "MANIFEST.sha256",
        "approvals/phase_completion_N2B0_7.yaml",
        "approvals/phase_completion_N2B0_7.sha256",
        "approvals/owner_local_research_execution_N2B1R_to_N5R.yaml",
        "research/N2B1R_local_research_artifact_register.json",
        "schemas/project_state_v1_6.schema.json",
        "schemas/phase_completion_approval_n2b0_7_v1_0.schema.json",
        "schemas/owner_local_research_execution_v1_0.schema.json",
        "schemas/task_contract_n2b1r_v1_0.schema.json",
        "schemas/n2b1r_artifact_register_v1.schema.json",
    )
    missing = [rel for rel in required if not (ROOT / rel).is_file()]
    if missing:
        fail("missing required current-stage files: " + ", ".join(missing))
    else:
        ok("required N2B1R contracts, register, and approval files exist")


def check_current_authorization() -> None:
    state = load_json("PROJECT_STATE.json")
    completion = load_yaml("approvals/phase_completion_N2B0_7.yaml")
    research_approval = load_yaml("approvals/owner_local_research_execution_N2B1R_to_N5R.yaml")
    task = load_yaml(CURRENT_TASK)
    register = load_json("research/N2B1R_local_research_artifact_register.json")
    index = load_json("tasks/index.json")
    documents = (
        ("schemas/project_state_v1_6.schema.json", state),
        ("schemas/phase_completion_approval_n2b0_7_v1_0.schema.json", completion),
        ("schemas/owner_local_research_execution_v1_0.schema.json", research_approval),
        ("schemas/task_contract_n2b1r_v1_0.schema.json", task),
        ("schemas/n2b1r_artifact_register_v1.schema.json", register),
        ("schemas/task_index_v1_2.schema.json", index),
    )
    if not all(_validate(schema, document) for schema, document in documents):
        fail("current N2B1R authorization schema validation failed")
        return
    auth = state.get("authorization", {})
    phase_status = state.get("phase_status", {})
    gates = auth.get("capability_gates", {}) if isinstance(auth, dict) else {}
    active = auth.get("active_execution", {}) if isinstance(auth, dict) else {}
    current_index = next(
        (
            item
            for item in index.get("authorized", [])
            if isinstance(item, dict) and item.get("phase") == CURRENT_PHASE
        ),
        None,
    )
    locked = (
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
    valid = all(
        (
            state.get("schema_version") == "1.6",
            completion.get("owner_decision") == "N2B0_7_OWNER_APPROVED",
            completion.get("baseline", {}).get("n2b0_7_commit")
            == "f2b1c38301d71da52b855f73de8a67908cb525ef",
            (ROOT / "approvals" / "phase_completion_N2B0_7.sha256")
            .read_text(encoding="utf-8")
            .strip()
            == sha256(ROOT / "approvals" / "phase_completion_N2B0_7.yaml"),
            research_approval.get("start_phase", {}).get("status") == "AUTHORIZED_NOW",
            phase_status.get("N2B0_7") == "APPROVED_COMPLETE",
            phase_status.get(CURRENT_PHASE) == "AUTHORIZED",
            task.get("phase", {}).get("id") == CURRENT_PHASE,
            task.get("phase", {}).get("status") == "AUTHORIZED",
            task.get("capability") == CURRENT_CAPABILITY,
            task.get("mandatory_stop", {}).get("value") is True,
            gates.get(CURRENT_CAPABILITY) == "AUTHORIZED",
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
            all(phase_status.get(phase) == "LOCKED" for phase in locked),
            isinstance(current_index, dict),
            current_index.get("file") == Path(CURRENT_TASK).name,
            current_index.get("capability") == CURRENT_CAPABILITY,
            register.get("weights_rights", {}).get("status") == "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
            len(register.get("artifacts", [])) == 3,
            all(item.get("official_sha256") is None for item in register.get("artifacts", [])),
            state.get("required_stop_after")
            == {
                "condition": "N2B1R_ACQUISITION_AWAITING_LOCAL_VERIFICATION",
                "next_action": "VERIFY_QUARANTINE_AND_CREATE_N2B1P_AUTHORIZATION",
            },
        )
    )
    if not valid:
        fail("current N2B1R authorization boundary is inconsistent or broadened")
    else:
        ok("N2B1R is research-only; inference and real-photo entry points remain locked")


def check_baselines() -> None:
    expected = {
        "n0-approved-2026-07-14": "72a81f5984838b74304d23263ac450ea4b5a3a9a",
        "n1-approved-2026-07-14": "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc",
        "g1-approved-2026-07-19": "4a807dbbcd147a106b02b7e3899aa701c2028d83",
        "n2a-approved-2026-07-22": "f79d2df504622ff82aa5e53d1486310bbea9985a",
        "n2b0-approved-2026-07-24": "f331621c84905aef921c612908d01d3a8a2f577a",
        "n2b0-5-approved-2026-07-26": "5ad9f8d7d0d6fa267df02d90ef25957bc679e232",
        "n2b0-6-approved-2026-07-29": "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2",
        "n2b0-7-approved-2026-07-29": "f2b1c38301d71da52b855f73de8a67908cb525ef",
    }
    mismatched = [tag for tag, commit in expected.items() if git("rev-parse", tag) != (0, commit)]
    if mismatched:
        fail("immutable baseline tag mismatch: " + ", ".join(mismatched))
    elif git("merge-base", "--is-ancestor", expected["n2b0-7-approved-2026-07-29"], "HEAD")[0] != 0:
        fail("N2B0.7 approved baseline is not an ancestor of HEAD")
    elif git("rev-list", "--merges", "HEAD") != (0, ""):
        fail("current candidate contains a merge commit")
    else:
        ok("all immutable approved tags and the no-merge ancestry are intact")


def check_manifest() -> None:
    listed: dict[str, str] = {}
    try:
        for line in (ROOT / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
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
    tracked = {rel for rel in tracked_text.splitlines() if rel and rel != "MANIFEST.sha256"}
    if rc != 0 or set(listed) != tracked:
        fail("MANIFEST.sha256 does not bind exactly the tracked current-stage file set")
        return
    mismatches = [rel for rel, digest in listed.items() if sha256(ROOT / rel) != digest]
    if mismatches:
        fail("MANIFEST.sha256 hash mismatch: " + ", ".join(sorted(mismatches)))
    elif git("status", "--porcelain", "--untracked-files=all") != (0, ""):
        fail("worktree is not clean")
    else:
        ok("MANIFEST.sha256 binds every tracked current-stage file; worktree is clean")


def check_sensitive_paths() -> None:
    rc, tracked_text = git("ls-files")
    if rc != 0:
        fail("cannot inspect tracked paths")
        return
    suffixes = (".db", ".sqlite", ".sqlite3", ".pth", ".pt", ".onnx", ".safetensors")
    violations: list[str] = []
    for rel in (line for line in tracked_text.splitlines() if line):
        if rel.casefold().endswith(suffixes):
            violations.append(rel)
    if violations:
        fail("tracked model or runtime artifact: " + ", ".join(sorted(violations)))
    else:
        ok("no tracked model, cache, database, or source-image artifact")


def archival_n0_notice() -> int:
    """Retain the historical verifier mode as an explicit non-passing result."""
    print("N0_ARCHIVAL_SUPERSEDED")
    print("The original N0-only verifier cannot validate the governed current-stage tree.")
    print("Use `python tools/verify_handoff.py` for the current N2B1R integrity gate.")
    return 8


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--archival-n0":
        return archival_n0_notice()
    if len(sys.argv) != 1:
        print("usage: verify_handoff.py [--archival-n0]", file=sys.stderr)
        return 2
    check_required_files()
    check_current_authorization()
    check_baselines()
    check_manifest()
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
    print(
        "HANDOFF_VALID: N2B1R local-research acquisition only; inference and photos remain locked"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
