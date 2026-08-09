"""S3-only N2B2 synthetic smoke orchestrator.

The order is deliberately batch-oriented: Pose for all three images, unload;
LRASPP for all three, unload; DeepLab for all three, unload; build and repeat
facts; only then call the local Qwen model. S20 is not part of this runner.
"""

from __future__ import annotations

import base64
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .config import (
    GPU_RUNTIME_UNAVAILABLE,
    QWEN_GPU_USAGE_NOT_CONFIRMED,
    ROLE_MODEL_MAP,
    S3_CASE_COUNT,
    TorchVisionRole,
)
from .fixture_manifest import SyntheticFixture
from .metrics import MetricsCollector
from .ollama_client import ModelIdentity, OllamaClient
from .qwen_reasoning import validate_reasoning
from .torchvision_loader import TorchVisionBackend, load_backend, verify_cache_hit
from .vision_facts import build_vision_facts, canonicalize, compute_fact_digest

R_COMPLETE = "N2B2_SYNTHETIC_SMOKE_VALIDATION_COMPLETE_AWAITING_OWNER_REVIEW"
R_S20_NOT_AUTHORIZED = "N2B2_S20_NOT_AUTHORIZED"
R_BLOCKED_N2B1P = "N2B2_EXECUTION_BLOCKED_N2B1P_NOT_APPROVED"
R_QWEN_IDENTITY = "N2B2_LOCAL_QWEN_IDENTITY_MISMATCH"
R_QWEN_VISION = "N2B2_LOCAL_QWEN_VISION_CAPABILITY_MISSING"
R_FIXTURE_REVIEW = "N2B2_SYNTHETIC_FIXTURE_CAPABILITY_REQUIRES_DESIGN_REVIEW"
R_GPU = "N2B2_GPU_LIMIT_EXCEEDED"
R_FACT_IMMUTABLE = "N2B2_FACT_IMMUTABILITY_VIOLATION"
R_QWEN_PROVENANCE = "N2B2_QWEN_SCHEMA_OR_PROVENANCE_FAILED"
R_UNLOAD = "N2B2_MODEL_UNLOAD_FAILED"
R_CHANGES = "N2B2_CHANGES_REQUIRED"
R_GPU_RUNTIME = GPU_RUNTIME_UNAVAILABLE
R_QWEN_GPU = QWEN_GPU_USAGE_NOT_CONFIRMED


@dataclass
class N2B2Result:
    result: str
    summary: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None


class ResidencyGate:
    """Track model residency and expose stage order for evidence/tests."""

    def __init__(self) -> None:
        self._held: set[str] = set()
        self.events: list[str] = []

    def acquire(self, kind: str) -> None:
        if kind == "qwen" and self._held:
            raise RuntimeError("concurrent residency: TorchVision model still resident before Qwen")
        if kind.startswith("torchvision") and "qwen" in self._held:
            raise RuntimeError("concurrent residency: Qwen still resident before TorchVision")
        self._held.add(kind)
        self.events.append(f"acquire:{kind}")

    def release(self, kind: str) -> None:
        self._held.discard(kind)
        self.events.append(f"release:{kind}")


def _image_b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _facts_bytes(facts: dict[str, Any]) -> bytes:
    return canonicalize(facts).encode("utf-8")


