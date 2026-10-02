#!/usr/bin/env python3
"""Synthetic PKB1 contract validation only.

This is not a producer golden vector generator. The legacy Photo Intelligence
Bundle contract remains separate from App PKB1 Consumer v1.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

CONTRACT_MODE = "SYNTHETIC_CONTRACT_TEST_ONLY"


class BundleContractError(Exception):
    pass


def _token(name: str, value: str) -> bytes:
    """Encode name token then value token using UTF-8 byte lengths."""
    def one(value: str) -> bytes:
        raw = value.encode("utf-8")
        return str(len(raw)).encode("ascii") + b":" + raw + b"\n"
    return one(name) + one(value)


def pkb1_canonical_bytes(payload: dict) -> bytes:
    refs = payload["references"]
    out = bytearray(b"PKB1\n")
    ordered = [
        ("contract_version", payload["contract_version"]),
        ("bundle_id", payload["bundle_id"]),
        ("source.origin", payload["source"]["origin"]),
        ("source.producer_id", payload["source"]["producer_id"]),
        ("source.release_id", payload["source"]["release_id"]),
        ("references.count", str(len(refs))),
    ]
    for name, value in ordered:
        out.extend(_token(name, str(value)))
    fields = [
        "scene", "background_story", "lighting", "composition",
        "subject_intent", "emotion", "pose_template",
        "camera_position", "director_prompt",
    ]
    for index, ref in enumerate(refs):
        out.extend(_token(f"references[{index}].reference_id", ref["reference_id"]))
        for field in fields:
            out.extend(_token(f"references[{index}].photography.{field}", ref["photography"][field]))
    return bytes(out)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_bundle(root: Path) -> dict:
    payload = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
    digest = sha256_bytes(pkb1_canonical_bytes(payload))
    return {"mode": CONTRACT_MODE, "pkb1_payload_sha256": digest, "ready_for_t14": False}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    print(json.dumps(validate_bundle(parser.parse_args().bundle), indent=2))
