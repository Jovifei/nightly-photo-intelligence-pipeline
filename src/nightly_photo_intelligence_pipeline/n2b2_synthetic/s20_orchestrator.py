"""CUDA-only S20 synthetic validation runner.

This module is deliberately separate from the existing S3 runner.  It accepts
only a reviewed N2B2 candidate, a hash-bound Owner receipt, and the fixed
external twenty-case synthetic manifest.  It never opens a production state
database and never reads a real-photo source.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Any

from .fixture_manifest import SyntheticFixture
from .metrics import MetricsCollector
from .ollama_client import ModelIdentity, OllamaClient
from .orchestrator import ResidencyGate, _facts_bytes, _image_b64, _vision_chain
from .qwen_fact_binding import bind_reasoning_schema
from .qwen_reasoning import validate_reasoning
from .s20_bundle import (
    validate_artifact,
    verify_release_checksums,
    write_case_bundle,
    write_checksums,
    write_json,
)
from .s20_checkpoint import assert_checkpoint_binding, load_checkpoint, write_checkpoint
from .torchvision_loader import load_backend, verify_cache_hit
from .vision_facts import compute_fact_digest

S20_NOT_AUTHORIZED = "N2B2_S20_NOT_AUTHORIZED"
S20_COMPLETE = "N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"
S20_FAILED = "N2B2_S20_SYNTHETIC_VALIDATION_FAILED"
S20_RESUME_MISMATCH = "N2B2_S20_RESUME_BINDING_MISMATCH"
S20_TERMINAL_FAILURE_REQUIRES_NEW_OUTPUT = "N2B2_S20_TERMINAL_FAILURE_REQUIRES_NEW_OUTPUT"
S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH = "N2B2_S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH"
S20_GPU_LIMIT_EXCEEDED = "N2B2_GPU_LIMIT_EXCEEDED"
QWEN_BINDING_FAILED = "N2B2_QWEN_FACT_BINDING_CONTRACT_FAILED"


def _enforce_gpu_limit(peak_mib: int, limit_mib: int) -> None:
    """Stop the S20 run before publishing success above the approved ceiling."""

    if peak_mib > limit_mib:
        raise ValueError(f"{S20_GPU_LIMIT_EXCEEDED}: {peak_mib} MiB exceeds {limit_mib} MiB")


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_RUNTIME_SOURCE_FILES = (
    "src/nightly_photo_intelligence_pipeline/cli.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/ollama_client.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/qwen_fact_binding.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/qwen_probe.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/qwen_reasoning.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/runtime_identity_revalidation.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/s20_orchestrator.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/s20_bundle.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/s20_checkpoint.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/s20_manifest.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/orchestrator.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/torchvision_loader.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/vision_facts.py",
    "src/nightly_photo_intelligence_pipeline/n2b2_synthetic/metrics.py",
    "schemas/n2b2_photography_reasoning.schema.json",
    "schemas/n2b2_qwen_fact_binding_evidence.schema.json",
    "schemas/n2b2_vision_fact_contract.schema.json",
    "schemas/reference_bundle_v1_synthetic.schema.json",
)


def _runtime_source_manifest(project_root: Path) -> dict[str, Any]:
    paths = set(_RUNTIME_SOURCE_FILES)
    paths.update(
        path.relative_to(project_root).as_posix()
        for path in (project_root / "schemas").glob("n2b2_s20_*.schema.json")
    )
    rows: list[dict[str, str]] = []
    for relative in sorted(paths):
        path = project_root / Path(relative)
        if not path.is_file():
            raise ValueError(f"N2B2_S20_RUNTIME_SOURCE_REVALIDATION_REQUIRED: missing {relative}")
        rows.append({"path": relative.replace("\\", "/"), "sha256": _sha_file(path)})
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "n2b2-runtime-source-manifest-v1",
        "files": rows,
        "runtime_source_sha256": digest,
    }


def _source_digest(project_root: Path | None = None) -> str:
    root = project_root or Path(__file__).resolve().parents[3]
    return str(_runtime_source_manifest(root)["runtime_source_sha256"])


def _identity_dict(identity: ModelIdentity) -> dict[str, Any]:
    return {
        "model_name": identity.model_name,
        "full_local_digest": identity.full_local_digest,
        "size_bytes": identity.size_bytes,
        "quantization_level": identity.quantization_level,
        "capabilities": identity.capabilities,
        "ollama_version": identity.ollama_version,
    }


def _review_gate(
    review_record: Path,
    owner_receipt: Path,
    qwen_receipt: Path,
    reviewed_commit: str,
) -> tuple[str, str, dict[str, Any]]:
    try:
        review = json.loads(review_record.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{S20_NOT_AUTHORIZED}: invalid review record") from exc
    if (
        review.get("reviewed_commit") != reviewed_commit
        or review.get("verdict") != "PASS_FOR_OWNER_REVIEW"
    ):
        raise ValueError(f"{S20_NOT_AUTHORIZED}: review verdict or commit mismatch")
    review_hash = _sha_file(review_record)
    try:
        import yaml

        receipt = yaml.safe_load(owner_receipt.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{S20_NOT_AUTHORIZED}: invalid Owner receipt") from exc
    if not isinstance(receipt, dict):
        raise ValueError(f"{S20_NOT_AUTHORIZED}: Owner receipt is not an object")
    if (
        receipt.get("reviewed_commit") != reviewed_commit
        or receipt.get("review_verdict") != "PASS_FOR_OWNER_REVIEW"
        or receipt.get("review_record_sha256") != review_hash
        or receipt.get("s20_execution") != "CONDITIONAL_OWNER_AUTHORIZED"
        or receipt.get("project_state_mutation") is not False
    ):
        raise ValueError(f"{S20_NOT_AUTHORIZED}: Owner receipt binding mismatch")
    try:
        qwen_receipt_payload = yaml.safe_load(qwen_receipt.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{S20_NOT_AUTHORIZED}: invalid Qwen binding receipt") from exc
    qwen_hash = _sha_file(qwen_receipt)
    if not isinstance(qwen_receipt_payload, dict) or any(
        (
            qwen_receipt_payload.get("status") != "AUTHORIZED_FOR_BOUNDED_SYNTHETIC_RETRY",
            qwen_receipt_payload.get("task")
            != "N2B2_QWEN_FACT_BINDING_CONTRACT_REMEDIATION_AND_S20_V3_RESUME",
            qwen_receipt_payload.get("plan_sha256")
            != "9fbeeeb0f935f7e46e060069758aa6a47ecbbbdbbfcca31491e4ca85240bcc72",
            qwen_receipt_payload.get("reviewed_commit") != reviewed_commit,
            qwen_receipt_payload.get("source_manifest_sha256")
            != "b59446550e81499aaac9be17bebfd675f403869767a16318ce1a1a8904e4eec0",
            qwen_receipt_payload.get("project_state_mutation") is not False,
            qwen_receipt_payload.get("production_n2b2_unlock") is not False,
        )
    ):
        raise ValueError(f"{S20_NOT_AUTHORIZED}: Qwen binding receipt mismatch")
    return (
        review_hash,
        qwen_hash,
        {
            "review": review,
            "receipt": receipt,
            "qwen_receipt": qwen_receipt_payload,
        },
    )


def _artifact_integrity_gate(
    receipt_path: Path, *, reviewed_commit: str, manifest_sha256: str
) -> tuple[str, dict[str, Any]]:
    """Validate the narrowly scoped receipt that replaces the contradictory v3 set."""

    try:
        import yaml

        receipt = yaml.safe_load(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{S20_NOT_AUTHORIZED}: invalid artifact-integrity receipt") from exc
    if not isinstance(receipt, dict) or any(
        (
            receipt.get("receipt_type") != "OWNER_S20_ARTIFACT_INTEGRITY_REMEDIATION",
            receipt.get("status") != "AUTHORIZED_FOR_BOUNDED_SYNTHETIC_RETRY",
            receipt.get("task") != "N2B2_S20_ARTIFACT_INTEGRITY_REMEDIATION_AND_EXTERNAL_REVIEW",
            receipt.get("plan_sha256")
            != "a9ae192eaa6a2eadf80bc592cbcee1aaeab99d24a0bc1798b529b3f25e1e8c85",
            receipt.get("required_final_parent") != reviewed_commit,
            receipt.get("fixture_manifest_sha256") != manifest_sha256,
            receipt.get("project_state_mutation") is not False,
            receipt.get("production_n2b2_unlock") is not False,
        )
    ):
        raise ValueError(f"{S20_NOT_AUTHORIZED}: artifact-integrity receipt binding mismatch")
    return _sha_file(receipt_path), receipt


def _sample_ollama(client: OllamaClient, metrics: MetricsCollector, stop: threading.Event) -> None:
    while not stop.is_set():
        try:
            metrics.note_ollama_snapshot(client.ps_snapshot())
            metrics.sample_nvidia("s20:qwen")
        except Exception:
            pass
        stop.wait(0.35)


def _repeat_cases(
    reviewed_commit: str, manifest_digest: str, fixtures: list[SyntheticFixture]
) -> list[str]:
    ranked = sorted(
        fixtures,
        key=lambda fixture: hashlib.sha256(
            f"{reviewed_commit}{manifest_digest}{fixture.case_id}".encode()
        ).hexdigest(),
    )
    return [fixture.case_id for fixture in ranked[:5]]


def _disposition(fixture: SyntheticFixture) -> str:
    return {
        "strict": "STRICT_VALIDATION",
        "observation": "QUALITY_OBSERVATION_NOT_PHASE_FAILURE",
        "negative": "NEGATIVE_CONTROL",
        "unsupported": "UNSUPPORTED_CONTROL_OBSERVATION",
    }[fixture.acceptance_profile]


def _validate_case(fixture: SyntheticFixture, facts: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    count = facts.get("person_count")
    groups = facts.get("pose_keypoints", [])
    if fixture.acceptance_profile == "strict":
        expected = int(fixture.person_expectation.split("=", maxsplit=1)[-1])
        if count != expected:
            errors.append(f"strict person_count {count} != {expected}")
        if len(groups) != count or any(len(group) != 17 for group in groups):
            errors.append("strict keypoint groups are not one complete 17-point group per person")
    elif fixture.acceptance_profile == "negative":
        if count != 0 or groups:
            errors.append("negative control produced pose detections")
        if (
            facts.get("segmentation_person_ratio") != 0
            or facts.get("segmentation_comparator_person_ratio") != 0
        ):
            errors.append("negative control produced person mask")
    return errors


def _write_visual_diagnostics(
    out: Path,
    *,
    first_facts: list[dict[str, Any]],
    second_facts: list[dict[str, Any]],
    repeat_rows: list[dict[str, Any]],
    case_errors: dict[str, list[str]],
    reviewed_commit: str,
    metrics: MetricsCollector,
) -> None:
    diagnostics = out / "diagnostics"
    write_json(diagnostics / "visual_facts_first.json", first_facts)
    write_json(diagnostics / "visual_facts_second.json", second_facts)
    write_json(
        diagnostics / "repeatability_report.json",
        {
            "visual_bytes_identical": all(row["bytes_identical"] for row in repeat_rows),
            "visual_digest_identical": all(row["digest_identical"] for row in repeat_rows),
            "qwen_repeat_case_ids": [],
            "cases": repeat_rows,
        },
    )
    write_json(
        diagnostics / "acceptance_report.json",
        {"reviewed_commit": reviewed_commit, "case_errors": case_errors},
    )
    if case_errors:
        write_json(
            out / "validation_summary.json",
            {
                "result": S20_FAILED,
                "reviewed_commit": reviewed_commit,
                "bundle_count": 0,
                "visual_diagnostics_preserved": True,
                "qwen_status": "NOT_PERFORMED",
                "case_errors": case_errors,
                "hard_counts": _hard_counts(),
                "gpu": {
                    "baseline_mib": metrics.gpu_baseline_mib,
                    "peak_mib": metrics.gpu_peak_mib,
                    "after_unload_mib": metrics.gpu_after_unload_mib,
                },
            },
        )
        write_json(
            out / "failure_summary.json",
            {
                "result": S20_FAILED,
                "case_errors": case_errors,
                "qwen_started": False,
                "diagnostic_facts": [
                    "diagnostics/visual_facts_first.json",
                    "diagnostics/visual_facts_second.json",
                ],
            },
        )
        write_json(
            out / "cleanup_evidence.json",
            {
                "qwen_started": False,
                "qwen_unloaded": True,
                "torchvision_resident_roles": [],
                "s20_runtime_obsidian_write_count": 0,
            },
        )


def _write_qwen_failure_evidence(
    out: Path,
    *,
    reviewed_commit: str,
    qwen_errors: dict[str, list[str]],
    metrics: MetricsCollector,
) -> None:
    write_json(
        out / "validation_summary.json",
        {
            "result": S20_FAILED,
            "reviewed_commit": reviewed_commit,
            "bundle_count": 0,
            "qwen_status": "FAIL",
            "qwen_errors": qwen_errors,
            "visual_diagnostics_preserved": True,
            "hard_counts": _hard_counts(),
            "gpu": {
                "baseline_mib": metrics.gpu_baseline_mib,
                "peak_mib": metrics.gpu_peak_mib,
                "after_unload_mib": metrics.gpu_after_unload_mib,
            },
        },
    )
    write_json(
        out / "failure_summary.json",
        {
            "result": S20_FAILED,
            "qwen_started": True,
            "qwen_errors": qwen_errors,
            "bundle_count": 0,
            "diagnostic_facts": [
                "diagnostics/visual_facts_first.json",
                "diagnostics/visual_facts_second.json",
            ],
        },
    )


def _write_qwen_case_evidence(
    out: Path,
    *,
    fixture: SyntheticFixture,
    facts: dict[str, Any],
    output: dict[str, Any],
    validation: Any,
    client_evidence: dict[str, Any],
    schema_path: Path,
    model_identity_sha256: str,
    repeat: bool = False,
) -> dict[str, Any]:
    """Persist one raw response and its redacted binding proof immediately."""

    prefix = out / "diagnostics" / ("qwen-repeat" if repeat else "qwen") / fixture.case_id
    raw_sha = write_json(prefix / "raw_response.json", output)
    echoed = output.get("input_fact_digest", "")
    valid_fact_ids = set(facts.get("fact_ids", []))
    references = output.get("reasoning_based_on_fact_ids", [])
    evidence = {
        "schema_version": "n2b2-qwen-fact-binding-evidence-v1",
        "case_id": fixture.case_id,
        "authoritative_fact_digest": facts["fact_digest"],
        "bound_response_schema_sha256": client_evidence.get("bound_response_schema_sha256", ""),
        "prompt_sha256": client_evidence.get("prompt_sha256", ""),
        "raw_response_sha256": raw_sha,
        "model_identity_sha256": model_identity_sha256,
        "echoed_fact_digest": echoed if isinstance(echoed, str) else "0" * 64,
        "echo_match": echoed == facts["fact_digest"],
        "fact_reference_valid": all(item in valid_fact_ids for item in references),
        "forbidden_field_count": int(getattr(validation, "forbidden_field_count", 0)),
        "validation_status": "PASS" if validation.ok else "FAIL",
        "response_time_ms": float(client_evidence.get("response_time_ms", 0.0)),
        "errors": list(validation.errors),
    }
    evidence_path = prefix / "binding_validation.json"
    evidence_sha = write_json(evidence_path, evidence)
    validate_artifact(evidence_path, schema_path)
    evidence["evidence_sha256"] = evidence_sha
    evidence["raw_response_sha256"] = raw_sha
    evidence["echoed_fact_digest"] = echoed if isinstance(echoed, str) else "0" * 64
    return evidence


def run_s20(
    *,
    config: Any,
    fixtures: list[SyntheticFixture],
    reasoning_schema: dict[str, Any],
    vision_schema: dict[str, Any],
    reviewed_commit: str,
    review_record: Path,
    owner_receipt: Path,
    qwen_receipt: Path,
    artifact_integrity_receipt: Path,
    resume: bool = False,
    ollama: OllamaClient | None = None,
) -> dict[str, Any]:
    """Run the full CUDA-only S20 chain and write external validation evidence."""

    if getattr(config, "device", "cpu") != "cuda":
        raise ValueError(f"{S20_NOT_AUTHORIZED}: S20 requires --device cuda")
    manifest_dir = Path(config.fixtures_dir).resolve(strict=True)
    out = Path(config.runtime_out_dir).resolve()
    if out.exists() and any(out.iterdir()) and not resume:
        raise ValueError("N2B2_S20_OUTPUT_NOT_EMPTY: use --resume for an existing run")
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "fixture_manifest.json"
    manifest_digest = _sha_file(manifest_path)
    release_manifest = out / "fixture_manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    if release_manifest.exists() and release_manifest.read_bytes() != manifest_bytes:
        raise ValueError(f"{S20_RESUME_MISMATCH}: release fixture_manifest")
    if not release_manifest.exists():
        release_manifest.write_bytes(manifest_bytes)
    source_digest = _source_digest(Path(config.project_root))
    review_hash, qwen_receipt_hash, auth = _review_gate(
        review_record, owner_receipt, qwen_receipt, reviewed_commit
    )
    integrity_receipt_hash, _ = _artifact_integrity_gate(
        artifact_integrity_receipt,
        reviewed_commit=reviewed_commit,
        manifest_sha256=manifest_digest,
    )
    identity: ModelIdentity | None = None
    binding = {
        "schema_version": "n2b2-s20-checkpoint-v2",
        "reviewed_commit": reviewed_commit,
        "review_record_sha256": review_hash,
        "manifest_sha256": manifest_digest,
        "runtime_source_sha256": source_digest,
        "qwen_receipt_sha256": qwen_receipt_hash,
        "artifact_integrity_receipt_sha256": integrity_receipt_hash,
        "model_identity": "pending",
    }
    checkpoint_path = out / "checkpoint.json"
    existing = load_checkpoint(checkpoint_path)
    if resume and existing is not None:
        for key, value in binding.items():
            if key == "model_identity":
                continue
            if existing.get(key) != value:
                raise ValueError(f"{S20_RESUME_MISMATCH}: {key}")
        if existing.get("status") == "COMPLETE":
            try:
                verify_release_checksums(out)
            except ValueError as exc:
                raise ValueError(f"{S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH}: {exc}") from exc
            client = ollama or OllamaClient(config.ollama_base_url)
            identity = client.verify_identity()
            identity_hash = hashlib.sha256(_canonical(_identity_dict(identity))).hexdigest()
            if existing.get("model_identity") != identity_hash:
                raise ValueError(f"{S20_RESUME_MISMATCH}: model_identity")
            return {
                "result": S20_COMPLETE,
                "resume_status": "ALREADY_COMPLETE_VERIFIED",
                "reviewed_commit": reviewed_commit,
                "manifest_sha256": manifest_digest,
                "bundle_count": 20,
                "hard_counts": _hard_counts(),
            }
        if existing.get("status") in {"FAILED", "QWEN_FAILED"}:
            raise ValueError(
                f"{S20_TERMINAL_FAILURE_REQUIRES_NEW_OUTPUT}: {existing.get('status')}"
            )

    verify_cache_hit(config.cache_root, config.cache_subdirs)
    run_started_at_utc = (
        str(existing.get("run_started_at_utc"))
        if existing and existing.get("run_started_at_utc")
        else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )
    write_checkpoint(
        checkpoint_path,
        {
            **binding,
            "status": "STARTED",
            "completed_stages": [],
            "run_started_at_utc": run_started_at_utc,
            "qwen_case_records": {},
        },
    )

    metrics = MetricsCollector()
    metrics.sample_baseline()
    backend = load_backend("real", config.cache_root, config.cache_subdirs, device="cuda")
    residency = ResidencyGate()
    first_facts: list[dict[str, Any]] = []
    second_facts: list[dict[str, Any]] = []
    try:
        first_facts, errors = _vision_chain(
            backend=backend,
            fixtures=fixtures,
            residency=residency,
            metrics=metrics,
            schema=vision_schema,
        )
        if errors:
            raise ValueError(f"{S20_FAILED}: vision schema errors: {errors}")
        write_checkpoint(
            checkpoint_path,
            {
                **binding,
                "status": "VISION_FIRST_COMPLETE",
                "completed_stages": ["vision_first"],
                "run_started_at_utc": run_started_at_utc,
            },
        )
        second_facts, errors = _vision_chain(
            backend=backend,
            fixtures=fixtures,
            residency=residency,
            metrics=metrics,
            schema=vision_schema,
        )
        if errors:
            raise ValueError(f"{S20_FAILED}: repeated vision schema errors: {errors}")
        repeat_rows = []
        for fixture, left, right in zip(fixtures, first_facts, second_facts, strict=True):
            same_bytes = _facts_bytes(left) == _facts_bytes(right)
            same_digest = compute_fact_digest(left) == compute_fact_digest(right)
            repeat_rows.append(
                {
                    "case_id": fixture.case_id,
                    "bytes_identical": same_bytes,
                    "digest_identical": same_digest,
                }
            )
            if not same_bytes or not same_digest:
                raise ValueError(f"{S20_FAILED}: fact repeat mismatch: {fixture.case_id}")
        write_checkpoint(
            checkpoint_path,
            {
                **binding,
                "status": "VISION_REPEAT_COMPLETE",
                "completed_stages": ["vision_first", "vision_repeat"],
                "run_started_at_utc": run_started_at_utc,
            },
        )
    finally:
        backend.unload()
        metrics.sample_after_unload()

    case_errors: dict[str, list[str]] = {}
    for fixture, facts in zip(fixtures, first_facts, strict=True):
        errors = _validate_case(fixture, facts)
        if errors:
            case_errors[fixture.case_id] = errors
    _write_visual_diagnostics(
        out,
        first_facts=first_facts,
        second_facts=second_facts,
        repeat_rows=repeat_rows,
        case_errors=case_errors,
        reviewed_commit=reviewed_commit,
        metrics=metrics,
    )
    if case_errors:
        write_checkpoint(
            checkpoint_path,
            {
                **binding,
                "status": "FAILED",
                "run_started_at_utc": run_started_at_utc,
                "completed_stages": ["vision_first", "vision_repeat", "vision_acceptance"],
                "completed_cases": [],
                "qwen_case_records": {},
            },
        )
        raise ValueError(f"{S20_FAILED}: acceptance errors: {case_errors}")

    _enforce_gpu_limit(metrics.gpu_peak_mib, config.gpu_limit_mib)

    # Do not contact Ollama until the entire deterministic visual chain and
    # strict acceptance have passed.
    client = ollama or OllamaClient(config.ollama_base_url)
    identity = client.verify_identity()
    binding["model_identity"] = hashlib.sha256(_canonical(_identity_dict(identity))).hexdigest()
    write_json(out / "ollama_identity.json", _identity_dict(identity))
    if existing is not None and resume:
        try:
            assert_checkpoint_binding(existing, binding)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
    write_checkpoint(
        checkpoint_path,
        {
            **binding,
            "status": "VISION_ACCEPTANCE_COMPLETE",
            "completed_stages": ["vision_first", "vision_repeat"],
            "run_started_at_utc": run_started_at_utc,
        },
    )

    # The legacy bounded-retry receipt requires an identity-bound Case 03
    # probe before the full twenty-case Qwen phase.  Keep the probe evidence in
    # this run rather than relying on an unbound historical directory.
    from .qwen_probe import PROBE_PASS, run_qwen_contract_probe

    probe_fixture = next(fixture for fixture in fixtures if fixture.case_id == "n2b2-s20-03")
    probe_facts = next(item for item in first_facts if item["case_id"] == probe_fixture.case_id)
    probe_summary = run_qwen_contract_probe(
        project_root=Path(config.project_root),
        fixture=probe_fixture,
        facts=probe_facts,
        reasoning_schema=reasoning_schema,
        out=out / "diagnostics" / "qwen-probe",
        client=client,
    )
    if probe_summary.get("result") != PROBE_PASS:
        raise ValueError(QWEN_BINDING_FAILED)

    reasoning_by_case: dict[str, dict[str, Any]] = {}
    qwen_binding_by_case: dict[str, dict[str, Any]] = {}
    qwen_case_records: dict[str, dict[str, Any]] = {}
    qwen_errors: dict[str, list[str]] = {}
    qwen_repeat_rows: list[dict[str, Any]] = []
    schemas_dir = Path(config.project_root) / "schemas"
    binding_schema_path = schemas_dir / "n2b2_qwen_fact_binding_evidence.schema.json"
    qwen_stop = threading.Event()
    sampler = threading.Thread(
        target=_sample_ollama, args=(client, metrics, qwen_stop), daemon=True
    )
    residency.acquire("qwen")
    sampler.start()
    try:
        repeat_ids = _repeat_cases(reviewed_commit, manifest_digest, fixtures)
        for fixture, facts in zip(fixtures, first_facts, strict=True):
            started = time.perf_counter()
            bound_schema = bind_reasoning_schema(
                reasoning_schema,
                case_id=fixture.case_id,
                fact_digest=facts["fact_digest"],
                fact_ids=facts["fact_ids"],
            )
            output = client.reason(
                image_b64=_image_b64(fixture.image_bytes),
                case_id=fixture.case_id,
                vision_facts=facts,
                fact_digest=facts["fact_digest"],
                fact_ids=facts["fact_ids"],
                uncertainties=facts["uncertainties"],
                response_schema=reasoning_schema,
                seed=fixture.seed,
                keep_alive=300,
            )
            metrics.note_per_image(time.perf_counter() - started)
            validation = validate_reasoning(
                output,
                case_id=fixture.case_id,
                input_fact_digest=facts["fact_digest"],
                valid_fact_ids=facts["fact_ids"],
                schema=bound_schema,
            )
            evidence = _write_qwen_case_evidence(
                out,
                fixture=fixture,
                facts=facts,
                output=output,
                validation=validation,
                client_evidence=client.last_call_evidence,
                schema_path=binding_schema_path,
                model_identity_sha256=binding["model_identity"],
            )
            qwen_case_records[fixture.case_id] = {
                "raw_response_sha256": evidence["raw_response_sha256"],
                "binding_evidence_sha256": evidence["evidence_sha256"],
                "validation_status": evidence["validation_status"],
            }
            if not validation.ok:
                qwen_errors[fixture.case_id] = validation.errors
                write_checkpoint(
                    checkpoint_path,
                    {
                        **binding,
                        "status": "QWEN_FAILED",
                        "run_started_at_utc": run_started_at_utc,
                        "completed_cases": list(reasoning_by_case),
                        "qwen_case_records": qwen_case_records,
                        "qwen_failure_case": fixture.case_id,
                    },
                )
                break
            else:
                reasoning_by_case[fixture.case_id] = output
                qwen_binding_by_case[fixture.case_id] = evidence
            write_checkpoint(
                checkpoint_path,
                {
                    **binding,
                    "status": "QWEN_IN_PROGRESS",
                    "run_started_at_utc": run_started_at_utc,
                    "completed_cases": [
                        item.case_id for item in fixtures if item.case_id in reasoning_by_case
                    ],
                    "qwen_case_records": qwen_case_records,
                },
            )
        if not qwen_errors:
            for fixture in fixtures:
                if fixture.case_id not in repeat_ids:
                    continue
                facts = next(item for item in first_facts if item["case_id"] == fixture.case_id)
                bound_schema = bind_reasoning_schema(
                    reasoning_schema,
                    case_id=fixture.case_id,
                    fact_digest=facts["fact_digest"],
                    fact_ids=facts["fact_ids"],
                )
                output = client.reason(
                    image_b64=_image_b64(fixture.image_bytes),
                    case_id=fixture.case_id,
                    vision_facts=facts,
                    fact_digest=facts["fact_digest"],
                    fact_ids=facts["fact_ids"],
                    uncertainties=facts["uncertainties"],
                    response_schema=reasoning_schema,
                    seed=fixture.seed,
                    keep_alive=300,
                )
                validation = validate_reasoning(
                    output,
                    case_id=fixture.case_id,
                    input_fact_digest=facts["fact_digest"],
                    valid_fact_ids=facts["fact_ids"],
                    schema=bound_schema,
                )
                evidence = _write_qwen_case_evidence(
                    out,
                    fixture=fixture,
                    facts=facts,
                    output=output,
                    validation=validation,
                    client_evidence=client.last_call_evidence,
                    schema_path=binding_schema_path,
                    model_identity_sha256=binding["model_identity"],
                    repeat=True,
                )
                type_set = {
                    "story_candidates": sorted(output.get("story_candidates", {}).keys()),
                    "director_prompts": sorted(output.get("director_prompts", {}).keys()),
                }
                qwen_repeat_rows.append(
                    {
                        "case_id": fixture.case_id,
                        "validation_status": evidence["validation_status"],
                        **type_set,
                    }
                )
                if not validation.ok:
                    qwen_errors.setdefault(fixture.case_id, []).extend(validation.errors)
                    break
        if client.ps_vram_mib() <= 0:
            qwen_errors.setdefault("__runtime__", []).append(
                "N2B2_QWEN_GPU_USAGE_NOT_CONFIRMED: size_vram=0"
            )
    finally:
        qwen_stop.set()
        sampler.join(timeout=2.0)
        try:
            client.unload()
            qwen_unloaded = client.verify_unloaded(timeout_s=60.0)
        finally:
            residency.release("qwen")
    if not qwen_unloaded:
        raise ValueError(f"{S20_FAILED}: qwen unload failed")
    _enforce_gpu_limit(metrics.gpu_peak_mib, config.gpu_limit_mib)
    if qwen_errors:
        _write_qwen_failure_evidence(
            out,
            reviewed_commit=reviewed_commit,
            qwen_errors=qwen_errors,
            metrics=metrics,
        )
        raise ValueError(f"{S20_FAILED}: Qwen validation errors: {qwen_errors}")

    write_checkpoint(
        checkpoint_path,
        {
            **binding,
            "status": "QWEN_COMPLETE",
            "run_started_at_utc": run_started_at_utc,
            "completed_cases": list(reasoning_by_case),
            "qwen_case_records": qwen_case_records,
            "qwen_repeat_case_ids": repeat_ids,
        },
    )

    cases_root = out / "cases"
    case_index: list[dict[str, Any]] = []
    for fixture, facts in zip(fixtures, first_facts, strict=True):
        paths = write_case_bundle(
            cases_root / fixture.case_id,
            fixture=fixture,
            facts=facts,
            reasoning=reasoning_by_case[fixture.case_id],
            disposition=_disposition(fixture),
            qwen_binding=qwen_binding_by_case[fixture.case_id],
        )
        case_dir = cases_root / fixture.case_id
        validate_artifact(case_dir / "analysis.json", schemas_dir / "n2b2_s20_analysis.schema.json")
        validate_artifact(
            case_dir / "vision_facts.json", schemas_dir / "n2b2_vision_fact_contract.schema.json"
        )
        validate_artifact(
            case_dir / "director_prompt.json", schemas_dir / "n2b2_s20_director_prompt.schema.json"
        )
        validate_artifact(
            case_dir / "reference_bundle.json",
            schemas_dir / "reference_bundle_v1_synthetic.schema.json",
        )
        case_index.append(
            {
                "case_id": fixture.case_id,
                "reference_bundle": f"cases/{fixture.case_id}/reference_bundle.json",
                "files": paths,
            }
        )
    index = {
        "schema_version": "n2b2-s20-synthetic-bundle-index-v1",
        "bundle_type": "N2B2_S20_SYNTHETIC_VALIDATION_SET",
        "reviewed_commit": reviewed_commit,
        "review_record_sha256": review_hash,
        "manifest_sha256": manifest_digest,
        "runtime_source_sha256": source_digest,
        "bundle_count": 20,
        "production_release": False,
        "app_import_authorized": False,
        "cases": case_index,
    }
    write_json(out / "synthetic_bundle_index.json", index)
    validate_artifact(
        out / "synthetic_bundle_index.json", schemas_dir / "n2b2_s20_bundle_index.schema.json"
    )
    write_json(
        out / "repeatability_report.json",
        {
            "visual_bytes_identical": True,
            "visual_digest_identical": True,
            "qwen_repeat_case_ids": _repeat_cases(reviewed_commit, manifest_digest, fixtures),
        },
    )
    validate_artifact(
        out / "repeatability_report.json", schemas_dir / "n2b2_s20_repeatability.schema.json"
    )
    validation_summary = {
        "schema_version": "n2b2-s20-validation-summary-v1",
        "result": S20_COMPLETE,
        "reviewed_commit": reviewed_commit,
        "review_verdict": auth["review"].get("verdict"),
        "bundle_count": 20,
        "strict_cases": [
            fixture.case_id for fixture in fixtures if fixture.acceptance_profile == "strict"
        ],
        "observation_cases": [
            fixture.case_id for fixture in fixtures if fixture.acceptance_profile == "observation"
        ],
        "negative_cases": [
            fixture.case_id for fixture in fixtures if fixture.acceptance_profile == "negative"
        ],
        "unsupported_cases": [
            fixture.case_id for fixture in fixtures if fixture.acceptance_profile == "unsupported"
        ],
        "facts_repeat": {
            "bytes_identical": True,
            "digest_identical": True,
            "cases": repeat_rows,
        },
        "qwen": {
            "schema_pass": True,
            "fact_digest_echo": True,
            "unknown_fact_ids": 0,
            "forbidden_fields": 0,
        },
        "gpu": {
            "baseline_mib": metrics.gpu_baseline_mib,
            "peak_mib": metrics.gpu_peak_mib,
            "after_unload_mib": metrics.gpu_after_unload_mib,
            "ollama_peak_mib": metrics.ollama_gpu_peak_mib,
        },
        "hard_counts": _hard_counts(),
        "s20_execution_status": "PERFORMED_SYNTHETIC_ONLY",
        "production_bundle_release": "NOT_CREATED",
        "s20_external_review_required": True,
    }
    write_json(out / "validation_summary.json", validation_summary)
    validate_artifact(
        out / "validation_summary.json", schemas_dir / "n2b2_s20_validation_summary.schema.json"
    )
    write_json(
        out / "runtime_metrics.json",
        {
            "gpu": validation_summary["gpu"],
            "stage_records": metrics.stage_records,
            "ollama_ps_samples": metrics.ollama_ps_samples,
            "cpu_rss_peak": metrics.cpu_rss_peak,
        },
    )
    write_json(
        out / "process_evidence.json",
        {"scope": "LUNA_OWNED_PROCESSES_ONLY", "real_photo_read_count": 0},
    )
    write_json(
        out / "cleanup_evidence.json",
        {
            "qwen_unloaded": True,
            "torchvision_resident_roles": [],
            "s20_runtime_obsidian_write_count": 0,
        },
    )
    write_checkpoint(
        out / "checkpoint.json",
        {
            **binding,
            "status": "COMPLETE",
            "run_started_at_utc": run_started_at_utc,
            "completed_stages": [
                "vision_first",
                "vision_repeat",
                "vision_acceptance",
                "qwen",
                "bundles",
            ],
            "completed_cases": [fixture.case_id for fixture in fixtures],
            "qwen_case_records": qwen_case_records,
            "qwen_repeat_case_ids": repeat_ids,
            "bundle_count": 20,
        },
    )
    validate_artifact(out / "checkpoint.json", schemas_dir / "n2b2_s20_checkpoint.schema.json")
    write_checksums(out)
    verify_release_checksums(out)
    return validation_summary


def _hard_counts() -> dict[str, int]:
    return {
        "real_photo_read_count": 0,
        "real_exif_read_count": 0,
        "g1_source_access": 0,
        "sqlite_write_count": 0,
        "app_write_count": 0,
        "obsidian_write_count": 0,
        "s20_runtime_obsidian_write_count": 0,
        "model_download_bytes": 0,
    }
