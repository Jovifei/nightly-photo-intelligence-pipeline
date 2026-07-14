"""AT-N0-GIT-01 / N1 Git history acceptance (phase-boundary adjusted).

N0 baseline SHA 72a81f5 is the approved, immutable root. N1 adds exactly one
phase commit on top of it. The test verifies the N0 baseline was not rewritten
and that at most one N1 commit exists beyond it (does not treat arbitrary
multi-commit history as a pass).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

N0_BASELINE = "72a81f5984838b74304d23263ac450ea4b5a3a9a"
N0_TAG = "n0-approved-2026-07-14"

SENSITIVE_PATTERNS = (
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


def _git(project_root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_at_n1_git_n0_baseline_not_rewritten(project_root: Path) -> None:
    """The N0 approval tag must still point at the approved N0 baseline SHA."""
    if not (project_root / ".git").is_dir():
        pytest.skip("git repo not initialized")
    tag = _git(project_root, "rev-parse", N0_TAG)
    assert tag.returncode == 0, f"tag {N0_TAG} missing"
    assert tag.stdout.strip() == N0_BASELINE, "N0 baseline SHA was rewritten or tag moved"
    # The N0 baseline commit object must still exist.
    obj = _git(project_root, "cat-file", "-t", N0_BASELINE)
    assert obj.returncode == 0 and obj.stdout.strip() == "commit"


def test_at_n1_git_single_n1_commit_beyond_n0(project_root: Path) -> None:
    """At most one N1 phase commit exists beyond the N0 baseline.

    Pre-commit (HEAD == N0 baseline) the count is 0; post-N1-commit it is 1.
    A count > 1 means unauthorized extra commits and must fail.
    """
    if not (project_root / ".git").is_dir():
        pytest.skip("git repo not initialized")
    head = _git(project_root, "rev-parse", "--verify", "HEAD")
    if head.returncode != 0:
        pytest.skip("no commit yet")
    rev = _git(project_root, "rev-list", "--count", f"{N0_BASELINE}..HEAD")
    assert rev.returncode == 0, rev.stderr
    count = int(rev.stdout.strip() or "0")
    assert count <= 1, f"at most one N1 commit beyond N0 baseline; got {count}"


def test_at_n1_git_no_sensitive_tracked_files(project_root: Path) -> None:
    """No sensitive files tracked; only the 3 fixture PNGs as images."""
    if not (project_root / ".git").is_dir():
        pytest.skip("git repo not initialized")
    ls = _git(project_root, "ls-files")
    assert ls.returncode == 0, ls.stderr
    tracked = [line.strip() for line in ls.stdout.splitlines() if line.strip()]
    assert len(tracked) > 0, "repo must track deliverables"
    for rel in tracked:
        lower = rel.lower()
        for pat in SENSITIVE_PATTERNS:
            if lower.endswith(pat) or "secret" in lower or "token" in lower:
                pytest.fail(f"sensitive file tracked: {rel}")
        if lower.endswith(".png") and rel not in ALLOWED_TRACKED_PNGS:
            pytest.fail(f"unexpected tracked PNG: {rel}")


def test_at_n1_git_n0_baseline_is_root(project_root: Path) -> None:
    """The N0 baseline commit is the root (no parent)."""
    if not (project_root / ".git").is_dir():
        pytest.skip("git repo not initialized")
    parents = _git(project_root, "rev-list", "--parents", "-n", "1", N0_BASELINE)
    assert parents.returncode == 0, parents.stderr
    parts = parents.stdout.split()
    # rev-list --parents -n 1 prints "<sha> <parent1> <parent2>..."; root has no parent.
    assert len(parts) == 1, f"N0 baseline must be root commit (no parent); got {parts}"


# Keep the N0-era test name as a thin alias for backwards collection compatibility.
def test_at_n0_git_01_one_isolated_commit_no_sensitive_files(project_root: Path) -> None:
    """N0-era alias: delegates to the N1 phase-boundary history checks."""
    test_at_n1_git_n0_baseline_not_rewritten(project_root)
    test_at_n1_git_single_n1_commit_beyond_n0(project_root)
    test_at_n1_git_no_sensitive_tracked_files(project_root)
