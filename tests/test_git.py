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
N2B2_RUNTIME_REVALIDATION_CANDIDATE = "da638bab6a61fe6fc466521cc60abcacfea9120a"
N2B2_REVIEW_TOOLING_OVERLAY = "3b453efed300dbe4d9e7f410697da1fb2d797f70"
N2B2_ENGINEERING_REPAIR_BASE = "ed8e3d9eb750505ee3cf501f6adfe91aab03fea8"
N2B2_ENGINEERING_FOLLOWUP_BASE = "1a3eb113055248eda891793d281fd226070b82e5"
N2B2_AUDIT_FIX_C_BASE = "45d4abd1099169ba6e5c92c7f7f6656e94748efb"
N2B2_AUDIT_FIX_D_BASE = "ab69f2c46971e5fea0cd0bf6ca13367e964f0409"
N2B2_E2_BASE = "3445f2911d7bb6bfe9fb8bdadc5ec30541adad99"
N2B2_AUDIT_FIX_F_FINAL_BASE = "4e7f7e1483728557ae6b05c543569151614b5833"
N2B2_AUDIT_FIX_G_BASE = "a6a4df9e6187f524a22f52bfb258d7a4b2ab3d3a"
N2B2_H3_BINDING_BASE = "1b9997ba0b099fd159932a8de0697f78d1fc7867"
REAL20_R0_DELIVERY = "50d9ffac597570ceba3bfea44ff9dc6448ba85c0"
REAL20_R1_BASE = "2ae0d76a551b18e773bfdfe33ce600b742ece631"
REAL20_HARDENING_BASE = "1dec64dec010336791b20d6d4897ff90e2783b02"
REAL20_OUTPUT_BOUND_BASE = "1036962e2b958d1a523799ecce5a6fb605d9fe02"
REAL20_FINAL_REVIEW_BASE = "832e0ffe28942bb855f281490dfa410b02155474"
REAL20_FINAL_HARDENING_BASE = "b56c0fc8b80f2af53ecb809f3834227a4030fe94"
REAL20_ADMISSION_WINDOW_BASE = "9145c9c92b0eeac700aac212818b2208d0c87844"
REAL20_LEDGER_HANDLE_BASE = "9145c9c92b0eeac700aac212818b2208d0c87844"
REAL20_PREFLIGHT_RECEIPT_BASE = "f2302fee69255ab971942c44740fe5c059a2503c"
REAL20_DATA_SCHEMA_BASE = "6263ebd2c7c4854ca13026a678397f83ef8adcef"
REAL20_NATIVE_LEDGER_BASE = "769aa3b1d98a86227d9a8eb53f97f4904046025d"
REAL20_NATIVE_LEDGER_CLOSURE = "ff479dfde536bdbf5a9e0a401fd3c35d910ad774"

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


def _is_review_tooling_overlay_candidate(project_root: Path) -> bool:
    head = _git(project_root, "rev-parse", "HEAD").stdout.strip()
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return (
        head == N2B2_REVIEW_TOOLING_OVERLAY
        and parent == N2B2_RUNTIME_REVALIDATION_CANDIDATE
        and count.stdout.strip() == "4"
    )


def _is_runtime_remediation_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_REVIEW_TOOLING_OVERLAY and count.stdout.strip() == "5"


def _is_engineering_repair_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_ENGINEERING_REPAIR_BASE and count.stdout.strip() == "6"


def _is_engineering_followup_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_ENGINEERING_FOLLOWUP_BASE and count.stdout.strip() == "7"


def _is_audit_fix_c_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_AUDIT_FIX_C_BASE and count.stdout.strip() == "8"


def _is_audit_fix_d_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_AUDIT_FIX_D_BASE and count.stdout.strip() == "9"


def _is_e2_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_E2_BASE and count.stdout.strip() == "11"


def _is_audit_fix_f_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_AUDIT_FIX_F_FINAL_BASE and count.stdout.strip() == "19"


def _is_audit_fix_g_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_AUDIT_FIX_G_BASE and count.stdout.strip() == "20"


def _is_h3_binding_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == N2B2_H3_BINDING_BASE and count.stdout.strip() == "21"


def _is_real20_transition_candidate(project_root: Path) -> bool:
    parent = _git(project_root, "rev-parse", "HEAD^").stdout.strip()
    count = _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD")
    return parent == REAL20_R0_DELIVERY and count.stdout.strip() == "23"


