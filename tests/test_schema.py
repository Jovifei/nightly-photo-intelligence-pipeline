"""AT-N0-SCHEMA-01: valid example passes. AT-N0-SCHEMA-02: invalid examples fail."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

pytestmark = pytest.mark.acceptance


def _core_item_errors(item: dict[str, Any]) -> list[str]:
    """Mirror of tools/verify_handoff.py core_item_errors (business rules)."""
    out: list[str] = []
    required = {
        "schema_version",
        "asset_id",
        "source_reference",
        "observed_facts",
        "photographic_interpretation",
        "story_candidates",
        "pose_template",
        "director_prompts",
        "uncertainties",
        "review",
        "provenance",
        "output_hashes",
    }
    missing = required - set(item)
    if missing:
        out.append("missing:" + ",".join(sorted(missing)))
    source = item.get("source_reference", {})
    name = source.get("sanitized_name", "")
    if not isinstance(name, str) or "/" in name or "\\" in name or re.match(r"^[A-Za-z]:", name):
        out.append("absolute-or-unsanitized-source-name")
    review = item.get("review", {})
    if review.get("status") == "APPROVED" and review.get("approved_by_human") is not True:
        out.append("approved-without-human")
    producer = item.get("pose_template", {}).get("producer", {}).get("producer_type")
    if producer not in {"PROFESSIONAL_POSE_MODEL", "DETERMINISTIC_GEOMETRY"}:
        out.append("invalid-pose-producer")
    stories = item.get("story_candidates", {})
    if set(stories) != {"safe", "narrative", "dynamic"}:
        out.append("story-triplet-invalid")
    return out


@pytest.fixture(scope="module")
def validator(project_root: Path):
    pytest.importorskip("jsonschema")
    from jsonschema import Draft202012Validator  # type: ignore
    from referencing import Registry, Resource  # type: ignore

    schema_dir = project_root / "schemas"
    item_schema = __import__("json").loads(
        (schema_dir / "photo_intelligence_item_v1.schema.json").read_text("utf-8")
    )
    registry: Any = Registry()
    for path in schema_dir.glob("*.json"):
        schema = __import__("json").loads(path.read_text("utf-8"))
        if "$schema" not in schema:
            continue
        resource = Resource.from_contents(schema)
        if "$id" in schema:
            registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(path.resolve().as_uri(), resource)
    return Draft202012Validator(item_schema, registry=registry)


def test_at_n0_schema_01_valid_example_passes(project_root: Path, validator) -> None:
    """AT-N0-SCHEMA-01: the valid item passes core rules and Draft 2020-12 schema."""
    import json

    valid = json.loads(
        (project_root / "examples/valid/photo_intelligence_item_v1.json").read_text("utf-8")
    )
    assert _core_item_errors(valid) == [], "valid item must pass core rules"
    errors = sorted(validator.iter_errors(valid), key=lambda e: list(e.path))
    assert errors == [], f"valid item must pass schema: {errors[0].message if errors else ''}"


def test_at_n0_schema_02_invalid_examples_fail(project_root: Path, validator) -> None:
    """AT-N0-SCHEMA-02: each invalid example fails for its expected core reason."""
    import json

    expectations = {
        "item_absolute_path.json": "absolute-or-unsanitized-source-name",
        "item_auto_approved.json": "approved-without-human",
        "item_pose_from_vlm.json": "invalid-pose-producer",
    }
    for name, expected in expectations.items():
        item = json.loads((project_root / "examples/invalid" / name).read_text("utf-8"))
        found = _core_item_errors(item)
        assert expected in found, f"{name} did not fail expected rule {expected}; found {found}"
