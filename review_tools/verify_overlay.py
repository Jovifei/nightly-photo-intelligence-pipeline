"""Verify the exact review-tooling overlay, NOT production phase acceptance.

The frozen runtime candidate remains da638bab. Its files and root MANIFEST must
be byte-identical. Every additional tracked file is bound by the separate
review_tools/MANIFEST.sha256. Both manifests jointly bind the entire index.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

BASE = "da638bab6a61fe6fc466521cc60abcacfea9120a"
OVERLAY_MANIFEST = "review_tools/MANIFEST.sha256"
ALLOWED = frozenset({
    "review_tools/evidence_audit.py",
    "review_tools/negative_space.py",
    "review_tools/test_evidence_audit.py",
    "review_tools/test_negative_space.py",
    "review_tools/verify_overlay.py",
    "review_tools/test_verify_overlay.py",
    "review_tools/README.md",
    "review_tools/AUDIT_AND_ROADMAP_20260913.md",
    "review_tools/NEXT_LOCAL_CODEX_PROMPT.md",
    OVERLAY_MANIFEST,
})
TAGS = {
    "n0-approved-2026-07-14": "72a81f5984838b74304d23263ac450ea4b5a3a9a",
    "n1-approved-2026-07-14": "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc",
    "g1-approved-2026-07-19": "4a807dbbcd147a106b02b7e3899aa701c2028d83",
    "n2a-approved-2026-07-22": "f79d2df504622ff82aa5e53d1486310bbea9985a",
    "n2b0-approved-2026-07-24": "f331621c84905aef921c612908d01d3a8a2f577a",
    "n2b0-5-approved-2026-07-26": "5ad9f8d7d0d6fa267df02d90ef25957bc679e232",
    "n2b0-6-approved-2026-07-29": "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2",
    "n2b0-7-approved-2026-07-29": "f2b1c38301d71da52b855f73de8a67908cb525ef",
}


class OverlayError(ValueError):
    pass


def need(condition: bool, code: str) -> None:
    if not condition:
        raise OverlayError(code)


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                            check=False, timeout=30,
                            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    need(result.returncode == 0, "GIT_QUERY_FAILED")
    return result.stdout


def paths(data: bytes) -> set[str]:
    return {p.decode("utf-8") for p in data.split(b"\0") if p}


def manifest(data: bytes) -> dict[str, str]:
    need(data.endswith(b"\n") and b"\r" not in data, "MANIFEST_EOL")
    result: dict[str, str] = {}
    for line in data.decode("utf-8").splitlines():
        row = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9_./-]+)", line)
        need(row is not None, "MANIFEST_ROW")
        assert row is not None
        digest, path = row.groups()
        need(path not in result and all(p not in ("", ".", "..") for p in path.split("/")), "MANIFEST_PATH")
        result[path] = digest
    return result


def verify(root: Path, *, baseline: str = BASE, tags: dict[str, str] | None = None) -> dict[str, object]:
    """The optional arguments are for synthetic repository tests, not CLI flags."""
    root = root.resolve(strict=True)
    need(git(root, "status", "--porcelain=v1", "--untracked-files=all") == b"", "DIRTY_WORKTREE")
    head = git(root, "rev-parse", "HEAD").decode().strip()
    parents = git(root, "rev-list", "--parents", "-n", "1", "HEAD").decode().split()
    need(parents == [head, baseline], "OVERLAY_MUST_BE_ONE_DIRECT_CHILD")
    need(not git(root, "rev-list", "--merges", "HEAD").strip(), "MERGE_HISTORY")
    for tag, expected in (TAGS if tags is None else tags).items():
        need(git(root, "rev-parse", tag).decode().strip() == expected, "BASELINE_TAG_DRIFT")
    original = paths(git(root, "ls-tree", "-r", "--name-only", "-z", baseline))
    changed = paths(git(root, "diff", "--name-only", "-z", baseline, "HEAD", "--"))
    tracked = paths(git(root, "ls-files", "-z"))
    need(not (original & ALLOWED) and changed == ALLOWED and tracked == original | ALLOWED,
         "OVERLAY_FILE_SCOPE")
    # This includes src, schemas, approvals, fixtures, PROJECT_STATE and the
    # root MANIFEST. No runtime binding is silently grandfathered to this HEAD.
    for rel in original:
        need(git(root, "cat-file", "blob", f"{baseline}:{rel}") == git(root, "cat-file", "blob", f":{rel}"),
             "FROZEN_FILE_CHANGED")
    old_manifest = manifest(git(root, "cat-file", "blob", ":MANIFEST.sha256"))
    new_manifest = manifest(git(root, "cat-file", "blob", f":{OVERLAY_MANIFEST}"))
    need(set(old_manifest) == original - {"MANIFEST.sha256"}, "BASE_MANIFEST_FILE_SET")
    need(set(new_manifest) == ALLOWED - {OVERLAY_MANIFEST}, "OVERLAY_MANIFEST_FILE_SET")
    for rel, expected in {**old_manifest, **new_manifest}.items():
        need(hashlib.sha256(git(root, "cat-file", "blob", f":{rel}")).hexdigest() == expected,
             "MANIFEST_HASH_MISMATCH")
    return {"result": "REVIEW_TOOLING_OVERLAY_VERIFIED", "tooling_commit": head,
            "runtime_candidate": baseline, "frozen_files_unchanged": len(original),
            "overlay_files": len(ALLOWED), "production_phase_approval": False,
            "runtime_revalidation": "NOT_PERFORMED"}


def main() -> int:
    try:
        report = verify(Path(__file__).resolve().parents[1])
    except OverlayError as exc:
        report = {"result": "OVERLAY_INVALID", "error_code": str(exc)}
        code = 1
    except (OSError, ValueError, subprocess.TimeoutExpired):
        report = {"result": "OVERLAY_INVALID", "error_code": "INPUT_UNAVAILABLE"}
        code = 1
    else:
        code = 0
    print(json.dumps(report, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
