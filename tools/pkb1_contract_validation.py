#!/usr/bin/env python3
"""Synthetic PKB1 contract validation only.

Not a producer golden vector generator. Legacy Photo Intelligence Bundle
remains a separate contract.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CONTRACT_MODE = "SYNTHETIC_CONTRACT_TEST_ONLY"


class BundleContractError(Exception):
    pass


def _token(name: str, value: str) -> bytes:
    def one(text: str) -> bytes:
        raw = text.encode("utf-8")
        return str(len(raw)).encode("ascii") + b":" + raw + b"\n"
    return one(name) + one(value)


def pkb1_canonical_bytes(payload: dict) -> bytes:
    out = bytearray(b"PKB1\n")
    refs = payload["references"]
    fixed = [
        ("contract_version", payload["contract_version"]),
        ("bundle_id", payload["bundle_id"]),
        ("source.origin", payload["source"]["origin"]),
        ("source.producer_id", payload["source"]["producer_id"]),
        ("source.release_id", payload["source"]["release_id"]),
        ("references.count", str(len(refs))),
    ]
    for name, value in fixed:
        out.extend(_token(name, str(value)))
    fields = ["scene", "background_story", "lighting", "composition", "subject_intent", "emotion", "pose_template", "camera_position", "director_prompt"]
    for i, ref in enumerate(refs):
        out.extend(_token(f"references[{i}].reference_id", ref["reference_id"]))
        for field in fields:
            out.extend(_token(f"references[{i}].photography.{field}", ref["photography"][field]))
    return bytes(out)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_bundle(root: Path) -> dict:
    payload = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
    return {"mode": CONTRACT_MODE, "pkb1_payload_sha256": sha256_bytes(pkb1_canonical_bytes(payload)), "ready_for_t14": False}
