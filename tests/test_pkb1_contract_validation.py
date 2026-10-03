"""Consumer-origin synthetic regression; never producer golden evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tools.pkb1_canonical import canonical_pkb1_bytes, pkb1_sha256
from tools.pkb1_contract_validation import (BundleContractError, MAX_INPUT_BYTES,
                                           pkb1_canonical_bytes, validate_bundle)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/consumer_origin_synthetic_pkb1.json"
DIGEST = "9bd85c8b1be3e3544d9a74b4140e59fc57f85e6b97a343d7c6fba2018048bb69"


class PKB1ContractTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_actual_frozen_fixture_digest(self):
        self.assertEqual(pkb1_sha256(self.payload), DIGEST)
        self.assertIs(pkb1_canonical_bytes, canonical_pkb1_bytes)
        result = validate_bundle(FIXTURE)
        self.assertEqual(result["pkb1_payload_sha256"], DIGEST)
        self.assertFalse(result["authority"])
        self.assertFalse(result["ready_for_t14"])

    def test_names_values_and_utf8_byte_lengths(self):
        self.payload["references"][0]["photography"]["scene"] = "光\n🙂"
        data = canonical_pkb1_bytes(self.payload)
        self.assertTrue(data.startswith(b"PKB1\n16:contract_version\n3:1.0\n"))
        self.assertIn(b"31:references[0].photography.scene\n8:" + "光\n🙂".encode() + b"\n", data)

    def test_array_order_and_required_field_mutations(self):
        second = copy.deepcopy(self.payload["references"][0])
        second["reference_id"] = "second"
        self.payload["references"].append(second)
        digest = pkb1_sha256(self.payload)
        self.payload["references"].reverse()
        self.assertNotEqual(digest, pkb1_sha256(self.payload))
        for key in self.payload["references"][0]["photography"]:
            mutated = copy.deepcopy(self.payload)
            mutated["references"][0]["photography"][key] += "changed"
            self.assertNotEqual(pkb1_sha256(self.payload), pkb1_sha256(mutated))

    def test_root_reference_id_and_string_type(self):
        self.payload["references"][0]["reference_id"] += "changed"
        self.assertNotEqual(pkb1_sha256(self.payload), DIGEST)
        self.payload["references"][0]["photography"]["scene"] = 3
        with self.assertRaises(ValueError):
            canonical_pkb1_bytes(self.payload)

    def test_integrity_excluded_and_object_order_irrelevant(self):
        self.payload["integrity"] = {"anything": "changed"}
        self.assertEqual(pkb1_sha256(self.payload), DIGEST)
        self.assertEqual(pkb1_sha256(dict(reversed(list(self.payload.items())))), DIGEST)

    def test_bounded_strict_json_and_digest_failures(self):
        mutated = copy.deepcopy(self.payload)
        mutated["bundle_id"] += "changed"
        samples = [b"{", b"\xff", b'{"x":1,"x":2}', b'{"x":NaN}',
                   b" " * (MAX_INPUT_BYTES + 1), json.dumps(mutated).encode(),
                   b"[1]", b"[" * 1500 + b"]" * 1500]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for sample in samples:
                with self.subTest(sample_length=len(sample)):
                    path.write_bytes(sample)
                    with self.assertRaises(BundleContractError):
                        validate_bundle(path)

    def test_uppercase_declared_digest(self):
        self.payload["integrity"]["payload_sha256"] = DIGEST.upper()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_text(json.dumps(self.payload), encoding="utf-8")
            self.assertEqual(DIGEST, validate_bundle(path)["pkb1_payload_sha256"])

    def test_cli_success_and_failure(self):
        command = [sys.executable, str(ROOT / "tools/pkb1_contract_validation.py")]
        result = subprocess.run(command + [str(FIXTURE)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["pkb1_payload_sha256"], DIGEST)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_bytes(b"\xff")
            result = subprocess.run(command + [str(path)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stderr)["authority"])
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
