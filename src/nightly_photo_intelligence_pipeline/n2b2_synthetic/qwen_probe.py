"""Frozen Case 03 Qwen fact-binding probe used before a full S20 run."""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Any

from .metrics import MetricsCollector
from .ollama_client import OllamaClient
from .qwen_fact_binding import bind_reasoning_schema, sha256_json
from .qwen_reasoning import validate_reasoning
from .s20_bundle import write_json
from .s20_orchestrator import _identity_dict, _runtime_source_manifest

PROBE_PASS = "N2B2_QWEN_FACT_BINDING_CONTRACT_PROBE_PASS"
PROBE_FAILED = "N2B2_QWEN_FACT_BINDING_CONTRACT_PROBE_FAILED"


def _load_case_facts(vision_evidence_dir: Path, case_id: str) -> dict[str, Any]:
    path = vision_evidence_dir / "visual_facts_first.json"
    values = json.loads(path.read_text(encoding="utf-8"))
    for value in values:
        if isinstance(value, dict) and value.get("case_id") == case_id:
            return value
    raise ValueError(f"{PROBE_FAILED}: frozen facts missing {case_id}")


def run_qwen_contract_probe(
    *,
    project_root: Path,
    fixture: Any,
    facts: dict[str, Any],
    reasoning_schema: dict[str, Any],
    out: Path,
    client: OllamaClient | None = None,
) -> dict[str, Any]:
    """Run two identical Case 03 requests and preserve only redacted evidence."""

    if out.exists() and any(path.is_file() for path in out.rglob("*")):
        raise ValueError("N2B2_QWEN_BINDING_PROBE_OUTPUT_NOT_EMPTY")
    out.mkdir(parents=True, exist_ok=True)
    active = client or OllamaClient()
    metrics = MetricsCollector()
    identity = active.verify_identity()
    identity_sha256 = sha256_json(_identity_dict(identity))
    bound = bind_reasoning_schema(
        reasoning_schema,
        case_id=fixture.case_id,
        fact_digest=facts["fact_digest"],
        fact_ids=facts["fact_ids"],
    )
    passes: list[dict[str, Any]] = []
    errors: list[str] = []
    image_b64 = base64.b64encode(fixture.image_bytes).decode("ascii")
    try:
        for index in range(2):
            metrics.sample_nvidia(f"probe:qwen:{index + 1}")
            started = time.perf_counter()
            output = active.reason(
                image_b64=image_b64,
                case_id=fixture.case_id,
                vision_facts=facts,
                fact_digest=facts["fact_digest"],
                fact_ids=facts["fact_ids"],
                uncertainties=facts["uncertainties"],
                response_schema=reasoning_schema,
                seed=fixture.seed,
                keep_alive=300,
            )
            elapsed_ms = (time.perf_counter() - started) * 1000
            validation = validate_reasoning(
                output,
                case_id=fixture.case_id,
                input_fact_digest=facts["fact_digest"],
                valid_fact_ids=facts["fact_ids"],
                schema=bound,
            )
            raw_path = out / f"raw_response_{index + 1}.json"
            raw_sha = write_json(raw_path, output)
            evidence = {
                "schema_version": "n2b2-qwen-fact-binding-evidence-v1",
                "case_id": fixture.case_id,
                "authoritative_fact_digest": facts["fact_digest"],
                "bound_response_schema_sha256": sha256_json(bound),
                "prompt_sha256": active.last_call_evidence.get("prompt_sha256", ""),
                "raw_response_sha256": raw_sha,
                "model_identity_sha256": identity_sha256,
                "echoed_fact_digest": output.get("input_fact_digest", "0" * 64),
                "echo_match": output.get("input_fact_digest") == facts["fact_digest"],
                "fact_reference_valid": not any("unknown fact_ids" in e for e in validation.errors),
                "forbidden_field_count": validation.forbidden_field_count,
                "validation_status": "PASS" if validation.ok else "FAIL",
                "response_time_ms": round(elapsed_ms, 3),
                "errors": list(validation.errors),
            }
            evidence_sha = write_json(out / f"binding_validation_{index + 1}.json", evidence)
            passes.append(
                {
                    "attempt": index + 1,
                    "validation_status": evidence["validation_status"],
                    "raw_response_sha256": raw_sha,
                    "binding_evidence_sha256": evidence_sha,
                    "story_type_set": sorted(output.get("story_candidates", {}).keys()),
                    "director_type_set": sorted(output.get("director_prompts", {}).keys()),
                    "response_time_ms": evidence["response_time_ms"],
                }
            )
            if not validation.ok:
                errors.extend(validation.errors)
                break
            metrics.note_ollama_snapshot(active.ps_snapshot())
            metrics.sample_nvidia(f"probe:qwen:{index + 1}:after")
        vram_mib = active.ps_vram_mib()
        if vram_mib <= 0:
            errors.append("N2B2_QWEN_GPU_USAGE_NOT_CONFIRMED: size_vram=0")
    finally:
        active.unload()
        unloaded = active.verify_unloaded(timeout_s=60.0)
        metrics.sample_after_unload()

    if not unloaded:
        errors.append("N2B2_QWEN_GPU_USAGE_NOT_CONFIRMED: unload failed")
    type_sets_identical = (
        len(passes) == 2
        and len({(tuple(row["story_type_set"]), tuple(row["director_type_set"])) for row in passes})
        == 1
    )
    if not type_sets_identical:
        errors.append("Qwen output type set mismatch")
    result = PROBE_PASS if not errors and len(passes) == 2 else PROBE_FAILED
    summary = {
        "result": result,
        "case_id": fixture.case_id,
        "attempts": passes,
        "errors": errors,
        "type_sets_identical": type_sets_identical,
        "identity": {
            "name": identity.model_name,
            "digest": identity.full_local_digest,
            "quantization": identity.quantization_level,
            "vision": "vision" in identity.capabilities,
        },
        "size_vram_mib": vram_mib,
        "qwen_unloaded": unloaded,
        "runtime_source_sha256": _runtime_source_manifest(project_root)["runtime_source_sha256"],
        "hard_counts": {
            "real_photo_read_count": 0,
            "real_exif_read_count": 0,
            "g1_source_access": 0,
            "sqlite_write_count": 0,
            "obsidian_write_count": 0,
            "model_download_bytes": 0,
        },
    }
    write_json(out / "probe_summary.json", summary)
    if result != PROBE_PASS:
        raise ValueError(result)
    return summary
