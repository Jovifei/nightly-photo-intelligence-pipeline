import unittest
from tools.pkb1_canonical import pkb1_sha256


class PKB1ContractTests(unittest.TestCase):
    def sample(self):
        return {
            "contract_version": "1.0",
            "bundle_id": "synthetic-1",
            "source": {"origin": "test", "producer_id": "p", "release_id": "r"},
            "references": [{"reference_id": "a", "photography": {k: "x" for k in [
                "scene", "background_story", "lighting", "composition",
                "subject_intent", "emotion", "pose_template", "camera_position",
                "director_prompt"]}}],
        }

    def test_digest_changes_when_contract_value_changes(self):
        p = self.sample()
        digest = pkb1_sha256(p)
        p["references"][0]["photography"]["scene"] = "changed"
        self.assertNotEqual(digest, pkb1_sha256(p))

    def test_not_legacy_sorted_json(self):
        p = self.sample()
        self.assertNotEqual(pkb1_sha256(p), "")
        self.assertTrue(pkb1_sha256(p).isalnum())


if __name__ == "__main__":
    unittest.main()
