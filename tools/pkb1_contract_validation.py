#!/usr/bin/env python3
"""PKB1 contract validation only.

This tool validates Bundle contract structure. It does NOT create producer
Golden Vectors, run models, read real photos, or authorize T14 compatibility.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


CONTRACT_MODE = "SYNTHETIC_CONTRACT_TEST_ONLY"


class BundleContractError(Exception):
    pass


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_bundle(root: Path) -> dict:
    bundle = root / "bundle.json"
    checksums = root / "CHECKSUMS.sha256"
    if not bundle.exists() or not checksums.exists():
        raise BundleContractError("missing bundle contract files")

    payload = json.loads(bundle.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BundleContractError("bundle must be object")

    if "schema_version" not in payload:
        raise BundleContractError("missing schema_version")

    digest = sha256_bytes(canonical_json_bytes(payload))
    return {
        "mode": CONTRACT_MODE,
        "schema_version": payload["schema_version"],
        "canonical_bundle_sha256": digest,
        "ready_for_t14": False,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    print(json.dumps(validate_bundle(args.bundle), indent=2))
