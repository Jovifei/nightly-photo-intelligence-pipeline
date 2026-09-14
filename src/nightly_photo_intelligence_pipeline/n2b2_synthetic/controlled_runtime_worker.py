"""Subprocess worker for an already-admitted synthetic runtime execution.

This module is deliberately not an authorization entry point.  The parent
adapter performs every source, quality, lease, and ledger check first, then
passes only the runner configuration over stdin.  The worker reuses the
existing S3/S20 runners and returns process-bound evidence on stdout.
"""

from __future__ import annotations

import argparse
import platform
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from ..engineering.common import canonical, require, strict_json
from . import N2B2RunConfig, load_s3_manifest, load_s20_manifest, run_n2b2
from .ollama_client import ModelIdentity, OllamaClient
from .runtime_identity_revalidation import snapshot_tree
from .s20_bundle import S20_COMPLETE, write_json
from .s20_orchestrator import run_s20

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


def _observation(label: str, identity: ModelIdentity) -> dict[str, object]:
    return {
        "checkpoint": label,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "identity": _identity_record(identity),
    }


def _common(payload: Mapping[str, Any]) -> dict[str, Any]:
    root = _path(payload, "project_root")
    cache_root = _path(payload, "cache_root")
    s20_manifest = _path(payload, "s20_manifest_dir")
    baseline_manifest = _path(payload, "baseline_manifest_dir")
    prior_review = _path(payload, "prior_s20_review_record")
    reviewed_commit = payload.get("reviewed_commit")
    require(isinstance(reviewed_commit, str), "NPI_RUNNER_CONFIGURATION_INVALID")
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
    root = _path(payload, "project_root")
    cache_root = _path(payload, "cache_root")
    s3_manifest = _path(payload, "s3_manifest_dir")
    s20_out = _path(payload, "s20_out")
    s3_out = _path(payload, "s3_out")
    client = OllamaClient()
    observations: list[dict[str, object]] = []

    def observe(label: str) -> None:
        observations.append(_observation(label, client.verify_identity()))

    observe("before_s3")
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
        ollama=client,
    )
    require(s3_result.result == S3_COMPLETE, "NPI_S3_RUNNER_FAILED")
    write_json(s3_out / "validation_summary.json", s3_result.summary)

    observe("before_s20")
    common = _common(payload)
    s20_out.mkdir(parents=True, exist_ok=True)
    s20_summary = run_s20(**common, ollama=client)
    require(s20_summary.get("result") == S20_COMPLETE, "NPI_S20_RUNNER_FAILED")
    return {
        "python_version": platform.python_version(),
        "identity_observations": observations,
        "s3_hard_counts": s3_result.summary.get("hard_counts"),
        "s20_hard_counts": s20_summary.get("hard_counts"),
        "s20_result": s20_summary.get("result"),
    }


def _resume(payload: Mapping[str, Any]) -> dict[str, Any]:
    client = OllamaClient()
    observations = [_observation("before_resume", client.verify_identity())]
    output = _path(payload, "s20_out")
    before = snapshot_tree(output).entries
    common = _common(payload)
    resumed = run_s20(**common, resume=True, ollama=client)
    after = snapshot_tree(output).entries
    observations.append(_observation("after_resume", client.verify_identity()))
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--mode", choices=("fresh", "resume"), required=True)
    args = parser.parse_args(argv)
    payload = strict_json(sys.stdin.buffer.read())
    require(isinstance(payload, Mapping), "NPI_RUNNER_CONFIGURATION_INVALID")
    result = _fresh(payload) if args.mode == "fresh" else _resume(payload)
    sys.stdout.buffer.write(canonical(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - exercised by parent process
        sys.stderr.write(f"{type(exc).__name__}: {exc}\n")
        raise SystemExit(1) from None
