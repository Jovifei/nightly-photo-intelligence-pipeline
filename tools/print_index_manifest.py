#!/usr/bin/env python3
"""Print a FULL manifest from staged Git bytes; excludes only root MANIFEST.sha256.

Stage intended changes first. Redirect output to a Git-external temporary file,
inspect it, then copy it to root MANIFEST.sha256 and stage that file. Never use
an old 477-file count as current exact-set acceptance. No commit/push is done.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, check=True)
    return result.stdout


def main() -> int:
    rows = []
    for entry in git("ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        meta, raw_path = entry.split(b"\t", 1)
        mode, oid, stage = meta.decode().split()
        path = raw_path.decode("utf-8")
        if stage != "0" or mode not in ("100644", "100755") or "\n" in path or "\r" in path:
            raise ValueError("INDEX_NOT_A_REGULAR_MERGED_TREE")
        if path == "MANIFEST.sha256":
            continue
        digest = hashlib.sha256(git("cat-file", "blob", oid)).hexdigest()
        rows.append((path, digest))
    for path, digest in sorted(rows):
        print(f"{digest}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
