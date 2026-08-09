"""On-disk N2B1P independent-review gate for the bounded N2B2 smoke run."""

from __future__ import annotations

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
