"""No models or real photos: numeric, filesystem, JSON and synthetic Git fixtures."""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from nightly_photo_intelligence_pipeline.engineering.common import (
    EngineeringError,
    canonical,
    sha256,
    strict_json,
)
from nightly_photo_intelligence_pipeline.engineering.evidence import (
    REQUIRED_QUALITY,
    quality_matrix,
    validate_identity_observations,
    validate_resume_evidence,
)
from nightly_photo_intelligence_pipeline.engineering.lease import (
    DENIED,
    REQUIRED_BINDINGS,
    finish,
    reserve,
    validate_lease,
)
from nightly_photo_intelligence_pipeline.engineering.native_capability import (
    symlink_privilege_gap,
)
from nightly_photo_intelligence_pipeline.engineering.path_policy import (
    _linked,
    checked_path,
    recheck,
    validate_plan,
)
from nightly_photo_intelligence_pipeline.engineering.readiness import (
    dependency_checks,
    ollama_version_probe,
    python_check,
)
from nightly_photo_intelligence_pipeline.engineering.resources import validate_gpu_peak
from nightly_photo_intelligence_pipeline.engineering.source_identity import full_source_identity

NOW = datetime(2026, 9, 13, 10, tzinfo=UTC)


def bindings():
    return {
        name: ("a" * (40 if name in ("candidate_commit", "candidate_tree") else 64))
        for name in REQUIRED_BINDINGS
    }


def lease_data():
    return {
        "schema_version": "npi-synthetic-execution-lease-v3",
        "status": "APPROVED",
        "owner_id": "Jovi",
        "purpose": "SYNTHETIC_S3_S20_ENGINEERING_VALIDATION",
        "not_before_utc": "2026-09-13T09:00:00Z",
        "expires_at_utc": "2026-09-13T11:00:00Z",
        "bindings": bindings(),
        "boundaries": dict.fromkeys(DENIED, False),
        "max_fresh_s3_runs": 1,
        "max_fresh_s20_runs": 1,
        "production_unlock": False,
    }


def permit(data=None, now=NOW):
    raw = canonical(lease_data() if data is None else data)
    return validate_lease(
        raw, trusted_receipt_sha256=sha256(raw), observed_bindings=bindings(), now=now
    )


class JsonTests(unittest.TestCase):
    def test_duplicates_fail(self):
        with self.assertRaisesRegex(EngineeringError, "DUPLICATE"):
            strict_json(b'{"a":1,"a":2}')

    def test_nonfinite_fail(self):
        for data in (b"NaN", b"Infinity", b"1e1000", b"-Infinity"):
            with self.subTest(data=data), self.assertRaises(EngineeringError):
                strict_json(data)

    def test_canonical_sort(self):
        self.assertEqual(canonical({"b": 1, "a": 2}), b'{"a":2,"b":1}\n')

    def test_invalid_utf8(self):
        with self.assertRaises(EngineeringError):
            strict_json(b"\xff")


class ResourceTests(unittest.TestCase):
    def test_valid_int(self):
        self.assertEqual(validate_gpu_peak(10451), 10451.0)

    def test_valid_float(self):
        self.assertEqual(validate_gpu_peak(10451.5), 10451.5)

    def test_ceiling(self):
        self.assertEqual(validate_gpu_peak(11500), 11500.0)

    def test_high_float(self):
        with self.assertRaisesRegex(EngineeringError, "CEILING_EXCEEDED"):
            validate_gpu_peak(11500.01)

    def test_bad_types_and_values(self):
        for value in (None, True, False, "10451", float("nan"), float("inf"), 0, -1, 10**1000):
            with self.subTest(value=str(value)[:20]), self.assertRaises(EngineeringError):
                validate_gpu_peak(value)


class PathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.inputs = {"fixtures": self.root / "fixtures"}
        self.protected = {"repo": self.root / "repo", "cache": self.root / "cache"}
        for path in [*self.inputs.values(), *self.protected.values()]:
            path.mkdir()
        self.outputs = {
            "s3": self.root / "s3",
            "s20": self.root / "s20",
            "evidence": self.root / "evidence",
        }

    def check(self, outputs=None):
        return validate_plan(
            inputs=self.inputs, outputs=outputs or self.outputs, protected=self.protected
        )

    def test_disjoint(self):
        self.assertEqual(len(self.check()), 6)

    def test_output_collisions(self):
        for path in (self.root / "s3", self.root / "s3" / "nested"):
            with self.subTest(path=path.name), self.assertRaisesRegex(EngineeringError, "OVERLAP"):
                self.check({**self.outputs, "s20": path})

    def test_output_inside_input(self):
        with self.assertRaisesRegex(EngineeringError, "OVERLAP"):
            self.check({**self.outputs, "s3": self.inputs["fixtures"] / "output"})

    def test_output_inside_cache(self):
        with self.assertRaisesRegex(EngineeringError, "OVERLAP"):
            self.check({**self.outputs, "s3": self.protected["cache"] / "output"})

    def test_existing_output(self):
        self.outputs["s3"].mkdir()
        with self.assertRaisesRegex(EngineeringError, "ALREADY_EXISTS"):
            self.check()

    def test_missing_protected_root(self):
        self.protected["repo"].rmdir()
        with self.assertRaisesRegex(EngineeringError, "MISSING"):
            self.check()

    def test_relative_denied(self):
        with self.assertRaisesRegex(EngineeringError, "NOT_ABSOLUTE"):
            checked_path(Path("relative"), must_exist=False)

    def test_dotdot_denied(self):
        with self.assertRaisesRegex(EngineeringError, "TRAVERSAL"):
            checked_path(self.root / ".." / "escape", must_exist=False)

    def test_reparse_bit(self):
        self.assertTrue(_linked(SimpleNamespace(st_mode=0o40700, st_file_attributes=0x400)))

    def test_symlink_flag(self):
        self.assertTrue(_linked(SimpleNamespace(st_mode=0o120777)))

    def test_symlink_ancestor(self):
        link = self.root / "link"
        try:
            link.symlink_to(self.inputs["fixtures"], target_is_directory=True)
        except OSError as exc:
            reason = symlink_privilege_gap(exc, platform=sys.platform)
            if reason is None:
                raise
            self.skipTest(reason)
        with self.assertRaisesRegex(EngineeringError, "REPARSE"):
            checked_path(link / "output", must_exist=False)

    def test_recheck_new_output(self):
        plan = self.check()
        self.outputs["s3"].mkdir()
        with self.assertRaisesRegex(EngineeringError, "ALREADY_EXISTS"):
            recheck(plan)

    def test_recheck_replaced_parent(self):
        plan = self.check()
        self.protected["repo"].rename(self.root / "saved-repo")
        self.protected["repo"].mkdir()
        with self.assertRaisesRegex(EngineeringError, "BOUND_ROOT_CHANGED"):
            recheck(plan)

    def test_root_does_not_scan_inputs(self):
        (self.inputs["fixtures"] / "DO_NOT_OPEN").write_bytes(b"not a picture")
        plan = self.check()
        self.assertEqual(len(plan["fixtures"].ancestors), len(self.inputs["fixtures"].parents) + 1)


class LeaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_valid(self):
        self.assertEqual(permit().receipt_sha256, sha256(canonical(lease_data())))

    def test_draft_even_with_matching_hash_is_not_authority(self):
        data = lease_data()
        data["status"] = "DRAFT"
        with self.assertRaisesRegex(EngineeringError, "NOT_APPROVED"):
            permit(data)

    def test_trusted_hash_mismatch(self):
        with self.assertRaisesRegex(EngineeringError, "DIGEST_MISMATCH"):
            validate_lease(
                canonical(lease_data()),
                trusted_receipt_sha256="0" * 64,
                observed_bindings=bindings(),
                now=NOW,
            )

    def test_binding_drift(self):
        for key in REQUIRED_BINDINGS:
            data = lease_data()
            data["bindings"][key] = "b" * len(data["bindings"][key])
            with (
                self.subTest(key=key),
                self.assertRaisesRegex(EngineeringError, "BINDING_MISMATCH"),
            ):
                permit(data)

    def test_boundary_drift(self):
        for key in DENIED:
            data = lease_data()
            data["boundaries"][key] = True
            with self.subTest(key=key), self.assertRaisesRegex(EngineeringError, "SCOPE_INVALID"):
                permit(data)

    def test_bool_is_not_one(self):
        data = lease_data()
        data["max_fresh_s3_runs"] = True
        with self.assertRaisesRegex(EngineeringError, "SCOPE_INVALID"):
            permit(data)

    def test_expiration_is_exclusive(self):
        with self.assertRaisesRegex(EngineeringError, "OUTSIDE_WINDOW"):
            permit(now=NOW.replace(hour=11))

    def test_before_start(self):
        with self.assertRaisesRegex(EngineeringError, "OUTSIDE_WINDOW"):
            permit(now=NOW.replace(hour=8))

    def test_naive_timestamp(self):
        with self.assertRaisesRegex(EngineeringError, "TIME_INVALID"):
            permit(now=NOW.replace(tzinfo=None))

    def test_unknown_fields_denied(self):
        data = lease_data()
        data["allow_anything"] = True
        with self.assertRaisesRegex(EngineeringError, "SCHEMA_INVALID"):
            permit(data)

    def test_second_reservation(self):
        p = permit()
        reserve(self.root, p, observed_bindings=bindings(), now=NOW)
        with self.assertRaisesRegex(EngineeringError, "ALREADY_CONSUMED"):
            reserve(self.root, p, observed_bindings=bindings(), now=NOW)

    def test_crash_after_mkdir_stays_consumed(self):
        p = permit()
        (self.root / p.receipt_sha256).mkdir()
        with self.assertRaisesRegex(EngineeringError, "ALREADY_CONSUMED"):
            reserve(self.root, p, observed_bindings=bindings(), now=NOW)

    def test_failure_does_not_release(self):
        p = permit()
        claim = reserve(self.root, p, observed_bindings=bindings(), now=NOW)
        finish(claim, outcome="FAILED", evidence_sha256="b" * 64, now=NOW)
        with self.assertRaisesRegex(EngineeringError, "ALREADY_CONSUMED"):
            reserve(self.root, p, observed_bindings=bindings(), now=NOW)

    def test_terminal_written_once(self):
        claim = reserve(self.root, permit(), observed_bindings=bindings(), now=NOW)
        finish(claim, outcome="COMPLETE", evidence_sha256="b" * 64, now=NOW)
        with self.assertRaisesRegex(EngineeringError, "ALREADY_FINALIZED"):
            finish(claim, outcome="FAILED", evidence_sha256="b" * 64, now=NOW)

    def test_tampered_record(self):
        claim = reserve(self.root, permit(), observed_bindings=bindings(), now=NOW)
        (claim.directory / "reservation.json").write_text("{}")
        with self.assertRaisesRegex(EngineeringError, "RECORD_CHANGED"):
            finish(claim, outcome="COMPLETE", evidence_sha256="b" * 64, now=NOW)

    def test_revalidate_time_at_reservation(self):
        with self.assertRaisesRegex(EngineeringError, "OUTSIDE_WINDOW"):
            reserve(self.root, permit(), observed_bindings=bindings(), now=NOW.replace(hour=12))

    def test_concurrent_only_one_winner(self):
        barrier = threading.Barrier(8)
        p = permit()

        def attempt(_):
            barrier.wait()
            try:
                reserve(self.root, p, observed_bindings=bindings(), now=NOW)
                return "RESERVED"
            except EngineeringError as exc:
                return str(exc)

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(attempt, range(8)))
        self.assertEqual(results.count("RESERVED"), 1)
        self.assertEqual(results.count("NPI_LEASE_ALREADY_CONSUMED"), 7)


