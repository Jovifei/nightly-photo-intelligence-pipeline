"""Archival handoff integrity and current N1/G1 authorization boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.authorization import load_authorization

pytestmark = pytest.mark.acceptance

# Authorization-state files legitimately change with Owner-approved phase
# transitions; excluded from the "immutable contract files intact" check.
_AUTH_STATE_FILES = {
    "PROJECT_STATE.json",
    "tasks/index.json",
    "tasks/README.md",
    "tasks/phase_n1_ingest_state_machine.yaml",
    "research/benchmark_protocol.md",
    "research/license_review_checklist.md",
    "research/model_candidate_register.md",
    "research/source_register.md",
    "research/technology_decision_matrix.md",
}


def _is_auth_state_file(rel: str) -> bool:
    return rel in _AUTH_STATE_FILES


def _read_manifest(root: Path) -> dict[str, str]:
    listed: dict[str, str] = {}
    for line in (root / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split("  ", 1)
        listed[rel] = digest
    return listed


def test_at_n0_ho_01_immutable_contract_files_intact(project_root: Path) -> None:
    """AT-N0-HO-01: every immutable contract file listed in MANIFEST.sha256
    hashes correctly. Auth-state files (PROJECT_STATE, tasks/index, task files)
    are excluded - they change with phase transitions."""
    listed = _read_manifest(project_root)
    assert len(listed) >= 50, "manifest should list the delivered contract files"
    checked = 0
    for rel, digest in listed.items():
        if _is_auth_state_file(rel):
            continue
        p = project_root / rel
        assert p.is_file(), f"manifest file missing: {rel}"
        actual = hashlib.sha256(p.read_bytes()).hexdigest()
        assert actual == digest, f"manifest hash mismatch: {rel}"
        checked += 1
    assert checked > 0, "no immutable contract files checked"


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
    assert state["phase_status"]["N2B0_5"] == "AUTHORIZED"
    assert state["required_stop_after"]["condition"] == "N2B0_5_AWAITING_OWNER_APPROVAL"
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
    assert state["authorization"]["large_model_downloads"] == "NOT_AUTHORIZED"
    assert state["authorization"]["exif_real_data_read"] == "AUTHORIZED_NON_SENSITIVE_ONLY"


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
