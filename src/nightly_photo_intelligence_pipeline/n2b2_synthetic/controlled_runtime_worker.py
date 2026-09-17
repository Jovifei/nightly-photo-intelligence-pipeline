"""Subprocess worker for an already-admitted synthetic runtime execution.

This module is deliberately not an authorization entry point.  The parent
adapter performs every source, quality, lease, and ledger check first, then
passes only the runner configuration over stdin.  The worker reuses the
existing S3/S20 runners and returns process-bound evidence on stdout.
"""

from __future__ import annotations

import argparse
import platform
import stat
import sys
from collections.abc import Mapping
from contextlib import redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ..engineering.common import canonical, require, strict_json
from ..engineering.path_policy import checked_path
from . import N2B2RunConfig, load_s3_manifest, load_s20_manifest, run_n2b2
from .legacy_s20_binding import validate_legacy_s20_binding
from .ollama_client import ModelIdentity, OllamaClient
from .runtime_identity_revalidation import snapshot_tree
from .s20_bundle import S20_COMPLETE, write_json
from .s20_orchestrator import run_s20
from .worker_dispatch import (
    MAX_BYTES,
    assert_identity,
    assert_source,
    claim,
    finish,
    validate_bound_configuration,
)

WORKER_MODULE = "nightly_photo_intelligence_pipeline.n2b2_synthetic.controlled_runtime_worker"
N2B1P_SHA = "0fef0a8f6a2f2b2f75ce2fba3e3eef1e764037b8"
S3_COMPLETE = "N2B2_SYNTHETIC_SMOKE_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW"


def _path(payload: Mapping[str, Any], name: str) -> Path:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError("NPI_RUNNER_CONFIGURATION_INVALID")
    return Path(value)


def _identity_record(identity: ModelIdentity) -> dict[str, object]:
    return {
        "model_name": identity.model_name,
        "full_local_digest": identity.full_local_digest,
        "size_bytes": identity.size_bytes,
        "quantization_level": identity.quantization_level,
        "capabilities": list(identity.capabilities),
        "ollama_version": identity.ollama_version,
    }


class _AdmittedIdentityClient:
    """Delegate runtime calls while binding every identity observation to admission."""

    def __init__(self, delegate: OllamaClient, configuration: Mapping[str, Any]) -> None:
        self._delegate = delegate
        self._configuration = configuration

    def verify_identity(self) -> ModelIdentity:
        identity = self._delegate.verify_identity()
        assert_identity(self._configuration, _identity_record(identity))
        return identity

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)


def _require_parent_reservation(payload: Mapping[str, Any]) -> None:
    names = ("ledger_root", "reservation_dir", "receipt_sha256", "bindings_sha256")
    if not all(name in payload for name in names):
        raise ValueError("NPI_RUNNER_RESERVATION_REQUIRED")
    values = {name: payload.get(name) for name in names}
    if not all(isinstance(value, str) and value for value in values.values()):
        raise ValueError("NPI_RUNNER_RESERVATION_REQUIRED")
    ledger_root = Path(cast(str, values["ledger_root"]))
    reservation_dir = Path(cast(str, values["reservation_dir"]))
    receipt_sha256 = cast(str, values["receipt_sha256"])
    bindings_sha256 = cast(str, values["bindings_sha256"])
    if (
        len(receipt_sha256) != 64
        or any(char not in "0123456789abcdef" for char in receipt_sha256)
        or len(bindings_sha256) != 64
        or any(char not in "0123456789abcdef" for char in bindings_sha256)
        or reservation_dir != ledger_root / receipt_sha256
    ):
        raise ValueError("NPI_RUNNER_RESERVATION_INVALID")
    try:
        checked_path(ledger_root, must_exist=True)
        checked_path(reservation_dir, must_exist=True)
        record_path = reservation_dir / "reservation.json"
        info = record_path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("NPI_RUNNER_RESERVATION_INVALID")
        record = strict_json(record_path.read_bytes())
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc) == "NPI_RUNNER_RESERVATION_INVALID":
            raise
        raise ValueError("NPI_RUNNER_RESERVATION_INVALID") from exc
    if not isinstance(record, Mapping):
        raise ValueError("NPI_RUNNER_RESERVATION_INVALID")
    if (
        set(record)
        != {"schema_version", "status", "receipt_sha256", "bindings_sha256", "reserved_at_utc"}
        or record.get("schema_version") != "npi-lease-consumption-v1"
        or record.get("status") != "RESERVED"
        or record.get("receipt_sha256") != receipt_sha256
        or record.get("bindings_sha256") != bindings_sha256
    ):
        raise ValueError("NPI_RUNNER_RESERVATION_INVALID")
    terminal_path = reservation_dir / "terminal.json"
    try:
        terminal_path.lstat()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ValueError("NPI_RUNNER_RESERVATION_INVALID") from exc
    raise ValueError("NPI_RUNNER_RESERVATION_ALREADY_FINISHED")


