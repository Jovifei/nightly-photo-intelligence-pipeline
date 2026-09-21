"""Strict, independent Real20 control contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PureWindowsPath
from typing import Any, cast

from ..engineering.common import canonical, sha256, strict_json

EXIF_ALLOWLIST = (
    "ExposureTime",
    "FNumber",
    "ISOSpeedRatings",
    "FocalLength",
    "Flash",
    "WhiteBalance",
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_ASSET_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
_BOUNDARIES = frozenset(
    {
        "real_photo_read",
        "real_exif_read",
        "source_mutation",
        "acl_change",
        "sqlite_write",
        "app_write",
        "production_bundle",
        "model_download",
        "model_replacement",
        "n2b2_unlock",
        "push_merge_release",
    }
)


class Real20Error(ValueError):
    """Stable fail-closed Real20 error without private path details."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Real20Error(code)


def _digest(value: object, length: int = 64) -> None:
    pattern = _HEX64 if length == 64 else _HEX40
    _require(
        isinstance(value, str) and pattern.fullmatch(value) is not None, "REAL20_DIGEST_INVALID"
    )


def _safe_relative(value: object) -> str:
    if not isinstance(value, str) or value == "" or len(value) > 1024:
        raise Real20Error("REAL20_ASSET_PATH_INVALID")
    windows = PureWindowsPath(value)
    _require(not windows.drive and not windows.root, "REAL20_ASSET_PATH_INVALID")
    parts = value.replace("\\", "/").split("/")
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(10)),
        *(f"LPT{i}" for i in range(10)),
    }
    for part in parts:
        _require(part not in {"", ".", ".."}, "REAL20_ASSET_PATH_INVALID")
        _require(not part.endswith((".", " ")) and ":" not in part, "REAL20_ASSET_PATH_INVALID")
        _require(part.upper().split(".", 1)[0] not in reserved, "REAL20_ASSET_PATH_INVALID")
    return "/".join(parts)


def read_json(path: Any) -> dict[str, Any]:
    try:
        value = strict_json(path.read_bytes())
    except Real20Error:
        raise
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_CONTROL_JSON_INVALID") from exc
    _require(isinstance(value, dict), "REAL20_CONTROL_OBJECT_REQUIRED")
    return cast(dict[str, Any], value)


@dataclass(frozen=True)
class Asset:
    asset_id: str
    relative_path: str
    sha256: str
    duplicate_of: str | None


@dataclass(frozen=True)
class Manifest:
    source_fingerprint: str
    assets: tuple[Asset, ...]
    sha256: str

    @property
    def canonical_count(self) -> int:
        return len({asset.sha256 for asset in self.assets})


def load_manifest(path: Any) -> Manifest:
    raw = path.read_bytes()
    value = read_json(path)
    _require(
        set(value) == {"schema_version", "source_type", "source_fingerprint", "assets"},
        "REAL20_MANIFEST_FIELDS_INVALID",
    )
    _require(value["schema_version"] == "npi-real20-manifest-v2", "REAL20_MANIFEST_SCHEMA_INVALID")
    _require(
        value["source_type"] == "OWNER_FROZEN_REAL_PHOTO_SNAPSHOT", "REAL20_MANIFEST_SOURCE_INVALID"
    )
    _require(
        isinstance(value["source_fingerprint"], str)
        and 8 <= len(value["source_fingerprint"]) <= 256,
        "REAL20_SOURCE_FINGERPRINT_INVALID",
    )
    assets_value = value["assets"]
    _require(
        isinstance(assets_value, list) and len(assets_value) == 20, "REAL20_EXACTLY_20_REQUIRED"
    )
    assets: list[Asset] = []
    ids: set[str] = set()
    paths: set[str] = set()
    for item in assets_value:
        _require(isinstance(item, dict), "REAL20_ASSET_FIELDS_INVALID")
        _require(
            set(item)
            in (
                {"asset_id", "relative_path", "sha256"},
                {"asset_id", "relative_path", "sha256", "duplicate_of"},
            ),
            "REAL20_ASSET_FIELDS_INVALID",
        )
        asset_id = item.get("asset_id")
        _require(
            isinstance(asset_id, str)
            and _ASSET_ID.fullmatch(asset_id) is not None
            and asset_id not in ids,
            "REAL20_ASSET_ID_INVALID",
        )
        relative_path = _safe_relative(item.get("relative_path"))
        folded_path = relative_path.casefold()
        _require(folded_path not in paths, "REAL20_DUPLICATE_PATH")
        digest = item.get("sha256")
        _digest(digest)
        duplicate_of = item.get("duplicate_of")
        if duplicate_of is not None:
            _require(isinstance(duplicate_of, str), "REAL20_DUPLICATE_REFERENCE_INVALID")
        ids.add(asset_id)
        paths.add(folded_path)
        assets.append(Asset(asset_id, relative_path, digest, duplicate_of))
    by_id = {asset.asset_id: asset for asset in assets}
    duplicate_assets = [asset for asset in assets if asset.duplicate_of is not None]
    _require(len(duplicate_assets) == 1, "REAL20_DUPLICATE_COUNT_INVALID")
    duplicate = duplicate_assets[0]
    duplicate_id = duplicate.duplicate_of
    if duplicate_id is None:
        raise Real20Error("REAL20_DUPLICATE_REFERENCE_INVALID")
    _require(
        duplicate_id in by_id and duplicate_id != duplicate.asset_id,
        "REAL20_DUPLICATE_REFERENCE_INVALID",
    )
    _require(by_id[duplicate_id].sha256 == duplicate.sha256, "REAL20_DUPLICATE_HASH_MISMATCH")
    _require(len({asset.sha256 for asset in assets}) == 19, "REAL20_UNIQUE_ASSET_COUNT_INVALID")
    _require(
        all(asset.duplicate_of is None for asset in assets if asset.asset_id != duplicate.asset_id),
        "REAL20_DUPLICATE_REFERENCE_INVALID",
    )
    return Manifest(value["source_fingerprint"], tuple(assets), sha256(raw))


