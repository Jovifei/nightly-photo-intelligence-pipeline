"""Git acceptance for immutable milestones and generic linear review candidates."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from nightly_photo_intelligence_pipeline import preflight

pytestmark = pytest.mark.acceptance

N0_BASELINE = "72a81f5984838b74304d23263ac450ea4b5a3a9a"
N1_BASELINE = "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc"
N0_TAG = "n0-approved-2026-07-14"
N1_TAG = "n1-approved-2026-07-14"
G1_BASELINE = "4a807dbbcd147a106b02b7e3899aa701c2028d83"
G1_TAG = "g1-approved-2026-07-19"
N2B0_BASELINE = "f331621c84905aef921c612908d01d3a8a2f577a"
N2B0_TAG = "n2b0-approved-2026-07-24"
N2B0_5_BASELINE = "5ad9f8d7d0d6fa267df02d90ef25957bc679e232"
N2B0_5_TAG = "n2b0-5-approved-2026-07-26"
N2B0_6_BASELINE = "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2"
N2B0_6_TAG = "n2b0-6-approved-2026-07-29"
N2B0_7_BASELINE = "f2b1c38301d71da52b855f73de8a67908cb525ef"
N2B0_7_TAG = "n2b0-7-approved-2026-07-29"
N2B1R_BASELINE = "d3628e27334e819ba2d5944151447595e03f39f9"
N2B1P_BASELINE = "9b3d5a1cc4a6f81467ad98034ca8994d1ebab043"
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
    assert _git(project_root, "rev-parse", N2B0_TAG).stdout.strip() == N2B0_BASELINE
    assert _git(project_root, "rev-parse", N2B0_5_TAG).stdout.strip() == N2B0_5_BASELINE
    assert _git(project_root, "rev-parse", N2B0_6_TAG).stdout.strip() == N2B0_6_BASELINE
    assert _git(project_root, "rev-parse", N2B0_7_TAG).stdout.strip() == N2B0_7_BASELINE
    assert (
        _git(project_root, "merge-base", "--is-ancestor", N0_BASELINE, N1_BASELINE).returncode == 0
    )
    assert _git(project_root, "merge-base", "--is-ancestor", N1_BASELINE, "HEAD").returncode == 0
    assert _git(project_root, "merge-base", "--is-ancestor", G1_BASELINE, "HEAD").returncode == 0
    assert _git(project_root, "merge-base", "--is-ancestor", N2B0_BASELINE, "HEAD").returncode == 0
    assert (
        _git(project_root, "merge-base", "--is-ancestor", N2B0_5_BASELINE, "HEAD").returncode == 0
    )
    assert (
        _git(project_root, "merge-base", "--is-ancestor", N2B0_6_BASELINE, "HEAD").returncode == 0
    )
    assert (
        _git(project_root, "merge-base", "--is-ancestor", N2B0_7_BASELINE, "HEAD").returncode == 0
    )
    assert _git(project_root, "rev-list", "--parents", "-n", "1", N0_BASELINE).stdout.split() == [
        N0_BASELINE
    ]


def test_git_descends_from_immutable_n2b1p_baselines_linearly_without_merges(
    project_root: Path,
) -> None:
    completion = yaml.safe_load(
        (project_root / "approvals" / "phase_completion_N2B1P.yaml").read_text(encoding="utf-8")
    )
    approved_n2b1p = completion["baseline"]["candidate_commit"]
    assert completion["baseline"]["immutable"] is True
    for baseline in (N2B1R_BASELINE, N2B1P_BASELINE, approved_n2b1p):
        assert _git(project_root, "merge-base", "--is-ancestor", baseline, "HEAD").returncode == 0

    history = _git(project_root, "rev-list", "--parents", f"{N2B1P_BASELINE}..HEAD")
    assert history.returncode == 0
    assert all(len(line.split()) == 2 for line in history.stdout.splitlines())
    assert (
        _git(project_root, "rev-list", "--merges", f"{N2B1P_BASELINE}..HEAD").stdout.strip() == ""
    )


def test_preflight_git_baselines_accepts_linear_successor_without_candidate_allowlist(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(preflight, "find_project_root", lambda: project_root)
    actual_run = preflight._run

    def _run_without_worktree_status(args: list[str], **kwargs: object) -> tuple[int, str]:
        if len(args) >= 4 and args[0] == "git" and args[1] == "-C" and args[3] == "status":
            return 0, ""
        return actual_run(args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(preflight, "_run", _run_without_worktree_status)
    result = preflight._check_git_baselines()

    assert result.status == preflight.PASS


def test_synthetic_contract_does_not_hardcode_mutable_n2b1p_candidate_sha(
    project_root: Path,
) -> None:
    contract = yaml.safe_load(
        (project_root / "tasks" / "phase_n2b2_synthetic_model_stack_validation.yaml").read_text(
            encoding="utf-8"
        )
    )
    prerequisite = contract["prerequisite"]
    assert "n2b1p_sha" not in prerequisite
    assert prerequisite["n2b1p_parent_sha"] == N2B1R_BASELINE

    completion = yaml.safe_load(
        (project_root / "approvals" / "phase_completion_N2B1P.yaml").read_text(encoding="utf-8")
    )
    approved_n2b1p = completion["baseline"]["candidate_commit"]
    assert _git(project_root, "merge-base", "--is-ancestor", approved_n2b1p, "HEAD").returncode == 0
    for literal in prerequisite["n2b1p_sha_superseded_literals"]:
        assert _git(project_root, "merge-base", "--is-ancestor", literal, "HEAD").returncode != 0


def test_git_worktree_is_clean(project_root: Path) -> None:
    status = _git(project_root, "status", "--porcelain", "--untracked-files=all")
    assert status.returncode == 0
    assert status.stdout.strip() == "", "review-candidate acceptance requires a clean worktree"


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
    test_git_descends_from_immutable_n2b1p_baselines_linearly_without_merges(project_root)
    test_git_no_sensitive_tracked_files(project_root)
