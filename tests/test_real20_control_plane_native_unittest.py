"""Windows-native acceptance for the pre-opened Real20 cleanup handle."""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from nightly_photo_intelligence_pipeline.real20.cleanup_helper import (
    cleanup_helper_identity_sha256,
    cleanup_inherited_probe_handle,
)
from nightly_photo_intelligence_pipeline.windows_bound_promotion import (
    bind_existing_directory,
    current_process_identity_sha256,
)


@unittest.skipUnless(sys.platform == "win32", "Windows native handle test")
class TestReal20PreopenedCleanupHandle(unittest.TestCase):
    def test_policy_and_token_digests_are_stable_for_live_handle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="npi-real20-policy-") as temp:
            root = Path(temp) / "root"
            root.mkdir()
            with bind_existing_directory(root, writable=False, security_check=True) as bound:
                first = bound.security_policy_digest()
                second = bound.security_policy_digest()
            self.assertEqual(first, second)
            self.assertEqual(len(first), 64)
            self.assertEqual(len(current_process_identity_sha256()), 64)

    def test_released_handle_is_adopted_and_cleans_exact_probe_only(self) -> None:
        nonce = "e" * 64
        with tempfile.TemporaryDirectory(prefix="npi-real20-helper-") as temp:
            root = Path(temp) / "probe-root"
            claim = root / "probe"
            root.mkdir()
            claim.mkdir()
            (claim / "reservation.json").write_bytes(b"reservation")
            (claim / f"terminal-v1-{nonce}.json").write_bytes(b"terminal")

            with bind_existing_directory(root, writable=True, security_check=True) as parent:
                opened = parent.open_directory("probe", writable=True)
                object_digest = opened.identity.digest
                inherited_handle, released_digest = opened.release_for_inheritance()
                self.assertEqual(released_digest, object_digest)

            capability = {
                "capability_version": "npi-real20-cleanup-capability-v1",
                "probe_nonce_sha256": nonce,
                "probe_object_sha256": object_digest,
                "cleanup_identity_sha256": cleanup_helper_identity_sha256(),
                "expires_at_utc": "2099-01-01T00:00:00Z",
            }
            result = cleanup_inherited_probe_handle(
                inherited_handle,
                capability,
                expected_probe_nonce_sha256=nonce,
                now=datetime.now(UTC),
            )

            self.assertEqual(result["cleanup_status"], "CLEANUP_PASS")
            self.assertFalse(claim.exists())
            self.assertTrue(root.exists())
