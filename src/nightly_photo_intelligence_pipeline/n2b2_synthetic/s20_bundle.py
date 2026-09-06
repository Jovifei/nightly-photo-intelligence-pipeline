"""Synthetic-only per-case bundle and top-level index writers."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

S20_COMPLETE = "N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"
S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH = "N2B2_S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH"
_CHECKSUM_LINE = re.compile(r"^(?P<sha>[0-9a-f]{64})  (?P<path>[^\r\n]+)$")
_BACKSLASH = chr(92)
_CASE_IDS = tuple(f"n2b2-s20-{index:02d}" for index in range(1, 21))
_CASE_ARTIFACTS = {
    "analysis.json",
    "vision_facts.json",
    "director_prompt.json",
    "reference_bundle.json",
}
_TOP_LEVEL_ARTIFACTS = {
    "checkpoint.json",
    "cleanup_evidence.json",
    "fixture_manifest.json",
    "ollama_identity.json",
    "process_evidence.json",
    "repeatability_report.json",
    "runtime_metrics.json",
    "synthetic_bundle_index.json",
    "validation_summary.json",
}


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> str:
    data = canonical_bytes(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return sha256_bytes(data)


def validate_artifact(path: Path, schema_path: Path) -> None:
    """Validate one external JSON artifact against a repository schema."""

    import jsonschema  # type: ignore[import-untyped]

    payload = json.loads(path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(payload), key=str)
    if errors:
        raise ValueError(f"N2B2_S20_ARTIFACT_SCHEMA_INVALID: {path.name}: {errors[0].message}")


def write_case_bundle(
    case_dir: Path,
    *,
    fixture: Any,
    facts: dict[str, Any],
    reasoning: dict[str, Any],
    disposition: str,
    qwen_binding: dict[str, Any] | None = None,
) -> dict[str, str]:
    vision_path = case_dir / "vision_facts.json"
    analysis_path = case_dir / "analysis.json"
    director_path = case_dir / "director_prompt.json"
    bundle_path = case_dir / "reference_bundle.json"
    vision_sha = write_json(vision_path, facts)
    analysis = {
        "schema_version": "n2b2-s20-analysis-v1",
        "case_id": fixture.case_id,
        "input_fact_digest": facts["fact_digest"],
        "processing_disposition": disposition,
        "photographic_interpretation": reasoning.get("photographic_interpretation"),
        "story_candidates": reasoning.get("story_candidates"),
        "uncertainties": reasoning.get("uncertainties", []),
        "provenance": {"qwen_model": "qwen3.5:9b", "forbidden_field_count": 0},
    }
    analysis_sha = write_json(analysis_path, analysis)
    director = {
        "schema_version": "n2b2-s20-director-prompt-v1",
        "case_id": fixture.case_id,
        "input_fact_digest": facts["fact_digest"],
        "reasoning_based_on_fact_ids": reasoning.get("reasoning_based_on_fact_ids", []),
        "director_prompts": reasoning.get("director_prompts"),
    }
    director_sha = write_json(director_path, director)
    binding = qwen_binding or {}
    echoed_digest = str(binding.get("echoed_fact_digest", reasoning.get("input_fact_digest", "")))
    echo_verified = bool(binding.get("echo_verified", echoed_digest == facts["fact_digest"]))
    bundle = {
        "schema_version": "1.0-synthetic",
        "bundle_type": "SYNTHETIC_VALIDATION",
        "case_id": fixture.case_id,
        "image_sha256": fixture.image_sha256,
        "vision_facts": {"fact_digest": facts["fact_digest"], "fact_ids": facts["fact_ids"]},
        "photographic_reasoning": {
            "input_fact_digest": facts["fact_digest"],
            "reasoning_model": "qwen3.5:9b",
            "qwen_echo_verified": echo_verified,
            "qwen_echoed_fact_digest": echoed_digest,
        },
        "checksums": {
            "vision_facts_sha256": vision_sha,
            "reasoning_sha256": analysis_sha,
            "director_prompt_sha256": director_sha,
        },
        "provenance": {
            "data_gate": "SYNTHETIC_ONLY_DATA_GATE",
            "real_photo_read_count": 0,
            "real_exif_read_count": 0,
            "g1_source_access": 0,
            "sqlite_write_count": 0,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "pipeline_stage": "N2B2_SYNTHETIC_MODEL_STACK_VALIDATION",
        },
        "processing_disposition": disposition,
    }
    bundle_sha = write_json(bundle_path, bundle)
    return {
        "vision_facts": vision_sha,
        "analysis": analysis_sha,
        "director_prompt": director_sha,
        "reference_bundle": bundle_sha,
    }


def write_checksums(root: Path) -> str:
    rows: list[str] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file() and p.name != "CHECKSUMS.sha256"):
        rel = path.relative_to(root).as_posix()
        rows.append(f"{sha256_bytes(path.read_bytes())}  {rel}")
    data = ("\n".join(rows) + "\n").encode("utf-8")
    (root / "CHECKSUMS.sha256").write_bytes(data)
    return sha256_bytes(data)


def _integrity_error(detail: str) -> ValueError:
    return ValueError(f"{S20_COMPLETE_ARTIFACT_INTEGRITY_MISMATCH}: {detail}")


def _safe_relative_path(root: Path, relative: str) -> Path:
    if not relative or relative.startswith("/") or _BACKSLASH in relative:
        raise _integrity_error("invalid checksum path")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise _integrity_error("checksum path escapes release root")
    target = root.joinpath(*parts)
    if target.is_symlink() or not target.is_file():
        raise _integrity_error("checksum target is not a regular file")
    try:
        target.resolve(strict=True).relative_to(root.resolve(strict=True))
    except ValueError as exc:
        raise _integrity_error("checksum target escapes release root") from exc
    return target


def _checksum_entries(root: Path) -> dict[str, str]:
    checksum_path = root / "CHECKSUMS.sha256"
    if not checksum_path.is_file() or checksum_path.is_symlink():
        raise _integrity_error("CHECKSUMS.sha256 missing")
    try:
        text = checksum_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise _integrity_error("CHECKSUMS.sha256 must be UTF-8") from exc
    if not text.endswith("\n") or "\r" in text:
        raise _integrity_error("CHECKSUMS.sha256 must use LF-terminated rows")
    rows: dict[str, str] = {}
    for line in text.splitlines():
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise _integrity_error("malformed checksum row")
        relative = match.group("path")
        if relative == "CHECKSUMS.sha256" or relative in rows:
            raise _integrity_error("duplicate or self-referential checksum row")
        _safe_relative_path(root, relative)
        rows[relative] = match.group("sha")
    if not rows:
        raise _integrity_error("empty checksum manifest")
    return rows


def _actual_release_files(root: Path) -> set[str]:
    files: set[str] = set()
    for path in root.rglob("*"):
        if path.is_dir():
            if path.is_symlink():
                raise _integrity_error("release root contains a reparse directory")
            continue
        if path.is_symlink() or not path.is_file():
            raise _integrity_error("release root contains a non-regular file")
        relative = path.relative_to(root).as_posix()
        if relative != "CHECKSUMS.sha256":
            files.add(relative)
    return files


def _validate_complete_layout(root: Path, payload: dict[str, Any]) -> None:
    if payload.get("result") != S20_COMPLETE:
        raise _integrity_error("validation summary is not COMPLETE")
    if (root / "failure_summary.json").exists():
        raise _integrity_error("successful release contains failure_summary.json")

    index_path = root / "synthetic_bundle_index.json"
    if not index_path.is_file():
        raise _integrity_error("bundle index missing")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, dict):
        raise _integrity_error("bundle index must be an object")
    cases = index.get("cases")
    if index.get("bundle_count") != 20 or not isinstance(cases, list) or len(cases) != 20:
        raise _integrity_error("bundle index does not declare exactly twenty cases")
    if {item.get("case_id") for item in cases if isinstance(item, dict)} != set(_CASE_IDS):
        raise _integrity_error("bundle index case IDs drifted")
    for case_id in _CASE_IDS:
        case_dir = root / "cases" / case_id
        files = (
            {path.name for path in case_dir.iterdir() if path.is_file()}
            if case_dir.is_dir()
            else set()
        )
        if files != _CASE_ARTIFACTS:
            raise _integrity_error(f"case bundle layout invalid: {case_id}")

    checkpoint_path = root / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "reviewed_commit",
        "review_record_sha256",
        "manifest_sha256",
        "runtime_source_sha256",
        "qwen_receipt_sha256",
        "artifact_integrity_receipt_sha256",
        "model_identity",
        "run_started_at_utc",
        "completed_stages",
        "completed_cases",
        "qwen_case_records",
        "qwen_repeat_case_ids",
        "bundle_count",
        "status",
    }
    if (
        not isinstance(checkpoint, dict)
        or checkpoint.get("schema_version") != "n2b2-s20-checkpoint-v2"
        or checkpoint.get("status") != "COMPLETE"
        or checkpoint.get("bundle_count") != 20
        or set(checkpoint) != required
        or checkpoint.get("completed_cases") != list(_CASE_IDS)
        or not isinstance(checkpoint.get("qwen_case_records"), dict)
        or set(checkpoint["qwen_case_records"]) != set(_CASE_IDS)
        or not isinstance(checkpoint.get("qwen_repeat_case_ids"), list)
        or len(checkpoint["qwen_repeat_case_ids"]) != 5
    ):
        raise _integrity_error("COMPLETE checkpoint does not carry complete v2 evidence")
    identity_path = root / "ollama_identity.json"
    try:
        identity_payload = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _integrity_error("Ollama identity evidence is invalid") from exc
    identity_sha256 = sha256_bytes(canonical_bytes(identity_payload))
    if checkpoint.get("model_identity") != identity_sha256:
        raise _integrity_error("checkpoint model identity does not match saved identity evidence")

    diagnostics = root / "diagnostics"
    expected_diagnostics = {
        "acceptance_report.json",
        "repeatability_report.json",
        "visual_facts_first.json",
        "visual_facts_second.json",
        "qwen",
        "qwen-repeat",
        "qwen-probe",
    }
    diagnostic_items = (
        {item.name for item in diagnostics.iterdir()} if diagnostics.is_dir() else set()
    )
    if diagnostic_items != expected_diagnostics:
        raise _integrity_error("diagnostics layout mismatch")
    qwen_cases = diagnostics / "qwen"
    if {item.name for item in qwen_cases.iterdir()} != set(_CASE_IDS):
        raise _integrity_error("primary Qwen evidence case set mismatch")
    repeat_ids = checkpoint["qwen_repeat_case_ids"]
    qwen_repeat_cases = diagnostics / "qwen-repeat"
    if {item.name for item in qwen_repeat_cases.iterdir()} != set(repeat_ids):
        raise _integrity_error("repeat Qwen evidence case set mismatch")
    for case_dir in list(qwen_cases.iterdir()) + list(qwen_repeat_cases.iterdir()):
        if not case_dir.is_dir() or {item.name for item in case_dir.iterdir()} != {
            "binding_validation.json",
            "raw_response.json",
        }:
            raise _integrity_error(f"Qwen evidence layout mismatch: {case_dir.name}")
        try:
            binding = json.loads((case_dir / "binding_validation.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _integrity_error(f"Qwen binding evidence invalid: {case_dir.name}") from exc
        if not isinstance(binding, dict) or binding.get("model_identity_sha256") != identity_sha256:
            raise _integrity_error(f"Qwen identity binding mismatch: {case_dir.name}")

    probe = diagnostics / "qwen-probe"
    if not probe.is_dir() or {item.name for item in probe.iterdir()} != {
        "binding_validation_1.json",
        "binding_validation_2.json",
        "probe_summary.json",
        "raw_response_1.json",
        "raw_response_2.json",
    }:
        raise _integrity_error("Qwen preflight probe evidence layout mismatch")
    for name in ("binding_validation_1.json", "binding_validation_2.json"):
        try:
            binding = json.loads((probe / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise _integrity_error(f"Qwen probe binding evidence invalid: {name}") from exc
        if not isinstance(binding, dict) or binding.get("model_identity_sha256") != identity_sha256:
            raise _integrity_error(f"Qwen probe identity binding mismatch: {name}")

    actual = _actual_release_files(root)
    expected = set(_TOP_LEVEL_ARTIFACTS)
    expected.update(f"cases/{case_id}/{name}" for case_id in _CASE_IDS for name in _CASE_ARTIFACTS)
    expected.update(
        f"diagnostics/{name}"
        for name in (
            "acceptance_report.json",
            "repeatability_report.json",
            "visual_facts_first.json",
            "visual_facts_second.json",
        )
    )
    expected.update(
        f"diagnostics/qwen/{case_id}/{name}"
        for case_id in _CASE_IDS
        for name in ("binding_validation.json", "raw_response.json")
    )
    expected.update(
        f"diagnostics/qwen-repeat/{case_id}/{name}"
        for case_id in repeat_ids
        for name in ("binding_validation.json", "raw_response.json")
    )
    expected.update(
        f"diagnostics/qwen-probe/{name}"
        for name in (
            "binding_validation_1.json",
            "binding_validation_2.json",
            "probe_summary.json",
            "raw_response_1.json",
            "raw_response_2.json",
        )
    )
    if actual != expected:
        raise _integrity_error("successful release file set is not exact")


def verify_release_checksums(root: Path) -> dict[str, str]:
    """Recompute the exact successful-S20 artifact set without writing files."""

    root = root.resolve(strict=True)
    summary_path = root / "validation_summary.json"
    if not summary_path.is_file() or summary_path.is_symlink():
        raise _integrity_error("validation summary missing")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise _integrity_error("validation summary is invalid JSON") from exc
    if not isinstance(summary, dict):
        raise _integrity_error("validation summary is not an object")
    _validate_complete_layout(root, summary)

    expected = _checksum_entries(root)
    actual = _actual_release_files(root)
    if set(expected) != actual:
        raise _integrity_error("checksum rows do not exactly match release files")
    for relative, expected_sha in expected.items():
        actual_sha = sha256_bytes(_safe_relative_path(root, relative).read_bytes())
        if actual_sha != expected_sha:
            raise _integrity_error(f"checksum mismatch: {relative}")
    return expected