def _observation(label: str, identity: ModelIdentity) -> dict[str, object]:
    return {
        "checkpoint": label,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "identity": _identity_record(identity),
    }


def _common(payload: Mapping[str, Any]) -> dict[str, Any]:
    validate_bound_configuration(payload)
    root = _path(payload, "project_root")
    cache_root = _path(payload, "cache_root")
    s20_manifest = _path(payload, "s20_manifest_dir")
    baseline_manifest = _path(payload, "baseline_manifest_dir")
    prior_review = _path(payload, "prior_s20_review_record")
    # The historical review SHA and current execution SHA have different roles.
    reviewed_commit = validate_legacy_s20_binding(
        root, prior_review, s20_manifest / "fixture_manifest.json"
    )
    schemas = root / "schemas"
    fixtures = load_s20_manifest(
        s20_manifest, project_root=root, baseline_manifest_dir=baseline_manifest
    )
    return {
        "config": N2B2RunConfig(
            project_root=root,
            cache_root=cache_root,
            fixtures_dir=s20_manifest,
            runtime_out_dir=_path(payload, "s20_out"),
            backend="real",
            device="cuda",
            s3_only=False,
        ),
        "fixtures": fixtures,
        "reasoning_schema": cast(
            dict[str, Any],
            strict_json((schemas / "n2b2_photography_reasoning.schema.json").read_bytes()),
        ),
        "vision_schema": cast(
            dict[str, Any],
            strict_json((schemas / "n2b2_vision_fact_contract_v1_2.schema.json").read_bytes()),
        ),
        "reviewed_commit": reviewed_commit,
        "review_record": prior_review,
        "owner_receipt": root / "approvals" / "owner_n2b2_s20_synthetic_validation_receipt.yaml",
        "qwen_receipt": root
        / "approvals"
        / "owner_n2b2_qwen_fact_binding_remediation_receipt.yaml",
        "artifact_integrity_receipt": root
        / "approvals"
        / "owner_n2b2_s20_artifact_integrity_remediation_receipt.yaml",
    }


