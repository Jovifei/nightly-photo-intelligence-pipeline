"""Full-tree identity recorded OUTSIDE the tree; no self-referential receipt.

Includes every tracked file (code, tests, schemas, approvals, tools, both old
manifests and the current manifest). A selected runtime list is retained only
as historical evidence, never substituted for this source binding.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from .common import EngineeringError, canonical, is_digest, require, sha256


def _git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    # Isolate Git-dir/worktree overrides inherited from other agent commands.
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(name, None)
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args], check=False, capture_output=True, timeout=30, env=env
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EngineeringError("NPI_GIT_QUERY_UNAVAILABLE") from exc
    require(result.returncode == 0, "NPI_GIT_QUERY_FAILED")
    return result.stdout


def full_source_identity(root: Path) -> dict[str, Any]:
    head = _git(root, "rev-parse", "HEAD").decode().strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    require(is_digest(head, 40) and is_digest(tree, 40), "NPI_GIT_IDENTITY_INVALID")
    require(
        _git(root, "status", "--porcelain=v1", "--untracked-files=all") == b"",
        "NPI_SOURCE_NOT_CLEAN",
    )
    # Status can hide worktree changes after assume-unchanged/skip-worktree.
    # These index flags invalidate an executable-source identity.
    index_flags = _git(root, "ls-files", "-v", "-z").split(b"\0")
    require(
        all(not row or row.startswith(b"H ") for row in index_flags),
        "NPI_SOURCE_INDEX_FLAGS_INVALID",
    )
    require(
        _git(root, "rev-parse", "--is-shallow-repository").strip() == b"false",
        "NPI_SHALLOW_REPOSITORY",
    )
    entries = _git(root, "ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0")
    rows: list[dict[str, Any]] = []
    total = 0
    try:
        for entry in entries:
            if not entry:
                continue
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split()
            require(kind == "blob" and mode in ("100644", "100755"), "NPI_UNSUPPORTED_GIT_ENTRY")
            path = raw_path.decode("utf-8")
            require(
                not path.startswith("/")
                and ".." not in path.split("/")
                and "\n" not in path
                and "\r" not in path,
                "NPI_INVALID_GIT_PATH",
            )
            size = int(_git(root, "cat-file", "-s", oid))
            require(0 <= size <= 8 * 1024 * 1024, "NPI_SOURCE_BLOB_SIZE_LIMIT")
            total += size
            require(total <= 128 * 1024 * 1024 and len(rows) < 5000, "NPI_SOURCE_SIZE_LIMIT")
            data = _git(root, "cat-file", "blob", oid)
            require(len(data) == size, "NPI_SOURCE_BLOB_CHANGED")
            rows.append(
                {
                    "path": path,
                    "mode": mode,
                    "git_blob": oid,
                    "size_bytes": size,
                    "sha256": sha256(data),
                }
            )
    except (UnicodeError, ValueError) as exc:
        if isinstance(exc, EngineeringError):
            raise
        raise EngineeringError("NPI_INVALID_GIT_TREE") from exc
    require(bool(rows), "NPI_EMPTY_SOURCE_TREE")
    rows.sort(key=lambda row: row["path"])
    require(
        _git(root, "rev-parse", "HEAD").decode().strip() == head
        and _git(root, "status", "--porcelain=v1", "--untracked-files=all") == b"",
        "NPI_SOURCE_CHANGED_DURING_BINDING",
    )
    return {
        "schema_version": "npi-full-source-manifest-v1",
        "candidate_commit": head,
        "candidate_tree": tree,
        "files": rows,
        "file_count": len(rows),
        "source_manifest_sha256": sha256(canonical(rows)),
    }
