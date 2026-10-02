from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nightly_photo_intelligence_pipeline.real20 import Real20Error
from nightly_photo_intelligence_pipeline.real20.cleanup_capability import (
    validate_cleanup_capability,
)

NOW = datetime(2026, 10, 2, 12, 0, tzinfo=UTC)


def _capability() -> dict[str, str]:
    return {
        "capability_version": "npi-real20-cleanup-capability-v1",
        "probe_nonce_sha256": "a" * 64,
        "probe_object_sha256": "b" * 64,
        "cleanup_identity_sha256": "c" * 64,
        "expires_at_utc": "2026-10-02T13:00:00Z",
    }


def test_cleanup_capability_validates_binding() -> None:
    result = validate_cleanup_capability(
        _capability(),
        now=NOW,
        expected_probe_object_sha256="b" * 64,
        expected_cleanup_identity_sha256="c" * 64,
    )
    assert result.probe_object_sha256 == "b" * 64


@pytest.mark.parametrize(
    "mutator, error",
    [
        (lambda value: value.update({"probe_object_sha256": "x"}), "DIGEST_INVALID"),
        (lambda value: value.update({"capability_version": "old"}), "VERSION_INVALID"),
    ],
)
def test_cleanup_capability_rejects_invalid_values(mutator, error: str) -> None:
    value = _capability()
    mutator(value)
    with pytest.raises(Real20Error, match=error):
        validate_cleanup_capability(value, now=NOW)


def test_cleanup_capability_expired_fails_closed() -> None:
    value = _capability()
    value["expires_at_utc"] = (NOW - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    with pytest.raises(Real20Error, match="EXPIRED"):
        validate_cleanup_capability(value, now=NOW)