def _fresh(payload: Mapping[str, Any]) -> dict[str, Any]:
    payload = validate_bound_configuration(payload)
    root = _path(payload, "project_root")
    cache_root = _path(payload, "cache_root")
    s3_manifest = _path(payload, "s3_manifest_dir")
    s20_out = _path(payload, "s20_out")
    s3_out = _path(payload, "s3_out")
    # Check all legacy S20 inputs before S3 can consume GPU work.
    common = _common(payload)
    client = _AdmittedIdentityClient(OllamaClient(), payload)
    observations: list[dict[str, object]] = []

    def observe(label: str) -> None:
        validate_bound_configuration(payload)
        identity = client.verify_identity()
        assert_identity(payload, _identity_record(identity))
        observations.append(_observation(label, identity))

    observe("before_s3")
    validate_bound_configuration(payload)
    s3_fixtures = load_s3_manifest(s3_manifest, project_root=root)
    s3_config = N2B2RunConfig(
        project_root=root,
        cache_root=cache_root,
        fixtures_dir=s3_manifest,
        runtime_out_dir=s3_out,
        backend="real",
        device="cuda",
        s3_only=True,
    )
    s3_out.mkdir(parents=True, exist_ok=True)
    s3_result = run_n2b2(
        config=s3_config,
        s3_fixtures=s3_fixtures,
        s20_fixtures=[],
        reasoning_schema=cast(
            dict[str, Any],
            strict_json((root / "schemas" / "n2b2_photography_reasoning.schema.json").read_bytes()),
        ),
        vision_schema=cast(
            dict[str, Any],
            strict_json(
                (root / "schemas" / "n2b2_vision_fact_contract_v1_2.schema.json").read_bytes()
            ),
        ),
        n2b1p_sha=N2B1P_SHA,
        n2b1p_review_passed=True,
        start_head=str(payload["reviewed_commit"]),
        ollama=cast(OllamaClient, client),
    )
    require(s3_result.result == S3_COMPLETE, "NPI_S3_RUNNER_FAILED")
    write_json(s3_out / "validation_summary.json", s3_result.summary)

    observe("before_s20")
    validate_bound_configuration(payload)
    s20_out.mkdir(parents=True, exist_ok=True)
    s20_summary = run_s20(**common, ollama=cast(OllamaClient, client))
    require(s20_summary.get("result") == S20_COMPLETE, "NPI_S20_RUNNER_FAILED")
    return {
        "python_version": platform.python_version(),
        "identity_observations": observations,
        "s3_hard_counts": s3_result.summary.get("hard_counts"),
        "s20_hard_counts": s20_summary.get("hard_counts"),
        "s20_result": s20_summary.get("result"),
    }


def _resume(payload: Mapping[str, Any]) -> dict[str, Any]:
    payload = validate_bound_configuration(payload)
    client = _AdmittedIdentityClient(OllamaClient(), payload)
    identity = client.verify_identity()
    assert_identity(payload, _identity_record(identity))
    observations = [_observation("before_resume", identity)]
    output = _path(payload, "s20_out")
    before = snapshot_tree(output).entries
    common = _common(payload)
    validate_bound_configuration(payload)
    resumed = run_s20(**common, resume=True, ollama=cast(OllamaClient, client))
    after = snapshot_tree(output).entries
    identity = client.verify_identity()
    assert_identity(payload, _identity_record(identity))
    observations.append(_observation("after_resume", identity))
    require(
        resumed.get("resume_status") == "ALREADY_COMPLETE_VERIFIED", "NPI_RESUME_STATUS_INVALID"
    )
    model_load_count = resumed.get("model_load_count")
    require(type(model_load_count) is int, "NPI_RESUME_LOAD_COUNT_MISSING")
    return {
        "python_version": platform.python_version(),
        "identity_observations": observations,
        "resume": dict(resumed),
        "before": before,
        "after": after,
    }


def run_from_stdin(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=("fresh", "resume"), required=True)
    args = parser.parse_args(argv)
    data = sys.stdin.buffer.read(MAX_BYTES + 1)
    require(len(data) <= MAX_BYTES, "NPI_DISPATCH_SIZE_LIMIT")
    envelope = strict_json(data)
    require(isinstance(envelope, Mapping), "NPI_RUNNER_CONFIGURATION_INVALID")
    payload = validate_bound_configuration(claim(envelope, args.mode))
    try:
        _require_parent_reservation(payload)
        from ..engineering.readiness import python_check
        from ..engineering.source_identity import full_source_identity

        version = (sys.version_info[0], sys.version_info[1], sys.version_info[2])
        require(
            python_check(version)["status"] == "PASS",
            "NPI_UNSUPPORTED_PYTHON",
        )
        assert_source(payload, full_source_identity(_path(payload, "project_root")))
        # Keep machine-readable stdout separate from runner diagnostics.
        with redirect_stdout(sys.stderr):
            result = _fresh(payload) if args.mode == "fresh" else _resume(payload)
        finish(payload, args.mode, outcome="COMPLETE", result=result)
    except Exception as exc:
        finish(payload, args.mode, outcome="FAILED", result={"error_type": type(exc).__name__})
        raise
    sys.stdout.buffer.write(canonical(result))
    return 0


if __name__ == "__main__":
    sys.stderr.write("NPI_WORKER_DIRECT_INVOCATION_DENIED\n")
    raise SystemExit(1)
