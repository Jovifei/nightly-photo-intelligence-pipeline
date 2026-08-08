"""Validate qwen3.5:9b photography-reasoning output (CODEX §9).

The VLM output must:

* validate against ``n2b2_photography_reasoning.schema.json``;
* contain **zero** forbidden fields;
* echo the input ``fact_digest`` exactly;
* reference only fact_ids that exist in the authoritative vision facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:  # jsonschema is a project dependency (.venv).
    import jsonschema  # type: ignore[import-untyped]
    from jsonschema import Draft202012Validator
except Exception:  # pragma: no cover - dependency present in .venv
    jsonschema = None
    Draft202012Validator = None

FORBIDDEN_FIELDS = {
    "person_count",
    "bbox",
    "keypoints",
    "mask",
    "pose_confidence",
    "segmentation_confidence",
    "EXIF",
    "exact_focal_length",
    "exact_camera_distance",
    "copyright_status",
    "real_mental_state",
}


@dataclass
class ReasoningValidation:
    ok: bool
    errors: list[str] = field(default_factory=list)
    forbidden_field_count: int = 0


def validate_reasoning(
    output: dict[str, Any],
    *,
    input_fact_digest: str,
    valid_fact_ids: list[str],
    schema: dict[str, Any],
) -> ReasoningValidation:
    result = ReasoningValidation(ok=True)

    present_forbidden = sorted(set(output.keys()) & FORBIDDEN_FIELDS)
    result.forbidden_field_count = len(present_forbidden)
    if present_forbidden:
        result.ok = False
        result.errors.append(f"forbidden fields present: {present_forbidden}")

    if Draft202012Validator is not None:
        validator = Draft202012Validator(schema)
        for err in sorted(validator.iter_errors(output), key=lambda e: list(e.path)):
            result.ok = False
            result.errors.append(f"schema: {list(err.path)} {err.message}")
    elif jsonschema is None:  # pragma: no cover
        result.ok = False
        result.errors.append("jsonschema unavailable for reasoning validation")

    echoed = output.get("input_fact_digest")
    if echoed != input_fact_digest:
        result.ok = False
        result.errors.append(
            f"input_fact_digest mismatch: echoed={echoed!r} expected={input_fact_digest!r}"
        )

    referenced = output.get("reasoning_based_on_fact_ids", [])
    valid_set = set(valid_fact_ids)
    unknown = [fid for fid in referenced if fid not in valid_set]
    if unknown:
        result.ok = False
        result.errors.append(f"unknown fact_ids referenced: {unknown}")

    return result
