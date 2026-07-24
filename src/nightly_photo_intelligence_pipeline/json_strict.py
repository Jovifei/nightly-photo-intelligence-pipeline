"""Fail-closed JSON loading for authorization and other security contracts.

JSON Schema sees only the Python object produced by a parser.  The standard
``json.loads`` silently keeps the last value of a duplicate object member,
which is unsafe for authorization, approval, and artifact-gate documents.
This module is deliberately small: callers parse raw bytes here first, then
perform their existing structural Schema and semantic authorization checks.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypeAlias

from .domain.errors import DuplicateJsonMemberError

JsonObject: TypeAlias = dict[str, Any]


def _reject_duplicate_members(pairs: Sequence[tuple[str, Any]]) -> JsonObject:
    """Build one JSON object, rejecting a duplicate member in that object.

    ``object_pairs_hook`` runs separately for each object, so equal member
    names in different array entries remain valid. JSON member names are case
    sensitive; ``status`` and ``Status`` therefore remain distinct.
    """

    result: JsonObject = {}
    for name, value in pairs:
        if name in result:
            raise DuplicateJsonMemberError(name)
        result[name] = value
    return result


def loads_json_strict(payload: str | bytes | bytearray) -> Any:
    """Parse JSON and reject duplicate object members before Schema checks."""

    return json.loads(payload, object_pairs_hook=_reject_duplicate_members)


def load_json_strict(path: Path | str) -> Any:
    """Read UTF-8 JSON from *path* with duplicate-member rejection.

    The domain error deliberately identifies only the duplicate member name;
    it does not disclose a local path or document payload.
    """

    return loads_json_strict(Path(path).read_text(encoding="utf-8"))
