"""Verify this delivery-only commit. Not the pipeline handoff/quality gate.

Run before applying the E1 repair. The runtime base remains 835007b; only the
review_stages/E1 subtree may be added. No original file or approval may change.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

BASE = "835007b3cf12cd19a23cbd476545a2d10cf49c50"
PREFIX = "review_stages/E1/"
FILES = {
    "README.md", "NEXT_CODEX.md", "STATE.json", "FILES.sha256", "verify_delivery.py",
    "apply_runtime_fixes.py", "test_stage.py", "payload/worker_dispatch.py",
    "payload/legacy_s20_binding.py",
}


def git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(name, None)
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                          timeout=30, env=env).stdout


def verify(root: Path) -> dict[str, object]:
    head = git(root, "rev-parse", "HEAD").decode().strip()
    if git(root, "rev-list", "--parents", "-n", "1", "HEAD").decode().split() != [head, BASE]:
        raise ValueError("E1_EXPECTED_ONE_DIRECT_CHILD")
    if git(root, "rev-list", "--merges", "HEAD").strip():
        raise ValueError("E1_MERGE_NOT_ALLOWED")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("E1_WORKTREE_NOT_CLEAN")
    rows = git(root, "diff", "--name-status", "--no-renames", BASE, "HEAD").decode().splitlines()
    if set(rows) != {"A\t" + PREFIX + name for name in FILES}:
        raise ValueError("E1_FROZEN_RUNTIME_CHANGED_OR_DELIVERY_INCOMPLETE")
    manifest = git(root, "show", "HEAD:" + PREFIX + "FILES.sha256").decode()
    actual: dict[str, str] = {}
    for row in manifest.splitlines():
        digest, name = row.split("  ", 1)
        if not re.fullmatch("[0-9a-f]{64}", digest) or name in actual:
            raise ValueError("E1_MANIFEST_INVALID")
        actual[name] = digest
    if set(actual) != FILES - {"FILES.sha256"}:
        raise ValueError("E1_MANIFEST_SET_MISMATCH")
    for name, expected in actual.items():
        content = git(root, "show", "HEAD:" + PREFIX + name)
        if hashlib.sha256(content).hexdigest() != expected:
            raise ValueError("E1_MANIFEST_HASH_MISMATCH")
    # Diff exact-set validation above covers ALL old tracked files, including
    # source, tests, root MANIFEST, PROJECT_STATE, approvals, and old reports.
    return {
        "result": "E1_REPAIR_DELIVERY_VERIFIED_NOT_RUNTIME_QUALIFIED",
        "head": head, "runtime_base": BASE, "delivery_files": len(FILES),
        "original_runtime_files_unchanged": True, "execution_authorized": False,
        "next_stage": "E2_APPLY_INTEGRATE_AND_QUALIFY_ON_WINDOWS_312",
    }


def main() -> int:
    try:
        report = verify(Path(__file__).resolve().parents[2])
    except (OSError, ValueError, subprocess.SubprocessError):
        print('{"result":"E1_DELIVERY_INVALID","execution_authorized":false}')
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
