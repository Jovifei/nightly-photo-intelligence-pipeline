"""Authorization snapshot read from PROJECT_STATE.json.

The pipeline is double-gated (phase gate + data gate). In N1 the phase is N1
AUTHORIZED on G0 (three synthetic fixtures, max_assets=3). Non-dry-run ingest
is an N1 capability but is bounded by the G0 asset cap: a 4th asset must be
rejected. Real photo access, EXIF real-data read, model downloads, cloud, and
OpenClaw remain NOT_AUTHORIZED.
N2A is a model-free capability gate. N2B model download and inference remain
locked even while N2A planning is authorized.
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
    exif_real_data_read: str
    project_root: Path
    max_assets: int | None
    n0_baseline_commit: str | None
    n1_baseline_commit: str | None = None
    g1_completion_status: str = "UNKNOWN"
    n2a_status: str = "LOCKED"
    n2b_status: str = "LOCKED"

    @property
    def phase_authorized(self) -> bool:
        return self.phase_status in {"AUTHORIZED", "APPROVED_COMPLETE"}

    @property
    def data_gate_authorized(self) -> bool:
        return self.data_gate_status == "AUTHORIZED"

    @property
    def is_n0(self) -> bool:
        return self.phase_id == "N0"

    @property
    def is_n1(self) -> bool:
        return self.phase_id == "N1"

    @property
    def n2a_authorized(self) -> bool:
        return self.n2a_status == "AUTHORIZED"

    @property
    def n2b_model_authorized(self) -> bool:
        return self.n2b_status == "AUTHORIZED"

    def phase_at_least(self, required_phase: str) -> bool:
        """True if the authorized phase is >= required_phase."""
        if not self.phase_authorized:
            return False
        authorized_level = _PHASE_ORDER.get(self.phase_id, -1)
        required_level = _PHASE_ORDER.get(required_phase, 99)
        return authorized_level >= required_level

    def is_ingest_authorized(self, *, dry_run: bool) -> bool:
        """Dry-run ingest is an N0 capability; real ingest requires N1+.

        Real ingest is further bounded by the G0 asset cap (max_assets).
        """
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

    def asset_cap(self) -> int | None:
        """Return the max-assets cap for the active data gate, or None."""
        return self.max_assets

    def require_asset_within_cap(self, current_count: int, added: int = 1) -> None:
        """Raise GateNotAuthorizedError if adding *added* assets exceeds the cap.

        The G0 cap is 3 synthetic fixtures. A 4th asset must be rejected. This
        enforces the data-gate boundary independently of the phase gate.
        """
        cap = self.max_assets
        if cap is None:
            return  # no cap defined; phase gate still applies
        if current_count + added > cap:
            raise GateNotAuthorizedError(
                f"asset cap exceeded: data gate {self.data_gate_id} allows at most "
                f"{cap} assets; current={current_count}, attempted to add {added}",
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
    data_scope = data.get("data_scope", {}) or {}
    baselines = data.get("baselines", {}) or {}
    n0_baseline = baselines.get("N0", data.get("n0_baseline", {})) or {}
    n1_baseline = baselines.get("N1", {}) or {}
    phase_status = data.get("phase_status", {}) or {}
    capability_gates = auth.get("capability_gates", {}) or {}
    return AuthorizationSnapshot(
        phase_id=phase.get("id", "UNKNOWN"),
        phase_status=phase.get("status", "UNKNOWN"),
        data_gate_id=gate.get("id", "UNKNOWN"),
        data_gate_status=gate.get("status", "UNKNOWN"),
        real_photo_access=auth.get("real_photo_access", "NOT_AUTHORIZED"),
        large_model_downloads=auth.get("large_model_downloads", "NOT_AUTHORIZED"),
        openclaw_activation=auth.get("openclaw_activation", "NOT_AUTHORIZED"),
        exif_real_data_read=auth.get("exif_real_data_read", "NOT_AUTHORIZED"),
        project_root=root,
        max_assets=data_scope.get("max_assets"),
        n0_baseline_commit=n0_baseline.get("commit"),
        n1_baseline_commit=n1_baseline.get("commit"),
        g1_completion_status=capability_gates.get(
            "G1_COMPLETION", phase_status.get("G1", "UNKNOWN")
        ),
        n2a_status=capability_gates.get(
            "N2A_POSE_SEGMENTATION_BENCHMARK_PREPARATION", phase_status.get("N2A", "LOCKED")
        ),
        n2b_status=capability_gates.get(
            "N2B_MODEL_DOWNLOAD_AND_INFERENCE", phase_status.get("N2B", "LOCKED")
        ),
    )