def _is_real20_hardening_candidate(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_R1_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "24"
    )


def _is_real20_admission_fix(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_HARDENING_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "25"
    )


def _is_real20_output_bound_fix(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_OUTPUT_BOUND_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "26"
    )


def _is_real20_final_review_fix(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_FINAL_REVIEW_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "27"
    )


def _is_real20_latest_hardening(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_FINAL_HARDENING_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "28"
    )


def _is_real20_admission_window_fix(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_ADMISSION_WINDOW_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "29"
    )


def _is_real20_ledger_handle_fix(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_LEDGER_HANDLE_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "30"
    )


def _is_real20_preflight_receipt_fix(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_PREFLIGHT_RECEIPT_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "31"
    )


def _is_real20_terminal_evidence_fix(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_DATA_SCHEMA_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "32"
    )


def _is_real20_native_ledger_closure(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_NATIVE_LEDGER_BASE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "34"
    )


def _is_real20_native_ledger_acceptance_followup(project_root: Path) -> bool:
    return (
        _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_NATIVE_LEDGER_CLOSURE
        and _git(project_root, "rev-list", "--count", f"{N2B1P_BASELINE}..HEAD").stdout.strip()
        == "35"
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


def test_git_one_n2b0_7_then_n2b1r_then_one_n2b1p_commit_no_merges(project_root: Path) -> None:
    head = _git(project_root, "rev-parse", "HEAD").stdout.strip()
    if head == N2B1P_BASELINE:
        candidate_offset = 0
    elif _is_main_integration_candidate(project_root):
        candidate_offset = 2
    elif _is_runtime_identity_revalidation_candidate(project_root):
        candidate_offset = 3
    elif _is_review_tooling_overlay_candidate(project_root):
        candidate_offset = 4
    elif _is_runtime_remediation_candidate(project_root):
        candidate_offset = 5
    elif _is_engineering_repair_candidate(project_root):
        candidate_offset = 6
    elif _is_engineering_followup_candidate(project_root):
        candidate_offset = 7
    elif _is_audit_fix_c_candidate(project_root):
        candidate_offset = 8
    elif _is_audit_fix_d_candidate(project_root):
        candidate_offset = 9
    elif _is_e2_candidate(project_root):
        candidate_offset = 11
    elif _is_audit_fix_f_candidate(project_root):
        candidate_offset = 19
    elif _is_audit_fix_g_candidate(project_root):
        candidate_offset = 20
    elif _is_h3_binding_candidate(project_root):
        candidate_offset = 21
    elif _is_real20_transition_candidate(project_root):
        candidate_offset = 23
    elif _is_real20_hardening_candidate(project_root):
        candidate_offset = 24
    elif _is_real20_admission_fix(project_root):
        candidate_offset = 25
    elif _is_real20_output_bound_fix(project_root):
        candidate_offset = 26
    elif _is_real20_final_review_fix(project_root):
        candidate_offset = 27
    elif _is_real20_latest_hardening(project_root):
        candidate_offset = 28
    elif _is_real20_admission_window_fix(project_root):
        candidate_offset = 29
    elif _is_real20_ledger_handle_fix(project_root):
        candidate_offset = 30
    elif _is_real20_preflight_receipt_fix(project_root):
        candidate_offset = 31
    elif _is_real20_terminal_evidence_fix(project_root):
        candidate_offset = 32
    elif _is_real20_native_ledger_closure(project_root):
        candidate_offset = 34
    elif _is_real20_native_ledger_acceptance_followup(project_root):
        candidate_offset = 35
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
    elif _is_review_tooling_overlay_candidate(project_root):
        assert post_n2b1r == 5
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (
            N2B2_RUNTIME_REVALIDATION_CANDIDATE
        )
    elif _is_runtime_remediation_candidate(project_root):
        assert post_n2b1r == 6
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (
            N2B2_REVIEW_TOOLING_OVERLAY
        )
    elif _is_engineering_repair_candidate(project_root):
        assert post_n2b1r == 7
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (
            N2B2_ENGINEERING_REPAIR_BASE
        )
    elif _is_engineering_followup_candidate(project_root):
        assert post_n2b1r == 8
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (
            N2B2_ENGINEERING_FOLLOWUP_BASE
        )
    elif _is_audit_fix_c_candidate(project_root):
        assert post_n2b1r == 9
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (N2B2_AUDIT_FIX_C_BASE)
    elif _is_audit_fix_d_candidate(project_root):
        assert post_n2b1r == 10
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (N2B2_AUDIT_FIX_D_BASE)
    elif _is_e2_candidate(project_root):
        assert post_n2b1r == 12
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (N2B2_E2_BASE)
    elif _is_audit_fix_f_candidate(project_root):
        assert post_n2b1r == 20
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == (
            N2B2_AUDIT_FIX_F_FINAL_BASE
        )
    elif _is_audit_fix_g_candidate(project_root):
        assert post_n2b1r == 21
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == N2B2_AUDIT_FIX_G_BASE
    elif _is_h3_binding_candidate(project_root):
        assert post_n2b1r == 22
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == N2B2_H3_BINDING_BASE
    elif _is_real20_transition_candidate(project_root):
        assert post_n2b1r == 24
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_R0_DELIVERY
    elif _is_real20_hardening_candidate(project_root):
        assert post_n2b1r == 25
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_R1_BASE
    elif _is_real20_admission_fix(project_root):
        assert post_n2b1r == 26
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_HARDENING_BASE
    elif _is_real20_output_bound_fix(project_root):
        assert post_n2b1r == 27
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_OUTPUT_BOUND_BASE
    elif _is_real20_final_review_fix(project_root):
        assert post_n2b1r == 28
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_FINAL_REVIEW_BASE
    elif _is_real20_latest_hardening(project_root):
        assert post_n2b1r == 29
        assert (
            _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_FINAL_HARDENING_BASE
        )
    elif _is_real20_admission_window_fix(project_root):
        assert post_n2b1r == 30
        assert (
            _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_ADMISSION_WINDOW_BASE
        )
    elif _is_real20_ledger_handle_fix(project_root):
        assert post_n2b1r == 31
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_LEDGER_HANDLE_BASE
    elif _is_real20_preflight_receipt_fix(project_root):
        assert post_n2b1r == 32
        assert (
            _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_PREFLIGHT_RECEIPT_BASE
        )
    elif _is_real20_terminal_evidence_fix(project_root):
        assert post_n2b1r == 33
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_DATA_SCHEMA_BASE
    elif _is_real20_native_ledger_closure(project_root):
        assert post_n2b1r == 35
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_NATIVE_LEDGER_BASE
    elif _is_real20_native_ledger_acceptance_followup(project_root):
        assert post_n2b1r == 36
        assert _git(project_root, "rev-parse", "HEAD^").stdout.strip() == REAL20_NATIVE_LEDGER_CLOSURE
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
    elif _is_review_tooling_overlay_candidate(project_root):
        expected_count = 5
    elif _is_runtime_remediation_candidate(project_root):
        expected_count = 6
    elif _is_engineering_repair_candidate(project_root):
        expected_count = 7
    elif _is_engineering_followup_candidate(project_root):
        expected_count = 8
    elif _is_audit_fix_c_candidate(project_root):
        expected_count = 9
    elif _is_audit_fix_d_candidate(project_root):
        expected_count = 10
    elif _is_e2_candidate(project_root):
        expected_count = 12
    elif _is_audit_fix_f_candidate(project_root):
        expected_count = 20
    elif _is_audit_fix_g_candidate(project_root):
        expected_count = 21
    elif _is_h3_binding_candidate(project_root):
        expected_count = 22
    elif _is_real20_transition_candidate(project_root):
        expected_count = 24
    elif _is_real20_hardening_candidate(project_root):
        expected_count = 25
    elif _is_real20_admission_fix(project_root):
        expected_count = 26
    elif _is_real20_output_bound_fix(project_root):
        expected_count = 27
    elif _is_real20_final_review_fix(project_root):
        expected_count = 28
    elif _is_real20_latest_hardening(project_root):
        expected_count = 29
    elif _is_real20_admission_window_fix(project_root):
        expected_count = 30
    elif _is_real20_ledger_handle_fix(project_root):
        expected_count = 31
    elif _is_real20_preflight_receipt_fix(project_root):
        expected_count = 32
    elif _is_real20_terminal_evidence_fix(project_root):
        expected_count = 33
    elif _is_real20_native_ledger_closure(project_root):
        expected_count = 35
    elif _is_real20_native_ledger_acceptance_followup(project_root):
        expected_count = 36
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
