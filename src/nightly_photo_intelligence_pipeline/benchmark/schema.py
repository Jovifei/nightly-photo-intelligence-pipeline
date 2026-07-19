"""Fail-closed Draft 2020-12 plus finite-number validation for N2A documents."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from functools import cache, lru_cache
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from jsonschema.validators import extend  # type: ignore[import-untyped]

from .._paths import find_project_root
from ..domain.errors import SchemaValidationFailedError
from ..domain.numeric import reject_non_finite_numbers
from ..segmentation.contracts import validate_normalized_bbox_mapping


def _is_finite_json_number(_: object, instance: object) -> bool:
    """Keep Python in-memory NaN/Infinity from bypassing JSON syntax rules."""

    return (
        not isinstance(instance, bool)
        and isinstance(instance, (int, float))
        and math.isfinite(float(instance))
    )


StrictDraft202012Validator = extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine("number", _is_finite_json_number),
)


@lru_cache(maxsize=1)
def _schema() -> dict[str, Any]:
    path = find_project_root() / "schemas" / "n2a_pose_segmentation.schema.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@cache
def _fragment_validator(definition: str) -> Any:
    document = _schema()
    return StrictDraft202012Validator(
        {
            "$schema": document["$schema"],
            "$defs": document["$defs"],
            "$ref": f"#/$defs/{definition}",
        }
    )


def strict_json_dumps(document: object, *, indent: int | None = None) -> str:
    """Serialize only finite JSON values; used by all public N2A renderers."""

    reject_non_finite_numbers(document)
    return json.dumps(
        document,
        allow_nan=False,
        ensure_ascii=False,
        indent=indent,
        sort_keys=True,
    )


def _prevalidate_semantics(document: Mapping[str, object]) -> None:
    if document.get("contract_type") != "SEGMENTATION_CASE":
        return
    box = document.get("bbox")
    if isinstance(box, Mapping):
        validate_normalized_bbox_mapping(cast(Mapping[str, object], box))


def _validate_report_semantics(document: Mapping[str, object]) -> None:
    if document.get("contract_type") != "BENCHMARK_REPORT":
        return
    aggregate = document.get("aggregate")
    if not isinstance(aggregate, Mapping):
        return
    total = aggregate.get("total_cases")
    passed = aggregate.get("passed_cases")
    failed = aggregate.get("failed_cases")
    errors = aggregate.get("error_cases")
    pass_rate = aggregate.get("pass_rate")
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (total, passed, failed, errors)
    ):
        return
    if not isinstance(pass_rate, (int, float)) or isinstance(pass_rate, bool):
        return
    total_count = cast(int, total)
    passed_count = cast(int, passed)
    failed_count = cast(int, failed)
    error_count = cast(int, errors)
    if (
        total_count != passed_count + failed_count + error_count
        or total_count < 1
        or pass_rate != passed_count / total_count
    ):
        raise SchemaValidationFailedError("benchmark aggregate is internally inconsistent")


def _validate(validator: Any, document: Mapping[str, object], *, fragment: bool) -> None:
    reject_non_finite_numbers(document)
    _prevalidate_semantics(document)
    strict_json_dumps(document)
    errors = list(validator.iter_errors(document))
    if errors:
        message = (
            "N2A contract fragment does not satisfy the public schema"
            if fragment
            else ("N2A document does not satisfy the public schema")
        )
        raise SchemaValidationFailedError(message)
    _validate_report_semantics(document)


def validate_document(document: Mapping[str, object]) -> None:
    """Validate every public N2A document through the one strict entrypoint."""

    _validate(StrictDraft202012Validator(_schema()), document, fragment=False)


def validate_fragment(definition: str, document: Mapping[str, object]) -> None:
    """Validate an N2A DTO fragment through the same finite-number boundary."""

    _validate(_fragment_validator(definition), document, fragment=True)


def clear_schema_cache() -> None:
    """Test-only cache reset; does not modify schema content."""

    _schema.cache_clear()
    _fragment_validator.cache_clear()
