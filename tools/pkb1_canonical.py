"""Synthetic PKB1 contract-only utilities.

This is not a producer release generator and never creates golden vectors.
"""
from __future__ import annotations

import hashlib


def _token(name: str, value: str) -> bytes:
    raw = value.encode("utf-8")
    return f"{len(raw)}:".encode("ascii") + raw + b"\n"


def canonical_pkb1_bytes(payload: dict) -> bytes:
    out = bytearray(b"PKB1\n")
    ordered = [
        ("contract_version", payload["contract_version"]),
        ("bundle_id", payload["bundle_id"]),
        ("source.origin", payload["source"]["origin"]),
        ("source.producer_id", payload["source"]["producer_id"]),
        ("source.release_id", payload["source"]["release_id"]),
        ("references.count", str(len(payload["references"]))),
    ]
    for i, ref in enumerate(payload["references"]):
        ordered.extend((f"references[{i}].{k}", ref["photography"][k]) for k in [
            "reference_id", "scene", "background_story", "lighting",
            "composition", "subject_intent", "emotion", "pose_template",
            "camera_position", "director_prompt",
        ])
    for name, value in ordered:
        out.extend(_token(name, str(value)))
    return bytes(out)


def pkb1_sha256(payload: dict) -> str:
    return hashlib.sha256(canonical_pkb1_bytes(payload)).hexdigest()
