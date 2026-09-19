"""Verify H0 is a delivery-only direct child of the reviewed base."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

BASE = "ffc4130823c1308f089b835c766e341ec2173e82"
PREFIX = "review_stages/H0/"
FILES = {
    "README.md",
    "NEXT_CODEX.md",
    "STATE.json",
    "FILES.sha256",
    "lease_request.py",
    "test_stage.py",
    "verify_delivery.py",
}


def git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    for n in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(n, None)
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, timeout=30, env=env
    ).stdout


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    try:
        head = git(root, "rev-parse", "HEAD").decode().strip()
        if git(root, "rev-list", "--parents", "-n", "1", "HEAD").decode().split() != [head, BASE]:
            raise ValueError
        if git(root, "rev-list", "--merges", "HEAD").strip():
            raise ValueError
        if git(root, "status", "--porcelain=v1", "--untracked-files=all").strip():
            raise ValueError
        rows = (
            git(root, "diff", "--name-status", "--no-renames", BASE, "HEAD").decode().splitlines()
        )
        if set(rows) != {"A\t" + PREFIX + n for n in FILES}:
            raise ValueError
        manifest = git(root, "show", "HEAD:" + PREFIX + "FILES.sha256").decode()
        entries = {}
        for row in manifest.splitlines():
            d, n = row.split("  ", 1)
            if not re.fullmatch(r"[0-9a-f]{64}", d) or n in entries:
                raise ValueError
            entries[n] = d
        if set(entries) != FILES - {"FILES.sha256"}:
            raise ValueError
        for n, d in entries.items():
            if hashlib.sha256(git(root, "show", "HEAD:" + PREFIX + n)).hexdigest() != d:
                raise ValueError
    except Exception:
        print('{"result":"H0_DELIVERY_INVALID","execution_authorized":false}')
        return 1
    print(
        json.dumps(
            {
                "result": "H0_DELIVERY_VERIFIED_NOT_AUTHORIZED",
                "head": head,
                "base": BASE,
                "files": len(FILES),
                "execution_authorized": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
