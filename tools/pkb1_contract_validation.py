#!/usr/bin/env python3
"""Bounded offline PKB1 digest check; not full schema or T14 validation."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys

try:
    from .pkb1_canonical import canonical_pkb1_bytes as pkb1_canonical_bytes
except ImportError:
    from pkb1_canonical import canonical_pkb1_bytes as pkb1_canonical_bytes

CONTRACT_MODE = "SYNTHETIC_CONTRACT_TEST_ONLY"
MAX_INPUT_BYTES = 512 * 1024


class BundleContractError(ValueError):
    pass


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BundleContractError("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(value):
    raise BundleContractError("non-finite JSON constant")


def validate_bundle(root: Path):
    path = root / "bundle.json" if root.is_dir() else root
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise BundleContractError("input exceeds 512 KiB")
        payload = json.loads(raw.decode("utf-8", errors="strict"),
                             object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        digest = sha256_bytes(pkb1_canonical_bytes(payload))
        integrity = payload["integrity"]
        declared = integrity["payload_sha256"]
        if (integrity["algorithm"] != "SHA-256" or not isinstance(declared, str)
                or re.fullmatch(r"[0-9a-fA-F]{64}", declared) is None or declared.lower() != digest):
            raise BundleContractError("integrity digest mismatch")
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as exc:
        raise BundleContractError("invalid PKB1 input") from exc
    return {"mode": CONTRACT_MODE, "pkb1_payload_sha256": digest,
            "authority": False, "ready_for_t14": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="synthetic JSON file or directory containing bundle.json")
    args = parser.parse_args(argv)
    try:
        result = validate_bundle(args.input)
    except BundleContractError:
        print(json.dumps({"mode": CONTRACT_MODE, "authority": False,
                          "ready_for_t14": False, "error": "invalid PKB1 input"}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
