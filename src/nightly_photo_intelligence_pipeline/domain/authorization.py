"""Authorization snapshot read from PROJECT_STATE.json.

The pipeline is double-gated (phase gate + data gate). In N0 only the N0 phase
and G0 data gate are authorized; non-dry-run ingest is an N1 capability and
must fail closed with NPI_GATE_NOT_AUTHORIZED (exit 8).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .._paths import find_project_root
from .errors import GateNotAuthorizedError

# Phase ordering for capability checks. non-dry-run ingest requires N1+.
_PHASE_ORDER: dict[str, int] = {
    "N0": 0,
    "N1": 1,
    "N2": 2,
    "N3": 3,
    "N4": 4,
    "N5": 5,
    "N6": 6,
    "N7": 7,
    "N8": 8,
}


@dataclass(frozen=True)
class AuthorizationSnapshot:
    """Immutable view of the current authorization state."""

    phase_id: str
    phase_status: str
    data_gate_id: str
    data_gate_status: str
    real_photo_access: str
    large_model_downloads: str
    openclaw_activation: str
    project_root: Path

    @property
    def phase_authorized(self) -> bool:
        return self.phase_status == "AUTHORIZED"

    @property
    def data_gate_authorized(self) -> bool:
        return self.data_gate_status == "AUTHORIZED"

    @property
    def is_n0(self) -> bool:
        return self.phase_id == "N0"

    def phase_at_least(self, required_phase: str) -> bool:
        """True if the authorized phase is >= required_phase."""
        if not self.phase_authorized:
            return False
        authorized_level = _PHASE_ORDER.get(self.phase_id, -1)
        required_level = _PHASE_ORDER.get(required_phase, 99)
        return authorized_level >= required_level

    def is_ingest_authorized(self, *, dry_run: bool) -> bool:
        """Dry-run ingest is an N0 capability; real ingest requires N1+."""
        if not self.phase_authorized or not self.data_gate_authorized:
            return False
        if dry_run:
            return self.is_n0 or self.phase_at_least("N1")
        # Non-dry-run ingest mutates the asset table -> N1 capability.
        return self.phase_at_least("N1")

    def require_ingest_authorized(self, *, dry_run: bool) -> None:
        """Raise GateNotAuthorizedError if ingest is not authorized."""
        if not self.is_ingest_authorized(dry_run=dry_run):
            kind = "dry-run" if dry_run else "non-dry-run"
            raise GateNotAuthorizedError(
                f"{kind} ingest is not authorized in phase {self.phase_id} "
                f"({self.phase_status}); data gate {self.data_gate_id} "
                f"({self.data_gate_status})",
            )


def load_authorization(project_root: Path | None = None) -> AuthorizationSnapshot:
    """Read PROJECT_STATE.json from the project root."""
    root = project_root or find_project_root()
    state_path = root / "PROJECT_STATE.json"
    if not state_path.is_file():
        raise GateNotAuthorizedError(
            "PROJECT_STATE.json not found; cannot determine authorization",
        )
    data = json.loads(state_path.read_text(encoding="utf-8"))
    auth = data.get("authorization", {})
    phase = auth.get("phase", {})
    gate = auth.get("data_gate", {})
    return AuthorizationSnapshot(
        phase_id=phase.get("id", "UNKNOWN"),
        phase_status=phase.get("status", "UNKNOWN"),
        data_gate_id=gate.get("id", "UNKNOWN"),
        data_gate_status=gate.get("status", "UNKNOWN"),
        real_photo_access=auth.get("real_photo_access", "NOT_AUTHORIZED"),
        large_model_downloads=auth.get("large_model_downloads", "NOT_AUTHORIZED"),
        openclaw_activation=auth.get("openclaw_activation", "NOT_AUTHORIZED"),
        project_root=root,
    )
