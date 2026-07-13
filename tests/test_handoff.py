"""AT-N0-HO-01: handoff manifest integrity. AT-N0-GATE-02: N1-N8 locked."""

from __future__ import annotations

import hashlib
import json
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


def test_at_n0_ho_01_manifest_intact(project_root: Path) -> None:
    """AT-N0-HO-01: every file listed in MANIFEST.sha256 hashes correctly."""
    listed = _read_manifest(project_root)
    assert len(listed) >= 50, "manifest should list the delivered contract files"
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
    # The duplicate pair must be byte-identical.
    hashes = [e["sha256"] for e in files]
    assert hashes[0] == hashes[1], "fixture_a pair must be exact duplicates"


def test_at_n0_gate_02_n1_through_n8_locked(project_root: Path) -> None:
    """AT-N0-GATE-02: PROJECT_STATE locks N1-N8 and G1-G3; only N0/G0 authorized."""
    state = json.loads((project_root / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    assert state["authorization"]["phase"] == {"id": "N0", "status": "AUTHORIZED"}
    assert state["authorization"]["data_gate"] == {
        "id": "G0_THREE_SYNTHETIC_FIXTURES",
        "status": "AUTHORIZED",
    }
    assert state["locked"]["phases"] == [f"N{i}" for i in range(1, 9)]
    assert state["locked"]["data_gates"] == [
        "G1_CALIBRATION_20",
        "G2_PILOT_100",
        "G3_FULL_LIBRARY",
    ]
    assert state["required_stop_after"]["phase"] == "N0"


def test_at_n0_gate_02_n1_n8_task_files_locked(project_root: Path) -> None:
    """AT-N0-GATE-02: every N1-N8 task yaml is LOCKED."""
    task_files = sorted((project_root / "tasks").glob("phase_n[1-8]_*.yaml"))
    assert len(task_files) == 8, f"expected 8 locked task files, found {len(task_files)}"
    for path in task_files:
        text = path.read_text(encoding="utf-8")
        assert 'status: "LOCKED"' in text, f"{path.name} is not locked"


def test_at_n0_gate_02_authorization_snapshot_n0_only() -> None:
    """AT-N0-GATE-02: the authorization reader confirms N0-only state."""
    auth = load_authorization()
    assert auth.phase_id == "N0"
    assert auth.phase_authorized
    assert auth.data_gate_id == "G0_THREE_SYNTHETIC_FIXTURES"
    assert auth.data_gate_authorized
    assert auth.is_ingest_authorized(dry_run=True)
    assert not auth.is_ingest_authorized(dry_run=False)
