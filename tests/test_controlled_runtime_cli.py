"""Fake end-to-end tests for the public controlled runtime command."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.engineering import controlled_entry
from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256
from nightly_photo_intelligence_pipeline.engineering.controlled_entry import (
    REQUIRED_FORBIDDEN_COUNTERS,
)
from nightly_photo_intelligence_pipeline.engineering.evidence import REQUIRED_QUALITY
from nightly_photo_intelligence_pipeline.n2b1p_integrity import N2B1PRuntimeConfiguration
from nightly_photo_intelligence_pipeline.n2b2_synthetic import (
    controlled_runtime,
    controlled_runtime_worker,
    legacy_s20_binding,
)
from nightly_photo_intelligence_pipeline.n2b2_synthetic.runtime_identity_revalidation import (
    BASE_CANDIDATE,
    canonical_identity,
)

NOW = datetime(2026, 9, 15, 10, tzinfo=UTC)
IDENTITY = {
    "model_name": "qwen3.5:9b",
    "full_local_digest": "a" * 64,
    "size_bytes": 1,
    "quantization_level": "Q4_K_M",
    "capabilities": ["vision"],
    "ollama_version": "0.33.3",
}


def _quality_records() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "command": ["fake-check", name],
            "tool_version": "fake-1",
            "started_at_utc": NOW.isoformat(),
            "ended_at_utc": (NOW + timedelta(seconds=1)).isoformat(),
            "exit_code": 0,
            "status": "PASS",
            "stdout_sha256": "b" * 64,
            "stderr_sha256": "c" * 64,
            "skipped_count": 0,
        }
        for name in sorted(REQUIRED_QUALITY)
    ]


def _callback_evidence() -> dict[str, Any]:
    observations = [
        {
            "checkpoint": label,
            "observed_at_utc": (NOW + timedelta(seconds=index)).isoformat(),
            "identity": IDENTITY,
        }
        for index, label in enumerate(
            ("preflight", "before_s3", "before_s20", "before_resume", "after_resume")
        )
    ]
    return {
        "quality_records": _quality_records(),
        "identity_observations": observations,
        "resume": {
            "exit_code": 0,
            "resume_status": "ALREADY_COMPLETE_VERIFIED",
            "before": {"output": "d" * 64},
            "after": {"output": "d" * 64},
            "model_load_count": 0,
        },
        "artifacts": {"runner_output": "e" * 64},
        "forbidden_counters": {
            "real_photo_read_count": 0,
            "real_exif_read_count": 0,
            "g1_source_access": 0,
            "sqlite_write_count": 0,
            "app_write_count": 0,
            "production_bundle_count": 0,
            "model_download_bytes": 0,
        },
    }


class Harness:
    def __init__(self, tmp_path: Path, monkeypatch: Any, *, install_default: bool = True) -> None:
        self.project = Path(__file__).resolve().parents[1]
        monkeypatch.setenv("NPI_PROJECT_ROOT", str(self.project))
        self.now = datetime.now(UTC)
        self.root = tmp_path
        self.runtime_parent = tmp_path / "runtime"
        self.cache_root = tmp_path / "cache"
        self.runtime_parent.mkdir()
        self.cache_root.mkdir()
        self.owner_anchor_path = (
            self.runtime_parent
            / controlled_runtime._OWNER_LEASE_ANCHOR_DIR
            / controlled_runtime._OWNER_LEASE_ANCHOR_FILE
        )
        self.owner_anchor_path.parent.mkdir()
        self.inputs = {
            "old_s3": tmp_path / "old-s3",
            "old_s20": tmp_path / "old-s20",
            "s3_manifest": tmp_path / "s3-manifest",
            "s20_manifest": tmp_path / "s20-manifest",
            "baseline_manifest": tmp_path / "baseline-manifest",
        }
        for path in self.inputs.values():
            path.mkdir()
            (path / "fixture_manifest.json").write_text("fixture", encoding="utf-8")
        self.old_identity = {**IDENTITY, "ollama_version": "0.32.15"}
        (self.inputs["old_s20"] / "ollama_identity.json").write_bytes(canonical(self.old_identity))
        self.file_dirs = {
            "candidate_review": tmp_path / "candidate-review",
            "historical_review": tmp_path / "historical-review",
            "lease": tmp_path / "lease",
            "quality": tmp_path / "quality",
            "prior": tmp_path / "prior",
        }
        for path in self.file_dirs.values():
            path.mkdir()
        self.source = {
            "candidate_commit": "1" * 40,
            "candidate_tree": "2" * 40,
            "source_manifest_sha256": "3" * 64,
        }
        self.candidate_review = self.file_dirs["candidate_review"] / "review.json"
        self.candidate_review.write_bytes(
            canonical(
                {
                    "schema_version": "npi-independent-review-v1",
                    "reviewed_commit": self.source["candidate_commit"],
                    "reviewed_parent": "0" * 40,
                    "reviewed_tree": self.source["candidate_tree"],
                    "independent": True,
                    "verdict": "PASS_FOR_EXTERNAL_REVIEW",
                    "ready_to_merge_or_publish": True,
                }
            )
        )
        self.historical_review = self.file_dirs["historical_review"] / "review.txt"
        self.historical_review.write_text(
            "INCONCLUSIVE\nN2B2_S20_RESUME_BINDING_MISMATCH: model_identity\n",
            encoding="utf-8",
        )
        self.quality = self.file_dirs["quality"] / "quality.json"
        self.quality.write_bytes(canonical({"checks": _quality_records()}))
        self.prior = self.file_dirs["prior"] / "prior.json"
        self.prior.write_bytes(canonical({"reviewed_commit": "f" * 40}))
        self.outputs = {
            "s3_out": tmp_path / "s3-out",
            "s20_out": tmp_path / "s20-out",
            "evidence_out": tmp_path / "evidence-out",
        }
        self.runtime = N2B1PRuntimeConfiguration(
            configuration_version="TEST",
            runtime_parent=self.runtime_parent,
            work_root=self.runtime_parent / "work",
            snapshot_root="NOT_APPLICABLE_N2B1P_SOURCE_ACCESS_FORBIDDEN",
            cache_root=self.cache_root,
            cache_root_identity="4" * 64,
            configuration_digest="5" * 64,
        )
        self.lease_path = self.file_dirs["lease"] / "lease.json"
        self.lease_bytes = b""
        self.lease_sha = ""
        self.probe_calls = 0
        self.runner_calls = 0
        monkeypatch.setattr(
            controlled_runtime,
            "load_n2b1p_runtime_configuration",
            lambda _root: self.runtime,
        )
        monkeypatch.setattr(controlled_runtime, "full_source_identity", lambda _root: self.source)
        monkeypatch.setattr(controlled_entry, "full_source_identity", lambda _root: self.source)
        self.task_receipt = self._task_receipt()
        monkeypatch.setattr(
            controlled_runtime,
            "_load_task_specific_receipt",
            lambda _root: self.task_receipt,
            raising=False,
        )
        monkeypatch.setattr(
            legacy_s20_binding,
            "validate_legacy_s20_binding",
            lambda *_args: "f" * 40,
        )
        if install_default:
            self.install_fake_runner(monkeypatch, _callback_evidence())

    def _task_receipt(self) -> dict[str, Any]:
        old = dict(self.old_identity)
        new = dict(IDENTITY)
        old["canonical_identity_sha256"] = hashlib.sha256(canonical_identity(old)).hexdigest()
        new["canonical_identity_sha256"] = hashlib.sha256(canonical_identity(new)).hexdigest()
        return {
            "schema_version": "1.0",
            "receipt_type": "OWNER_N2B2_OLLAMA_RUNTIME_IDENTITY_REVALIDATION",
            "status": "APPROVED",
            "owner_id": "Jovi",
            "issued_at_utc": "2026-09-06T00:00:00Z",
            "task": "N2B2_OLLAMA_RUNTIME_IDENTITY_REVALIDATION_20260906",
            "base_candidate": BASE_CANDIDATE,
            "external_review_sha256": hashlib.sha256(
                self.historical_review.read_bytes()
            ).hexdigest(),
            "accepted_verdict": "INCONCLUSIVE",
            "accepted_blocker": "N2B2_S20_RESUME_BINDING_MISMATCH: model_identity",
            "old_identity": old,
            "authorized_identity": new,
            "project_state_sha256": sha256((self.project / "PROJECT_STATE.json").read_bytes()),
            "project_state_n2b2": "LOCKED",
            "production_unlock": False,
            "boundaries": {
                "real_photo": False,
                "real_exif": False,
                "g1_source": False,
                "sqlite": False,
                "real20": False,
                "app": False,
                "production_bundle": False,
                "model_download": False,
                "model_replacement": False,
            },
            "max_fresh_s3_runs": 1,
            "max_fresh_s20_runs": 1,
            "new_output_required": True,
            "old_evidence_mutation": False,
            "mandatory_external_review": True,
        }

    def _protected(self) -> dict[str, Path]:
        return {
            "project_root": self.project,
            "ledger_root": self.runtime_parent / "n2b2-controlled-execution-ledger",
            "cache_root": self.cache_root,
            "owner_anchor_root": self.owner_anchor_path.parent,
            "candidate_review_root": self.file_dirs["candidate_review"],
            "historical_review_root": self.file_dirs["historical_review"],
            "lease_root": self.file_dirs["lease"],
            "quality_root": self.file_dirs["quality"],
            "prior_review_root": self.file_dirs["prior"],
        }

    def write_lease(
        self, *, status: str = "APPROVED", identity: dict[str, Any] | None = None
    ) -> None:
        bound_identity = identity or IDENTITY
        inputs = self.inputs
        outputs = self.outputs
        protected = self._protected()
        path_sha = controlled_runtime.path_plan_digest(
            inputs=inputs, outputs=outputs, protected=protected
        )
        state_bytes = (self.project / "PROJECT_STATE.json").read_bytes()
        bindings = {
            **self.source,
            "project_state_sha256": sha256(state_bytes),
            "candidate_review_sha256": sha256(self.candidate_review.read_bytes()),
            "historical_review_sha256": sha256(self.historical_review.read_bytes()),
            "prior_s20_review_sha256": sha256(self.prior.read_bytes()),
            "quality_evidence_sha256": sha256(self.quality.read_bytes()),
            "runtime_identity_sha256": sha256(canonical(bound_identity)),
            "s3_manifest_sha256": sha256(
                (inputs["s3_manifest"] / "fixture_manifest.json").read_bytes()
            ),
            "s20_manifest_sha256": sha256(
                (inputs["s20_manifest"] / "fixture_manifest.json").read_bytes()
            ),
            "model_cache_binding_sha256": self.runtime.cache_root_identity,
            "path_plan_sha256": path_sha,
        }
        lease = {
            "schema_version": "npi-synthetic-execution-lease-v3",
            "status": status,
            "owner_id": "Jovi",
            "purpose": "SYNTHETIC_S3_S20_ENGINEERING_VALIDATION",
            "not_before_utc": (self.now - timedelta(minutes=1)).isoformat(),
            "expires_at_utc": (self.now + timedelta(days=1)).isoformat(),
            "bindings": bindings,
            "boundaries": {
                "real_photo": False,
                "real_exif": False,
                "g1_source": False,
                "sqlite_ingest": False,
                "app": False,
                "production_bundle": False,
                "model_download": False,
                "model_replacement": False,
                "project_state_mutation": False,
            },
            "max_fresh_s3_runs": 1,
            "max_fresh_s20_runs": 1,
            "production_unlock": False,
        }
        self.lease_bytes = canonical(lease)
        self.lease_path.write_bytes(self.lease_bytes)
        self.lease_sha = hashlib.sha256(self.lease_bytes).hexdigest()
        self.owner_anchor_path.write_bytes(
            canonical(
                {
                    "schema_version": "npi-owner-execution-lease-anchor-v1",
                    "status": "APPROVED",
                    "owner_id": "Jovi",
                    "purpose": "SYNTHETIC_S3_S20_ENGINEERING_VALIDATION",
                    "execution_lease_sha256": self.lease_sha,
                    "production_unlock": False,
                }
            )
        )

    def install_fake_runner(
        self,
        monkeypatch: Any,
        evidence: dict[str, Any],
        identity: dict[str, Any] | None = None,
    ) -> None:
        fake_identity = SimpleNamespace(**(identity or IDENTITY))

        class FakeClient:
            def verify_identity(inner_self: Any) -> Any:
                self.probe_calls += 1
                return fake_identity

        def fake_execute_factory(**_kwargs: Any):
            def fake_execute() -> dict[str, Any]:
                self.runner_calls += 1
                return json.loads(json.dumps(evidence))

            return fake_execute

        monkeypatch.setattr(
            "nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client.OllamaClient",
            FakeClient,
        )
        monkeypatch.setattr(controlled_runtime, "_default_execute", fake_execute_factory)

    def command(self, *, include_caller_hash: bool = False) -> list[str]:
        values = {
            "candidate-review-artifact": self.candidate_review,
            "historical-review-artifact": self.historical_review,
            "execution-lease": self.lease_path,
            "quality-evidence": self.quality,
            "prior-s20-review-record": self.prior,
            "old-s3-runtime": self.inputs["old_s3"],
            "old-s20-runtime": self.inputs["old_s20"],
            "s3-manifest-dir": self.inputs["s3_manifest"],
            "s20-manifest-dir": self.inputs["s20_manifest"],
            "baseline-manifest-dir": self.inputs["baseline_manifest"],
            "s3-out": self.outputs["s3_out"],
            "s20-out": self.outputs["s20_out"],
            "evidence-out": self.outputs["evidence_out"],
        }
        args = ["n2b2", "runtime-identity-revalidate"]
        for name, value in values.items():
            args.extend([f"--{name}", str(value)])
        if include_caller_hash:
            args.extend(["--execution-lease-sha256", self.lease_sha])
        return args

    def invoke(self, *, include_caller_hash: bool = False):
        return CliRunner().invoke(app, self.command(include_caller_hash=include_caller_hash))

    @property
    def ledger(self) -> Path:
        return self.runtime_parent / "n2b2-controlled-execution-ledger" / self.lease_sha


def test_public_command_accepts_only_controlled_fake_execution(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    result = harness.invoke()
    assert result.exit_code == 0, result.output
    assert harness.probe_calls == 1
    assert harness.runner_calls == 1
    assert (harness.ledger / "terminal.json").is_file()
    assert (harness.outputs["evidence_out"] / "controlled_execution_evidence.json").is_file()


def test_public_command_rejects_candidate_review_with_wrong_source_before_probe(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    review = json.loads(harness.candidate_review.read_text(encoding="utf-8"))
    review["reviewed_commit"] = "9" * 40
    harness.candidate_review.write_bytes(canonical(review))
    harness.write_lease()

    result = harness.invoke()

    assert result.exit_code != 0
    assert "NPI_CANDIDATE_REVIEW_BINDING_INVALID" in result.output
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not harness.ledger.exists()


def test_public_command_rejects_historical_review_not_accepted_by_task_receipt(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.historical_review.write_bytes(harness.candidate_review.read_bytes())
    harness.write_lease()

    result = harness.invoke()

    assert result.exit_code != 0
    assert "NPI_TASK_RECEIPT_BINDING_INVALID" in result.output
    assert harness.probe_calls == 1
    assert harness.runner_calls == 0
    assert not (harness.ledger / "reservation.json").exists()


def test_public_command_rejects_passing_quality_substitution_before_probe(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    quality = json.loads(harness.quality.read_text(encoding="utf-8"))
    quality["extra"] = "substituted"
    harness.quality.write_bytes(canonical(quality))

    result = harness.invoke()

    assert result.exit_code != 0
    assert "NPI_LEASE_BINDING_MISMATCH" in result.output
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not harness.ledger.exists()


def test_public_command_rejects_caller_supplied_self_hash(tmp_path: Path, monkeypatch: Any) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    result = harness.invoke(include_caller_hash=True)
    assert result.exit_code != 0
    assert "execution-lease-sha256" in result.output
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not harness.ledger.exists()


def test_public_command_requires_external_owner_anchor(tmp_path: Path, monkeypatch: Any) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    harness.owner_anchor_path.unlink()
    result = harness.invoke()
    assert result.exit_code != 0
    assert "NPI_REQUIRED_FILE_MISSING" in result.output
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not harness.ledger.exists()


def test_public_command_rejects_draft_before_probe_or_ledger(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease(status="DRAFT")
    result = harness.invoke()
    assert result.exit_code != 0
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not harness.ledger.exists()


def test_public_command_rejects_wrong_owner_anchor_before_probe(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    anchor = json.loads(harness.owner_anchor_path.read_text(encoding="utf-8"))
    anchor["execution_lease_sha256"] = "a" * 64
    harness.owner_anchor_path.write_bytes(canonical(anchor))
    result = harness.invoke()
    assert result.exit_code != 0
    assert "NPI_OWNER_LEASE_ANCHOR_MISMATCH" in result.output
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not harness.ledger.exists()


def test_public_command_rechecks_replaced_input_before_reservation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    original = harness.inputs["old_s3"]
    saved = tmp_path / "old-s3-saved"

    def replace_input(inner_self: Any) -> Any:
        harness.probe_calls += 1
        original.rename(saved)
        original.mkdir()
        return SimpleNamespace(**IDENTITY)

    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client.OllamaClient.verify_identity",
        replace_input,
    )
    result = harness.invoke()
    assert result.exit_code != 0
    assert harness.probe_calls == 1
    assert harness.runner_calls == 0
    assert not (harness.ledger / "reservation.json").exists()


def test_public_command_rejects_replaced_ledger_binding(tmp_path: Path, monkeypatch: Any) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    real = controlled_runtime.run_controlled_execution
    alternate = tmp_path / "alternate-ledger"
    alternate.mkdir()

    def replace_ledger(plan: Any, **kwargs: Any) -> dict[str, Any]:
        return real(replace(plan, ledger_root=alternate), **kwargs)

    monkeypatch.setattr(controlled_runtime, "run_controlled_execution", replace_ledger)
    result = harness.invoke()
    assert result.exit_code != 0
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not (alternate / "reservation.json").exists()


def test_public_command_rejects_bad_quality_before_probe(tmp_path: Path, monkeypatch: Any) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.quality.write_bytes(
        canonical({"checks": [{**_quality_records()[0], "status": "FAIL"}]})
    )
    harness.write_lease()
    result = harness.invoke()
    assert result.exit_code != 0
    assert harness.probe_calls == 0
    assert harness.runner_calls == 0
    assert not harness.ledger.exists()


def test_public_command_rejects_bad_artifacts_after_reservation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    evidence = _callback_evidence()
    evidence["artifacts"] = {}
    harness.install_fake_runner(monkeypatch, evidence)
    harness.write_lease()
    result = harness.invoke()
    assert result.exit_code != 0
    assert harness.probe_calls == 1
    assert harness.runner_calls == 1
    assert (harness.ledger / "reservation.json").is_file()
    assert (harness.ledger / "terminal.json").is_file()


def test_public_command_rejects_nonzero_counter_after_reservation(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    evidence = _callback_evidence()
    evidence["forbidden_counters"]["real_photo_read_count"] = 1
    harness.install_fake_runner(monkeypatch, evidence)
    harness.write_lease()
    result = harness.invoke()
    assert result.exit_code != 0
    assert harness.probe_calls == 1
    assert harness.runner_calls == 1
    assert (harness.ledger / "terminal.json").is_file()


def test_public_command_rechecks_protected_evidence_after_runner(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch, install_default=False)
    harness.install_fake_runner(monkeypatch, _callback_evidence())

    def fake_execute_factory(**_kwargs: Any):
        def fake_execute() -> dict[str, Any]:
            harness.candidate_review.write_text("tampered after admission\n", encoding="utf-8")
            return _callback_evidence()

        return fake_execute

    monkeypatch.setattr(controlled_runtime, "_default_execute", fake_execute_factory)
    harness.write_lease()
    result = harness.invoke()
    assert result.exit_code != 0
    assert "NPI_BOUND_FILE_CHANGED" in result.output
    terminal = json.loads((harness.ledger / "terminal.json").read_text(encoding="utf-8"))
    assert terminal["status"] == "FAILED"
    assert not (harness.outputs["evidence_out"] / "controlled_execution_evidence.json").exists()


def test_persisted_controlled_evidence_binds_execution_lease(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    harness.write_lease()
    result = harness.invoke()
    assert result.exit_code == 0, result.output
    evidence = json.loads(
        (harness.outputs["evidence_out"] / "controlled_execution_evidence.json").read_text(
            encoding="utf-8"
        )
    )
    assert evidence["execution_lease_sha256"] == harness.lease_sha
    bindings = evidence["input_bindings"]
    assert bindings["candidate_review_sha256"] == sha256(harness.candidate_review.read_bytes())
    assert bindings["historical_review_sha256"] == sha256(harness.historical_review.read_bytes())
    assert bindings["prior_s20_review_sha256"] == sha256(harness.prior.read_bytes())
    assert bindings["quality_evidence_sha256"] == sha256(harness.quality.read_bytes())


def test_counter_aggregation_preserves_extra_runner_counters() -> None:
    first = dict.fromkeys(REQUIRED_FORBIDDEN_COUNTERS, 0)
    second = dict.fromkeys(REQUIRED_FORBIDDEN_COUNTERS, 0)
    first["obsidian_write_count"] = 1
    second["s20_runtime_obsidian_write_count"] = 2
    result = controlled_runtime._combine_counters(first, second)
    assert result["obsidian_write_count"] == 1
    assert result["s20_runtime_obsidian_write_count"] == 2


def test_regular_file_rejects_ntfs_alternate_stream_syntax(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="NPI_ALTERNATE_STREAM_DENIED"):
        controlled_runtime._regular_file(tmp_path / "evidence.json:review_stream")


def test_worker_module_direct_invocation_is_denied() -> None:
    root = Path(__file__).resolve().parents[1]
    environment = {**os.environ, "PYTHONPATH": str(root / "src")}
    result = subprocess.run(
        [sys.executable, "-m", controlled_runtime_worker.WORKER_MODULE, "--mode", "fresh"],
        input=b"{}",
        capture_output=True,
        check=False,
        env=environment,
    )
    assert result.returncode != 0
    assert b"NPI_WORKER_DIRECT_INVOCATION_DENIED" in result.stderr


def test_worker_internal_call_requires_parent_reservation() -> None:
    with pytest.raises(ValueError, match="NPI_RUNNER_RESERVATION_REQUIRED"):
        controlled_runtime_worker._require_parent_reservation({})


def test_public_command_rejects_old_ollama_identity_transition(
    tmp_path: Path, monkeypatch: Any
) -> None:
    harness = Harness(tmp_path, monkeypatch)
    old_identity = {**IDENTITY, "ollama_version": "0.32.15"}
    harness.install_fake_runner(monkeypatch, _callback_evidence(), identity=old_identity)
    harness.write_lease(identity=old_identity)
    result = harness.invoke()
    assert result.exit_code != 0
    assert harness.probe_calls == 1
    assert harness.runner_calls == 0
    assert not (harness.ledger / "reservation.json").exists()


def test_repository_task_receipt_is_loaded_with_its_schema() -> None:
    root = Path(__file__).resolve().parents[1]
    receipt = controlled_runtime._load_task_specific_receipt(root)
    assert receipt["task"] == "N2B2_OLLAMA_RUNTIME_IDENTITY_REVALIDATION_20260906"
    assert receipt["status"] == "APPROVED"


@pytest.mark.parametrize(
    ("command", "options"),
    [
        ("run", ["--s3-only"]),
        ("gpu-validate", ["--s3-manifest-dir", "external", "--out", "external-out"]),
        (
            "case17-remediate",
            [
                "--baseline-manifest-dir",
                "external",
                "--candidate-dir",
                "external-candidates",
                "--out",
                "external-out",
            ],
        ),
        (
            "s20-validate",
            [
                "--review-record",
                "external/review.json",
                "--s20-manifest-dir",
                "external/s20",
                "--out",
                "external-out",
            ],
        ),
        (
            "qwen-contract-probe",
            [
                "--review-record",
                "external/review.json",
                "--fixture-manifest-dir",
                "external/s20",
                "--baseline-manifest-dir",
                "external/baseline",
                "--vision-evidence-dir",
                "external/vision",
                "--out",
                "external-out",
            ],
        ),
    ],
)
def test_legacy_n2b2_commands_require_controlled_entry(command: str, options: list[str]) -> None:
    result = CliRunner().invoke(app, ["n2b2", command, *options])
    assert result.exit_code == 8, result.output
    assert "NPI_CONTROLLED_ENTRY_REQUIRED" in result.output
