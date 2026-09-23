"""Offline interoperability with Label Studio's documented JSON/tag protocol.

No Label Studio server is installed or contacted. No image is opened. Model
predictions and human annotations stay separate; imported choices never grant
execution authority or make a production Bundle. All code here is NPI-authored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import parse_qs, urlsplit

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry
from referencing.exceptions import NoSuchResource

MAX_BYTES = 16 * 1024 * 1024
CASE_IDS = tuple(f"real20-{i:03d}" for i in range(1, 21))
DECISIONS = {"ACCEPT", "EDIT", "REJECT"}
ISSUES = {"COUNT", "POSE", "SEGMENTATION", "COMPOSITION", "UNSUPPORTED_CLAIM", "ADVICE"}


class ReviewExchangeError(ValueError):
    """Stable error codes, not paths or annotation text."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ReviewExchangeError(code)


def canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_sha(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def parse(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "REVIEW_DUPLICATE_JSON_MEMBER")
            result[key] = value
        return result

    def finite(text: str) -> float:
        value = float(text)
        require(math.isfinite(value), "REVIEW_NONFINITE_JSON")
        return value

    def invalid(_text: str) -> Any:
        raise ReviewExchangeError("REVIEW_NONFINITE_JSON")

    require(len(data) <= MAX_BYTES, "REVIEW_SIZE_LIMIT")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                          parse_float=finite, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ReviewExchangeError("REVIEW_INVALID_JSON") from exc


def no_remote_resource(uri: str) -> Any:
    raise NoSuchResource(ref=uri)


# Reuse the existing jsonschema/referencing dependencies instead of inventing
# another validator. Only this fixed local schema is selected by the program.
BINDING_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "required": ["schema_version", "evaluation_sha256", "candidate_commit", "case_id",
                 "source_row_sha256", "source_image_sha256", "fact_digest"],
    "properties": {
        "schema_version": {"const": "npi-label-studio-binding-v1"},
        "evaluation_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$", "minLength": 64, "maxLength": 64},
        "candidate_commit": {"type": "string", "pattern": "^[0-9a-f]{40}$", "minLength": 40, "maxLength": 40},
        "case_id": {"enum": list(CASE_IDS)},
        "source_row_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$", "minLength": 64, "maxLength": 64},
        "source_image_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$", "minLength": 64, "maxLength": 64},
        "fact_digest": {"type": "string", "pattern": "^[0-9a-f]{64}$", "minLength": 64, "maxLength": 64},
    },
}
BINDING_VALIDATOR = Draft202012Validator(
    BINDING_SCHEMA, registry=Registry(retrieve=no_remote_resource)
)


def _preview_url(value: object, case_id: str) -> str:
    require(isinstance(value, str), "REVIEW_PREVIEW_URL_INVALID")
    url = urlsplit(value)
    query = parse_qs(url.query, keep_blank_values=True, strict_parsing=True)
    require(not url.scheme and not url.netloc and not url.fragment
            and url.path == "/data/local-files/" and set(query) == {"d"}
            and len(query["d"]) == 1, "REVIEW_REMOTE_OR_UNSCOPED_PREVIEW")
    relative = query["d"][0]
    path = PurePosixPath(relative)
    require(path.parts == ("real20-previews", path.name)
            and relative == str(path) and path.stem == case_id
            and path.suffix.lower() in {".jpg", ".png", ".webp"}
            and re.fullmatch(r"real20-previews/real20-[0-9]{3}\.(jpg|png|webp)", relative) is not None,
            "REVIEW_PREVIEW_OUTSIDE_APPROVED_SUBDIRECTORY")
    return value


