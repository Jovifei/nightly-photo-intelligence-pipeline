"""PKB1 serialization for already schema-validated mappings only.

This helper checks required string fields, not the full consumer JSON Schema.
It emits no producer golden evidence and never grants T14 readiness.
"""
import hashlib

FIELDS = ("scene", "background_story", "lighting", "composition", "subject_intent",
          "emotion", "pose_template", "camera_position", "director_prompt")


def _token(text):
    if not isinstance(text, str):
        raise ValueError("PKB1 fields must be strings")
    raw = text.encode("utf-8", errors="strict")
    return str(len(raw)).encode("ascii") + b":" + raw + b"\n"


def canonical_pkb1_bytes(payload):
    refs = payload["references"]
    if not isinstance(refs, list):
        raise ValueError("references must be an array")
    pairs = [("contract_version", payload["contract_version"]),
             ("bundle_id", payload["bundle_id"])]
    pairs.extend(("source." + key, payload["source"][key])
                 for key in ("origin", "producer_id", "release_id"))
    pairs.append(("references.count", str(len(refs))))
    for index, ref in enumerate(refs):
        prefix = f"references[{index}]."
        pairs.append((prefix + "reference_id", ref["reference_id"]))
        pairs.extend((prefix + "photography." + field, ref["photography"][field])
                     for field in FIELDS)
    return b"PKB1\n" + b"".join(_token(name) + _token(value) for name, value in pairs)


def pkb1_sha256(payload):
    return hashlib.sha256(canonical_pkb1_bytes(payload)).hexdigest()