class ReadinessTests(unittest.TestCase):
    def test_supported(self):
        for v in ((3, 11, 0), (3, 12, 10)):
            self.assertEqual(python_check(v)["status"], "PASS")

    def test_unsupported(self):
        for v in ((3, 10, 9), (3, 13, 5), (3, 14, 2), (4, 11, 0)):
            self.assertEqual(python_check(v)["status"], "FAIL")

    def test_dependency_missing_and_drift(self):
        with tempfile.TemporaryDirectory() as t:
            file = Path(t) / "pyproject.toml"
            file.write_text(
                '[project]\nrequires-python=">=3.11,<3.13"\ndependencies=["a==1"]\n'
                '[project.optional-dependencies]\ndev=["b==2"]\n'
            )

            def lookup(name):
                if name == "a":
                    raise importlib.metadata.PackageNotFoundError(name)
                return "3"

            rows = dependency_checks(file, lookup)
            self.assertEqual([r["status"] for r in rows], ["NOT_AVAILABLE", "FAIL"])

    def fake(self, body=b'{"version":"0.33.3"}', status=200, refused=False):
        calls = []

        class Connection:
            def __init__(self, host, port, timeout):
                calls.append((host, port, timeout))

            def request(self, method, path, headers):
                calls.append((method, path))
                if refused:
                    raise ConnectionRefusedError()

            def getresponse(self):
                return SimpleNamespace(status=status, read=lambda n: body[:n])

            def close(self):
                calls.append("closed")

        return ollama_version_probe(Connection), calls

    def test_metadata_only(self):
        result, calls = self.fake()
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["identity_verified"])
        self.assertFalse(result["model_loaded"])
        self.assertEqual(calls, [("127.0.0.1", 11434, 3), ("GET", "/api/version"), "closed"])

    def test_refused_is_environment_not_identity_mismatch(self):
        result, _ = self.fake(refused=True)
        self.assertEqual(result["status"], "NOT_AVAILABLE")
        self.assertEqual(result["code"], "NPI_OLLAMA_UNREACHABLE")

    def test_redirect_denied(self):
        self.assertEqual(self.fake(status=302)[0]["status"], "FAIL")

    def test_invalid_response(self):
        for body in (b"{}", b'{"version":"a","version":"b"}', b"not json"):
            self.assertEqual(self.fake(body=body)[0]["status"], "FAIL")

    def test_oversized_response(self):
        result, _ = self.fake(body=b"a" * (1024 * 1024 + 1))
        self.assertEqual(result["code"], "NPI_OLLAMA_RESPONSE_TOO_LARGE")


