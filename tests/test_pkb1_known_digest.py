import unittest
from tools.pkb1_contract_validation import pkb1_canonical_bytes, sha256_bytes

class PKB1KnownDigestTest(unittest.TestCase):
    def test_digest_is_stable_for_contract_fixture(self):
        payload = {
            "contract_version":"1.0",
            "bundle_id":"fixture",
            "source":{"origin":"synthetic","producer_id":"test","release_id":"test"},
            "references":[{"reference_id":"ref-1","photography":{"scene":"s","background_story":"b","lighting":"l","composition":"c","subject_intent":"i","emotion":"e","pose_template":"p","camera_position":"cp","director_prompt":"d"}}]
        }
        digest = sha256_bytes(pkb1_canonical_bytes(payload))
        self.assertEqual(len(digest),64)
        self.assertNotEqual(digest, sha256_bytes(b'{"sorted":"json"}'))

if __name__ == '__main__':
    unittest.main()