def export_tasks(
    evaluation_bytes: bytes, *, expected_sha256: str, previews: Mapping[str, Any]
) -> list[dict[str, Any]]:
    """Convert one completed evaluation, not raw photos, into importable tasks.

    previews maps the 19 canonical IDs to explicit local preview URL + source
    image SHA. Preview pixels must be prepared separately under Owner authority;
    this converter verifies the mapping, not the preview file bytes.
    """
    require(is_sha(expected_sha256) and sha(evaluation_bytes) == expected_sha256,
            "REVIEW_EVALUATION_HASH_MISMATCH")
    value = parse(evaluation_bytes)
    require(isinstance(value, dict) and value.get("status") == "REAL20_COMPLETE"
            and value.get("schema_version") == "npi-real20-evaluation-v1"
            and value.get("review_decision") == "PENDING_HUMAN_REVIEW"
            and all(value.get(key) is False for key in ("sqlite_write", "app_write", "production_bundle")),
            "REVIEW_EVALUATION_NOT_ELIGIBLE")
    rows = value.get("assets")
    require(isinstance(rows, list) and len(rows) == 20
            and all(isinstance(row, dict) for row in rows), "REVIEW_CASE_SET_INVALID")
    by_id = {row.get("case_id"): row for row in rows}
    require(set(by_id) == set(CASE_IDS), "REVIEW_CASE_SET_INVALID")
    canonical_ids = {key for key, row in by_id.items() if row.get("action") == "INFER_ONCE"}
    require(len(canonical_ids) == 19 and set(previews) == canonical_ids,
            "REVIEW_PREVIEW_SET_INVALID")
    tasks: list[dict[str, Any]] = []
    for ordinal, case_id in enumerate(CASE_IDS, 1):
        row = by_id[case_id]
        target_id = case_id if case_id in canonical_ids else row.get("duplicate_of")
        require(target_id in canonical_ids, "REVIEW_DUPLICATE_REFERENCE_INVALID")
        if target_id != case_id:
            require(row.get("action") == "REFERENCE_ONLY", "REVIEW_DUPLICATE_REFERENCE_INVALID")
        target = by_id[target_id]
        facts = target.get("facts")
        require(isinstance(facts, dict) and facts.get("schema_version") == "1.2"
                and facts.get("case_id") == target_id, "REVIEW_FACTS_INVALID")
        fact_bytes = json.dumps(
            {key: item for key, item in facts.items() if key != "fact_digest"},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
        require(sha(fact_bytes) == facts.get("fact_digest"), "REVIEW_FACT_DIGEST_MISMATCH")
        image_sha = target.get("source_sha256")
        require(is_sha(image_sha) and facts.get("image_sha256") == image_sha,
                "REVIEW_IMAGE_BINDING_MISMATCH")
        preview = previews[target_id]
        require(isinstance(preview, Mapping) and set(preview) == {"image_url", "source_sha256"}
                and preview["source_sha256"] == image_sha, "REVIEW_PREVIEW_BINDING_MISMATCH")
        image_url = _preview_url(preview["image_url"], target_id)
        interpretation = target.get("interpretation")
        advice = json.dumps(interpretation, ensure_ascii=False, sort_keys=True, indent=2)
        binding = {
            "schema_version": "npi-label-studio-binding-v1",
            "evaluation_sha256": expected_sha256,
            "candidate_commit": value.get("candidate_commit"),
            "case_id": case_id,
            "source_row_sha256": sha(canonical(row)),
            "source_image_sha256": image_sha,
            "fact_digest": facts["fact_digest"],
        }
        require(not list(BINDING_VALIDATOR.iter_errors(binding)), "REVIEW_BINDING_SCHEMA_INVALID")
        # Do not preselect ACCEPT or create any annotations on the user's behalf.
        tasks.append({
            "id": ordinal,
            "data": {
                "case_id": case_id,
                "duplicate_of": target_id if target_id != case_id else "none",
                "image": image_url,
                "facts_text": json.dumps(facts, ensure_ascii=False, sort_keys=True, indent=2),
                "advice_text": advice,
                "npi_binding": binding,
            },
            "predictions": [{
                "model_version": str(value.get("candidate_commit")),
                "result": [{"from_name": "revision", "to_name": "photo", "type": "textarea",
                            "value": {"text": [advice]}}],
            }],
            "annotations": [],
        })
    return tasks


def import_annotations(
    exported: object, *, original_tasks: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Import human records without upgrading them to Owner or Bundle approval.

    Canceled, missing and conflicting annotations are surfaced, never silently
    accepted. Predictions alone are not human work. Original task data and model
    predictions must be unchanged, preventing stale/cross-evaluation imports.
    """
    require(isinstance(exported, list) and len(exported) <= 20
            and all(isinstance(task, dict) for task in exported), "REVIEW_EXPORT_INVALID")
    require(len(original_tasks) == 20, "REVIEW_ORIGINAL_TASKS_INVALID")
    original = {task["data"]["case_id"]: task for task in original_tasks}
    require(set(original) == set(CASE_IDS), "REVIEW_ORIGINAL_TASKS_INVALID")
    rows: dict[str, Any] = {}
    blockers: list[dict[str, str]] = []
    for task in exported:
        data = task.get("data")
        require(isinstance(data, dict), "REVIEW_TASK_DATA_INVALID")
        case_id = data.get("case_id")
        require(case_id in original and case_id not in rows, "REVIEW_UNKNOWN_OR_DUPLICATE_TASK")
        source = original[case_id]
        predictions = task.get("predictions", [])
        require(isinstance(predictions, list) and all(isinstance(p, dict) for p in predictions),
                "REVIEW_ORIGINAL_DATA_CHANGED")
        predicted_values = [{"model_version": p.get("model_version"), "result": p.get("result")}
                            for p in predictions]
        original_values = [{"model_version": p.get("model_version"), "result": p.get("result")}
                           for p in source["predictions"]]
        require(data == source["data"] and predicted_values == original_values,
                "REVIEW_ORIGINAL_DATA_CHANGED")
        require(not list(BINDING_VALIDATOR.iter_errors(data.get("npi_binding"))),
                "REVIEW_BINDING_SCHEMA_INVALID")
        annotations = task.get("annotations", [])
        require(isinstance(annotations, list) and all(isinstance(a, dict) for a in annotations),
                "REVIEW_ANNOTATIONS_INVALID")
        rows[case_id] = None
        active = [item for item in annotations if item.get("was_cancelled") is False]
        if len(active) != 1:
            blockers.append({"case_id": case_id, "reason": "NO_UNIQUE_NONCANCELLED_ANNOTATION"})
            continue
        annotation = active[0]
        reviewer = annotation.get("completed_by")
        if isinstance(reviewer, dict):
            reviewer = reviewer.get("id")
        require(type(reviewer) is int and reviewer > 0, "REVIEW_REVIEWER_ID_REQUIRED")
        annotation_id = annotation.get("id")
        require(type(annotation_id) is int and annotation_id > 0, "REVIEW_ANNOTATION_ID_REQUIRED")
        values = annotation.get("result")
        require(isinstance(values, list), "REVIEW_ANNOTATION_RESULT_INVALID")
        fields: dict[str, Any] = {}
        for item in values:
            require(isinstance(item, dict) and item.get("from_name") in {"decision", "issues", "revision", "notes"}
                    and item.get("from_name") not in fields and item.get("to_name") == "photo",
                    "REVIEW_ANNOTATION_FIELDS_INVALID")
            fields[item["from_name"]] = item
        decision_field = fields.get("decision", {})
        choices = decision_field.get("value", {}).get("choices")
        require(decision_field.get("type") == "choices" and isinstance(choices, list)
                and len(choices) == 1 and choices[0] in DECISIONS, "REVIEW_HUMAN_DECISION_REQUIRED")
        issue_field = fields.get("issues", {"type": "choices", "value": {"choices": []}})
        issues = issue_field.get("value", {}).get("choices")
        require(issue_field.get("type") == "choices" and isinstance(issues, list)
                and all(isinstance(issue, str) and issue in ISSUES for issue in issues),
                "REVIEW_ISSUES_INVALID")
        text_fields: dict[str, list[str]] = {}
        for name in ("revision", "notes"):
            item = fields.get(name, {"type": "textarea", "value": {"text": []}})
            text = item.get("value", {}).get("text")
            require(item.get("type") == "textarea" and isinstance(text, list)
                    and all(isinstance(t, str) and len(t) <= 64000 for t in text), "REVIEW_TEXT_INVALID")
            text_fields[name] = text
        require(choices[0] != "EDIT" or any(t.strip() for t in text_fields["notes"]),
                "REVIEW_EDIT_REASON_REQUIRED")
        rows[case_id] = {
            "case_id": case_id, "binding": data["npi_binding"],
            "reviewer_id": reviewer, "annotation_id": annotation_id,
            "human_decision": choices[0], "issues": sorted(set(issues)), **text_fields,
            "annotation_sha256": sha(canonical(annotation)),
            "owner_approved": False, "bundle_eligible": False,
        }
    for case_id in CASE_IDS:
        if case_id not in rows:
            blockers.append({"case_id": case_id, "reason": "MISSING_TASK"})
    decisions = [rows[key] for key in CASE_IDS if rows.get(key) is not None]
    return {
        "schema_version": "npi-label-studio-human-review-v1",
        "status": "HUMAN_REVIEW_RECORDED_PENDING_OWNER" if not blockers else "HUMAN_REVIEW_INCOMPLETE",
        "review_count": len(decisions), "records": decisions, "blockers": blockers,
        "original_tasks_sha256": sha(canonical(list(original_tasks))),
        "imported_export_sha256": sha(canonical(exported)),
        "execution_authorized": False, "production_bundle_created": False,
    }


def read_json_file(path: Path) -> bytes:
    require(path.is_absolute() and path.suffix == ".json" and ".." not in path.parts
            and not str(path).startswith(("\\\\", "//"))
            and all(":" not in p for p in path.parts[1:]), "REVIEW_CONTROL_PATH_INVALID")
    for parent in path.parents:
        info = parent.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                "REVIEW_REPARSE_DENIED")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and not getattr(before, "st_file_attributes", 0) & 0x400
            and before.st_size <= MAX_BYTES, "REVIEW_REGULAR_JSON_REQUIRED")
    with path.open("rb") as handle:
        data = handle.read(MAX_BYTES + 1)
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            and len(data) == before.st_size, "REVIEW_INPUT_CHANGED")
    return data


def _overlaps(left: Path, right: Path) -> bool:
    first = os.path.normcase(str(left))
    second = os.path.normcase(str(right))
    try:
        return os.path.commonpath((first, second)) in (first, second)
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    export = commands.add_parser("export")
    export.add_argument("--evaluation", type=Path, required=True)
    export.add_argument("--evaluation-sha256", required=True)
    export.add_argument("--preview-map", type=Path, required=True)
    imported = commands.add_parser("import")
    imported.add_argument("--annotations", type=Path, required=True)
    imported.add_argument("--original-tasks", type=Path, required=True)
    imported.add_argument("--original-tasks-sha256", required=True)
    for command in (export, imported):
        command.add_argument("--out", type=Path, required=True)
        command.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        # A lexical exclusion only: do not stat or traverse the original-photo
        # directory merely to perform an artifact-only review conversion.
        require(args.source_root.is_absolute() and ".." not in args.source_root.parts
                and not str(args.source_root).startswith(("\\\\", "//"))
                and all(":" not in p for p in args.source_root.parts[1:]),
                "REVIEW_SOURCE_BOUNDARY_INVALID")
        inputs = ([args.evaluation, args.preview_map] if args.mode == "export"
                  else [args.original_tasks, args.annotations])
        require(all(path.is_absolute() and not _overlaps(path, args.source_root)
                    for path in [*inputs, args.out]), "REVIEW_SOURCE_ACCESS_DENIED")
        require(all(args.out != path for path in inputs), "REVIEW_OUTPUT_INPUT_COLLISION")
        require(args.out.is_absolute() and args.out.suffix == ".json"
                and ".." not in args.out.parts and not str(args.out).startswith(("\\\\", "//"))
                and all(":" not in part for part in args.out.parts[1:]), "REVIEW_OUTPUT_PATH_INVALID")
        for parent in args.out.parents:
            info = parent.lstat()
            require(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
                    and not (parent / ".git").exists(), "REVIEW_OUTPUT_IN_GIT_OR_REPARSE")
        if args.mode == "export":
            data = read_json_file(args.evaluation)
            previews = parse(read_json_file(args.preview_map))
            require(isinstance(previews, Mapping), "REVIEW_PREVIEW_MAP_INVALID")
            result = export_tasks(data, expected_sha256=args.evaluation_sha256, previews=previews)
        else:
            original = read_json_file(args.original_tasks)
            require(is_sha(args.original_tasks_sha256) and sha(original) == args.original_tasks_sha256,
                    "REVIEW_ORIGINAL_TASKS_HASH_MISMATCH")
            result = import_annotations(parse(read_json_file(args.annotations)), original_tasks=parse(original))
        output = canonical(result)
        # Explicit, fresh, Owner-controlled external destination only. Not a
        # protected-source writer or a replacement for the native runtime I/O.
        with args.out.open("xb") as handle:
            handle.write(output)
            handle.flush()
            os.fsync(handle.fileno())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        error = str(exc) if isinstance(exc, ReviewExchangeError) else "REVIEW_INPUT_OR_OUTPUT_INVALID"
        print(json.dumps({"status": "REVIEW_EXCHANGE_FAILED", "error_code": error}))
        return 1
    print(json.dumps({"status": "REVIEW_EXCHANGE_WRITTEN", "sha256": sha(output),
                      "execution_authorized": False, "production_bundle_created": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
