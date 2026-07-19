"""Stage-aware Git acceptance for N0 -> N1 -> G1 -> exactly one N2A commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

N0_BASELINE = "72a81f5984838b74304d23263ac450ea4b5a3a9a"
N1_BASELINE = "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc"
N0_TAG = "n0-approved-2026-07-14"
N1_TAG = "n1-approved-2026-07-14"
G1_BASELINE = "4a807dbbcd147a106b02b7e3899aa701c2028d83"
G1_TAG = "g1-approved-2026-07-19"

SENSITIVE_SUFFIXES = (
    ".db",
    ".sqlite",
    ".sqlite3",
    ".db-wal",
    ".db-shm",
    ".log",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".pt",
    ".pth",
    ".ckpt",
    ".safetensors",
    ".onnx",
    ".engine",
    ".npy",
    ".npz",
    ".env",
)
ALLOWED_TRACKED_PNGS = {
    "fixtures/three_image_smoke_set/fixture_a_corridor_abstract.png",
    "fixtures/three_image_smoke_set/fixture_a_exact_copy.png",
    "fixtures/three_image_smoke_set/fixture_b_tonal_abstract.png",
}


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_git_approved_tags_and_ancestry_are_exact(project_root: Path) -> None:
    assert _git(project_root, "rev-parse", N0_TAG).stdout.strip() == N0_BASELINE
    assert _git(project_root, "rev-parse", N1_TAG).stdout.strip() == N1_BASELINE
    assert _git(project_root, "rev-parse", G1_TAG).stdout.strip() == G1_BASELINE
    assert (
        _git(project_root, "merge-base", "--is-ancestor", N0_BASELINE, N1_BASELINE).returncode == 0
    )
    assert _git(project_root, "merge-base", "--is-ancestor", N1_BASELINE, "HEAD").returncode == 0
    assert _git(project_root, "merge-base", "--is-ancestor", G1_BASELINE, "HEAD").returncode == 0
    assert _git(project_root, "rev-list", "--parents", "-n", "1", N0_BASELINE).stdout.split() == [
        N0_BASELINE
    ]


def test_git_exactly_one_n2a_commit_and_no_merges(project_root: Path) -> None:
    assert int(_git(project_root, "rev-list", "--count", "HEAD").stdout.strip()) == 4
    assert (
        int(_git(project_root, "rev-list", "--count", f"{N1_BASELINE}..HEAD").stdout.strip()) == 2
    )
    assert (
        int(_git(project_root, "rev-list", "--count", f"{G1_BASELINE}..HEAD").stdout.strip()) == 1
    )
    assert _git(project_root, "rev-list", "--merges", "HEAD").stdout.strip() == ""


def test_git_worktree_is_clean(project_root: Path) -> None:
    status = _git(project_root, "status", "--porcelain", "--untracked-files=all")
    assert status.returncode == 0
    assert status.stdout.strip() == "", "G1 acceptance requires a clean worktree after amend"


def test_git_no_sensitive_tracked_files(project_root: Path) -> None:
    tracked = [
        line.strip() for line in _git(project_root, "ls-files").stdout.splitlines() if line.strip()
    ]
    assert tracked
    for rel in tracked:
        lower = rel.lower()
        assert not lower.endswith(SENSITIVE_SUFFIXES), f"sensitive file tracked: {rel}"
        assert "secret" not in lower and "token" not in lower
        if lower.endswith(".png"):
            assert rel in ALLOWED_TRACKED_PNGS, f"unexpected tracked PNG: {rel}"


# Historical AT name retained for acceptance-catalog continuity.
def test_at_n0_git_01_one_isolated_commit_no_sensitive_files(project_root: Path) -> None:
    test_git_approved_tags_and_ancestry_are_exact(project_root)
    test_git_exactly_one_n2a_commit_and_no_merges(project_root)
    test_git_no_sensitive_tracked_files(project_root)
