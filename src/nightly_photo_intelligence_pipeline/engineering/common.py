"""Strict JSON and stable, path-free errors for the engineering repair."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any


class EngineeringError(ValueError):
    """A stable diagnostic code; do not include private paths in public errors."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise EngineeringError(code)


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_digest(value: object, length: int = 64) -> bool:
    return isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is not None


def strict_json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "NPI_DUPLICATE_JSON_MEMBER")
            result[key] = value
        return result

    def number(text: str) -> float:
        value = float(text)
        require(math.isfinite(value), "NPI_NONFINITE_NUMBER")
        return value

    def invalid(_: str) -> None:
        raise EngineeringError("NPI_NONFINITE_NUMBER")

    try:
        return json.loads(
            data.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_float=number,
            parse_constant=invalid,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise EngineeringError("NPI_INVALID_JSON") from exc
