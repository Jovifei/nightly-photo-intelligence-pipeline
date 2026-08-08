"""Single canonical serialization and runtime configuration for N2B1P."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from .domain.errors import DuplicateJsonMemberError, GateNotAuthorizedError
from .json_strict import load_json_strict
from .windows_bound_promotion import normalize_windows_path, paths_overlap

_RUNTIME_CONFIG_PATH = Path("approvals") / "n2b1p_runtime_configuration.json"
_RUNTIME_SCHEMA = "n2b1p_runtime_configuration_v1_0.schema.json"
_SHA256_HEX = frozenset("0123456789abcdef")
_SNAPSHOT_FORBIDDEN = "NOT_APPLICABLE_N2B1P_SOURCE_ACCESS_FORBIDDEN"


def _deny(message: str) -> None:
    raise GateNotAuthorizedError(message)


def _finite_json(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        _deny("N2B1P canonical JSON rejects non-finite numbers")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if not isinstance(key, str):
                _deny("N2B1P canonical JSON object key is invalid")
            _finite_json(item)
    elif isinstance(value, list):
        for item in value:
            _finite_json(item)


def canonical_json_bytes(value: object) -> bytes:
    """The only N2B1P JSON representation used for evidence hashing."""
    _finite_json(value)
    try:
        return (
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise GateNotAuthorizedError("N2B1P canonical JSON is unavailable") from exc


def _duplicate_rejecting_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonMemberError(key)
        value[key] = item
    return value


def load_canonical_json_bytes(raw: bytes) -> Mapping[str, object]:
    """Strict-load canonical JSON, rejecting equivalent but noncanonical bytes."""
    if raw.startswith(b"\xef\xbb\xbf"):
        _deny("N2B1P canonical JSON rejects BOM")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_rejecting_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError("non-finite")),
        )
    except (UnicodeDecodeError, ValueError, TypeError, DuplicateJsonMemberError) as exc:
        raise GateNotAuthorizedError("N2B1P canonical JSON is invalid") from exc
    if not isinstance(parsed, Mapping) or canonical_json_bytes(parsed) != raw:
        _deny("N2B1P cache manifest is not canonical")
    return cast(Mapping[str, object], parsed)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def build_legacy_cache_manifest_bytes(
    *,
    artifact_id: str,
    revision: str,
    filename: str,
    byte_count: int,
    local_sha256: str,
    transfer_manifest_sha256: str,
    status: str = "PROMOTED",
) -> bytes:
    """Rebuild immutable N2B1P v1.0 external manifest bytes exactly."""
    return canonical_json_bytes(
        {
            "schema_version": "1.0",
            "stage": "N2B1P",
            "artifact_id": artifact_id,
            "revision": revision,
            "filename": filename,
            "cache_key": local_sha256,
            "byte_count": byte_count,
            "local_sha256": local_sha256,
            "transfer_manifest_sha256": transfer_manifest_sha256,
            "status": status,
            "weights_rights": "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
            "use_restriction": "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION",
        }
    )


def compute_legacy_cache_manifest_sha256(**kwargs: object) -> str:
    return sha256_bytes(build_legacy_cache_manifest_bytes(**kwargs))  # type: ignore[arg-type]


@dataclass(frozen=True)
class N2B1PRuntimeConfiguration:
    configuration_version: str
    runtime_parent: Path
    work_root: Path
    snapshot_root: str
    cache_root: Path
    cache_root_identity: str
    configuration_digest: str

    @property
    def redacted_cache_root(self) -> str:
        return "EXTERNAL_REDACTED_CONTENT_ADDRESSED_NON_REPARSE"


def _runtime_payload(raw: Mapping[str, object]) -> dict[str, object]:
    expected = {
        "schema_version",
        "configuration_version",
        "runtime_parent",
        "work_root",
        "snapshot_root",
        "cache_root",
        "cache_root_identity",
        "configuration_digest",
    }
    if set(raw) != expected:
        _deny("N2B1P runtime configuration has unknown or missing fields")
    return {key: raw[key] for key in sorted(expected - {"configuration_digest"})}


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _SHA256_HEX


def load_n2b1p_runtime_configuration(project_root: Path) -> N2B1PRuntimeConfiguration:
    """Strict-load the only approved N2B1P runtime/cache path source."""
    try:
        raw = load_json_strict(project_root / _RUNTIME_CONFIG_PATH)
        schema = load_json_strict(project_root / "schemas" / _RUNTIME_SCHEMA)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    except (OSError, ValueError, DuplicateJsonMemberError) as exc:
        raise GateNotAuthorizedError("N2B1P runtime configuration is unavailable") from exc
    if list(validator.iter_errors(raw)):
        _deny("N2B1P runtime configuration schema is invalid")
    if not isinstance(raw, Mapping):
        _deny("N2B1P runtime configuration is invalid")
    payload = _runtime_payload(cast(Mapping[str, object], raw))
    digest = raw.get("configuration_digest")
    if not _is_sha256(digest) or digest != sha256_bytes(canonical_json_bytes(payload)):
        _deny("N2B1P runtime configuration digest mismatch")
    runtime_parent = raw.get("runtime_parent")
    work_root = raw.get("work_root")
    snapshot_root = raw.get("snapshot_root")
    cache_root = raw.get("cache_root")
    cache_identity = raw.get("cache_root_identity")
    version = raw.get("configuration_version")
    if not all(
        isinstance(value, str)
        for value in (runtime_parent, work_root, snapshot_root, cache_root, version)
    ):
        _deny("N2B1P runtime configuration path is invalid")
    if snapshot_root != _SNAPSHOT_FORBIDDEN:
        _deny("N2B1P source snapshot must remain inaccessible")
    if not _is_sha256(cache_identity):
        _deny("N2B1P cache root identity is invalid")
    runtime = Path(cast(str, runtime_parent))
    work = Path(cast(str, work_root))
    cache = Path(cast(str, cache_root))
    try:
        normalized_runtime = normalize_windows_path(runtime)
        normalized_work = normalize_windows_path(work)
        normalized_cache = normalize_windows_path(cache)
    except GateNotAuthorizedError:
        raise
    if not normalized_work.startswith(normalized_runtime + "\\"):
        _deny("N2B1P work root is outside the approved runtime parent")
    if paths_overlap(normalized_cache, normalized_runtime) or paths_overlap(
        normalized_cache, normalized_work
    ):
        _deny("N2B1P cache root overlaps the approved runtime configuration")
    return N2B1PRuntimeConfiguration(
        configuration_version=cast(str, version),
        runtime_parent=runtime,
        work_root=work,
        snapshot_root=cast(str, snapshot_root),
        cache_root=cache,
        cache_root_identity=cast(str, cache_identity),
        configuration_digest=cast(str, digest),
    )


def validate_bound_cache_root(
    configuration: N2B1PRuntimeConfiguration, *, identity_digest: str
) -> None:
    if identity_digest != configuration.cache_root_identity:
        _deny("N2B1P cache root identity does not match the approved configuration")


def build_manifest_binding_payload(
    *,
    artifact_id: str,
    approved_evidence_id: str,
    approved_payload_sha256: str,
    payload_size_bytes: int,
    cache_relative_path: str,
    cache_filename: str,
    promotion_completed_at_utc: str,
    cache_root_identity: str,
    runtime_configuration_digest: str,
    raw_cache_manifest_sha256: str,
) -> dict[str, object]:
    """Build the non-self-referential envelope for immutable legacy manifests."""
    return {
        "schema_version": "1.0",
        "artifact_id": artifact_id,
        "approved_evidence_id": approved_evidence_id,
        "approved_payload_sha256": approved_payload_sha256,
        "payload_size_bytes": payload_size_bytes,
        "cache_relative_path": cache_relative_path,
        "cache_filename": cache_filename,
        "promotion_source": "N2B1R_COPY_ONLY",
        "promotion_completed_at_utc": promotion_completed_at_utc,
        "cache_root_identity": cache_root_identity,
        "runtime_configuration_digest": runtime_configuration_digest,
        "raw_cache_manifest_sha256": raw_cache_manifest_sha256,
    }


def compute_manifest_binding_sha256(payload: Mapping[str, object]) -> str:
    return sha256_bytes(canonical_json_bytes(payload))
