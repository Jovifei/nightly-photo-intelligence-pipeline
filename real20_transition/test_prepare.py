"""Synthetic metadata tests only; no real image, model, network, or Owner lease."""
from __future__ import annotations
import contextlib
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import prepare as p


def make_manifest():
    return {"schema_version": "1.0", "manifest_id": "npi-manifest-test",
            "data_gate": "G1_CALIBRATION_20", "created_at": "2026-07-14T00:00:00Z",
            "source_root_fingerprint": "synthetic-fingerprint", "max_assets": 20,
            "approval_reference": "EXPIRED_HISTORICAL_REFERENCE",
            "expires_at": "2026-07-31T00:00:00Z", "assets": [
                {"asset_ref": f"private-name-{i}", "source_relative_path": f"private-photo-{i}.jpg",
                 "expected_sha256": hashlib.sha256(str(min(i, 19)).encode()).hexdigest(),
                 "size_bytes": 123, "media_type": "image/jpeg"} for i in range(1, 21)]}


def encode_manifest(value):
    data = p.canonical(value)
    return p.manifest_plan(data, p.sha(data))


class ManifestTests(unittest.TestCase):
    def test_twenty_becomes_19_canonical_and_one_reference(self):
        value = encode_manifest(make_manifest())
        self.assertEqual((value["asset_count"], value["canonical_count"], value["duplicate_count"]), (20, 19, 1))
        self.assertEqual(value["assets"][-1]["duplicate_of"], "R20-019")
        self.assertEqual(value["assets"][-1]["action"], "REFERENCE_ONLY")
        self.assertNotIn("private-photo", json.dumps(value))
        self.assertNotIn("private-name", json.dumps(value))
        self.assertFalse(value["historical_authorization_reused"])
        self.assertFalse(value["source_bytes_verified"])

    def test_no_source_access_even_for_nonexistent_asset_paths(self):
        with patch.object(Path, "open", side_effect=AssertionError("asset opened")), \
             patch.object(Path, "stat", side_effect=AssertionError("asset stat")):
            self.assertEqual(encode_manifest(make_manifest())["asset_count"], 20)

    def test_wrong_manifest_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "FROZEN_MANIFEST_MISMATCH"):
            p.manifest_plan(p.canonical(make_manifest()), "0" * 64)

    def test_21st_and_19_entry_rejected(self):
        for delta in (-1, 1):
            value = make_manifest()
            value["assets"] = value["assets"][:-1] if delta < 0 else value["assets"] + [value["assets"][0]]
            with self.subTest(delta=delta), self.assertRaisesRegex(ValueError, "EXACTLY_20"):
                encode_manifest(value)

    def test_unsafe_relative_names(self):
        for name in ("../x.jpg", "a/../b.jpg", "C:/x.jpg", "C:x.jpg", "/x.jpg", "\\\\s\\x",
                     "x.jpg:secret", "a//b.jpg", "NUL.jpg", "folder/COM1.jpg", "x. ", "x\n.jpg"):
            value = make_manifest()
            value["assets"][0]["source_relative_path"] = name
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "ASSET_PATH"):
                encode_manifest(value)

    def test_duplicate_ref_or_casefold_path_rejected(self):
        for key in ("asset_ref", "source_relative_path"):
            value = make_manifest()
            value["assets"][1][key] = value["assets"][0][key] if key == "asset_ref" else value["assets"][0][key].upper()
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "DUPLICATE_ASSET"):
                encode_manifest(value)

    def test_boolean_size_and_scope_rejected(self):
        for key in ("max_assets", "size_bytes"):
            value = make_manifest()
            (value if key == "max_assets" else value["assets"][0])[key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                encode_manifest(value)

    def test_same_digest_inconsistent_metadata_rejected(self):
        value = make_manifest()
        value["assets"][-1]["size_bytes"] += 1
        with self.assertRaisesRegex(ValueError, "DUPLICATE_METADATA"):
            encode_manifest(value)

    def test_duplicate_trailing_garbage_and_nonfinite_json(self):
        for data in (b'{"a":1,"a":2}', b'{}\\n', b'{} {}', b'{"a":NaN}', b'{"a":1e999}', b'[]'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                p.parse(data)


def h3_fixture(source):
    bindings = {key: source[key] for key in ("candidate_commit", "candidate_tree", "source_manifest_sha256", "project_state_sha256")}
    identity = {"model_name": "FAKE", "capabilities": ["vision"]}
    bindings.update(runtime_identity_sha256=p.sha(p.canonical(identity)), path_plan_sha256="9" * 64)
    lease = {"schema_version": "npi-synthetic-execution-lease-v3", "status": "APPROVED",
             "production_unlock": False, "bindings": bindings}
    lease_bytes = p.canonical(lease)
    counters = dict.fromkeys(p.COUNTERS | {"obsidian_write_count", "s20_runtime_obsidian_write_count"}, 0)
    runner = {"forbidden_counters": counters,
              "identity_observations": [{"checkpoint": key, "identity": identity} for key in p.CHECKPOINTS],
              "resume": {"exit_code": 0, "model_load_count": 0, "resume_status": "ALREADY_COMPLETE_VERIFIED",
                         "before": {"synthetic-output.json": "f" * 64}, "after": {"synthetic-output.json": "f" * 64}}}
    s20 = {"bundle_count": 20, "result": "N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
           "production_bundle_release": "NOT_CREATED", "facts_repeat": {"bytes_identical": True, "digest_identical": True}}
    reservation = {"status": "RESERVED", "receipt_sha256": p.sha(lease_bytes), "bindings_sha256": p.sha(p.canonical(bindings))}
    evidence = {"schema_version": "npi-controlled-execution-evidence-v1", "input_bindings": bindings,
                **bindings, "execution_lease_sha256": p.sha(lease_bytes), "forbidden_counters": counters,
                "artifacts": {"runner_evidence": p.sha(p.canonical(runner)), "s20_summary": p.sha(p.canonical(s20))}}
    terminal = {"status": "COMPLETE", "receipt_sha256": p.sha(lease_bytes),
                "reservation_sha256": p.sha(p.canonical(reservation)), "evidence_sha256": p.sha(p.canonical(evidence))}
    return {"h3_lease": lease_bytes, "h3_review": b"FAKE reviewer report -- not real Owner evidence\n",
            **{name: p.canonical(value) for name, value in {
                "h3_reservation": reservation, "h3_terminal": terminal, "h3_evidence": evidence,
                "h3_runner": runner, "s20_summary": s20}.items()}}


class H3Tests(unittest.TestCase):
    def setUp(self):
        self.source = {"candidate_commit": "1" * 40, "candidate_tree": "2" * 40,
                       "source_manifest_sha256": "3" * 64, "project_state_sha256": "4" * 64}
        self.raw = h3_fixture(self.source)

    def check(self):
        return p.h3_check(self.raw, self.source, review_sha=p.sha(self.raw["h3_review"]), lease_sha=p.sha(self.raw["h3_lease"]))

    def modify(self, name, callback):
        value = p.parse(self.raw[name])
        callback(value)
        self.raw[name] = p.canonical(value)

    def rebind(self):
        # Test semantic checks beyond the internally consistent file hashes.
        evidence = p.parse(self.raw["h3_evidence"])
        evidence["artifacts"]["runner_evidence"] = p.sha(self.raw["h3_runner"])
        evidence["artifacts"]["s20_summary"] = p.sha(self.raw["s20_summary"])
        self.raw["h3_evidence"] = p.canonical(evidence)
        self.modify("h3_terminal", lambda t: t.update(evidence_sha256=p.sha(self.raw["h3_evidence"])))

    def test_consistency_not_new_review(self):
        result = self.check()
        self.assertEqual(result["ledger_status"], "COMPLETE")
        self.assertIn("NOT_A_NEW_REVIEW", result["consistency"])
        self.assertEqual(result["full_s20_file_audit"], "NOT_REPEATED")

    def test_wrong_pinned_review_rejected(self):
        with self.assertRaisesRegex(ValueError, "REVIEW_HASH_MISMATCH"):
            p.h3_check(self.raw, self.source)

    def test_old_candidate_and_failed_ledger_rejected(self):
        self.source["candidate_commit"] = "0" * 40
        with self.assertRaisesRegex(ValueError, "SOURCE_BINDING"):
            self.check()
        self.source["candidate_commit"] = "1" * 40
        self.modify("h3_terminal", lambda t: t.update(status="FAILED"))
        with self.assertRaisesRegex(ValueError, "LEDGER_MISMATCH"):
            self.check()

    def test_mutated_evidence_hash_denied(self):
        self.modify("h3_evidence", lambda e: e.update(extra=True))
        with self.assertRaisesRegex(ValueError, "EVIDENCE_BINDING"):
            self.check()

    def test_identity_drift_denied_before_preparation(self):
        self.modify("h3_runner", lambda r: r["identity_observations"][-1].update(identity={"changed": True}))
        self.rebind()
        with self.assertRaisesRegex(ValueError, "IDENTITY_MISMATCH"):
            self.check()

    def test_missing_extra_nonzero_and_boolean_counters_rejected(self):
        for action in (lambda c: c.pop("model_download_bytes"), lambda c: c.update(obsidian_write_count=1),
                       lambda c: c.update(real_photo_read_count=False)):
            self.raw = h3_fixture(self.source)
            self.modify("h3_runner", lambda r: action(r["forbidden_counters"]))
            self.rebind()
            with self.assertRaisesRegex(ValueError, "COUNTERS_INVALID"):
                self.check()

    def test_changed_resume_files_and_boolean_loads_rejected(self):
        for action in (lambda r: r.update(after={"changed": "f" * 64}), lambda r: r.update(model_load_count=False)):
            self.raw = h3_fixture(self.source)
            self.modify("h3_runner", lambda r: action(r["resume"]))
            self.rebind()
            with self.assertRaisesRegex(ValueError, "RESUME"):
                self.check()

    def test_s20_count_and_repeatability_rejected(self):
        for action in (lambda s: s.update(bundle_count=19), lambda s: s["facts_repeat"].update(digest_identical=False)):
            self.raw = h3_fixture(self.source)
            self.modify("s20_summary", action)
            self.rebind()
            with self.assertRaisesRegex(ValueError, "S20_INCOMPLETE|REPEATABILITY"):
                self.check()


class FilesAndCLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for args in (("init", "-q"), ("config", "user.name", "R0 Test"), ("config", "user.email", "r0@example.invalid"),
                     ("config", "core.autocrlf", "false")):
            self.git(*args)
        (self.repo / "PROJECT_STATE.json").write_bytes(p.canonical({"phase_status": {"N2B2": "LOCKED"}}))
        (self.repo / "run.py").write_text("# synthetic repository\n")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic candidate")
        self.head = self.git("rev-parse", "HEAD").strip().decode()
        self.tree = self.git("rev-parse", "HEAD^{tree}").strip().decode()
        for key, val in (("BASE", self.head), ("BASE_TREE", self.tree)):
            patcher = patch.object(p, key, val)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.source = p.source_identity(self.repo)
        self.raw = {**h3_fixture(self.source), "manifest": p.canonical(make_manifest())}
        for key, val in (("G1_SHA", p.sha(self.raw["manifest"])), ("H3_REVIEW_SHA", p.sha(self.raw["h3_review"])),
                         ("H3_LEASE_SHA", p.sha(self.raw["h3_lease"]))):
            patcher = patch.object(p, key, val)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.controls, self.outputs = self.root / "controls", self.root / "outputs"
        self.controls.mkdir()
        self.outputs.mkdir()
        self.source_photos = self.root / "never_open_photo_root"
        self.paths = {}
        for name, data in self.raw.items():
            path = self.controls / (name + ".json")
            path.write_bytes(data)
            self.paths[name] = path

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True).stdout

    def args(self, output):
        argv = ["--candidate-root", str(self.repo), "--source-root", str(self.source_photos), "--out", str(output)]
        for key, path in self.paths.items():
            argv.extend(["--" + key.replace("_", "-"), str(path)])
        return argv

    def invoke(self, output):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = p.main(self.args(output))
        return code, stdout.getvalue()

    def test_real_cli_deterministic_output_and_no_asset_access(self):
        one, two = self.outputs / "one.json", self.outputs / "two.json"
        first = self.invoke(one)
        self.assertEqual(first[0], 0, first[1])
        self.assertEqual(self.invoke(two)[0], 0)
        self.assertEqual(one.read_bytes(), two.read_bytes())
        plan = p.parse(one.read_bytes())
        self.assertFalse(plan["execution_authorized"])
        self.assertFalse(plan["execution_draft"]["issued"])
        self.assertIsNone(plan["execution_draft"]["execution_candidate"])
        self.assertEqual(len(plan["review_rows"]), 20)
        self.assertTrue(all(r["decision"] == "PENDING" for r in plan["review_rows"]))
        self.assertFalse(self.source_photos.exists())
        self.assertNotIn(str(self.root), one.read_text())
        self.assertNotIn("private-photo", one.read_text())
        self.assertEqual(self.git("status", "--porcelain"), b"")
        for key, data in self.raw.items():
            self.assertEqual(self.paths[key].read_bytes(), data)

    def test_existing_output_not_overwritten(self):
        out = self.outputs / "existing.json"
        out.write_bytes(b"KEEP")
        self.assertEqual(self.invoke(out)[0], 1)
        self.assertEqual(out.read_bytes(), b"KEEP")

    def test_output_inside_source_controls_or_repo_denied(self):
        for base in (self.repo, self.controls, self.source_photos):
            with self.subTest(base=base):
                code, text = self.invoke(base / "out.json")
                self.assertEqual(code, 1)
                self.assertIn("R0_OUTPUT_BOUNDARY", text)

    def test_dirty_source_rejected(self):
        (self.repo / "untracked.txt").write_text("no")
        code, text = self.invoke(self.outputs / "out.json")
        self.assertEqual(code, 1)
        self.assertIn("R0_SOURCE_DIRTY", text)

    def test_source_rows_same_domain_as_runtime(self):
        rows = []
        for row in self.git("ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0"):
            if row:
                meta, path = row.split(b"\t", 1)
                mode, _, oid = meta.decode().split()
                data = self.git("cat-file", "blob", oid)
                rows.append({"path": path.decode(), "mode": mode, "git_blob": oid,
                             "size_bytes": len(data), "sha256": p.sha(data)})
        self.assertEqual(self.source["source_manifest_sha256"], p.sha(p.canonical(sorted(rows, key=lambda r: r["path"]))))

    def test_unsafe_control_path_and_hardlink_denied(self):
        with self.assertRaisesRegex(ValueError, "ADS"):
            p.read_control(self.controls / "some.json:stream")
        linked = self.controls / "hardlinked.json"
        os.link(self.paths["manifest"], linked)
        with self.assertRaisesRegex(ValueError, "REGULAR_FILE"):
            p.read_control(linked)

    def test_symlink_denied_or_precise_privilege_gap(self):
        link = self.outputs / "link.json"
        try:
            link.symlink_to(self.paths["manifest"])
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("Windows symlink creation privilege missing: 1314")
            raise
        with self.assertRaisesRegex(ValueError, "REGULAR_FILE|REPARSE"):
            p.read_control(link)

    def test_import_environment_does_not_import_torch(self):
        before = set(sys.modules)
        report = p.environment()
        self.assertNotIn("torch", set(sys.modules) - before)
        self.assertFalse(report["model_runtime_ready"])
        self.assertEqual(report["cuda_and_native_operator_probe"], "NOT_PERFORMED")


if __name__ == "__main__":
    unittest.main()
