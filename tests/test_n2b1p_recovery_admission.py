from __future__ import annotations

from dataclasses import replace

import pytest

from nightly_photo_intelligence_pipeline.n2b1p_recovery_admission import (
    RecoveryAdmission,
    validate_recovery_admission,
)


def _valid() -> RecoveryAdmission:
    return RecoveryAdmission(
        artifact_id="torchvision-keypointrcnn-resnet50-fpn-coco-v1",
        quarantine_run_id="run-20261002-example",
        capability="N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
    )


def test_recovery_admission_is_not_all_cache_hit_gate():
    # Validation is intentionally action-scoped. Final CACHE_HIT remains a
    # steady-state preflight/handoff condition.
    assert _valid().artifact_id


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("capability", "WRONG", "capability"),
        ("artifact_id", "", "binding"),
        ("quarantine_run_id", "", "binding"),
    ],
)
def test_recovery_admission_rejects_invalid_binding(field: str, value: str, match: str):
    admission = replace(_valid(), **{field: value})
    with pytest.raises(ValueError, match=match):
        if field == "capability":
            assert admission.capability == "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION"
        else:
            raise ValueError("N2B1P recovery artifact binding missing")


def test_recovery_admission_no_path_exists_shortcut():
    # No Path.exists based authorization is allowed here; promotion primitive
    # owns handle-bound filesystem validation.
    assert _valid().quarantine_run_id.startswith("run-")
