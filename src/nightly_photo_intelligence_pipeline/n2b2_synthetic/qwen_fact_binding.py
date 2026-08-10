"""Request-bound Qwen fact contract helpers.

The vision facts are authoritative.  This module only derives a request schema
and redacted hashes; it never repairs or injects fields into a model response.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def bind_reasoning_schema(
    base_schema: dict[str, Any], *, case_id: str, fact_digest: str, fact_ids: list[str]
) -> dict[str, Any]:
    """Return a deep-copied schema bound to this exact request.

    The caller's base schema is never mutated.  The schema is an additional
    decoding constraint, not a substitute for post-response validation.
    """

    bound = copy.deepcopy(base_schema)
    properties = bound.setdefault("properties", {})
    properties["case_id"] = {"const": case_id}
    properties["input_fact_digest"] = {"const": fact_digest}

    reasoning = properties.setdefault("reasoning_based_on_fact_ids", {})
    reasoning_items = reasoning.setdefault("items", {})
    reasoning_items["enum"] = list(fact_ids)

    uncertainty = bound.setdefault("$defs", {}).setdefault("qwen_uncertainty", {})
    uncertainty_properties = uncertainty.setdefault("properties", {})
    related = uncertainty_properties.setdefault("related_fact_ids", {})
    related_items = related.setdefault("items", {})
    related_items["enum"] = list(fact_ids)
    return bound


@dataclass(frozen=True)
class BoundReasoningRequest:
    case_id: str
    fact_digest: str
    fact_ids: tuple[str, ...]
    schema: dict[str, Any]
    schema_sha256: str
    prompt: str
    prompt_sha256: str


def make_bound_request(
    base_schema: dict[str, Any],
    *,
    case_id: str,
    fact_digest: str,
    fact_ids: list[str],
    prompt: str,
) -> BoundReasoningRequest:
    schema = bind_reasoning_schema(
        base_schema, case_id=case_id, fact_digest=fact_digest, fact_ids=fact_ids
    )
    return BoundReasoningRequest(
        case_id=case_id,
        fact_digest=fact_digest,
        fact_ids=tuple(fact_ids),
        schema=schema,
        schema_sha256=sha256_json(schema),
        prompt=prompt,
        prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
    )
