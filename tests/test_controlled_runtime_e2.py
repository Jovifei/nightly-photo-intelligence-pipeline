"""E2 integration contracts for the default controlled runtime path."""

from __future__ import annotations

import inspect
import io
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256
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
    assert "_AdmittedIdentityClient" in source
    assert "redirect_stdout(sys.stderr)" in source


def test_admitted_identity_guard_rejects_runner_identity_drift() -> None:
    first = SimpleNamespace(**IDENTITY)
    second = SimpleNamespace(**{**IDENTITY, "ollama_version": "0.33.4"})

    class FakeClient:
        def __init__(self) -> None:
            self.values = iter((first, second))

        def verify_identity(self) -> Any:
            return next(self.values)

    guarded = controlled_runtime_worker._AdmittedIdentityClient(
        FakeClient(), {"runtime_identity_sha256": sha256(canonical(IDENTITY))}
    )
    assert guarded.verify_identity() is first
    with pytest.raises(ValueError, match="NPI_WORKER_RUNTIME_IDENTITY_DRIFT"):
        guarded.verify_identity()


def test_worker_revalidates_manifest_bindings_and_configured_paths() -> None:
    source = inspect.getsource(controlled_runtime_worker.validate_bound_configuration)
    source += inspect.getsource(worker_dispatch._validate_manifest_bindings)
    assert "checked_path" in source
    assert "s3_manifest_sha256" in source
    assert "s20_manifest_sha256" in source


def test_worker_rejects_manifest_drift_after_claim(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    paths = {
        name: tmp_path / name
        for name in (
            "cache",
            "s3-manifest",
            "s20-manifest",
            "baseline-manifest",
            "ledger",
        )
    }
    for path in paths.values():
        path.mkdir()
    manifest = b"manifest\n"
    for name in ("s3-manifest", "s20-manifest"):
        (paths[name] / "fixture_manifest.json").write_bytes(manifest)
    prior = tmp_path / "prior-review.json"
    prior.write_bytes(b"{}\n")
    reservation = paths["ledger"] / ("a" * 64)
    reservation.mkdir()
    config = {
        "project_root": str(project),
        "cache_root": str(paths["cache"]),
        "s3_manifest_dir": str(paths["s3-manifest"]),
        "s20_manifest_dir": str(paths["s20-manifest"]),
        "baseline_manifest_dir": str(paths["baseline-manifest"]),
        "s3_out": str(tmp_path / "s3-out"),
        "s20_out": str(tmp_path / "s20-out"),
        "prior_s20_review_record": str(prior),
        "reviewed_commit": "b" * 40,
        "candidate_tree": "c" * 40,
        "source_manifest_sha256": "d" * 64,
        "s3_manifest_sha256": sha256(manifest),
        "s20_manifest_sha256": sha256(manifest),
        "ledger_root": str(paths["ledger"]),
        "reservation_dir": str(reservation),
        "receipt_sha256": "a" * 64,
        "bindings_sha256": "e" * 64,
        "runtime_identity_sha256": "f" * 64,
    }
    worker_dispatch.validate_bound_configuration(config)
    (paths["s3-manifest"] / "fixture_manifest.json").write_bytes(b"changed\n")
    with pytest.raises(ValueError, match="NPI_WORKER_MANIFEST_MISMATCH"):
        worker_dispatch.validate_bound_configuration(config)


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
    harness = Harness(tmp_path, monkeypatch, install_default=False)
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

    class FakeWorkerClient:
        def verify_identity(self) -> Any:
            calls.append("identity")
            return SimpleNamespace(**IDENTITY)

    def fake_s3(**kwargs: Any) -> Any:
        calls.append("s3")
        kwargs["ollama"].verify_identity()
        out = Path(kwargs["config"].runtime_out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "validation_summary.json").write_bytes(canonical({"result": "fake"}))
        return SimpleNamespace(
            result=controlled_runtime_worker.S3_COMPLETE,
            summary={"hard_counts": counters},
        )

    def fake_s20(**kwargs: Any) -> dict[str, Any]:
        calls.append("resume" if kwargs.get("resume") else "s20")
        kwargs["ollama"].verify_identity()
        out = Path(kwargs["config"].runtime_out_dir)
        if kwargs.get("resume"):
            return {
                "result": controlled_runtime_worker.S20_COMPLETE,
                "resume_status": "ALREADY_COMPLETE_VERIFIED",
                "model_load_count": 0,
            }
        out.mkdir(parents=True, exist_ok=True)
        for name in (
            "validation_summary.json",
            "checkpoint.json",
            "runtime_metrics.json",
            "CHECKSUMS.sha256",
        ):
            (out / name).write_bytes(b"{}\n")
        return {"result": controlled_runtime_worker.S20_COMPLETE, "hard_counts": counters}

    monkeypatch.setattr(controlled_runtime_worker, "OllamaClient", FakeWorkerClient)
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.n2b2_synthetic.ollama_client.OllamaClient",
        FakeWorkerClient,
    )
    monkeypatch.setattr(controlled_runtime_worker, "load_s3_manifest", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(
        controlled_runtime_worker, "load_s20_manifest", lambda *_args, **_kwargs: []
    )
    monkeypatch.setattr(
        controlled_runtime_worker, "validate_legacy_s20_binding", lambda *_args: "f" * 40
    )
    monkeypatch.setattr(controlled_runtime_worker, "run_n2b2", fake_s3)
    monkeypatch.setattr(controlled_runtime_worker, "run_s20", fake_s20)
    monkeypatch.setattr(
        "nightly_photo_intelligence_pipeline.engineering.source_identity.full_source_identity",
        lambda _root: harness.source,
    )

    def worker_process(command: list[str], **kwargs: object) -> SimpleNamespace:
        input_bytes = cast(bytes, kwargs["input"])
        stdin = io.TextIOWrapper(io.BytesIO(input_bytes), encoding="utf-8")
        stdout_buffer = io.BytesIO()
        stderr_buffer = io.BytesIO()
        stdout = io.TextIOWrapper(stdout_buffer, encoding="utf-8")
        stderr = io.TextIOWrapper(stderr_buffer, encoding="utf-8")
        old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
        try:
            sys.stdin, sys.stdout, sys.stderr = stdin, stdout, stderr
            returncode = controlled_runtime_worker.run_from_stdin(["--mode", str(command[-1])])
            stdout.flush()
            stderr.flush()
            return SimpleNamespace(
                returncode=returncode,
                stdout=stdout_buffer.getvalue(),
                stderr=stderr_buffer.getvalue(),
            )
        finally:
            sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr

    monkeypatch.setattr(controlled_runtime.subprocess, "run", worker_process)
    result = harness.invoke()
    assert result.exit_code == 0, result.output
    assert [item for item in calls if item in {"s3", "s20", "resume"}] == [
        "s3",
        "s20",
        "resume",
    ]
    assert (harness.ledger / "worker-fresh-claim.json").is_file()
    assert (harness.ledger / "worker-resume-claim.json").is_file()
