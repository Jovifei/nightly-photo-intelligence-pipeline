"""E2 integration contracts for the default controlled runtime path."""

from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from nightly_photo_intelligence_pipeline.engineering.common import canonical
from nightly_photo_intelligence_pipeline.n2b2_synthetic import (
    controlled_runtime,
    controlled_runtime_worker,
    orchestrator,
    s20_orchestrator,
    worker_dispatch,
)
from test_controlled_runtime_cli import IDENTITY, Harness


def test_parent_worker_launch_issues_a_dispatch_envelope(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    issued: list[tuple[dict[str, object], str]] = []
    sent: list[bytes] = []

    def issue(configuration: dict[str, object], mode: str) -> dict[str, object]:
        issued.append((configuration, mode))
        return {"envelope": "fake", "mode": mode}

    def run(*_command: object, **kwargs: object) -> SimpleNamespace:
        sent.append(kwargs["input"])  # type: ignore[arg-type]
        return SimpleNamespace(returncode=0, stdout=b"{}", stderr=b"")

    monkeypatch.setattr(
        controlled_runtime,
        "worker_dispatch",
        SimpleNamespace(issue=issue),
        raising=False,
    )
    monkeypatch.setattr(controlled_runtime.subprocess, "run", run)
    configuration = {"project_root": str(tmp_path)}
    controlled_runtime._run_worker(
        project_root=tmp_path,
        mode="fresh",
        configuration=configuration,
    )
    assert issued == [(configuration, "fresh")]
    assert sent == [canonical({"envelope": "fake", "mode": "fresh"})]


def test_e1_protocol_modules_are_integrated_into_project_package() -> None:
    assert hasattr(controlled_runtime, "worker_dispatch")
    assert hasattr(controlled_runtime_worker, "claim")
    from nightly_photo_intelligence_pipeline.n2b2_synthetic import legacy_s20_binding

    assert callable(legacy_s20_binding.validate_legacy_s20_binding)


def test_historical_s20_binding_is_not_replaced_by_current_candidate() -> None:
    source = inspect.getsource(controlled_runtime_worker._common)
    assert "validate_legacy_s20_binding" in source


def test_worker_checks_identity_and_source_before_runner() -> None:
    source = "".join(
        inspect.getsource(function)
        for function in (
            controlled_runtime_worker.run_from_stdin,
            controlled_runtime_worker._fresh,
            controlled_runtime_worker._resume,
        )
    )
    assert "claim(envelope, args.mode)" in source
    assert "assert_source" in source
    assert "assert_identity" in source
    assert "redirect_stdout(sys.stderr)" in source


def test_both_synthetic_producers_declare_production_bundle_counter() -> None:
    assert '"production_bundle_count": 0' in inspect.getsource(orchestrator.run_n2b2)
    assert '"production_bundle_count": 0' in inspect.getsource(s20_orchestrator._hard_counts)


def test_legacy_binding_passes_historical_commit_to_existing_gates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = Path(__file__).resolve().parents[1]
    prior_review = tmp_path / "prior-review.json"
    manifest = tmp_path / "fixture_manifest.json"
    prior_review.write_bytes(canonical({"reviewed_commit": "a" * 40}))
    manifest.write_bytes(b"manifest")
    calls: list[tuple[str, str]] = []

    def review_gate(_review: Path, _owner: Path, _qwen: Path, reviewed_commit: str):
        calls.append(("review", reviewed_commit))
        return "review", "qwen", {}

    def integrity_gate(_receipt: Path, *, reviewed_commit: str, manifest_sha256: str):
        calls.append(("integrity", reviewed_commit))
        return "integrity", {}

    monkeypatch.setattr(s20_orchestrator, "_review_gate", review_gate)
    monkeypatch.setattr(s20_orchestrator, "_artifact_integrity_gate", integrity_gate)
    from nightly_photo_intelligence_pipeline.n2b2_synthetic.legacy_s20_binding import (
        validate_legacy_s20_binding,
    )

    historical = validate_legacy_s20_binding(root, prior_review, manifest)
    assert historical == "a" * 40
    assert calls == [("review", "a" * 40), ("integrity", "a" * 40)]


def test_public_command_uses_default_factory_and_real_dispatch_protocol(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real_factory = controlled_runtime._default_execute
    harness = Harness(tmp_path, monkeypatch, install_default=False)
    harness.install_fake_runner(monkeypatch, {})
    monkeypatch.setattr(controlled_runtime, "_default_execute", real_factory)
    harness.write_lease()
    calls: list[str] = []
    counters = {
        "real_photo_read_count": 0,
        "real_exif_read_count": 0,
        "g1_source_access": 0,
        "sqlite_write_count": 0,
        "app_write_count": 0,
        "production_bundle_count": 0,
        "model_download_bytes": 0,
        "obsidian_write_count": 0,
        "s20_runtime_obsidian_write_count": 0,
    }

    def observation(label: str) -> dict[str, object]:
        return {
            "checkpoint": label,
            "observed_at_utc": datetime.now(UTC).isoformat(),
            "identity": IDENTITY,
        }

    def worker_process(command: list[str], **kwargs: object) -> SimpleNamespace:
        mode = str(command[-1])
        envelope = json.loads(cast(bytes, kwargs["input"]))
        configuration = worker_dispatch.claim(envelope, mode)
        controlled_runtime_worker._require_parent_reservation(configuration)
        if mode == "fresh":
            calls.append("fresh")
            s3_out = Path(configuration["s3_out"])
            s20_out = Path(configuration["s20_out"])
            s3_out.mkdir()
            s20_out.mkdir()
            (s3_out / "validation_summary.json").write_text("{}", encoding="utf-8")
            for name in (
                "validation_summary.json",
                "checkpoint.json",
                "runtime_metrics.json",
                "CHECKSUMS.sha256",
            ):
                (s20_out / name).write_text("{}", encoding="utf-8")
            payload: dict[str, Any] = {
                "identity_observations": [observation("before_s3"), observation("before_s20")],
                "s3_hard_counts": counters,
                "s20_hard_counts": counters,
            }
        else:
            calls.append("resume")
            payload = {
                "identity_observations": [
                    observation("before_resume"),
                    observation("after_resume"),
                ],
                "resume": {
                    "resume_status": "ALREADY_COMPLETE_VERIFIED",
                    "model_load_count": 0,
                },
                "before": {"output": "a" * 64},
                "after": {"output": "a" * 64},
            }
        worker_dispatch.finish(configuration, mode, outcome="COMPLETE", result=payload)
        return SimpleNamespace(returncode=0, stdout=canonical(payload), stderr=b"")

    monkeypatch.setattr(controlled_runtime.subprocess, "run", worker_process)
    result = harness.invoke()
    assert result.exit_code == 0, result.output
    assert calls == ["fresh", "resume"]
    assert (harness.ledger / "worker-fresh-claim.json").is_file()
    assert (harness.ledger / "worker-resume-claim.json").is_file()
