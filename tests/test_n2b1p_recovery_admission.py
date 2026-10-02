from __future__ import annotations

import pytest

from nightly_photo_intelligence_pipeline.n2b1p_recovery_admission import (
    RecoveryAdmission,
    ensure_existing_root,
    validate_recovery_admission,
)


def _valid() -> RecoveryAdmission:
    return RecoveryAdmission(
        capability="N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
        artifact_id="torchvision-keypointrcnn-resnet50-fpn-coco-v1",
        quarantine_run_id="run-20261002-example",
        runtime_configuration_digest="a" * 64,
        cache_root_identity="b" * 64,
    )


def test_recovery_admission_does_not_require_cache_hit():
    validate_recovery_admission(
        _valid(),
        expected_capability="N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
        expected_runtime_configuration_digest="a" * 64,
        expected_cache_root_identity="b" * 64,
    )


@pytest.mark.parametrize(
    "field,expected,match",
    [
        ("capability", "WRONG", "capability"),
        ("runtime_configuration_digest", "c" * 64, "runtime"),
        ("cache_root_identity", "d" * 64, "cache identity"),
    ],
)
def test_recovery_admission_rejects_identity_drift(field: str, expected: str, match: str):
    value = _valid().__dict__
    value[field] = expected
    with pytest.raises(ValueError, match=match):
        validate_recovery_admission(
            RecoveryAdmission(**value),
            expected_capability="N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
            expected_runtime_configuration_digest="a" * 64,
            expected_cache_root_identity="b" * 64,
        )


def test_recovery_admission_rejects_missing_binding():
    value = _valid().__dict__
    value["artifact_id"] = ""
    with pytest.raises(ValueError, match="binding"):
        validate_recovery_admission(
            RecoveryAdmission(**value),
            expected_capability="N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
            expected_runtime_configuration_digest="a" * 64,
            expected_cache_root_identity="b" * 64,
        )


def test_root_check_has_no_creation_side_effect(tmp_path):
    with pytest.raises(FileNotFoundError, match="missing"):
        ensure_existing_root(tmp_path / "missing")
