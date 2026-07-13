"""AT-N0-GIT-01: one isolated commit; no sensitive files tracked."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.acceptance

# Pathname patterns that must never appear in tracked files.
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
# Files allowed despite matching image-extension rules.
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


def test_at_n0_git_01_one_isolated_commit_no_sensitive_files(project_root: Path) -> None:
    """AT-N0-GIT-01: exactly one local commit; working tree clean; no sensitive tracked files."""
    if not (project_root / ".git").is_dir():
        pytest.skip("git repo not yet initialized; verified post-commit in evidence")
    # Also skip if no commit exists yet (HEAD missing).
    head = _git(project_root, "rev-parse", "--verify", "HEAD")
    if head.returncode != 0:
        pytest.skip("no commit yet; verified post-commit in evidence")

    # Exactly one commit.
    log = _git(project_root, "rev-list", "--count", "HEAD")
    assert log.returncode == 0, log.stderr
    commit_count = int(log.stdout.strip() or "0")
    assert commit_count == 1, f"expected exactly one commit, found {commit_count}"

    # Working tree clean (no uncommitted changes to tracked files).
    status = _git(project_root, "status", "--porcelain")
    assert status.stdout.strip() == "", f"working tree not clean: {status.stdout!r}"

    # No sensitive files tracked.
    ls = _git(project_root, "ls-files")
    assert ls.returncode == 0, ls.stderr
    tracked = [line.strip() for line in ls.stdout.splitlines() if line.strip()]
    assert len(tracked) > 0, "repo must track the N0 deliverables"
    for rel in tracked:
        lower = rel.lower()
        for pat in SENSITIVE_PATTERNS:
            if lower.endswith(pat) or (pat in lower and "token" in lower) or "secret" in lower:
                pytest.fail(f"sensitive file tracked: {rel}")
        # No PNGs except the three fixtures.
        if lower.endswith(".png") and rel not in ALLOWED_TRACKED_PNGS:
            pytest.fail(f"unexpected tracked PNG: {rel}")
    # The core N0 deliverables are present.
    assert "pyproject.toml" in tracked
    assert any(p.startswith("src/nightly_photo_intelligence_pipeline/") for p in tracked)
