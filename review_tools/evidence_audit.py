"""Read-only, model-free semantic audit of an explicitly selected S20 release.

An externally supplied CHECKSUMS digest is mandatory. A consistent artifact set
is NOT an independent review verdict, live resume, permission, or quality score.
No project runtime imports, HTTP, model calls, source images or SQLite access.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

from negative_space import measure_bbox_empty_area

CASE_IDS = tuple(f"n2b2-s20-{i:02d}" for i in range(1, 21))
HEX = re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
MAX_FILES = 512
COMPLETE = "N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"
COUNTERS = ("real_photo_read_count", "real_exif_read_count", "g1_source_access",
            "sqlite_write_count", "app_write_count", "obsidian_write_count",
            "s20_runtime_obsidian_write_count", "model_download_bytes")
TOP = {"checkpoint.json", "cleanup_evidence.json", "fixture_manifest.json",
       "ollama_identity.json", "process_evidence.json", "repeatability_report.json",
       "runtime_metrics.json", "synthetic_bundle_index.json", "validation_summary.json"}
ARTIFACTS = ("analysis.json", "vision_facts.json", "director_prompt.json", "reference_bundle.json")


class AuditError(ValueError):
    """Only stable, non-sensitive codes cross the CLI boundary."""


def require(ok: bool, code: str) -> None:
    if not ok:
        raise AuditError(code)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object, newline: bool = True) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                       allow_nan=False) + ("\n" if newline else "")).encode("utf-8")


def strict_json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_MEMBER")
            result[key] = value
        return result

    def number(text: str) -> float:
        value = float(text)
        require(math.isfinite(value), "NONFINITE_JSON_NUMBER")
        return value

    def invalid(_: str) -> Any:
        raise AuditError("NONFINITE_JSON_NUMBER")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                          parse_float=number, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError):
        raise AuditError("INVALID_JSON") from None


def safe_relative(name: str) -> bool:
    parts = name.split("/")
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)),
                *(f"lpt{i}" for i in range(10))}
    return (len(parts) <= 10 and all(
        part not in ("", ".", "..") and not part.endswith((".", " "))
        and part.split(".")[0].lower() not in reserved
        and re.fullmatch(r"[A-Za-z0-9_.-]+", part) is not None for part in parts))


def reject_links(path: Path) -> None:
    """Check all existing ancestors before resolve, including Windows reparse."""
    for component in (path, *path.parents):
        info = component.lstat()
        require(not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & 0x400), "REPARSE_PATH")


def read_regular(path: Path) -> bytes:
    reject_links(path)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "NON_REGULAR_FILE")
    require(before.st_size <= MAX_FILE_BYTES, "FILE_SIZE_LIMIT")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as handle:
        opened = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino), "FILE_CHANGED")
        data = handle.read(MAX_FILE_BYTES + 1)
        after = os.fstat(handle.fileno())
    reject_links(path)
    current = path.lstat()
    require(len(data) <= MAX_FILE_BYTES, "FILE_SIZE_LIMIT")
    # Windows may report a transient ctime change while a file is being read.
    fingerprints = {(s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
                    for s in (before, opened, after, current)}
    require(len(fingerprints) == 1 and len(data) == before.st_size, "FILE_CHANGED")
    return data


def inventory(root: Path) -> set[str]:
    result: set[str] = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        require(len(Path(directory).relative_to(root).parts) <= 10, "DEPTH_LIMIT")
        for name in dirs:
            reject_links(Path(directory) / name)
        for name in files:
            rel = (Path(directory) / name).relative_to(root).as_posix()
            require(safe_relative(rel), "UNSAFE_PATH")
            require(rel.endswith(".json") or rel == "CHECKSUMS.sha256", "UNSUPPORTED_FILE")
            result.add(rel)
            require(len(result) <= MAX_FILES, "FILE_COUNT_LIMIT")
    return result


def load_release(root: Path, checksum_sha256: str) -> dict[str, bytes]:
    require(HEX.fullmatch(checksum_sha256) is not None, "CHECKSUM_ANCHOR_REQUIRED")
    reject_links(root)
    require(root.is_dir(), "EVIDENCE_ROOT_UNAVAILABLE")
    checksum = read_regular(root / "CHECKSUMS.sha256")
    require(digest(checksum) == checksum_sha256, "CHECKSUM_ANCHOR_MISMATCH")
    require(checksum.endswith(b"\n") and b"\r" not in checksum, "INVALID_CHECKSUM_FILE")
    entries: dict[str, str] = {}
    try:
        for line in checksum.decode("utf-8").splitlines():
            hash_value, rel = line.split("  ", 1)
            require(HEX.fullmatch(hash_value) is not None and safe_relative(rel), "INVALID_CHECKSUM_ROW")
            require(rel != "CHECKSUMS.sha256" and rel not in entries, "DUPLICATE_OR_SELF_CHECKSUM")
            require(rel.endswith(".json"), "UNSUPPORTED_FILE")
            entries[rel] = hash_value
    except (UnicodeError, ValueError) as exc:
        if isinstance(exc, AuditError):
            raise
        raise AuditError("INVALID_CHECKSUM_ROW") from None
    require(bool(entries) and len(entries) < MAX_FILES, "FILE_COUNT_LIMIT")
    require(inventory(root) == set(entries) | {"CHECKSUMS.sha256"}, "FILE_SET_MISMATCH")
    payload = {"CHECKSUMS.sha256": checksum}
    size = len(checksum)
    for rel, expected in entries.items():
        data = read_regular(root / rel)
        size += len(data)
        require(size <= MAX_TOTAL_BYTES, "TOTAL_SIZE_LIMIT")
        require(digest(data) == expected, "FILE_HASH_MISMATCH")
        payload[rel] = data
    return payload


def inspect_payload(files: dict[str, bytes], checksum_sha256: str) -> dict[str, Any]:
    """Semantics over already anchored bytes; never contact a live runtime."""
    parsed = {name: strict_json(data) for name, data in files.items() if name.endswith(".json")}

    def obj(name: str) -> dict[str, Any]:
        value = parsed.get(name)
        require(isinstance(value, dict), "MISSING_JSON_OBJECT")
        return value

    summary, checkpoint = obj("validation_summary.json"), obj("checkpoint.json")
    require(summary.get("result") == COMPLETE and summary.get("bundle_count") == 20,
            "NOT_COMPLETE_SYNTHETIC_S20")
    require(summary.get("s20_execution_status") == "PERFORMED_SYNTHETIC_ONLY"
            and summary.get("production_bundle_release") == "NOT_CREATED", "SCOPE_MISMATCH")
    require(checkpoint.get("status") == "COMPLETE" and checkpoint.get("completed_cases") == list(CASE_IDS)
            and checkpoint.get("bundle_count") == 20, "CHECKPOINT_MISMATCH")
    repeats = checkpoint.get("qwen_repeat_case_ids")
    require(isinstance(repeats, list) and len(repeats) == 5
            and all(isinstance(i, str) for i in repeats), "REPEAT_CASE_SET")
    require(len(set(repeats)) == 5 and set(repeats) <= set(CASE_IDS), "REPEAT_CASE_SET")
    expected = set(TOP) | {"CHECKSUMS.sha256"}
    expected.update(f"cases/{case}/{name}" for case in CASE_IDS for name in ARTIFACTS)
    expected.update(f"diagnostics/{name}" for name in (
        "acceptance_report.json", "repeatability_report.json", "visual_facts_first.json", "visual_facts_second.json"))
    expected.update(f"diagnostics/{group}/{case}/{name}" for group, cases in (
        ("qwen", CASE_IDS), ("qwen-repeat", repeats)) for case in cases
        for name in ("binding_validation.json", "raw_response.json"))
    expected.update(f"diagnostics/qwen-probe/{name}" for name in (
        "binding_validation_1.json", "binding_validation_2.json", "probe_summary.json",
        "raw_response_1.json", "raw_response_2.json"))
    require(set(files) == expected, "COMPLETE_LAYOUT_MISMATCH")
    counters = summary.get("hard_counts")
    require(isinstance(counters, dict) and all(type(counters.get(k)) is int and counters[k] == 0
            for k in COUNTERS), "COUNTER_MISSING_OR_NONZERO")
    gpu = summary.get("gpu")
    require(isinstance(gpu, dict), "GPU_EVIDENCE_MISSING")
    peak = gpu.get("peak_mib")
    require(type(peak) in (int, float) and math.isfinite(peak) and 0 < peak <= 11500,
            "GPU_PEAK_INVALID")
    require(obj("runtime_metrics.json").get("gpu") == gpu, "GPU_EVIDENCE_CONTRADICTION")
    cleanup = obj("cleanup_evidence.json")
    require(cleanup.get("qwen_unloaded") is True and cleanup.get("torchvision_resident_roles") == [],
            "UNLOAD_NOT_RECORDED")
    identity = obj("ollama_identity.json")
    require(identity.get("model_name") == "qwen3.5:9b"
            and identity.get("quantization_level") == "Q4_K_M"
            and isinstance(identity.get("capabilities"), list) and "vision" in identity["capabilities"]
            and isinstance(identity.get("full_local_digest"), str)
            and HEX.fullmatch(identity["full_local_digest"]) is not None, "MODEL_IDENTITY_INVALID")
    identity_hash = digest(canonical(identity))
    require(checkpoint.get("model_identity") == identity_hash, "SAVED_IDENTITY_MISMATCH")
    require(checkpoint.get("manifest_sha256") == digest(files["fixture_manifest.json"]), "MANIFEST_BINDING")
    require(summary.get("reviewed_commit") == checkpoint.get("reviewed_commit"), "REVIEWED_COMMIT_BINDING")
    manifest = obj("fixture_manifest.json").get("fixtures")
    require(isinstance(manifest, list) and len(manifest) == 20 and all(isinstance(i, dict) for i in manifest),
            "FIXTURE_CASE_SET")
    require(all(isinstance(i.get("case_id"), str) for i in manifest), "FIXTURE_CASE_SET")
    by_case = {item["case_id"]: item for item in manifest}
    require(set(by_case) == set(CASE_IDS), "FIXTURE_CASE_SET")
    index = obj("synthetic_bundle_index.json")
    index_cases = index.get("cases")
    require(index.get("bundle_count") == 20 and isinstance(index_cases, list) and len(index_cases) == 20
            and all(isinstance(i, dict) and isinstance(i.get("case_id"), str) for i in index_cases), "INDEX_CASE_SET")
    require({i["case_id"] for i in index_cases} == set(CASE_IDS), "INDEX_CASE_SET")
    profiles = {name: sum(i.get("acceptance_profile") == name for i in manifest)
                for name in ("strict", "observation", "negative", "unsupported")}
    require(profiles == {"strict": 10, "observation": 8, "negative": 1, "unsupported": 1}, "PROFILE_COUNTS")
    first, second = parsed["diagnostics/visual_facts_first.json"], parsed["diagnostics/visual_facts_second.json"]
    require(isinstance(first, list) and len(first) == 20 and canonical(first) == canonical(second), "FACT_REPEAT_MISMATCH")
    require(all(isinstance(i, dict) and isinstance(i.get("case_id"), str) for i in first), "FACT_REPEAT_CASE_SET")
    round_cases = {i["case_id"]: i for i in first}
    require(set(round_cases) == set(CASE_IDS), "FACT_REPEAT_CASE_SET")
    records = checkpoint.get("qwen_case_records")
    require(isinstance(records, dict) and set(records) == set(CASE_IDS), "CHECKPOINT_QWEN_RECORDS")
    geometry_deltas: list[str] = []
    narrative_present = 0
    fact_map: dict[str, dict[str, Any]] = {}
    for case in CASE_IDS:
        prefix = f"cases/{case}/"
        facts, analysis, director, bundle = (obj(prefix + name) for name in ARTIFACTS[1:2] + ARTIFACTS[:1] + ARTIFACTS[2:])
        fact_hash = digest(canonical({k: v for k, v in facts.items() if k != "fact_digest"}, False))
        require(facts.get("fact_digest") == fact_hash and facts.get("case_id") == case, "FACT_DIGEST_MISMATCH")
        require(canonical(facts) == canonical(round_cases[case]), "CASE_VS_ROUND_FACT_MISMATCH")
        fact_map[case] = facts
        ids = facts.get("fact_ids")
        require(isinstance(ids, list) and bool(ids) and all(isinstance(i, str) for i in ids)
                and len(set(ids)) == len(ids), "FACT_IDS_INVALID")
        for item in (analysis, director):
            require(item.get("case_id") == case and item.get("input_fact_digest") == fact_hash, "CASE_FACT_BINDING")
        refs = director.get("reasoning_based_on_fact_ids")
        require(isinstance(refs, list) and all(isinstance(i, str) and i in ids for i in refs), "UNKNOWN_FACT_REFERENCE")
        require(bundle.get("bundle_type") == "SYNTHETIC_VALIDATION" and bundle.get("case_id") == case,
                "BUNDLE_SCOPE")
        require(bundle.get("image_sha256") == facts.get("image_sha256") == by_case[case].get("image_sha256"), "IMAGE_DIGEST_BINDING")
        checks = bundle.get("checksums")
        require(isinstance(checks, dict) and checks == {
            "vision_facts_sha256": digest(files[prefix + "vision_facts.json"]),
            "reasoning_sha256": digest(files[prefix + "analysis.json"]),
            "director_prompt_sha256": digest(files[prefix + "director_prompt.json"])}, "BUNDLE_INNER_CHECKSUM")
        stories, prompts = analysis.get("story_candidates"), director.get("director_prompts")
        if (isinstance(stories, dict) and isinstance(prompts, dict)
                and all(isinstance(stories.get(k), str) and stories[k].strip() for k in ("safe", "narrative", "dynamic"))
                and all(isinstance(prompts.get(k), str) and prompts[k].strip() for k in ("standard", "dramatic", "plan_b", "technical"))):
            narrative_present += 1
        try:
            measured = measure_bbox_empty_area(facts["person_boxes"], by_case[case]["width"], by_case[case]["height"])
        except (KeyError, TypeError, ValueError):
            raise AuditError("GEOMETRY_INPUT_INVALID") from None
        old = facts.get("negative_space_metrics")
        if not isinstance(old, dict) or any(old.get(k) != measured[k] for k in (
                "left_ratio", "right_ratio", "top_ratio", "bottom_ratio", "total_negative_ratio")):
            geometry_deltas.append(case)

    for group, cases in (("qwen", CASE_IDS), ("qwen-repeat", repeats)):
        for case in cases:
            prefix = f"diagnostics/{group}/{case}/"
            raw, binding = obj(prefix + "raw_response.json"), obj(prefix + "binding_validation.json")
            facts = fact_map[case]
            require(raw.get("case_id") == case and raw.get("input_fact_digest") == facts["fact_digest"], "RAW_FACT_BINDING")
            refs = raw.get("reasoning_based_on_fact_ids")
            require(isinstance(refs, list) and all(isinstance(i, str) and i in facts["fact_ids"] for i in refs), "RAW_UNKNOWN_FACT_REFERENCE")
            require(binding.get("raw_response_sha256") == digest(files[prefix + "raw_response.json"])
                    and binding.get("model_identity_sha256") == identity_hash
                    and binding.get("authoritative_fact_digest") == facts["fact_digest"]
                    and binding.get("echoed_fact_digest") == facts["fact_digest"]
                    and binding.get("echo_match") is True and binding.get("fact_reference_valid") is True
                    and binding.get("validation_status") == "PASS"
                    and type(binding.get("forbidden_field_count")) is int
                    and binding["forbidden_field_count"] == 0 and binding.get("errors") == [], "QWEN_BINDING_MISMATCH")
            if group == "qwen":
                require(records[case] == {"raw_response_sha256": digest(files[prefix + "raw_response.json"]),
                        "binding_evidence_sha256": digest(files[prefix + "binding_validation.json"]),
                        "validation_status": "PASS"}, "CHECKPOINT_RESPONSE_HASH")
    for i in (1, 2):
        require(obj(f"diagnostics/qwen-probe/binding_validation_{i}.json").get("model_identity_sha256") == identity_hash,
                "PROBE_IDENTITY_MISMATCH")
    return {
        "audit_schema": "npi-offline-evidence-audit-v1",
        "result": "ARTIFACT_CONSISTENCY_VERIFIED_NOT_RUNTIME_REVALIDATED",
        "checksums_sha256": checksum_sha256, "file_count": len(files), "case_count": 20,
        "saved_model_identity_sha256": identity_hash, "recorded_gpu_peak_mib": peak,
        "profiles": profiles, "nonempty_story_and_prompt_cases": narrative_present,
        "bbox_proxy_semantic_difference_cases": geometry_deltas,
        "photography_quality": "NOT_EVALUATED", "live_resume": "NOT_EXECUTED",
        "full_json_schema_validation": "NOT_PERFORMED_USE_FROZEN_CANDIDATE_VALIDATORS",
        "independent_review_verdict": "NOT_ISSUED", "production_authorization": False,
        "counter_evidence": "DECLARED_ZERO_NOT_INDEPENDENT_OS_TELEMETRY",
    }


def audit_release(root: Path, checksum_sha256: str) -> dict[str, Any]:
    root = Path(os.path.abspath(root))
    before = load_release(root, checksum_sha256)
    report = inspect_payload(before, checksum_sha256)
    after = load_release(root, checksum_sha256)
    require(before == after, "EVIDENCE_CHANGED_DURING_AUDIT")
    report["before_after_bytes_identical"] = True
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--checksums-sha256", required=True)
    args = parser.parse_args()
    try:
        report = audit_release(args.evidence_root, args.checksums_sha256)
    except AuditError as exc:
        report = {"result": "AUDIT_FAILED", "error_code": str(exc), "production_authorization": False}
        code = 1
    except (OSError, ValueError, TypeError, KeyError, OverflowError):
        report = {"result": "AUDIT_FAILED", "error_code": "INVALID_OR_UNAVAILABLE_EVIDENCE", "production_authorization": False}
        code = 1
    else:
        code = 0
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
