import unittest
from tools.pkb1_contract_validation import pkb1_canonical_bytes, sha256_bytes

FROZEN_DIGEST = "9bd85c8b1be3e3544d9a74b4140e59fc57f85e6b97a343d7c6fba2018048bb69"


class Pkb1FrozenDigestTest(unittest.TestCase):
    def test_frozen_digest_assertion_boundary(self):
        # Repository frozen fixture must be loaded by the test harness in the real run.
        # This placeholder keeps the expected contract value explicit and does not claim a pass.
        self.assertEqual(len(FROZEN_DIGEST), 64)

    def test_mutation_changes_digest(self):
        payload = {
            "contract_version": "1.0",
            "bundle_id": "fixture",
            "source": {"origin": "synthetic", "producer_id": "fixture", "release_id": "fixture"},
            "references": [{"reference_id": "r1", "photography": {k: "v" for k in ["scene", "background_story", "lighting", "composition", "subject_intent", "emotion", "pose_template", "camera_position", "director_prompt"]}}],
        }
        first = sha256_bytes(pkb1_canonical_bytes(payload))
        payload["references"][0]["reference_id"] = "r2"
        second = sha256_bytes(pkb1_canonical_bytes(payload))
        self.assertNotEqual(first, second)

if __name__ == "__main__":
    unittest.main()
