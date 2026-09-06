"""On-disk N2B1P independent-review gate for the bounded N2B2 smoke run."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

REQUIRED_RESULT = "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"


def validate_n2b1p_review(evidence: dict[str, Any]) -> tuple[bool, str]:  # noqa: PLR0911
    """Require independent evidence fields; phase-completion is not this gate."""

    if evidence.get("result") != REQUIRED_RESULT:
        return False, "N2B1P evidence result is not the reviewed continuation state"
    if evidence.get("review_verdict") != "PASS":
        return False, "N2B1P independent review_verdict is not PASS"
    reviewer = evidence.get("independent_reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        return False, "N2B1P independent_reviewer is empty"
    external_review = evidence.get("external_review")
    if not isinstance(external_review, dict):
        return False, "N2B1P external_review is missing"
    reviewed_at = external_review.get("reviewed_at_utc")
    if not isinstance(reviewed_at, str) or not reviewed_at.endswith("Z"):
        return False, "N2B1P reviewed_at_utc is not UTC"
    try:
        datetime.fromisoformat(reviewed_at[:-1] + "+00:00")
    except ValueError:
        return False, "N2B1P reviewed_at_utc is invalid"
    if external_review.get("all_three_artifacts_cache_hit_verified") is not True:
        return False, "N2B1P three-cache-hit review field is not true"
    if external_review.get("prohibited_actions_confirmed") is not True:
        return False, "N2B1P prohibited-actions review field is not true"
    return True, "N2B1P independent review passed"


def validate_bounded_synthetic_authorization(
    completion: Mapping[str, Any],
    receipt: Mapping[str, Any],
    project_state: Mapping[str, Any],
    completion_sha256: str,
) -> tuple[bool, str]:
    """Validate the Owner records required before any N2B2 synthetic model call."""

    baseline = completion.get("baseline")
    if not isinstance(baseline, Mapping):
        return False, "N2B1P phase-completion baseline is missing"
    review = completion.get("independent_review")
    boundaries = receipt.get("boundaries")
    if not isinstance(boundaries, Mapping):
        return False, "N2B2 Owner receipt boundaries are missing"
    state_status = project_state.get("phase_status")
    if not isinstance(state_status, Mapping) or state_status.get("N2B2") != "LOCKED":
        return False, "N2B2 PROJECT_STATE lock is not preserved"
    production = receipt.get("production_state")
    if not isinstance(production, Mapping) or production.get("production_unlock") is not False:
        return False, "N2B2 production unlock boundary is not false"
    checks = [
        (completion.get("status") == "APPROVED", "N2B1P phase-completion record is not approved"),
        (completion.get("phase_id") == "N2B1P", "N2B1P phase id mismatch"),
        (
            isinstance(baseline.get("candidate_commit"), str)
            and len(baseline["candidate_commit"]) == 40,
            "N2B1P candidate commit is invalid",
        ),
        (
            isinstance(review, Mapping) and review.get("verdict") == "PASS_FOR_OWNER_REVIEW",
            "N2B1P independent review is not PASS_FOR_OWNER_REVIEW",
        ),
        (receipt.get("status") == "APPROVED", "N2B2 Owner receipt is not approved"),
        (
            receipt.get("task") == "N2B2_SYNTHETIC_MODEL_STACK_VALIDATION",
            "N2B2 Owner receipt task mismatch",
        ),
        (
            receipt.get("scope") == "SYNTHETIC_GPU_S3_S20_ONLY",
            "N2B2 Owner receipt scope mismatch",
        ),
        (
            receipt.get("n2b1p_completion_sha256") == completion_sha256,
            "N2B1P completion hash does not match Owner receipt",
        ),
    ]
    checks.extend(
        (
            boundaries.get(field) is False,
            f"N2B2 boundary {field} is not false",
        )
        for field in (
            "real_photo",
            "real_exif",
            "g1_source",
            "sqlite",
            "real20",
            "project_state_mutation",
            "production_bundle",
        )
    )
    for valid, detail in checks:
        if not valid:
            return False, detail
    return True, "bounded N2B2 synthetic authorization passed"
