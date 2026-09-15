"""Bind each subprocess dispatch to one admitted reservation and one configuration.

This is an anti-confusion/anti-replay protocol inside an Owner-controlled local
account, NOT an OS sandbox against that same account modifying Python or ledger
files. No model/network code is imported. A reservation alone is not a dispatch.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
from collections.abc import Mapping
from pathlib import Path
from typing import Any

MAX_BYTES = 128 * 1024
MODES = {"fresh", "resume"}
CONFIG_FIELDS = {
    "project_root",
    "cache_root",
    "s3_manifest_dir",
    "s20_manifest_dir",
    "baseline_manifest_dir",
    "s3_out",
    "s20_out",
    "prior_s20_review_record",
    "reviewed_commit",
    "candidate_tree",
    "source_manifest_sha256",
    "ledger_root",
    "reservation_dir",
    "receipt_sha256",
    "bindings_sha256",
    "runtime_identity_sha256",
}
PATH_FIELDS = {
    "project_root",
    "cache_root",
    "s3_manifest_dir",
    "s20_manifest_dir",
    "baseline_manifest_dir",
    "s3_out",
    "s20_out",
    "prior_s20_review_record",
    "ledger_root",
    "reservation_dir",
}


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: object, length: int = 64) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(c in "0123456789abcdef" for c in value)
    )


def _json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "NPI_DISPATCH_DUPLICATE_JSON")
            result[key] = value
        return result

    def invalid(_: str) -> None:
        raise ValueError("NPI_DISPATCH_NONFINITE_JSON")

    _require(len(data) <= MAX_BYTES, "NPI_DISPATCH_SIZE_LIMIT")
    return json.loads(data, object_pairs_hook=pairs, parse_constant=invalid)


def _path(value: object) -> Path:
    _require(isinstance(value, str) and bool(value), "NPI_DISPATCH_PATH_INVALID")
    assert isinstance(value, str)
    path = Path(value)
    _require(path.is_absolute() and ".." not in path.parts, "NPI_DISPATCH_PATH_INVALID")
    _require(not value.startswith(("\\\\", "//")), "NPI_NETWORK_PATH_DENIED")
    _require(all(":" not in part for part in path.parts[1:]), "NPI_ALTERNATE_STREAM_DENIED")
    return path


def _check_existing(path: Path) -> None:
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        _require(
            not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
            "NPI_DISPATCH_REPARSE_PATH",
        )


def _read(path: Path) -> bytes:
    _check_existing(path)
    before = path.lstat()
    _require(
        stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= MAX_BYTES,
        "NPI_DISPATCH_RECORD_INVALID",
    )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        data = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    _check_existing(path)
    current = path.lstat()
    ids = {(s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns) for s in (before, opened, after, current)}
    _require(len(ids) == 1 and len(data) == before.st_size, "NPI_DISPATCH_RECORD_CHANGED")
    return data


def _write_new(path: Path, value: object) -> None:
    _check_existing(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
            stream.write(_canonical(value))
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise ValueError("NPI_WORKER_DISPATCH_ALREADY_USED") from exc


def _configuration(configuration: Mapping[str, Any]) -> dict[str, Any]:
    _require(set(configuration) == CONFIG_FIELDS, "NPI_WORKER_CONFIGURATION_FIELDS")
    result = dict(configuration)
    for key in PATH_FIELDS:
        _path(result[key])
    for key in (
        "receipt_sha256",
        "bindings_sha256",
        "source_manifest_sha256",
        "runtime_identity_sha256",
    ):
        _require(_hex(result[key]), "NPI_WORKER_CONFIGURATION_DIGEST")
    for key in ("reviewed_commit", "candidate_tree"):
        _require(_hex(result[key], 40), "NPI_WORKER_CONFIGURATION_DIGEST")
    _require(
        _path(result["reservation_dir"]) == _path(result["ledger_root"]) / result["receipt_sha256"],
        "NPI_WORKER_RESERVATION_LOCATION",
    )
    return result


def _reservation(configuration: Mapping[str, Any]) -> tuple[Path, str]:
    root = _path(configuration["reservation_dir"])
    record_bytes = _read(root / "reservation.json")
    record = _json(record_bytes)
    _require(
        isinstance(record, dict)
        and set(record)
        == {"schema_version", "status", "receipt_sha256", "bindings_sha256", "reserved_at_utc"},
        "NPI_WORKER_RESERVATION_INVALID",
    )
    _require(
        record["schema_version"] == "npi-lease-consumption-v1"
        and record["status"] == "RESERVED"
        and record["receipt_sha256"] == configuration["receipt_sha256"]
        and record["bindings_sha256"] == configuration["bindings_sha256"],
        "NPI_WORKER_RESERVATION_INVALID",
    )
    try:
        (root / "terminal.json").lstat()
    except FileNotFoundError:
        return root, _sha(record_bytes)
    raise ValueError("NPI_WORKER_RESERVATION_ALREADY_FINISHED")


def _fresh_complete(root: Path, configuration_sha: str) -> None:
    value = _json(_read(root / "worker-fresh-result.json"))
    _require(
        isinstance(value, dict)
        and value.get("outcome") == "COMPLETE"
        and value.get("configuration_sha256") == configuration_sha
        and _hex(value.get("result_sha256")),
        "NPI_WORKER_FRESH_NOT_COMPLETE",
    )


def issue(configuration: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """Called by the admitted parent, after reservation and before subprocess start."""
    _require(mode in MODES, "NPI_WORKER_MODE_INVALID")
    config = _configuration(configuration)
    root, reservation_sha = _reservation(config)
    config_sha = _sha(_canonical(config))
    if mode == "resume":
        _fresh_complete(root, config_sha)
    nonce = secrets.token_hex(32)
    record = {
        "schema_version": "npi-worker-dispatch-v1",
        "mode": mode,
        "configuration_sha256": config_sha,
        "reservation_sha256": reservation_sha,
        "nonce_sha256": _sha(nonce.encode("ascii")),
    }
    _write_new(root / f"worker-{mode}-dispatch.json", record)
    return {
        "schema_version": "npi-worker-envelope-v1",
        "mode": mode,
        "configuration": config,
        "nonce": nonce,
    }


def claim(envelope: Mapping[str, Any], mode: str) -> dict[str, Any]:
    """A replay, changed configuration, bare reservation, or terminal lease is denied."""
    _require(
        mode in MODES and set(envelope) == {"schema_version", "mode", "configuration", "nonce"},
        "NPI_WORKER_ENVELOPE_INVALID",
    )
    _require(
        envelope["schema_version"] == "npi-worker-envelope-v1"
        and envelope["mode"] == mode
        and _hex(envelope["nonce"])
        and isinstance(envelope["configuration"], Mapping),
        "NPI_WORKER_ENVELOPE_INVALID",
    )
    config = _configuration(envelope["configuration"])
    root, reservation_sha = _reservation(config)
    config_sha = _sha(_canonical(config))
    expected = {
        "schema_version": "npi-worker-dispatch-v1",
        "mode": mode,
        "configuration_sha256": config_sha,
        "reservation_sha256": reservation_sha,
        "nonce_sha256": _sha(envelope["nonce"].encode("ascii")),
    }
    _require(
        _json(_read(root / f"worker-{mode}-dispatch.json")) == expected,
        "NPI_WORKER_DISPATCH_MISMATCH",
    )
    if mode == "resume":
        _fresh_complete(root, config_sha)
    _write_new(root / f"worker-{mode}-claim.json", expected)
    return config


def finish(configuration: Mapping[str, Any], mode: str, *, outcome: str, result: object) -> None:
    """Never release claims, including exceptions/crashes. No automatic retry."""
    _require(mode in MODES and outcome in {"COMPLETE", "FAILED"}, "NPI_WORKER_RESULT_INVALID")
    config = _configuration(configuration)
    root, _ = _reservation(config)
    config_sha = _sha(_canonical(config))
    record = _json(_read(root / f"worker-{mode}-claim.json"))
    _require(
        isinstance(record, dict) and record.get("configuration_sha256") == config_sha,
        "NPI_WORKER_CLAIM_MISMATCH",
    )
    _write_new(
        root / f"worker-{mode}-result.json",
        {
            "outcome": outcome,
            "configuration_sha256": config_sha,
            "result_sha256": _sha(_canonical(result)),
        },
    )


def assert_identity(configuration: Mapping[str, Any], identity: Mapping[str, Any]) -> None:
    """Check immediately BEFORE each stage, not after inference has already happened."""
    _require(
        _sha(_canonical(dict(identity))) == configuration.get("runtime_identity_sha256"),
        "NPI_WORKER_RUNTIME_IDENTITY_DRIFT",
    )


def assert_source(configuration: Mapping[str, Any], source: Mapping[str, Any]) -> None:
    _require(
        configuration.get("reviewed_commit") == source.get("candidate_commit")
        and configuration.get("candidate_tree") == source.get("candidate_tree")
        and configuration.get("source_manifest_sha256") == source.get("source_manifest_sha256"),
        "NPI_WORKER_EXECUTION_SOURCE_DRIFT",
    )