class EvidenceTests(unittest.TestCase):
    def rows(self):
        return [
            {
                "name": name,
                "command": ["python", "-m", name],
                "tool_version": "test",
                "started_at_utc": "2026-09-13T10:00:00Z",
                "ended_at_utc": "2026-09-13T10:01:00Z",
                "exit_code": 0,
                "status": "PASS",
                "stdout_sha256": "a" * 64,
                "stderr_sha256": "b" * 64,
                "skipped_count": 0,
            }
            for name in sorted(REQUIRED_QUALITY)
        ]

    def test_complete(self):
        self.assertTrue(quality_matrix(self.rows(), python_supported=True)["complete"])

    def test_unsupported_even_when_tests_pass(self):
        self.assertFalse(quality_matrix(self.rows(), python_supported=False)["complete"])

    def test_placeholder_rejected(self):
        with self.assertRaisesRegex(EngineeringError, "INCOMPLETE"):
            quality_matrix([{"runtime_gate": "PASS"}], python_supported=True)

    def test_nonzero_is_not_pass(self):
        rows = self.rows()
        rows[0]["exit_code"] = 10
        with self.assertRaisesRegex(EngineeringError, "FALSE_PASS"):
            quality_matrix(rows, python_supported=True)

    def test_skipped_is_not_pass(self):
        rows = self.rows()
        rows[0]["skipped_count"] = 1
        with self.assertRaisesRegex(EngineeringError, "FALSE_PASS"):
            quality_matrix(rows, python_supported=True)

    def test_explicit_skip_incomplete(self):
        rows = self.rows()
        rows[0].update(status="SKIPPED", skipped_count=1)
        self.assertFalse(quality_matrix(rows, python_supported=True)["complete"])

    def test_missing_check(self):
        with self.assertRaisesRegex(EngineeringError, "CHECK_SET"):
            quality_matrix(self.rows()[:-1], python_supported=True)

    def test_duplicate_check(self):
        with self.assertRaisesRegex(EngineeringError, "DUPLICATE"):
            quality_matrix(self.rows() + [self.rows()[0]], python_supported=True)

    def test_five_observations(self):
        labels = ["preflight", "before_s3", "before_s20", "before_resume", "after_resume"]
        values = [
            {"checkpoint": k, "observed_at_utc": NOW.isoformat(), "identity": {"version": "v"}}
            for k in labels
        ]
        self.assertEqual(len(validate_identity_observations(values, {"version": "v"})), 64)
        values[2]["identity"]["version"] = "changed"
        with self.assertRaisesRegex(EngineeringError, "DRIFT"):
            validate_identity_observations(values, {"version": "v"})

    def test_no_fabricated_five_count(self):
        with self.assertRaisesRegex(EngineeringError, "INCOMPLETE"):
            validate_identity_observations([], {})

    def test_resume_pass(self):
        result = validate_resume_evidence(
            exit_code=0,
            resume_status="ALREADY_COMPLETE_VERIFIED",
            before={"x": "a" * 64},
            after={"x": "a" * 64},
            model_load_count=0,
        )
        self.assertEqual(result["changed"], 0)

    def test_resume_connection_failure_not_pass(self):
        with self.assertRaisesRegex(EngineeringError, "NOT_SUCCESSFUL"):
            validate_resume_evidence(
                exit_code=10,
                resume_status="",
                before={"x": "a" * 64},
                after={"x": "a" * 64},
                model_load_count=0,
            )

    def test_resume_load_unknown_not_zero(self):
        with self.assertRaisesRegex(EngineeringError, "NOT_PROVEN"):
            validate_resume_evidence(
                exit_code=0,
                resume_status="ALREADY_COMPLETE_VERIFIED",
                before={"x": "a" * 64},
                after={"x": "a" * 64},
                model_load_count=None,
            )

    def test_resume_changed(self):
        with self.assertRaisesRegex(EngineeringError, "CHANGED"):
            validate_resume_evidence(
                exit_code=0,
                resume_status="ALREADY_COMPLETE_VERIFIED",
                before={"x": "a" * 64},
                after={"x": "b" * 64},
                model_load_count=0,
            )


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "synthetic@example.invalid")
        (self.root / "sample.py").write_text("print(1)\n")
        (self.root / "approval.json").write_text('{"status":"DRAFT"}\n')
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic fixture")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.root), *args], check=True, capture_output=True
        ).stdout

    def test_all_tracked_files(self):
        result = full_source_identity(self.root)
        self.assertEqual(result["file_count"], 2)
        self.assertEqual({r["path"] for r in result["files"]}, {"sample.py", "approval.json"})

    def test_dirty_fails(self):
        (self.root / "sample.py").write_text("print(2)\n")
        with self.assertRaisesRegex(EngineeringError, "NOT_CLEAN"):
            full_source_identity(self.root)

    def test_untracked_fails(self):
        (self.root / "new.txt").write_text("not ignored")
        with self.assertRaisesRegex(EngineeringError, "NOT_CLEAN"):
            full_source_identity(self.root)

    def test_every_source_change_alters_digest(self):
        before = full_source_identity(self.root)
        (self.root / "approval.json").write_text('{"status":"OTHER"}\n')
        self.git("add", ".")
        self.git("commit", "-qm", "change synthetic contract")
        after = full_source_identity(self.root)
        self.assertNotEqual(before["source_manifest_sha256"], after["source_manifest_sha256"])

    def test_deterministic(self):
        self.assertEqual(full_source_identity(self.root), full_source_identity(self.root))


if __name__ == "__main__":
    unittest.main()
