"""Candidate identity binding for the final Real20 implementation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..engineering.common import sha256, strict_json
from ..engineering.source_identity import full_source_identity


def candidate_identity(project_root: Path) -> dict[str, Any]:
    identity = full_source_identity(Path(project_root))
    state_path = Path(project_root) / "PROJECT_STATE.json"
    state_bytes = state_path.read_bytes()
    state = strict_json(state_bytes)
    if not isinstance(state, dict) or state.get("phase_status", {}).get("N2B2") != "LOCKED":
        raise ValueError("REAL20_PROJECT_STATE_NOT_LOCKED")
    identity = dict(identity)
    identity["project_state_sha256"] = sha256(state_bytes)
    identity["project_state_n2b2"] = "LOCKED"
    return identity
