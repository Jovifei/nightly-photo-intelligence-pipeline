from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

from nightly_photo_intelligence_pipeline.engineering import controlled_entry
from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256
from nightly_photo_intelligence_pipeline.engineering.controlled_entry import (
    REQUIRED_FORBIDDEN_COUNTERS,
    ControlledExecutionPlan,
    path_plan_digest,
    run_controlled_execution,
)
from nightly_photo_intelligence_pipeline.engineering.evidence import REQUIRED_QUALITY
from nightly_photo_intelligence_pipeline.engineering.lease import DENIED
from nightly_photo_intelligence_pipeline.engineering.source_identity import full_source_identity

NOW = datetime(2026, 9, 13, 10, 0, tzinfo=UTC)


class ControlledEntryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        self.external = Path(self.temp.name) / "external"
        self.root.mkdir()
        self.external.mkdir()
        self._git("init", "-q")
        self._git("config", "user.name", "Engineering Test")
        self._git("config", "user.email", "engineering@example.invalid")
        (self.root / "PROJECT_STATE.json").write_text(
            '{"phase_status":{"N2B2":"LOCKED"}}\n', encoding="utf-8"
        )
        (self.root / "source.py").write_text("print(1)\n", encoding="utf-8")
        self._git("add", ".")
        self._git("commit", "-qm", "controlled-entry fixture")

        self.inputs = {}
        for name in ("s3_manifest", "s20_manifest", "cache", "old_s3", "old_s20"):
            path = self.external / name
            path.mkdir()
            self.inputs[name] = path
        self.outputs = {
            name: self.external / name for name in ("s3_output", "s20_output", "evidence_output")
        }
        self.ledger = self.external / "ledger"
        self.ledger.mkdir()
        self.protected = {
            "project_root": self.root,
            "cache_protected": self.inputs["cache"],
            "old_s3_protected": self.inputs["old_s3"],
            "old_s20_protected": self.inputs["old_s20"],
            "ledger_root": self.ledger,
        }
        source = full_source_identity(self.root)
        identity = {"runtime": "fake", "runtime_kind": "not-loaded"}
        self.identity = identity
        bindings = {
            "candidate_commit": source["candidate_commit"],
            "candidate_tree": source["candidate_tree"],
            "source_manifest_sha256": source["source_manifest_sha256"],
            "project_state_sha256": sha256((self.root / "PROJECT_STATE.json").read_bytes()),
            "runtime_identity_sha256": sha256(canonical(identity)),
            "s3_manifest_sha256": "a" * 64,
            "s20_manifest_sha256": "b" * 64,
            "model_cache_binding_sha256": "c" * 64,
            "path_plan_sha256": path_plan_digest(
                inputs=self.inputs, outputs=self.outputs, protected=self.protected
            ),
        }
        self.bindings = bindings
        lease = {
            "schema_version": "npi-synthetic-execution-lease-v2",
            "status": "APPROVED",
            "owner_id": "Jovi",
            "purpose": "SYNTHETIC_S3_S20_ENGINEERING_VALIDATION",
            "not_before_utc": "2026-09-13T00:00:00Z",
            "expires_at_utc": "2026-09-14T00:00:00Z",
            "bindings": bindings,
            "boundaries": dict.fromkeys(DENIED, False),
            "max_fresh_s3_runs": 1,
            "max_fresh_s20_runs": 1,
            "production_unlock": False,
        }
        self.lease = canonical(lease)
        self.plan = ControlledExecutionPlan(
            project_root=self.root,
            ledger_root=self.ledger,
            lease=self.lease,
            trusted_receipt_sha256=sha256(self.lease),
            inputs=self.inputs,
            outputs=self.outputs,
            protected=self.protected,
            observed_bindings=bindings,
        )
        self.addCleanup(self.temp.cleanup)

    def _git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def _evidence(self) -> dict[str, Any]:
        records = [
            {
                "name": name,
                "command": ["fake", name],
                "tool_version": "fake-1",
                "started_at_utc": "2026-09-13T10:00:00Z",
                "ended_at_utc": "2026-09-13T10:01:00Z",
                "exit_code": 0,
                "status": "PASS",
                "stdout_sha256": "d" * 64,
                "stderr_sha256": "e" * 64,
                "skipped_count": 0,
            }
            for name in sorted(REQUIRED_QUALITY)
        ]
        observations = [
            {
                "checkpoint": label,
                "observed_at_utc": (NOW + timedelta(seconds=index)).isoformat(),
                "identity": self.identity,
            }
            for index, label in enumerate(
                ("preflight", "before_s3", "before_s20", "before_resume", "after_resume")
            )
        ]
        return {
            "quality_records": records,
            "identity_observations": observations,
            "resume": {
                "exit_code": 0,
                "resume_status": "ALREADY_COMPLETE_VERIFIED",
                "before": {"summary": "f" * 64},
                "after": {"summary": "f" * 64},
                "model_load_count": 0,
            },
            "artifacts": {"s3_summary": "1" * 64, "s20_summary": "2" * 64},
            "forbidden_counters": dict.fromkeys(REQUIRED_FORBIDDEN_COUNTERS, 0),
        }

    def test_fake_callback_runs_only_after_reservation(self) -> None:
        events: list[tuple[str, bool]] = []

        def probe() -> dict[str, object]:
            events.append(("probe", any(self.ledger.iterdir())))
            return self.identity

        def execute() -> dict[str, Any]:
            events.append(("execute", any(self.ledger.iterdir())))
            return self._evidence()

        with patch.object(sys, "version_info", (3, 12, 10)):
            result = run_controlled_execution(
                self.plan, now=NOW, identity_probe=probe, execute=execute
            )
        self.assertEqual(result["result"], "CONTROLLED_EXECUTION_COMPLETE")
        self.assertEqual(events, [("probe", False), ("execute", True)])
        reservation = next(self.ledger.iterdir())
        terminal = json.loads((reservation / "terminal.json").read_text(encoding="utf-8"))
        self.assertEqual(terminal["status"], "COMPLETE")

    def test_draft_lease_blocks_callback(self) -> None:
        draft = json.loads(self.lease)
        draft["status"] = "DRAFT"
        draft_bytes = canonical(draft)
        plan = ControlledExecutionPlan(
            **{
                **self.plan.__dict__,
                "lease": draft_bytes,
                "trusted_receipt_sha256": sha256(draft_bytes),
            }
        )
        called = False

        def execute() -> dict[str, Any]:
            nonlocal called
            called = True
            return self._evidence()

        with (
            self.assertRaisesRegex(ValueError, "NPI_LEASE_NOT_APPROVED"),
            patch.object(sys, "version_info", (3, 12, 10)),
        ):
            run_controlled_execution(
                plan, now=NOW, identity_probe=lambda: self.identity, execute=execute
            )
        self.assertFalse(called)
        self.assertEqual(list(self.ledger.iterdir()), [])

    def test_path_collision_blocks_before_reservation(self) -> None:
        plan = ControlledExecutionPlan(
            **{
                **self.plan.__dict__,
                "outputs": {"s3_output": self.inputs["s3_manifest"] / "future-output"},
            }
        )
        with (
            self.assertRaisesRegex(ValueError, "NPI_OUTPUT_ROOT_OVERLAP"),
            patch.object(sys, "version_info", (3, 12, 10)),
        ):
            run_controlled_execution(
                plan, now=NOW, identity_probe=lambda: self.identity, execute=self._evidence
            )
        self.assertEqual(list(self.ledger.iterdir()), [])

    def test_recheck_blocks_replaced_protected_root(self) -> None:
        original_validate = controlled_entry.validate_plan
        called = False

        def replace_after_validate(**kwargs: object) -> dict[str, object]:
            checked = original_validate(**kwargs)  # type: ignore[arg-type]
            old_root = self.inputs["old_s3"]
            old_root.rename(self.external / "old_s3_saved")
            old_root.mkdir()
            return checked  # type: ignore[return-value]

        def execute() -> dict[str, Any]:
            nonlocal called
            called = True
            return self._evidence()

        with (
            self.assertRaisesRegex(ValueError, "NPI_BOUND_ROOT_CHANGED"),
            patch.object(sys, "version_info", (3, 12, 10)),
            patch.object(
                controlled_entry,
                "validate_plan",
                side_effect=replace_after_validate,
            ),
        ):
            run_controlled_execution(
                self.plan, now=NOW, identity_probe=lambda: self.identity, execute=execute
            )
        self.assertFalse(called)
        self.assertEqual(list(self.ledger.iterdir()), [])

    def test_failed_callback_consumes_lease(self) -> None:
        def fail() -> dict[str, Any]:
            raise RuntimeError("fake runner failure")

        with (
            self.assertRaisesRegex(RuntimeError, "fake runner failure"),
            patch.object(sys, "version_info", (3, 12, 10)),
        ):
            run_controlled_execution(
                self.plan, now=NOW, identity_probe=lambda: self.identity, execute=fail
            )
        reservation = next(self.ledger.iterdir())
        terminal = json.loads((reservation / "terminal.json").read_text(encoding="utf-8"))
        self.assertEqual(terminal["status"], "FAILED")
        with (
            self.assertRaisesRegex(ValueError, "NPI_LEASE_ALREADY_CONSUMED"),
            patch.object(sys, "version_info", (3, 12, 10)),
        ):
            run_controlled_execution(
                self.plan, now=NOW, identity_probe=lambda: self.identity, execute=self._evidence
            )

    def test_failed_callback_still_runs_post_execution_integrity_check(self) -> None:
        checked = False

        def fail() -> dict[str, Any]:
            raise RuntimeError("fake runner failure")

        def detect_tamper() -> None:
            nonlocal checked
            checked = True
            raise ValueError("NPI_BOUND_FILE_CHANGED")

        with (
            self.assertRaisesRegex(ValueError, "NPI_BOUND_FILE_CHANGED") as raised,
            patch.object(sys, "version_info", (3, 12, 10)),
        ):
            run_controlled_execution(
                self.plan,
                now=NOW,
                identity_probe=lambda: self.identity,
                execute=fail,
                post_execute_check=detect_tamper,
            )
        self.assertTrue(checked)
        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
        reservation = next(self.ledger.iterdir())
        terminal = json.loads((reservation / "terminal.json").read_text(encoding="utf-8"))
        self.assertEqual(terminal["status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
