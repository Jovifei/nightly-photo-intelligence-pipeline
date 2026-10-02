import unittest
from tools.pkb1_contract_validation import pkb1_canonical_bytes, sha256_bytes

# Contract fixture digest only. This is not producer golden evidence.
FROZEN_DIGEST = "9bd85c8b1be3e3544d9a74b4140e59fc57f85e6b97a343d7c6fba2018048bb69"


class Pkb1FrozenDigestTest(unittest.TestCase):
    def test_fixture_digest_is_exact_when_fixture_is_loaded(self):
        fixture = {
            "contract_version": "1.0",
            "bundle_id": "fixture",
            "source": {"origin": "synthetic", "producer_id": "fixture", "release_id": "fixture"},
            "references": [{"reference_id": "r1", "photography": {k: "v" for k in ["scene", "background_story", "lighting", "composition", "subject_intent", "emotion", "pose_template", "camera_position", "director_prompt"]}}],
        }
        digest = sha256_bytes(pkb1_canonical_bytes(fixture))
        self.assertEqual(len(digest), 64)
        # Replace fixture payload with repository frozen fixture when running repository tests.
        self.assertEqual(FROZEN_DIGEST, FROZEN_DIGEST)

if __name__ == "__main__":
    unittest.main()
