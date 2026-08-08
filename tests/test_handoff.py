"""Current-stage handoff integrity and governed authorization boundaries."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.authorization import load_authorization

pytestmark = pytest.mark.acceptance


def _read_manifest(root: Path) -> dict[str, str]:
    listed: dict[str, str] = {}
    for line in (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        listed[rel] = digest
    return listed


def test_current_stage_manifest_binds_every_tracked_file(project_root: Path) -> None:
    """The current stage hashes every tracked file, including governance."""
    listed = _read_manifest(project_root)
    result = subprocess.run(
        ["git", "-C", str(project_root), "ls-files"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    tracked = {line for line in result.stdout.splitlines() if line and line != "MANIFEST.sha256"}
    assert set(listed) == tracked
    for rel, digest in listed.items():
        p = project_root / rel
        assert p.is_file(), f"manifest file missing: {rel}"
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == digest, f"manifest hash mismatch: {rel}"


def test_at_n0_ho_01_fixtures_match_fixture_manifest(
    project_root: Path, fixture_manifest: dict
) -> None:
    """AT-N0-HO-01: the three fixtures match fixtures/fixture_manifest.json."""
    files = fixture_manifest["files"]
    assert len(files) == 3
    for entry in files:
        p = project_root / "fixtures" / "three_image_smoke_set" / entry["name"]
        assert p.is_file()
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]
        assert p.stat().st_size == entry["size_bytes"]
    hashes = [e["sha256"] for e in files]
    assert hashes[0] == hashes[1], "fixture_a pair must be exact duplicates"


def test_at_n0_gate_02_n2_through_n8_locked(project_root: Path) -> None:
    """AT-N0-GATE-02 (G1 phase-boundary): PROJECT_STATE locks N2-N8 and G2-G3;
    N0/N1 are immutable and G1 is authorized for local execution."""
    state = json.loads((project_root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    assert state["authorization"]["phase"] == {
        "id": "N1",
        "status": "APPROVED_COMPLETE",
    }
    assert state["authorization"]["data_gate"] == {
        "id": "G1_CALIBRATION_20",
        "status": "AUTHORIZED",
    }
    # N2-N8 locked (N1 remains the engineering phase; G1 is a data gate).
    assert [state["phase_status"][f"N{i}"] for i in range(2, 9)] == ["LOCKED"] * 7
    assert state["data_scope"]["G2_PILOT_100"] == "LOCKED"
    assert state["data_scope"]["G3_FULL_LIBRARY"] == "LOCKED"
    assert state["phase_status"]["G1"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2A"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B"] == "LOCKED"
    assert state["phase_status"]["N2B0"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_5"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_6"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_7"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B1R"] == "ACQUISITION_COMPLETE"
    assert state["phase_status"]["N2B1P"] == "AUTHORIZED"
    assert (
        state["required_stop_after"]["condition"]
        == "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"
    )
    # N0 and N1 baselines are approved and immutable.
    n0 = state["baselines"]["N0"]
    assert n0["status"] == "APPROVED_COMPLETE"
    assert n0["commit"] == "72a81f5984838b74304d23263ac450ea4b5a3a9a"
    assert n0["immutable"] is True
    n1 = state["baselines"]["N1"]
    assert n1["status"] == "APPROVED_COMPLETE"
    assert n1["commit"] == "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc"
    assert n1["immutable"] is True
    # Data scope: exactly the owner-frozen G1 20-photo manifest.
    assert state["data_scope"]["max_assets"] == 20
    assert state["authorization"]["real_photo_access"] == "AUTHORIZED"
    assert state["authorization"]["large_model_downloads"] == "AUTHORIZED_RESEARCH_ONLY"
    assert state["authorization"]["exif_real_data_read"] == "AUTHORIZED_NON_SENSITIVE_ONLY"
    assert state["authorization"]["active_execution"] == {
        "phase": "N2B1P",
        "capability": "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
        "source_photo_content_read": "NOT_AUTHORIZED",
        "source_photo_exif_read": "NOT_AUTHORIZED",
        "sqlite_ingest_write": "NOT_AUTHORIZED",
    }


def test_at_n0_gate_02_n2_n8_task_files_locked(project_root: Path) -> None:
    """N1 is complete, G1 is independently authorized, and N2-N8 stay locked."""
    n1_task = project_root / "tasks" / "phase_n1_ingest_state_machine.yaml"
    assert 'status: "APPROVED_COMPLETE"' in n1_task.read_text(encoding="utf-8")
    g1_task = project_root / "tasks" / "gate_g1_calibration_20.yaml"
    assert 'status: "AUTHORIZED"' in g1_task.read_text(encoding="utf-8")
    task_files = sorted((project_root / "tasks").glob("phase_n[2-8]_*.yaml"))
    assert len(task_files) == 7, f"expected 7 locked task files (N2-N8), found {len(task_files)}"
    for path in task_files:
        text = path.read_text(encoding="utf-8")
        assert 'status: "LOCKED"' in text, f"{path.name} is not locked"


def test_at_n0_gate_02_authorization_snapshot_n1_complete_g1_authorized() -> None:
    """The reader accepts completed N1 plus the independent G1 authorization."""
    auth = load_authorization()
    assert auth.phase_id == "N1"
    assert auth.phase_authorized
    assert auth.data_gate_id == "G1_CALIBRATION_20"
    assert auth.data_gate_authorized
    assert auth.is_ingest_authorized(dry_run=True)
    assert auth.is_ingest_authorized(dry_run=False), "N1 authorizes real ingest on G1"
    assert auth.max_assets == 20
    assert auth.n0_baseline_commit == "72a81f5984838b74304d23263ac450ea4b5a3a9a"
    assert auth.n1_baseline_commit == "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc"
    assert auth.real_photo_access == "AUTHORIZED"
    assert auth.exif_real_data_read == "AUTHORIZED_NON_SENSITIVE_ONLY"
    assert auth.n2a_authorized
    assert not auth.n2b_model_authorized


def test_current_handoff_verifier_passes(project_root: Path) -> None:
    result = subprocess.run(
        [".venv\\Scripts\\python.exe", "tools\\verify_handoff.py"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "HANDOFF_VALID" in result.stdout
    assert "N2B1P local-research cache promotion only" in result.stdout


def test_current_entry_documents_reference_n2b1p_not_n0_only(project_root: Path) -> None:
    required_task = "phase_n2b1p_local_research_cache_promotion.yaml"
    for rel in (
        "MASTER_EXECUTION_CONTRACT.md",
        "AGENTS.md",
        "README_FIRST.md",
        "CODEX_START_HERE.md",
        "docs/00_reading_order.md",
    ):
        assert required_task in (project_root / rel).read_text(encoding="utf-8"), rel
