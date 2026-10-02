"""Bounded N2B1P recovery admission primitives.

Recovery admission is intentionally separate from steady-state CACHE_HIT
verification. It validates the same control-plane bindings used by the
promotion primitive before allowing an individual promotion attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .local_research_promotion import load_authorized_promotion
from .n2b1p_integrity import load_n2b1p_runtime_configuration


@dataclass(frozen=True)
class RecoveryAdmission:
    artifact_id: str
    quarantine_run_id: str
    capability: str


def validate_recovery_admission(
    admission: RecoveryAdmission,
    *,
    project_root: Path,
) -> None:
    """Validate one recovery action without requiring all artifacts CACHE_HIT.

    The final three-artifact CACHE_HIT requirement remains a stage-close
    condition owned by preflight/handoff. This function only admits the
    individual promotion action.
    """
    if admission.capability != "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION":
        raise ValueError("N2B1P recovery capability mismatch")
    if not admission.artifact_id or not admission.quarantine_run_id:
        raise ValueError("N2B1P recovery artifact binding missing")

    runtime = load_n2b1p_runtime_configuration(project_root)
    selected = load_authorized_promotion(admission.artifact_id, project_root=project_root)

    if not selected.artifact_id == admission.artifact_id:
        raise ValueError("N2B1P recovery artifact identity mismatch")
    if selected.runtime_configuration_digest != runtime.configuration_digest:
        raise ValueError("N2B1P recovery runtime binding mismatch")

    # Do not replace handle-bound validation with Path.exists(). The actual
    # cache-root identity is checked by promote_artifact through
    # windows_bound_promotion.bind_existing_directory.
