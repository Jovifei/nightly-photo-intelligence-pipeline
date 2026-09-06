"""Stage-aware Git acceptance for N0 -> N1 -> G1 -> exactly one N2A commit."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

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
N2B1P_PORTABILITY_CANDIDATE = "0fef0a8f6a2f2b2f75ce2fba3e3eef1e764037b8"
N2B2_GPU_REVIEW_CANDIDATE = "49e653b27884f9ba09d15ca17682e496687dc59f"
N2B2_S20_REVIEW_CANDIDATE = "c1008132654d32e7ac6a2032eb5d3a2c7e07cdb6"
N2B2_REVIEW_CONTROL_PLANE_CANDIDATE = "d83f96271f754763d61cedcc314fc725c840c86f"

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


def _is_main_integration_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B1P_PORTABILITY_CANDIDATE and count.stdout.strip() == "2"


def _is_runtime_identity_revalidation_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_REVIEW_CONTROL_PLANE_CANDIDATE and count.stdout.strip() == "3"


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


def test_git_one_n2b0_7_then_n2b1r_then_one_n2b1p_commit_no_merges(project_root: Path) -> None:
    head = _git(project_root, "rev-parse", "HEAD").stdout.strip()
    if head == N2B1P_BASELINE:
        candidate_offset = 0
    elif _is_main_integration_candidate(project_root):
        candidate_offset = 2
    elif _is_runtime_identity_revalidation_candidate(project_root):
        candidate_offset = 3
    elif _git(project_root, "rev-parse", "HEAD^").stdout.strip() == N2B1P_BASELINE:
        candidate_offset = 1
    else:
        parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
        assert parent in {N2B2_GPU_REVIEW_CANDIDATE, N2B2_S20_REVIEW_CANDIDATE}
        candidate_offset = 2 if parent == N2B2_GPU_REVIEW_CANDIDATE else 3
    assert int(_git(project_root, "rev-list", "--count", "HEAD").stdout.strip()) == (
        10 + candidate_offset
    )
    assert (
        int(_git(project_root, "rev-list", "--count", f"{N1_BASELINE}..HEAD").stdout.strip())
        == 8 + candidate_offset
    )
    assert (
        int(_git(project_root, "rev-list", "--count", f"{G1_BASELINE}..HEAD").stdout.strip())
        == 7 + candidate_offset
    )
    assert (
        int(
            _git(
                project_root, "rev-list", "--count", f"{N2B0_5_BASELINE}..{N2B0_6_BASELINE}"
            ).stdout.strip()
        )
        == 1
    )
    post_n2b1r = int(
        _git(project_root, "rev-list", "--count", f"{N2B1R_BASELINE}..HEAD").stdout.strip()
    )
    assert post_n2b1r == 1 + candidate_offset
    if candidate_offset == 0:
        assert post_n2b1r == 1
    elif candidate_offset == 1:
        assert post_n2b1r == 2
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == N2B1P_BASELINE
        assert (
            int(_git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip())
            == 1
        )
    elif _is_main_integration_candidate(project_root):
        assert post_n2b1r == 3
        assert (
            _git(project_root, "rev-parse", "HEAD^").stdout.strip() == N2B1P_PORTABILITY_CANDIDATE
        )
        assert (project_root / "research" / "N2B1P_manifest_portability_remediation.json").is_file()
    elif _is_runtime_identity_revalidation_candidate(project_root):
        assert post_n2b1r == 4
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (
            N2B2_REVIEW_CONTROL_PLANE_CANDIDATE
        )
    else:
        assert post_n2b1r == 1 + candidate_offset
        parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
        assert parent in {N2B2_GPU_REVIEW_CANDIDATE, N2B2_S20_REVIEW_CANDIDATE}
        assert (
            int(_git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip())
            == candidate_offset
        )
    assert (
        int(
            _git(
                project_root, "rev-list", "--count", f"{N2B0_6_BASELINE}..{N2B0_7_BASELINE}"
            ).stdout.strip()
        )
        == 1
    )
    assert (
        int(_git(project_root, "rev-list", "--count", f"{N2B0_7_BASELINE}..HEAD").stdout.strip())
        == 2 + candidate_offset
    )
    assert _git(project_root, "rev-list", "--merges", "HEAD").stdout.strip() == ""


def test_n2b1p_candidate_is_resolved_not_hardcoded(project_root: Path) -> None:
    """The N2B1P review target must be resolved from an immutable anchor, never hardcoded.

    The candidate is amended in place (squash-to-one is enforced by
    tools/verify_handoff.py), so a literal SHA describes a commit that the very next
    amend makes unreachable. This regressed twice: b819e2c was squashed into ffbcaaf,
    which was then amended away -- both stayed recorded as the active review target
    while pointing at nothing, and cli.py resolved one of them with check=True, which
    crashes on a fresh clone or after git gc.
    """
    contract = yaml.safe_load(
        (project_root / "tasks" / "phase_n2b2_synthetic_model_stack_validation.yaml").read_text(
            encoding="utf-8"
        )
    )
    prerequisite = contract["prerequisite"]
    assert "n2b1p_sha" not in prerequisite, "candidate SHA must not be hardcoded in the contract"
    assert prerequisite["n2b1p_parent_sha"] == N2B1R_BASELINE
    assert _git(project_root, "merge-base", "--is-ancestor", N2B1R_BASELINE, "HEAD").returncode == 0
    resolved = _git(project_root, "rev-list", f"{N2B1R_BASELINE}..HEAD").stdout.split()
    head = _git(project_root, "rev-parse", "HEAD").stdout.strip()
    if head == N2B1P_BASELINE:
        expected_count = 1
    elif _is_main_integration_candidate(project_root):
        expected_count = 3
    elif _is_runtime_identity_revalidation_candidate(project_root):
        expected_count = 4
    elif _git(project_root, "rev-parse", "HEAD^").stdout.strip() == N2B1P_BASELINE:
        expected_count = 2
    else:
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() in {
            N2B2_GPU_REVIEW_CANDIDATE,
            N2B2_S20_REVIEW_CANDIDATE,
        }
        expected_count = (
            3
            if _git(project_root, "rev-parse", "HEAD^").stdout.strip() == N2B2_GPU_REVIEW_CANDIDATE
            else 4
        )
    assert len(resolved) == expected_count, (
        f"candidate must resolve to exactly {expected_count} commits, got {len(resolved)}"
    )
    for literal in prerequisite["n2b1p_sha_superseded_literals"]:
        assert _git(project_root, "merge-base", "--is-ancestor", literal, "HEAD").returncode != 0, (
            f"{literal} is recorded as superseded but is still reachable from HEAD"
        )


def test_git_worktree_is_clean(project_root: Path) -> None:
    status = _git(project_root, "status", "--porcelain", "--untracked-files=all")
    assert status.returncode == 0
    assert status.stdout.strip() == "", "N2B0.5 acceptance requires a clean worktree"


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
    test_git_one_n2b0_7_then_n2b1r_then_one_n2b1p_commit_no_merges(project_root)
    test_git_no_sensitive_tracked_files(project_root)