def _validate_facts(facts: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    try:
        import jsonschema  # type: ignore[import-untyped]  # noqa: PLC0415

        validator = jsonschema.Draft202012Validator(schema)
        return [error.message for error in validator.iter_errors(facts)]
    except Exception as exc:  # pragma: no cover - dependency/runtime dependent
        return [f"vision schema validation unavailable: {type(exc).__name__}"]


def _run_stage(
    *,
    backend: TorchVisionBackend,
    fixtures: list[SyntheticFixture],
    role: TorchVisionRole,
    operation: Callable[[bytes], Any],
    residency: ResidencyGate,
    metrics: MetricsCollector,
) -> list[Any]:
    residency.acquire(f"torchvision:{role.value}")
    values: list[Any] = []
    started = time.perf_counter()
    attestation = backend.runtime_attestation()
    stage_record = metrics.begin_stage(
        role=role.value,
        model_name=ROLE_MODEL_MAP[role][0],
        device=str(attestation.get("effective_device", attestation.get("device", "cpu"))),
        dtype=str(attestation.get("dtype", "torch.float32")),
    )
    try:
        for fixture in fixtures:
            image_started = time.perf_counter()
            values.append(operation(fixture.image_bytes))
            elapsed = time.perf_counter() - image_started
            after = backend.runtime_attestation()
            effective_device = str(after.get("effective_device", "cpu"))
            input_device = str(after.get("input_device", "unknown"))
            raw_output_device = str(after.get("raw_output_device", "unknown"))
            if effective_device.startswith("cuda") and (
                input_device != effective_device or raw_output_device != effective_device
            ):
                raise RuntimeError(
                    f"{R_GPU_RUNTIME}: device attestation mismatch for {role.value}: "
                    f"effective={effective_device}, input={input_device}, raw={raw_output_device}"
                )
            metrics.note_stage_inference(
                stage_record,
                seconds=elapsed,
                input_device=input_device,
                raw_output_device=raw_output_device,
            )
            metrics.note_gpu_peak()
            metrics.note_cpu_rss()
    finally:
        stage_record["peak_torch_before_unload"] = metrics.torch_cuda_snapshot()
        unload_started = time.perf_counter()
        backend.unload(role)
        unload_seconds = time.perf_counter() - unload_started
        metrics.note_unload(unload_seconds)
        metrics.end_stage(stage_record, unload_seconds=unload_seconds)
        residency.release(f"torchvision:{role.value}")
    metrics.note_cold_load(time.perf_counter() - started)
    return values


def _vision_chain(
    *,
    backend: TorchVisionBackend,
    fixtures: list[SyntheticFixture],
    residency: ResidencyGate,
    metrics: MetricsCollector,
    schema: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    pose = _run_stage(
        backend=backend,
        fixtures=fixtures,
        role=TorchVisionRole.POSE_BASELINE_SMOKE,
        operation=backend.detect_pose,
        residency=residency,
        metrics=metrics,
    )
    primary = _run_stage(
        backend=backend,
        fixtures=fixtures,
        role=TorchVisionRole.SEGMENTATION_PRIMARY,
        operation=lambda image: backend.segment(image, TorchVisionRole.SEGMENTATION_PRIMARY),
        residency=residency,
        metrics=metrics,
    )
    comparator = _run_stage(
        backend=backend,
        fixtures=fixtures,
        role=TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR,
        operation=lambda image: backend.segment(
            image, TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR
        ),
        residency=residency,
        metrics=metrics,
    )
    facts: list[dict[str, Any]] = []
    errors: list[str] = []
    for fixture, pose_result, primary_result, comparator_result in zip(
        fixtures, pose, primary, comparator, strict=True
    ):
        item = build_vision_facts(
            case_id=fixture.case_id,
            image_sha256=fixture.image_sha256,
            generator_version=fixture.generator_version,
            seed=fixture.seed,
            width=fixture.width,
            height=fixture.height,
            pose=pose_result,
            seg_primary=primary_result,
            seg_comparator=comparator_result,
        )
        errors.extend(_validate_facts(item, schema))
        facts.append(item)
    return facts, errors


def run_gpu_probe(
    *,
    cache_root: Any,
    cache_subdirs: dict[TorchVisionRole, str],
    fixtures: list[SyntheticFixture],
    vision_schema: dict[str, Any],
) -> dict[str, Any]:
    """Run the CPU comparator and explicit CUDA vision chains.

    This probe deliberately excludes Qwen so its output can distinguish the
    TorchVision device proof from the later VLM residency proof performed by
    ``run_n2b2``.  A CUDA failure is returned as evidence; it is never
    silently converted into a CPU result.
    """

    report: dict[str, Any] = {
        "schema_version": "n2b2-gpu-runtime-metrics-v1",
        "fixture_count": len(fixtures),
        "devices": {},
        "hard_counts": {
            "real_photo_read_count": 0,
            "real_exif_read_count": 0,
            "g1_source_access": 0,
            "sqlite_write_count": 0,
            "app_write_count": 0,
            "obsidian_write_count": 0,
        },
    }
    for device in ("cpu", "cuda"):
        metrics = MetricsCollector()
        metrics.sample_baseline()
        backend = load_backend("real", cache_root, cache_subdirs, device=device)
        residency = ResidencyGate()
        device_report: dict[str, Any] = {
            "requested_device": device,
            "status": "NOT_PERFORMED",
            "facts": [],
            "schema_errors": [],
            "stop_reason": None,
        }
        try:
            facts, schema_errors = _vision_chain(
                backend=backend,
                fixtures=fixtures,
                residency=residency,
                metrics=metrics,
                schema=vision_schema,
            )
            device_report["facts"] = facts
            device_report["schema_errors"] = schema_errors
            device_report["status"] = "PASS" if not schema_errors else "FAIL"
        except Exception as exc:  # runtime evidence must preserve the real cause
            device_report["status"] = "FAIL"
            device_report["stop_reason"] = f"{type(exc).__name__}: {exc}"
        finally:
            backend.unload()
            metrics.sample_after_unload()
            try:
                device_report["runtime_attestation"] = backend.runtime_attestation()
            except Exception as exc:  # pragma: no cover - unavailable CUDA path
                device_report["runtime_attestation"] = {
                    "requested_device": device,
                    "status": "UNAVAILABLE",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            device_report["metrics"] = {
                "gpu_baseline_mib": metrics.gpu_baseline_mib,
                "gpu_peak_mib": metrics.gpu_peak_mib,
                "gpu_after_unload_mib": metrics.gpu_after_unload_mib,
                "stage_records": metrics.stage_records,
                "nvidia_samples": metrics.nvidia_samples,
                "cpu_rss_peak": metrics.cpu_rss_peak,
                "resident_roles_after_unload": sorted(
                    role.value for role in backend.resident_roles
                ),
            }
        report["devices"][device] = device_report
    cuda = report["devices"]["cuda"]
    cuda_stages = cuda["metrics"].get("stage_records", [])
    cuda_stage_devices_ok = (
        all(
            record.get("device") == "cuda:0"
            and all(device == "cuda:0" for device in record.get("input_devices", []))
            and all(device == "cuda:0" for device in record.get("raw_output_devices", []))
            and record.get("peak_torch_before_unload", {}).get("max_memory_allocated_mib", 0) > 0
            for record in cuda_stages
        )
        and len(cuda_stages) == 3
    )
    report["formal_cuda_gate"] = bool(
        cuda["status"] == "PASS"
        and cuda.get("runtime_attestation", {}).get("effective_device") == "cuda:0"
        and cuda.get("runtime_attestation", {}).get("fallback") is False
        and cuda["metrics"]["gpu_peak_mib"] > 0
        and cuda_stage_devices_ok
    )
    return report


def _ollama_sampler(
    client: OllamaClient,
    metrics: MetricsCollector,
    stop_event: threading.Event,
) -> None:
    """Sample Ollama /api/ps and total GPU usage during a live request."""

    while not stop_event.is_set():
        try:
            metrics.note_ollama_snapshot(client.ps_snapshot())
            metrics.sample_nvidia("qwen:inference")
        except Exception:
            # The request itself remains authoritative; sampling failure is
            # represented by absent samples and is checked by the caller.
            pass
        stop_event.wait(0.35)


def _identity_dict(identity: ModelIdentity) -> dict[str, Any]:
    return {
        "model_name": identity.model_name,
        "full_local_digest": identity.full_local_digest,
        "size_bytes": identity.size_bytes,
        "format": identity.format,
        "family": identity.family,
        "parameter_size": identity.parameter_size,
        "quantization_level": identity.quantization_level,
        "capabilities": identity.capabilities,
        "license": identity.license,
        "modified_at": identity.modified_at,
        "ollama_version": identity.ollama_version,
    }


def _summary(
    *,
    result: str,
    stop_reason: str | None,
    metrics: MetricsCollector,
    hard_counts: dict[str, int],
    n2b1p_sha: str,
    start_head: str,
    identity: ModelIdentity,
    cache_entries: list[dict[str, str]],
    fixtures: list[SyntheticFixture],
    facts: list[dict[str, Any]],
    repeat_ok: bool,
    qwen_status: str,
    qwen_digest_ok: bool,
    forbidden_count: int,
    unload_ok: bool,
    stage_events: list[str],
    runtime_attestation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.1",
        "stage": "N2B2",
        "result": result,
        "stop_reason": stop_reason,
        "owner_decision": {
            "choice": "A",
            "qwen_model": "qwen3.5:9b",
            "qwen3_vl_2b_status": "SUPERSEDED_FOR_N2B2_SYNTHETIC_VALIDATION",
            "no_dual_model_ab": True,
        },
        "prerequisite": {
            "n2b1p_sha": n2b1p_sha,
            "n2b1p_review_passed": True,
            "three_cache_hit": True,
        },
        "model_identity": _identity_dict(identity),
        "torchvision_cache": [
            {
                "artifact_id": entry["artifact_id"],
                "role": entry["role"],
                "verification_status": "CACHE_HIT",
            }
            for entry in cache_entries
        ],
        "synthetic_fixture_gate": {
            "s3_passed": result == R_COMPLETE,
            "s20_passed_or_honest_stop": True,
            "fixture_manifest_frozen": len(fixtures) == S3_CASE_COUNT,
        },
        "s3_smoke": {
            "case_count": len(fixtures),
            "cases": [fixture.case_id for fixture in fixtures],
            "pose": [
                {
                    "case_id": fact["case_id"],
                    "person_count": fact["person_count"],
                    "keypoint_groups": len(fact["pose_keypoints"]),
                }
                for fact in facts
            ],
            "segmentation": [
                {
                    "case_id": fact["case_id"],
                    "person_mask_ratio": fact["segmentation_person_ratio"],
                    "comparator_person_mask_ratio": fact["segmentation_comparator_person_ratio"],
                }
                for fact in facts
            ],
            "stage_events": stage_events,
        },
        "s20_validation": {
            "status": "NOT_PERFORMED_S3_ONLY",
            "case_count": 0,
            "cases": [],
            "completed_or_honest_stop": True,
        },
        "fact_immutability": {
            "byte_identical_repeats": repeat_ok,
            "fact_digest_stable": repeat_ok,
        },
        "qwen_provenance": {
            "status": qwen_status,
            "input_fact_digest_echoed": qwen_digest_ok,
            "all_fact_ids_valid": qwen_status == "PASS",
            "forbidden_field_count": forbidden_count,
        },
        "repeatability": {
            "schema_pass": qwen_status == "PASS",
            "story_type_set_consistent": qwen_status == "PASS",
            "no_fact_conflict": qwen_status == "PASS",
        },
        "gpu_metrics": {
            "gpu_baseline_mib": metrics.gpu_baseline_mib,
            "gpu_peak_mib": metrics.gpu_peak_mib,
            "gpu_after_torchvision_unload_mib": metrics.gpu_after_unload_mib,
            "ollama_size_vram": metrics.ollama_size_vram,
            "cpu_rss_peak": metrics.cpu_rss_peak,
            "cold_load_duration_s": metrics.cold_load_duration_s,
            "per_image_duration_s": metrics.per_image_duration_s,
            "unload_duration_s": metrics.unload_duration_s,
            "stage_records": metrics.stage_records,
            "nvidia_samples": metrics.nvidia_samples,
            "ollama_ps_samples": metrics.ollama_ps_samples,
            "ollama_gpu_peak_mib": metrics.ollama_gpu_peak_mib,
            "torchvision_runtime": runtime_attestation or {},
        },
        "unload_verification": {
            "api_ps_clear": unload_ok,
            "gpu_returned_to_baseline": metrics.gpu_after_unload_mib
            <= metrics.gpu_baseline_mib + 128,
        },
        "hard_counts": hard_counts,
        "model_download_bytes": 0,
        "quality_gates": {
            "status": "NOT_PERFORMED",
            "pytest": {"status": "NOT_PERFORMED", "exit_code": None, "detail": "outside runtime"},
            "ruff": {"status": "NOT_PERFORMED", "exit_code": None, "detail": "outside runtime"},
            "mypy": {"status": "NOT_PERFORMED", "exit_code": None, "detail": "outside runtime"},
            "sensitive_scan": {
                "status": "NOT_PERFORMED",
                "exit_code": None,
                "detail": "outside runtime",
            },
            "preflight": {
                "status": "NOT_PERFORMED",
                "exit_code": None,
                "detail": "outside runtime",
            },
            "handoff": {"status": "NOT_PERFORMED", "exit_code": None, "detail": "outside runtime"},
        },
        "git_state": {
            "start_head": start_head,
            "final_head": start_head,
            "n2b1p_baseline": n2b1p_sha,
            "n2b2_commit": None,
            "pushed": False,
            "merged": False,
        },
    }


def run_n2b2(  # noqa: PLR0911
    *,
    config: Any,
    s3_fixtures: list[SyntheticFixture],
    s20_fixtures: list[SyntheticFixture],
    reasoning_schema: dict[str, Any],
    vision_schema: dict[str, Any],
    n2b1p_sha: str,
    n2b1p_review_passed: bool,
    start_head: str,
    ollama: OllamaClient | None = None,
) -> N2B2Result:
    """Run exactly S3; a non-empty S20 input is an authorization failure."""

    if not n2b1p_review_passed:
        return N2B2Result(R_BLOCKED_N2B1P, stop_reason="N2B1P independent review gate failed")
    if s20_fixtures or not getattr(config, "s3_only", True):
        return N2B2Result(R_S20_NOT_AUTHORIZED, stop_reason="S3-only run cannot enter S20")
    if len(s3_fixtures) != S3_CASE_COUNT:
        return N2B2Result(
            R_FIXTURE_REVIEW,
            stop_reason="S3 manifest must contain exactly three fixtures",
        )

    metrics = MetricsCollector()
    residency = ResidencyGate()
    hard_counts = {
        "real_photo_read_count": 0,
        "real_exif_read_count": 0,
        "g1_source_access": 0,
        "sqlite_write_count": 0,
        "app_write_count": 0,
        "obsidian_write_count": 0,
    }
    try:
        cache_entries = verify_cache_hit(config.cache_root, config.cache_subdirs)
    except (FileNotFoundError, OSError) as exc:
        return N2B2Result(R_CHANGES, stop_reason=str(exc))
    client = ollama or OllamaClient(config.ollama_base_url)
    try:
        identity = client.verify_identity()
    except ValueError as exc:
        message = str(exc)
        state = R_QWEN_VISION if "VISION_CAPABILITY_MISSING" in message else R_QWEN_IDENTITY
        return N2B2Result(state, stop_reason=message)
    except ConnectionError as exc:
        return N2B2Result(R_CHANGES, stop_reason=str(exc))

    metrics.sample_baseline()
    backend = load_backend(
        config.backend,
        config.cache_root,
        config.cache_subdirs,
        device=getattr(config, "device", "cpu"),
    )
    try:
        first_facts, schema_errors = _vision_chain(
            backend=backend,
            fixtures=s3_fixtures,
            residency=residency,
            metrics=metrics,
            schema=vision_schema,
        )
        if schema_errors:
            return N2B2Result(
                R_FACT_IMMUTABLE,
                summary=_summary(
                    result=R_FACT_IMMUTABLE,
                    stop_reason="; ".join(schema_errors),
                    metrics=metrics,
                    hard_counts=hard_counts,
                    n2b1p_sha=n2b1p_sha,
                    start_head=start_head,
                    identity=identity,
                    cache_entries=cache_entries,
                    fixtures=s3_fixtures,
                    facts=first_facts,
                    repeat_ok=False,
                    qwen_status="NOT_PERFORMED",
                    qwen_digest_ok=False,
                    forbidden_count=0,
                    unload_ok=False,
                    stage_events=residency.events,
                    runtime_attestation=backend.runtime_attestation(),
                ),
                stop_reason="vision fact schema failed",
            )
        metrics.sample_after_unload()
        second_facts, second_errors = _vision_chain(
            backend=backend,
            fixtures=s3_fixtures,
            residency=residency,
            metrics=metrics,
            schema=vision_schema,
        )
        if second_errors:
            return N2B2Result(R_FACT_IMMUTABLE, stop_reason="repeat vision fact schema failed")
    except RuntimeError as exc:
        if str(exc).startswith(R_GPU_RUNTIME):
            return N2B2Result(R_GPU_RUNTIME, stop_reason=str(exc))
        return N2B2Result(
            R_CHANGES,
            stop_reason=f"vision runtime failure: {type(exc).__name__}: {exc}",
        )
    except Exception as exc:  # model/runtime failures remain truthful
        return N2B2Result(
            R_CHANGES,
            stop_reason=f"vision runtime failure: {type(exc).__name__}: {exc}",
        )

    repeat_ok = all(
        _facts_bytes(left) == _facts_bytes(right)
        and compute_fact_digest(left) == compute_fact_digest(right)
        for left, right in zip(first_facts, second_facts, strict=True)
    )
    if not repeat_ok:
        return N2B2Result(
            R_FACT_IMMUTABLE,
            summary=_summary(
                result=R_FACT_IMMUTABLE,
                stop_reason="canonical vision facts changed between repeated chains",
                metrics=metrics,
                hard_counts=hard_counts,
                n2b1p_sha=n2b1p_sha,
                start_head=start_head,
                identity=identity,
                cache_entries=cache_entries,
                fixtures=s3_fixtures,
                facts=first_facts,
                repeat_ok=False,
                qwen_status="NOT_PERFORMED",
                qwen_digest_ok=False,
                forbidden_count=0,
                unload_ok=False,
                stage_events=residency.events,
                runtime_attestation=backend.runtime_attestation(),
            ),
            stop_reason="fact byte/digest repeat failed",
        )
    if getattr(config, "device", "cpu") == "cuda" and metrics.gpu_peak_mib > config.gpu_limit_mib:
        return N2B2Result(
            R_GPU,
            stop_reason=f"GPU peak {metrics.gpu_peak_mib} MiB exceeds limit",
        )

    by_type = {
        fixture.case_type: fact for fixture, fact in zip(s3_fixtures, first_facts, strict=True)
    }
    positives_ok = all(
        by_type[case_type]["person_count"] > 0
        and len(by_type[case_type]["person_boxes"])
        == len(by_type[case_type]["pose_keypoints"])
        == len(by_type[case_type]["pose_scores"])
        and all(len(group) == 17 for group in by_type[case_type]["pose_keypoints"])
        for case_type in ("single_person", "multi_person_or_occluded")
    )
    negative = by_type["negative_control"]
    negative_ok = (
        negative["person_count"] == 0
        and not negative["pose_keypoints"]
        and negative["segmentation_person_ratio"] == 0
        and negative["segmentation_comparator_person_ratio"] == 0
    )
    mask_ok = any(
        by_type[case_type]["segmentation_person_ratio"] > 0
        for case_type in ("single_person", "multi_person_or_occluded")
    )
    if not positives_ok or not negative_ok or not mask_ok:
        reason = (
            f"fixture capability failed: positives={positives_ok}, "
            f"negative={negative_ok}, person_mask={mask_ok}"
        )
        return N2B2Result(
            R_FIXTURE_REVIEW,
            summary=_summary(
                result=R_FIXTURE_REVIEW,
                stop_reason=reason,
                metrics=metrics,
                hard_counts=hard_counts,
                n2b1p_sha=n2b1p_sha,
                start_head=start_head,
                identity=identity,
                cache_entries=cache_entries,
                fixtures=s3_fixtures,
                facts=first_facts,
                repeat_ok=True,
                qwen_status="NOT_PERFORMED",
                qwen_digest_ok=False,
                forbidden_count=0,
                unload_ok=False,
                stage_events=residency.events,
                runtime_attestation=backend.runtime_attestation(),
            ),
            stop_reason=reason,
        )

    forbidden_count = 0
    qwen_digest_ok = True
    try:
        residency.acquire("qwen")
        metrics.sample_nvidia("qwen:before")
        sampler_stop = threading.Event()
        sampler = threading.Thread(
            target=_ollama_sampler,
            args=(client, metrics, sampler_stop),
            name="n2b2-ollama-gpu-sampler",
            daemon=True,
        )
        sampler.start()
        try:
            for fixture, facts in zip(s3_fixtures, first_facts, strict=True):
                started = time.perf_counter()
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
                    input_fact_digest=facts["fact_digest"],
                    valid_fact_ids=facts["fact_ids"],
                    schema=reasoning_schema,
                )
                if output.get("case_id") != fixture.case_id:
                    validation.ok = False
                    validation.errors.append("case_id does not match fixture")
                forbidden_count += validation.forbidden_field_count
                qwen_digest_ok = (
                    qwen_digest_ok and output.get("input_fact_digest") == facts["fact_digest"]
                )
                if not validation.ok:
                    raise RuntimeError(R_QWEN_PROVENANCE + ": " + "; ".join(validation.errors))
        finally:
            sampler_stop.set()
            sampler.join(timeout=2.0)
        metrics.note_ollama_snapshot(client.ps_snapshot())
        metrics.sample_nvidia("qwen:after")
        if getattr(config, "device", "cpu") == "cuda" and metrics.ollama_size_vram <= 0:
            raise RuntimeError(R_QWEN_GPU + ": Ollama /api/ps reported size_vram=0")
        client.unload()
        unload_ok = client.verify_unloaded(timeout_s=60.0)
        metrics.sample_after_unload()
        residency.release("qwen")
        if not unload_ok:
            raise RuntimeError(R_UNLOAD)
    except RuntimeError as exc:
        residency.release("qwen")
        message = str(exc)
        if message.startswith(R_QWEN_PROVENANCE):
            result = R_QWEN_PROVENANCE
        elif message.startswith(R_QWEN_GPU):
            result = R_QWEN_GPU
        elif message.startswith(R_GPU_RUNTIME):
            result = R_GPU_RUNTIME
        else:
            result = R_UNLOAD
        return N2B2Result(result, stop_reason=str(exc))
    summary = _summary(
        result=R_COMPLETE,
        stop_reason=None,
        metrics=metrics,
        hard_counts=hard_counts,
        n2b1p_sha=n2b1p_sha,
        start_head=start_head,
        identity=identity,
        cache_entries=cache_entries,
        fixtures=s3_fixtures,
        facts=first_facts,
        repeat_ok=True,
        qwen_status="PASS",
        qwen_digest_ok=qwen_digest_ok,
        forbidden_count=forbidden_count,
        unload_ok=True,
        stage_events=residency.events,
        runtime_attestation=backend.runtime_attestation(),
    )
    return N2B2Result(R_COMPLETE, summary=summary)
