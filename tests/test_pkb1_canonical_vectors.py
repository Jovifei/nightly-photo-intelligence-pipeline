import unittest
from tools.pkb1_contract_validation import pkb1_canonical_bytes, sha256_bytes


class PKB1CanonicalVectorTest(unittest.TestCase):
    def sample(self):
        return {
            "contract_version": "1.0",
            "bundle_id": "demo",
            "source": {"origin": "offline", "producer_id": "p", "release_id": "r"},
            "references": [{
                "reference_id": "ref1",
                "photography": {
                    "scene": "s", "background_story": "b", "lighting": "l",
                    "composition": "c", "subject_intent": "i", "emotion": "e",
                    "pose_template": "p", "camera_position": "cp", "director_prompt": "d"
                }
            }]
        }

    def test_known_prefix_and_field_names(self):
        data = pkb1_canonical_bytes(self.sample())
        self.assertTrue(data.startswith(b"PKB1\n6:contract_version\n"))
        self.assertIn(b"references[0].photography.scene", data)
        self.assertEqual(len(sha256_bytes(data)), 64)

    def test_mutation_changes_digest(self):
        a = self.sample()
        b = self.sample()
        b["references"][0]["photography"]["scene"] = "changed"
        self.assertNotEqual(
            sha256_bytes(pkb1_canonical_bytes(a)),
            sha256_bytes(pkb1_canonical_bytes(b)),
        )

if __name__ == '__main__':
    unittest.main()
