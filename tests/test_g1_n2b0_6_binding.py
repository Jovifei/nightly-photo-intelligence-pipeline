"""N2B0.6 state upgrades preserve the immutable historical G1 approval."""

from __future__ import annotations

from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.errors import GateNotAuthorizedError
from nightly_photo_intelligence_pipeline.ingest.g1_contract import load_g1_approval


def test_g1_historical_approval_cannot_reopen_photo_access_in_n2b1p(project_root: Path) -> None:
    """The immutable G1 record remains archival only during cache promotion."""
    with pytest.raises(GateNotAuthorizedError):
        load_g1_approval(project_root)
