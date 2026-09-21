"""Validate the standalone Real20 preparation branch, not the ML runtime gate."""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
from pathlib import Path

BASE = "ffc4130823c1308f089b835c766e341ec2173e82"
PREFIX = "real20_transition/"
FILES = {"prepare.py", "test_prepare.py", "verify_delivery.py", "README.md",
         "NEXT_CODEX.md", "STATE.json", "FILES.sha256"}


def git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(name, None)
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                          timeout=30, env=env).stdout


def verify(root: Path) -> dict[str, object]:
    head = git(root, "rev-parse", "HEAD").decode().strip()
    git(root, "merge-base", "--is-ancestor", BASE, "HEAD")
    if git(root, "rev-list", "--merges", BASE + "..HEAD").strip():
        raise ValueError("R0_MERGE_NOT_ALLOWED")
    if git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
        raise ValueError("R0_WORKTREE_NOT_CLEAN")
    rows = git(root, "diff", "--name-status", "--no-renames", BASE, "HEAD").decode().splitlines()
    if set(rows) != {"A\t" + PREFIX + name for name in FILES}:
        raise ValueError("R0_UNEXPECTED_CHANGE_OR_MISSING_FILE")
    manifest = git(root, "show", "HEAD:" + PREFIX + "FILES.sha256").decode()
    found = {}
    for line in manifest.splitlines():
        digest, name = line.split("  ", 1)
        if name in found or len(digest) != 64:
            raise ValueError("R0_BAD_MANIFEST")
        found[name] = digest
    if set(found) != FILES - {"FILES.sha256"}:
        raise ValueError("R0_MANIFEST_SET_MISMATCH")
    for name, expected in found.items():
        data = git(root, "show", "HEAD:" + PREFIX + name)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("R0_MANIFEST_DIGEST_MISMATCH")
    return {"status": "R0_PREPARATION_BRANCH_VERIFIED_NOT_EXECUTION_AUTHORIZED",
            "head": head, "h3_base": BASE, "original_files_unchanged": True,
            "execution_authorized": False}


if __name__ == "__main__":
    try:
        result = verify(Path(__file__).resolve().parents[1])
    except (OSError, ValueError, subprocess.SubprocessError):
        print('{"status":"R0_DELIVERY_INVALID","execution_authorized":false}')
        raise SystemExit(1)
    print(json.dumps(result, indent=2))
