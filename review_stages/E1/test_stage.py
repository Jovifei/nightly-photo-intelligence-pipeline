"""No-model Stage E1 tests. Temp synthetic ledger files only.

The original worker fixture is byte-verified against GitHub's blob. Runner,
fixture loader, and process-source probes are isolated where explicitly noted;
this does not constitute Windows/native/GPU or supported-environment acceptance.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping, cast

import apply_runtime_fixes as recipe

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("worker_dispatch", ROOT / "payload" / "worker_dispatch.py")
assert spec and spec.loader
protocol = importlib.util.module_from_spec(spec)
spec.loader.exec_module(protocol)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def base_worker() -> bytes:
    override = os.environ.get("NPI_E1_BASE_SOURCE_DIR")
    if override:
        data = (Path(override) / "controlled_runtime_worker.py").read_bytes()
    else:
        result = subprocess.run(
            ["git", "-C", str(ROOT.parents[1]), "show",
             recipe.BASE + ":" + recipe.PACKAGE + "controlled_runtime_worker.py"],
            check=True, capture_output=True,
        )
        data = result.stdout
    require(sha(data) == recipe.EXPECTED["controlled_runtime_worker.py"], "E1_BASE_BYTES_CHANGED")
    return data


class ProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ledger = self.root / "ledger"
        self.reservation = self.ledger / ("a" * 64)
        self.reservation.mkdir(parents=True)
        self.config = {name: str(self.root / name) for name in protocol.PATH_FIELDS}
        self.config.update({
            "ledger_root": str(self.ledger), "reservation_dir": str(self.reservation),
            "receipt_sha256": "a" * 64, "bindings_sha256": "b" * 64,
            "reviewed_commit": "c" * 40, "candidate_tree": "d" * 40,
            "source_manifest_sha256": "e" * 64, "runtime_identity_sha256": "f" * 64,
        })
        self.record = {
            "schema_version": "npi-lease-consumption-v1", "status": "RESERVED",
            "receipt_sha256": "a" * 64, "bindings_sha256": "b" * 64,
            "reserved_at_utc": "2026-09-15T00:00:00+00:00",
        }
        (self.reservation / "reservation.json").write_bytes(canonical(self.record))

    def test_round_trip_and_fresh_resume(self) -> None:
        envelope = protocol.issue(self.config, "fresh")
        self.assertEqual(protocol.claim(envelope, "fresh"), self.config)
        protocol.finish(self.config, "fresh", outcome="COMPLETE", result={"test": "fake"})
        resumed = protocol.issue(self.config, "resume")
        self.assertEqual(protocol.claim(resumed, "resume"), self.config)
        protocol.finish(self.config, "resume", outcome="COMPLETE", result={"test": "fake-resume"})

    def test_original_guard_accepts_changed_config_and_replay(self) -> None:
        # Regression reproduction uses the exact Git-verified original function,
        # actual temporary reservation bytes, and a no-op directory checker.
        # No _fresh/_resume call, model, network, or production ledger is used.
        node = next(n for n in ast.parse(base_worker().decode()).body
                    if isinstance(n, ast.FunctionDef) and n.name == "_require_parent_reservation")
        namespace = {"Mapping": Mapping, "Any": Any, "Path": Path, "cast": cast,
                     "stat": stat, "strict_json": json.loads, "checked_path": lambda *a, **k: None}
        exec(compile(ast.Module(body=[node], type_ignores=[]), "original_guard", "exec"), namespace)
        guard = namespace["_require_parent_reservation"]
        guard(self.config)
        guard({**self.config, "s20_out": str(self.root / "different-output")})
        guard(self.config)
        self.assertFalse((self.reservation / "terminal.json").exists())

    def test_bare_reservation_is_not_dispatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "ENVELOPE"):
            protocol.claim(self.config, "fresh")

    def test_same_envelope_cannot_run_twice(self) -> None:
        env = protocol.issue(self.config, "fresh")
        protocol.claim(env, "fresh")
        with self.assertRaisesRegex(ValueError, "ALREADY_USED"):
            protocol.claim(env, "fresh")

    def test_each_configuration_field_is_bound(self) -> None:
        env = protocol.issue(self.config, "fresh")
        for field in self.config:
            with self.subTest(field=field):
                modified = copy.deepcopy(env)
                modified["configuration"][field] += "0"
                with self.assertRaises((ValueError, OSError)):
                    protocol.claim(modified, "fresh")
        self.assertFalse((self.reservation / "worker-fresh-claim.json").exists())
        protocol.claim(env, "fresh")

    def test_nonce_and_mode_tampering(self) -> None:
        env = protocol.issue(self.config, "fresh")
        for replacement in ({"nonce": "0" * 64}, {"mode": "resume"}, {"extra": 1}):
            with self.subTest(replacement=replacement):
                with self.assertRaises(ValueError):
                    protocol.claim({**env, **replacement}, "fresh")

    def test_reservation_changed_after_issue(self) -> None:
        env = protocol.issue(self.config, "fresh")
        self.record["reserved_at_utc"] = "2026-09-16T00:00:00Z"
        (self.reservation / "reservation.json").write_bytes(canonical(self.record))
        with self.assertRaisesRegex(ValueError, "DISPATCH_MISMATCH"):
            protocol.claim(env, "fresh")

    def test_parent_terminal_blocks_claim(self) -> None:
        env = protocol.issue(self.config, "fresh")
        (self.reservation / "terminal.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "ALREADY_FINISHED"):
            protocol.claim(env, "fresh")

    def test_crash_does_not_release_claim(self) -> None:
        env = protocol.issue(self.config, "fresh")
        protocol.claim(env, "fresh")
        with self.assertRaises(ValueError):
            protocol.issue(self.config, "fresh")
        with self.assertRaises(ValueError):
            protocol.claim(env, "fresh")

    def test_failed_fresh_blocks_resume(self) -> None:
        env = protocol.issue(self.config, "fresh")
        protocol.claim(env, "fresh")
        protocol.finish(self.config, "fresh", outcome="FAILED", result={"error": "fake"})
        with self.assertRaisesRegex(ValueError, "FRESH_NOT_COMPLETE"):
            protocol.issue(self.config, "resume")

    def test_resume_before_fresh_rejected(self) -> None:
        with self.assertRaises((ValueError, OSError)):
            protocol.issue(self.config, "resume")

    def test_fresh_completed_for_other_config_cannot_resume(self) -> None:
        env = protocol.issue(self.config, "fresh")
        protocol.claim(env, "fresh")
        protocol.finish(self.config, "fresh", outcome="COMPLETE", result={})
        altered = {**self.config, "s20_out": str(self.root / "other")}
        with self.assertRaisesRegex(ValueError, "FRESH_NOT_COMPLETE"):
            protocol.issue(altered, "resume")

    def test_two_claimers_only_one_wins(self) -> None:
        env = protocol.issue(self.config, "fresh")
        def claim_once(_: int) -> bool:
            try:
                protocol.claim(env, "fresh")
                return True
            except ValueError:
                return False
        with ThreadPoolExecutor(max_workers=8) as pool:
            outcomes = list(pool.map(claim_once, range(16)))
        self.assertEqual(sum(outcomes), 1)

    def test_ads_rejected_without_opening_stream(self) -> None:
        for field in protocol.PATH_FIELDS:
            with self.subTest(field=field):
                changed = {**self.config, field: self.config[field] + ":hidden"}
                with self.assertRaisesRegex(ValueError, "ALTERNATE_STREAM"):
                    protocol.issue(changed, "fresh")

    def test_paths_and_schema_rejected(self) -> None:
        for patch in ({"cache_root": "relative"}, {"cache_root": str(self.root / ".." / "else")},
                      {"cache_root": "//network/share"}, {"receipt_sha256": "z" * 64},
                      {"source_manifest_sha256": True}, {"extra": "x"}):
            with self.subTest(patch=patch):
                with self.assertRaises(ValueError):
                    protocol.issue({**self.config, **patch}, "fresh")

    def test_duplicate_and_nonfinite_json(self) -> None:
        for data in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}'):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    protocol._json(data)

    def test_size_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "SIZE_LIMIT"):
            protocol._json(b" " * (protocol.MAX_BYTES + 1))

    def test_symbolic_link_record_rejected(self) -> None:
        record = self.reservation / "reservation.json"
        original = self.root / "real-record.json"
        record.rename(original)
        try:
            record.symlink_to(original)
        except OSError as exc:
            if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
                self.skipTest("native Windows symlink privilege missing: winerror=1314")
            raise
        with self.assertRaisesRegex(ValueError, "REPARSE"):
            protocol.issue(self.config, "fresh")

    def test_identity_drift_rejected(self) -> None:
        identity = {"model": "fake", "version": "0.33.3"}
        config = {**self.config, "runtime_identity_sha256": sha(canonical(identity))}
        protocol.assert_identity(config, identity)
        with self.assertRaisesRegex(ValueError, "IDENTITY_DRIFT"):
            protocol.assert_identity(config, {**identity, "version": "0.33.4"})

    def test_full_source_binding(self) -> None:
        source = {"candidate_commit": self.config["reviewed_commit"],
                  "candidate_tree": self.config["candidate_tree"],
                  "source_manifest_sha256": self.config["source_manifest_sha256"]}
        protocol.assert_source(self.config, source)
        for name in source:
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, "SOURCE_DRIFT"):
                    protocol.assert_source(self.config, {**source, name: "0" * len(source[name])})


class RecipeTests(unittest.TestCase):
    def test_all_payload_has_python312_syntax(self) -> None:
        for path in (ROOT / "payload").glob("*.py"):
            ast.parse(path.read_text(), feature_version=(3, 12))

    def test_anchors_are_exact_not_best_effort(self) -> None:
        for text in ("", "xx"):
            with self.assertRaisesRegex(ValueError, "ANCHOR_MISMATCH"):
                recipe.once(text, "x", "y")

    def test_counter_recipe_adds_explicit_producer_declaration(self) -> None:
        original = ('def hard_counts():\n    return {\n'
                    '        "app_write_count": 0,\n        "obsidian_write_count": 0,\n'
                    '        "s20_runtime_obsidian_write_count": 0,\n    }\n')
        namespace: dict[str, Any] = {}
        exec(original, namespace)
        self.assertNotIn("production_bundle_count", namespace["hard_counts"]())
        modified = recipe.patch_counter_producer(original)
        exec(modified, namespace)
        counters = namespace["hard_counts"]()
        self.assertEqual(counters["production_bundle_count"], 0)
        self.assertIn("obsidian_write_count", counters)
        self.assertIn("s20_runtime_obsidian_write_count", counters)
        with self.assertRaises(ValueError):
            recipe.patch_counter_producer(modified)

    def test_worker_patch_against_verified_original(self) -> None:
        data = base_worker()
        self.assertEqual(sha(data), recipe.EXPECTED["controlled_runtime_worker.py"])
        self.assertEqual(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest(),
                         "cc1fc97224f95168c22012234ad12d53f648f0bd")
        changed = recipe.patch_worker(data.decode())
        ast.parse(changed, feature_version=(3, 12))
        with self.assertRaises(ValueError):
            recipe.patch_worker(changed)
        self.assertIn("payload = claim(envelope, args.mode)", changed)
        self.assertIn("assert_source(payload, full_source_identity", changed)
        self.assertIn("with redirect_stdout(sys.stderr):", changed)

    def test_patched_real_fresh_stops_identity_drift_before_runner(self) -> None:
        original = base_worker().decode()
        text = recipe.patch_worker(original)
        tree = ast.parse(text)
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in {"_fresh", "_path", "_identity_record", "_observation"}]
        calls: list[str] = []
        identity = SimpleNamespace(model_name="fake", full_local_digest="1" * 64, size_bytes=1,
                                   quantization_level="fake", capabilities=["vision"], ollama_version="drifted")
        class Client:
            def verify_identity(self):
                calls.append("identity")
                return identity
        namespace = {"Mapping": Mapping, "Any": Any, "Path": Path, "cast": cast,
                     "ModelIdentity": Any, "datetime": datetime, "UTC": UTC,
                     "OllamaClient": Client, "_common": lambda p: calls.append("legacy") or {},
                     "assert_identity": protocol.assert_identity,
                     "run_n2b2": lambda **kw: calls.append("model"), "require": require}
        exec(compile(ast.Module(body=functions, type_ignores=[]), "verified_worker", "exec"), namespace)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            payload = {name: str(root / name) for name in protocol.PATH_FIELDS}
            payload["runtime_identity_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "IDENTITY_DRIFT"):
                namespace["_fresh"](payload)
        self.assertEqual(calls, ["legacy", "identity"])

    def test_common_separates_historical_and_execution_sha(self) -> None:
        original = base_worker().decode()
        old_commit, current_commit = "4" * 40, "8" * 40
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "schemas").mkdir()
            for name in ("n2b2_photography_reasoning.schema.json", "n2b2_vision_fact_contract_v1_2.schema.json"):
                (root / "schemas" / name).write_text("{}")
            payload = {name: str(root / name) for name in protocol.PATH_FIELDS}
            payload.update(project_root=str(root), reviewed_commit=current_commit)
            results = []
            for text in (original, recipe.patch_worker(original)):
                nodes = [n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name in {"_common", "_path"}]
                namespace = {"Mapping": Mapping, "Any": Any, "Path": Path, "cast": cast, "require": require,
                             "strict_json": json.loads, "load_s20_manifest": lambda *a, **k: [],
                             "N2B2RunConfig": lambda **kw: kw,
                             "validate_legacy_s20_binding": lambda *a: old_commit}
                exec(compile(ast.Module(body=nodes, type_ignores=[]), "verified_worker", "exec"), namespace)
                results.append(namespace["_common"](payload)["reviewed_commit"])
            self.assertEqual(results, [current_commit, old_commit])
            self.assertEqual(payload["reviewed_commit"], current_commit)


if __name__ == "__main__":
    unittest.main()
