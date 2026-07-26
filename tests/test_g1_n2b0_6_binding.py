"""N2B0.6 state upgrades preserve the immutable historical G1 approval."""

from __future__ import annotations

from pathlib import Path

from nightly_photo_intelligence_pipeline.ingest.g1_contract import load_g1_approval


def test_g1_historical_approval_remains_valid_under_closed_n2b0_6_state(project_root: Path) -> None:
    approval = load_g1_approval(project_root)
    assert approval.manifest_count == 20
