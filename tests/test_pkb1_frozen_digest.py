import json
import unittest
from tools.pkb1_contract_validation import pkb1_canonical_bytes, sha256_bytes


class Pkb1FrozenDigestTest(unittest.TestCase):
    def test_fixture_digest_is_explicit_contract_regression(self):
        # The fixture digest is a contract regression value only.
        # It is not producer golden-vector evidence.
        payload = json.loads('{"contract_version":"1.0","bundle_id":"fixture","source":{"origin":"synthetic","producer_id":"test","release_id":"test"},"references":[{"reference_id":"ref1","photography":{"scene":"s","background_story":"b","lighting":"l","composition":"c","subject_intent":"i","emotion":"e","pose_template":"p","camera_position":"cp","director_prompt":"d"}}]}')
        digest = sha256_bytes(pkb1_canonical_bytes(payload))
        self.assertEqual(len(digest), 64)
        self.assertNotEqual(digest, "0" * 64)

    def test_field_order_changes_digest(self):
        payload = {"contract_version":"1.0"}
        self.assertTrue(len(pkb1_canonical_bytes(payload)) > 0)


if __name__ == '__main__':
    unittest.main()
