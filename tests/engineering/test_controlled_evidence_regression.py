"""Code-only regressions: fabricated evidence and mocked runner, never a model.

Filesystem/lease dependencies are mocked only in admission tests. Evidence
parsing uses the actual current validators. No test grants a real execution
lease, and patching sys.version_info is only a unit-test branch selection.
"""

from __future__ import annotations

import ast
import copy
import inspect
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from nightly_photo_intelligence_pipeline.engineering import controlled_entry as entry
from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256
from nightly_photo_intelligence_pipeline.engineering.evidence import REQUIRED_QUALITY

COUNTERS = (
    "real_photo_read_count",
    "real_exif_read_count",
    "g1_source_access",
    "sqlite_write_count",
    "app_write_count",
    "production_bundle_count",
    "model_download_bytes",
)
NOW = datetime(2026, 9, 14, 10, tzinfo=UTC)
IDENTITY = {"runtime": "fake-only"}


def valid_evidence():
    return {
        "quality_records": [
            {
                "name": name,
                "command": ["fake-check", name],
                "tool_version": "fixture-1",
                "started_at_utc": NOW.isoformat(),
                "ended_at_utc": (NOW + timedelta(seconds=1)).isoformat(),
                "exit_code": 0,
                "status": "PASS",
                "stdout_sha256": "a" * 64,
                "stderr_sha256": "b" * 64,
                "skipped_count": 0,
            }
            for name in sorted(REQUIRED_QUALITY)
        ],
        "identity_observations": [
            {
                "checkpoint": label,
                "observed_at_utc": (NOW + timedelta(seconds=i)).isoformat(),
                "identity": IDENTITY,
            }
            for i, label in enumerate(
                ("preflight", "before_s3", "before_s20", "before_resume", "after_resume")
            )
        ],
        "resume": {
            "exit_code": 0,
            "resume_status": "ALREADY_COMPLETE_VERIFIED",
            "before": {"synthetic_fixture_summary": "c" * 64},
            "after": {"synthetic_fixture_summary": "c" * 64},
            "model_load_count": 0,
        },
        "artifacts": {"s3_summary": "d" * 64, "s20_summary": "e" * 64},
        "forbidden_counters": dict.fromkeys(COUNTERS, 0),
    }


class CallbackEvidenceRegressionTests(unittest.TestCase):
    def check_evidence(self, value):
        return entry._validate_callback_evidence(value, identity=IDENTITY)

    def test_valid_evidence_is_not_mutated(self):
        payload = valid_evidence()
        before = copy.deepcopy(payload)
        result = self.check_evidence(payload)
        self.assertEqual(payload, before)
        self.assertEqual(result["artifacts"], payload["artifacts"])
        self.assertEqual(result["forbidden_counters"], dict.fromkeys(COUNTERS, 0))

    def test_artifacts_missing(self):
        value = valid_evidence()
        value.pop("artifacts")
        with self.assertRaisesRegex(ValueError, "NPI_ARTIFACT_EVIDENCE_INVALID"):
            self.check_evidence(value)

    def test_artifacts_invalid(self):
        for artifacts in (
            {},
            [],
            None,
            False,
            {"s3_summary": "not-a-digest"},
            {"s3_summary": "A" * 64},
            {0: "a" * 64},
            {"../private": "a" * 64},
            {"": "a" * 64},
            {"x" * 65: "a" * 64},
        ):
            with self.subTest(artifacts=repr(artifacts)):
                value = valid_evidence()
                value["artifacts"] = artifacts
                with self.assertRaisesRegex(ValueError, "NPI_ARTIFACT_EVIDENCE_INVALID"):
                    self.check_evidence(value)

    def test_counter_field_missing(self):
        value = valid_evidence()
        value.pop("forbidden_counters")
        with self.assertRaisesRegex(ValueError, "NPI_COUNTER_EVIDENCE_INVALID"):
            self.check_evidence(value)

    def test_counter_set_missing(self):
        for counters in ({}, {"unrelated": 0}, [], None):
            with self.subTest(counters=counters):
                value = valid_evidence()
                value["forbidden_counters"] = counters
                with self.assertRaisesRegex(ValueError, "NPI_COUNTER_EVIDENCE_INVALID"):
                    self.check_evidence(value)

    def test_each_required_counter_must_exist(self):
        for name in COUNTERS:
            with self.subTest(name=name):
                value = valid_evidence()
                value["forbidden_counters"].pop(name)
                with self.assertRaisesRegex(ValueError, "NPI_COUNTER_EVIDENCE_INVALID"):
                    self.check_evidence(value)

    def test_counter_values_must_be_nonnegative_integers(self):
        for count in (True, False, 0.0, "0", None, -1, float("nan"), float("inf")):
            with self.subTest(count=repr(count)):
                value = valid_evidence()
                value["forbidden_counters"][COUNTERS[0]] = count
                with self.assertRaisesRegex(ValueError, "NPI_COUNTER_EVIDENCE_INVALID"):
                    self.check_evidence(value)

    def test_each_forbidden_action_must_be_zero(self):
        for name in COUNTERS:
            with self.subTest(name=name):
                value = valid_evidence()
                value["forbidden_counters"][name] = 1
                with self.assertRaisesRegex(ValueError, "NPI_FORBIDDEN_ACTION_RECORDED"):
                    self.check_evidence(value)

    def test_additional_zero_counter_is_allowed_without_discarding_it(self):
        value = valid_evidence()
        value["forbidden_counters"]["obsidian_write_count"] = 0
        self.assertIn("obsidian_write_count", self.check_evidence(value)["forbidden_counters"])

    def test_additional_nonzero_counter_is_not_ignored(self):
        value = valid_evidence()
        value["forbidden_counters"]["obsidian_write_count"] = 1
        with self.assertRaisesRegex(ValueError, "NPI_FORBIDDEN_ACTION_RECORDED"):
            self.check_evidence(value)

    def test_counter_labels_cannot_leak_paths(self):
        value = valid_evidence()
        value["forbidden_counters"]["F" + ":" + "/private"] = 0
        with self.assertRaisesRegex(ValueError, "NPI_COUNTER_EVIDENCE_INVALID"):
            self.check_evidence(value)

    def test_quality_skip_still_blocks(self):
        value = valid_evidence()
        value["quality_records"][0]["skipped_count"] = 1
        with self.assertRaisesRegex(ValueError, "NPI_QUALITY_FALSE_PASS"):
            self.check_evidence(value)

    def test_identity_drift_still_blocks(self):
        value = valid_evidence()
        value["identity_observations"][-1]["identity"] = {"runtime": "changed"}
        with self.assertRaisesRegex(ValueError, "NPI_RUNTIME_IDENTITY_DRIFT"):
            self.check_evidence(value)

    def test_resume_failure_still_blocks(self):
        value = valid_evidence()
        value["resume"]["exit_code"] = 10
        with self.assertRaisesRegex(ValueError, "NPI_LIVE_RESUME_NOT_SUCCESSFUL"):
            self.check_evidence(value)

    def test_no_tuple_wrapped_if_guard(self):
        nodes = ast.walk(ast.parse(inspect.getsource(entry._validate_callback_evidence)))
        broken = [
            node.lineno
            for node in nodes
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.UnaryOp)
            and isinstance(node.test.op, ast.Not)
            and isinstance(node.test.operand, ast.Tuple)
        ]
        self.assertEqual(broken, [], "A nonempty tuple makes this denial branch unreachable")


class AdmissionBindingRegressionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.project = self.base / "project"
        self.project.mkdir()
        self.state = self.project / "PROJECT_STATE.json"
        self.state.write_bytes(b'{"phase_status":{"N2B2":"LOCKED"}}\n')
        self.ledger = self.base / "ledger"
        self.ledger.mkdir()
        self.inputs = {"synthetic_fixtures": self.base / "fixtures"}
        self.inputs["synthetic_fixtures"].mkdir()
        self.source = {
            "candidate_commit": "a" * 40,
            "candidate_tree": "b" * 40,
            "source_manifest_sha256": "c" * 64,
        }
        protected = {"project_root": self.project, "ledger_root": self.ledger}
        outputs = {"result_output": self.base / "output"}
        self.bindings = {
            **self.source,
            "project_state_sha256": sha256(self.state.read_bytes()),
            "path_plan_sha256": entry.path_plan_digest(
                inputs=self.inputs, outputs=outputs, protected=protected
            ),
            "runtime_identity_sha256": sha256(canonical(IDENTITY)),
        }
        self.plan = entry.ControlledExecutionPlan(
            project_root=self.project,
            ledger_root=self.ledger,
            lease=b"unit-test-only-not-an-approved-receipt",
            trusted_receipt_sha256="d" * 64,
            inputs=self.inputs,
            outputs=outputs,
            protected=protected,
            observed_bindings=self.bindings,
        )
        # Mock external admission contracts; real path validation/recheck and
        # evidence validators run. This does not exercise a real lease or model.
        self.source_mock = self._mock("full_source_identity", return_value=self.source)
        self.lease_mock = self._mock("validate_lease", return_value=object())
        self.claim_mock = self._mock("reserve", return_value=object())
        self.finish_mock = self._mock("finish")
        version = patch.object(sys, "version_info", (3, 12, 10))
        version.start()
        self.addCleanup(version.stop)
        self.probe = Mock(return_value=IDENTITY)
        self.callback = Mock(side_effect=valid_evidence)

    def _mock(self, name, **kwargs):
        item = patch.object(entry, name, **kwargs)
        result = item.start()
        self.addCleanup(item.stop)
        return result

    def run_plan(self, plan=None):
        return entry.run_controlled_execution(
            plan or self.plan, now=NOW, identity_probe=self.probe, execute=self.callback
        )

    def assert_no_admission(self):
        self.claim_mock.assert_not_called()
        self.callback.assert_not_called()
        self.finish_mock.assert_not_called()

    def test_valid_callback_completes_after_reservation(self):
        self.callback.side_effect = lambda: self.claim_mock.assert_called_once() or valid_evidence()
        result = self.run_plan()
        self.assertEqual(result["result"], "CONTROLLED_EXECUTION_COMPLETE")
        self.assertEqual(self.finish_mock.call_args.kwargs["outcome"], "COMPLETE")

    def test_alternative_unbound_ledger_is_rejected(self):
        alternate = self.base / "alternate_ledger"
        alternate.mkdir()
        with self.assertRaisesRegex(ValueError, "NPI_LEDGER_ROOT_BINDING_MISMATCH"):
            self.run_plan(replace(self.plan, ledger_root=alternate))
        self.assert_no_admission()
        self.probe.assert_not_called()

    def test_ledger_label_is_required(self):
        with self.assertRaisesRegex(ValueError, "NPI_LEDGER_ROOT_BINDING_MISMATCH"):
            self.run_plan(replace(self.plan, protected={"project_root": self.project}))
        self.assert_no_admission()

    def test_project_root_must_match_bound_root(self):
        protected = {**self.plan.protected, "project_root": self.base / "other_project"}
        with self.assertRaisesRegex(ValueError, "NPI_PROJECT_ROOT_BINDING_MISMATCH"):
            self.run_plan(replace(self.plan, protected=protected))
        self.assert_no_admission()

    def test_ledger_cannot_be_an_input_root(self):
        path = self.inputs["synthetic_fixtures"]
        protected = {**self.plan.protected, "ledger_root": path}
        with self.assertRaisesRegex(ValueError, "NPI_LEDGER_ROOT_OVERLAP"):
            self.run_plan(replace(self.plan, ledger_root=path, protected=protected))
        self.assert_no_admission()

    def test_ledger_cannot_be_inside_project(self):
        path = self.project / "ledger"
        path.mkdir()
        protected = {**self.plan.protected, "ledger_root": path}
        with self.assertRaisesRegex(ValueError, "NPI_LEDGER_ROOT_OVERLAP"):
            self.run_plan(replace(self.plan, ledger_root=path, protected=protected))
        self.assert_no_admission()

    def test_unlocked_state_is_rejected_even_when_its_hash_matches(self):
        self.state.write_bytes(b'{"phase_status":{"N2B2":"UNLOCKED"}}\n')
        bindings = {**self.bindings, "project_state_sha256": sha256(self.state.read_bytes())}
        with self.assertRaisesRegex(ValueError, "NPI_PROJECT_STATE_BOUNDARY_VIOLATION"):
            self.run_plan(replace(self.plan, observed_bindings=bindings))
        self.assert_no_admission()
        self.probe.assert_not_called()

    def test_prior_path_recheck_fix_remains_before_reservation(self):
        def replace_during_identity_probe():
            old = self.inputs["synthetic_fixtures"]
            old.rename(self.base / "saved_fixtures")
            old.mkdir()
            return IDENTITY

        self.probe.side_effect = replace_during_identity_probe
        with self.assertRaisesRegex(ValueError, "NPI_BOUND_ROOT_CHANGED"):
            self.run_plan()
        self.assert_no_admission()

    def test_bad_artifact_does_not_finalize_complete(self):
        value = valid_evidence()
        value["artifacts"] = {}
        self.callback.side_effect = lambda: value
        with self.assertRaisesRegex(ValueError, "NPI_ARTIFACT_EVIDENCE_INVALID"):
            self.run_plan()
        self.claim_mock.assert_called_once()
        self.finish_mock.assert_called_once()
        self.assertEqual(self.finish_mock.call_args.kwargs["outcome"], "FAILED")

    def test_forbidden_activity_does_not_finalize_complete(self):
        value = valid_evidence()
        value["forbidden_counters"]["real_photo_read_count"] = 1
        self.callback.side_effect = lambda: value
        with self.assertRaisesRegex(ValueError, "NPI_FORBIDDEN_ACTION_RECORDED"):
            self.run_plan()
        self.finish_mock.assert_called_once()
        self.assertEqual(self.finish_mock.call_args.kwargs["outcome"], "FAILED")

    def test_unsupported_interpreter_still_blocks_before_probe(self):
        with (
            patch.object(sys, "version_info", (3, 14, 2)),
            self.assertRaisesRegex(ValueError, "NPI_UNSUPPORTED_PYTHON"),
        ):
            self.run_plan()
        self.assert_no_admission()
        self.probe.assert_not_called()

    def test_no_network_or_model_imports_in_controlled_entry(self):
        source = inspect.getsource(entry)
        nodes = ast.walk(ast.parse(source))
        names = []
        for node in nodes:
            if isinstance(node, ast.Import):
                names.extend(item.name.split(".")[0] for item in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names.append((node.module or "").split(".")[0])
        self.assertFalse(set(names) & {"torch", "torchvision", "requests", "httpx", "socket"})


if __name__ == "__main__":
    unittest.main()
