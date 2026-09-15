"""Validate immutable historical S20 provenance, without granting execution.

The review's commit is NOT the current execution commit. The current candidate
must independently remain bound by the new source identity, Owner lease, and
controlled-entry reservation. No historical approval is edited or upgraded.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from ..engineering.common import is_digest, require, sha256, strict_json


def validate_legacy_s20_binding(project_root: Path, prior_review: Path, manifest: Path) -> str:
    # Reuse the real validators, not a new permissive reimplementation.
    from .controlled_runtime import _regular_file
    from .s20_orchestrator import _artifact_integrity_gate, _review_gate

    _, review_bytes = _regular_file(prior_review)
    review = strict_json(review_bytes)
    require(isinstance(review, Mapping), "NPI_PRIOR_REVIEW_INVALID")
    historical_commit = review.get("reviewed_commit")
    require(is_digest(historical_commit, 40), "NPI_PRIOR_REVIEW_INVALID")
    assert isinstance(historical_commit, str)
    owner = project_root / "approvals" / "owner_n2b2_s20_synthetic_validation_receipt.yaml"
    qwen = project_root / "approvals" / "owner_n2b2_qwen_fact_binding_remediation_receipt.yaml"
    integrity = (
        project_root / "approvals" / "owner_n2b2_s20_artifact_integrity_remediation_receipt.yaml"
    )
    for path in (owner, qwen, integrity):
        _regular_file(path)
    _review_gate(prior_review, owner, qwen, historical_commit)
    _, manifest_bytes = _regular_file(manifest)
    _artifact_integrity_gate(
        integrity, reviewed_commit=historical_commit, manifest_sha256=sha256(manifest_bytes)
    )
    return historical_commit