def _utc(value: object, code: str) -> datetime:
    if not isinstance(value, str):
        raise Real20Error(code)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise Real20Error(code) from exc
    _require(
        parsed.tzinfo is not None and parsed.utcoffset() == datetime.now(UTC).utcoffset(), code
    )
    return parsed.astimezone(UTC)


def validate_credential(
    raw: bytes,
    *,
    anchor: dict[str, Any],
    expected: dict[str, str],
    runtime_identity: dict[str, Any],
    model_identity: dict[str, Any],
    now: datetime,
) -> str:
    credential_hash = sha256(raw)
    _require(
        anchor.get("credential_sha256") == credential_hash, "REAL20_ANCHOR_CREDENTIAL_MISMATCH"
    )
    value = strict_json(raw)
    _require(isinstance(value, dict), "REAL20_CREDENTIAL_OBJECT_REQUIRED")
    _require(
        set(value)
        == {
            "schema_version",
            "status",
            "owner_id",
            "purpose",
            "not_before_utc",
            "expires_at_utc",
            "bindings",
            "scope",
            "boundaries",
            "production_n2b2",
        },
        "REAL20_CREDENTIAL_FIELDS_INVALID",
    )
    _require(
        value["schema_version"] == "npi-real20-execution-lease-v1",
        "REAL20_CREDENTIAL_SCHEMA_INVALID",
    )
    _require(
        value["status"] == "APPROVED" and value["owner_id"] == "Jovi",
        "REAL20_CREDENTIAL_NOT_APPROVED",
    )
    _require(value["purpose"] == "REAL20_READ_ONLY_EVALUATION", "REAL20_CREDENTIAL_PURPOSE_INVALID")
    start, end = (
        _utc(value["not_before_utc"], "REAL20_CREDENTIAL_TIME_INVALID"),
        _utc(value["expires_at_utc"], "REAL20_CREDENTIAL_TIME_INVALID"),
    )
    current = now.astimezone(UTC)
    _require(start < end and start <= current < end, "REAL20_CREDENTIAL_OUTSIDE_WINDOW")
    bindings = value["bindings"]
    _require(
        isinstance(bindings, dict) and set(bindings) == set(expected) | {"facts_schema_version"},
        "REAL20_CREDENTIAL_BINDINGS_INVALID",
    )
    for key, expected_value in expected.items():
        _require(bindings.get(key) == expected_value, "REAL20_CREDENTIAL_BINDING_MISMATCH")
    _require(bindings["facts_schema_version"] == "1.2", "REAL20_FACT_SCHEMA_INVALID")
    _require(
        bindings["runtime_identity_sha256"] == sha256(canonical(runtime_identity)),
        "REAL20_RUNTIME_IDENTITY_BINDING_MISMATCH",
    )
    _require(
        bindings["model_identity_sha256"] == sha256(canonical(model_identity)),
        "REAL20_MODEL_IDENTITY_BINDING_MISMATCH",
    )
    scope = value["scope"]
    _require(
        isinstance(scope, dict)
        and set(scope) == {"max_assets", "max_unique_inferences", "max_runs", "exif_allowlist"},
        "REAL20_CREDENTIAL_SCOPE_INVALID",
    )
    _require(
        scope["max_assets"] == 20
        and scope["max_unique_inferences"] == 19
        and scope["max_runs"] == 1,
        "REAL20_CREDENTIAL_SCOPE_INVALID",
    )
    _require(scope["exif_allowlist"] == list(EXIF_ALLOWLIST), "REAL20_EXIF_SCOPE_INVALID")
    boundaries = value["boundaries"]
    _require(
        isinstance(boundaries, dict) and set(boundaries) == _BOUNDARIES,
        "REAL20_CREDENTIAL_BOUNDARIES_INVALID",
    )
    _require(
        boundaries["real_photo_read"] is True and boundaries["real_exif_read"] is True,
        "REAL20_CREDENTIAL_READ_NOT_AUTHORIZED",
    )
    _require(
        all(
            boundaries[key] is False for key in _BOUNDARIES - {"real_photo_read", "real_exif_read"}
        ),
        "REAL20_CREDENTIAL_BOUNDARIES_INVALID",
    )
    _require(value["production_n2b2"] == "LOCKED", "REAL20_PRODUCTION_UNLOCK")
    _require(
        anchor.get("schema_version") == "npi-real20-owner-anchor-v1", "REAL20_ANCHOR_SCHEMA_INVALID"
    )
    _require(
        anchor.get("status") == "APPROVED" and anchor.get("owner_id") == "Jovi",
        "REAL20_ANCHOR_NOT_APPROVED",
    )
    _require(
        anchor.get("purpose") == "REAL20_READ_ONLY_EVALUATION"
        and anchor.get("production_unlock") is False
        and anchor.get("n2b2") == "LOCKED",
        "REAL20_ANCHOR_SCOPE_INVALID",
    )
    return credential_hash
