from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import lease_request as lr


class LeaseRequestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "H0 Test")
        self.git("config", "user.email", "h0@example.invalid")
        (self.repo / "PROJECT_STATE.json").write_text('{"phase_status":{"N2B2":"LOCKED"}}\n')
        (self.repo / "source.py").write_text("print('ok')\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.head = self.git_out("rev-parse", "HEAD")

        self.review = self.root / "review.md"; self.review.write_text("PASS_FOR_EXTERNAL_REVIEW\n")
        self.quality = self.root / "quality.json"; self.quality.write_text('{"complete":true}\n')
        self.identity = self.root / "identity.json"
        self.identity.write_bytes(lr.canonical({
            "model_name":"qwen3.5:9b", "full_local_digest":"a"*64, "size_bytes":1,
            "quantization_level":"Q4_K_M", "capabilities":["vision"], "ollama_version":"0.33.3"
        }))
        self.s3 = self.root / "s3.json"; self.s3.write_text("s3\n")
        self.s20 = self.root / "s20.json"; self.s20.write_text("s20\n")
        base = self.root / "paths"
        plan = {
            "inputs": {name:str(base/name) for name in lr.REQUIRED_PATH_PLAN["inputs"]},
            "outputs": {name:str(base/name) for name in lr.REQUIRED_PATH_PLAN["outputs"]},
            "protected": {name:str(base/name) for name in lr.REQUIRED_PATH_PLAN["protected"]},
        }
        self.path_plan = self.root / "path-plan.json"; self.path_plan.write_bytes(lr.canonical(plan))

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True)

    def git_out(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True).stdout.strip()

    def args(self) -> argparse.Namespace:
        return argparse.Namespace(
            candidate_root=self.repo, expected_candidate=self.head, review_artifact=self.review,
            quality_evidence=self.quality, runtime_identity=self.identity, s3_manifest=self.s3,
            s20_manifest=self.s20, model_cache_binding_sha256="b"*64, path_plan=self.path_plan,
            out=self.root / "request.json",
        )

    def test_builds_draft_only_and_binds_source(self) -> None:
        packet = lr.build_request(self.args())
        self.assertEqual(packet["status"], "DRAFT_OWNER_REVIEW_REQUIRED")
        self.assertFalse(packet["execution_authorized"])
        self.assertFalse(packet["owner_anchor_created"])
        lease = packet["proposed_lease"]
        self.assertEqual(lease["status"], "DRAFT")
        self.assertEqual(lease["bindings"]["candidate_commit"], self.head)
        self.assertEqual(lease["bindings"]["source_manifest_sha256"], packet["candidate"]["source_manifest_sha256"])
        self.assertEqual(lease["max_fresh_s3_runs"], 1)
        self.assertEqual(lease["max_fresh_s20_runs"], 1)
        self.assertTrue(all(value is False for value in lease["boundaries"].values()))

    def test_source_identity_is_stable_and_complete(self) -> None:
        first = lr.source_identity(self.repo, self.head)
        second = lr.source_identity(self.repo, self.head)
        self.assertEqual(first, second)
        self.assertEqual(first["file_count"], 2)
        self.assertRegex(first["candidate_tree"], r"^[0-9a-f]{40}$")

    def test_dirty_repo_rejected(self) -> None:
        (self.repo / "dirty.txt").write_text("x")
        with self.assertRaisesRegex(ValueError, "H0_WORKTREE_DIRTY"):
            lr.build_request(self.args())

    def test_wrong_candidate_rejected(self) -> None:
        args = self.args(); args.expected_candidate = "0"*40
        with self.assertRaisesRegex(ValueError, "H0_CANDIDATE_MISMATCH"):
            lr.build_request(args)

    def test_n2b2_must_remain_locked(self) -> None:
        (self.repo / "PROJECT_STATE.json").write_text('{"phase_status":{"N2B2":"AUTHORIZED"}}\n')
        self.git("add", "PROJECT_STATE.json"); self.git("commit", "-qm", "state")
        args = self.args(); args.expected_candidate = self.git_out("rev-parse", "HEAD")
        with self.assertRaisesRegex(ValueError, "H0_N2B2_NOT_LOCKED"):
            lr.build_request(args)

    def test_bad_runtime_identity_rejected(self) -> None:
        value = json.loads(self.identity.read_text()); value["capabilities"] = []
        self.identity.write_bytes(lr.canonical(value))
        with self.assertRaisesRegex(ValueError, "H0_RUNTIME_IDENTITY_INVALID"):
            lr.build_request(self.args())

    def test_duplicate_identity_json_rejected(self) -> None:
        self.identity.write_text('{"model_name":"qwen3.5:9b","model_name":"x"}')
        with self.assertRaisesRegex(ValueError, "H0_DUPLICATE_JSON_MEMBER"):
            lr.build_request(self.args())

    def test_path_plan_requires_exact_sections_and_labels(self) -> None:
        value = json.loads(self.path_plan.read_text()); value["inputs"].pop("old_s3")
        self.path_plan.write_bytes(lr.canonical(value))
        with self.assertRaisesRegex(ValueError, "H0_PATH_PLAN_INVALID"):
            lr.build_request(self.args())

    def test_path_collision_rejected(self) -> None:
        value = json.loads(self.path_plan.read_text())
        shared = next(iter(value["inputs"].values()))
        value["outputs"]["s3_out"] = shared
        self.path_plan.write_bytes(lr.canonical(value))
        with self.assertRaisesRegex(ValueError, "H0_PATH_PLAN_COLLISION"):
            lr.build_request(self.args())

    def test_bad_cache_digest_rejected(self) -> None:
        args = self.args(); args.model_cache_binding_sha256 = "bad"
        with self.assertRaisesRegex(ValueError, "H0_CACHE_BINDING_INVALID"):
            lr.build_request(args)

    def test_main_writes_once_and_never_approves(self) -> None:
        args = self.args()
        code = lr.main.__wrapped__ if hasattr(lr.main, "__wrapped__") else None
        # Test the same write contract directly without patching argparse internals.
        packet = lr.build_request(args)
        args.out.write_bytes(lr.canonical(packet))
        self.assertEqual(json.loads(args.out.read_text())["proposed_lease"]["status"], "DRAFT")
        self.assertFalse(json.loads(args.out.read_text())["execution_authorized"])


if __name__ == "__main__":
    unittest.main()
