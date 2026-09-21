"""Real20 metadata preparation, not an image reader or an execution permit.

Only explicit control files and Git objects are read. Paths named by manifest
assets are validated as strings, never opened. Output is redacted and DRAFT.
This tool does not import torch, contact Ollama, reserve a lease, or edit state.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import math
import os
import platform
import re
import stat
import subprocess
import sys
from pathlib import Path, PureWindowsPath
from typing import Any

BASE = "ffc4130823c1308f089b835c766e341ec2173e82"
BASE_TREE = "3b01e26388d131181a8553b4122a9abbaff177b2"
G1_SHA = "29eee5fdb8e16c85649752501c4b722d2b4d071950c8a989add040e895a75c47"
H3_LEASE_SHA = "6763dcfe658860a1c0ea76689799d5e0bd92d7d51c9898a47f75c8cee45a99e4"
H3_REVIEW_SHA = "820f76ba48c5d55fd66b83f158afe7b12b62aad0315df710a57163ea407ffc33"
MAX_BYTES = 16 * 1024 * 1024
COUNTERS = {"real_photo_read_count", "real_exif_read_count", "g1_source_access",
            "sqlite_write_count", "app_write_count", "production_bundle_count",
            "model_download_bytes"}
CHECKPOINTS = ["preflight", "before_s3", "before_s20", "before_resume", "after_resume"]
INPUTS = ("manifest", "h3_review", "h3_lease", "h3_reservation", "h3_terminal",
          "h3_evidence", "h3_runner", "s20_summary")
MANIFEST_KEYS = {"schema_version", "manifest_id", "data_gate", "created_at",
                 "source_root_fingerprint", "max_assets", "assets", "approval_reference"}


class PreparationError(ValueError):
    """Only stable codes, never private paths or source names, reach stdout."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PreparationError(code)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def digest(value: object, length: int = 64) -> bool:
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def parse(data: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "R0_DUPLICATE_JSON")
            result[key] = value
        return result

    def reject(_: str) -> Any:
        raise PreparationError("R0_NONFINITE_JSON")

    def floating(value: str) -> float:
        result = float(value)
        require(math.isfinite(result), "R0_NONFINITE_JSON")
        return result

    require(len(data) <= MAX_BYTES, "R0_INPUT_SIZE_LIMIT")
    try:
        value = json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=reject, parse_float=floating)
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError):
        raise PreparationError("R0_INVALID_JSON") from None
    require(isinstance(value, dict), "R0_OBJECT_REQUIRED")
    return value


def path_syntax(path: Path) -> None:
    require(path.is_absolute() and ".." not in path.parts, "R0_ABSOLUTE_PATH_REQUIRED")
    require(not str(path).startswith(("\\\\", "//")), "R0_NETWORK_PATH_DENIED")
    for part in path.parts[1:]:
        require(":" not in part and not part.endswith((".", " ")),
                "R0_ADS_OR_PATH_ALIAS_DENIED")


def ancestors(path: Path) -> tuple[tuple[Path, int, int], ...]:
    path_syntax(path)
    records = []
    for item in (*reversed(path.parents), path):
        info = item.lstat()
        require(not stat.S_ISLNK(info.st_mode)
                and not (getattr(info, "st_file_attributes", 0) & 0x400), "R0_REPARSE_DENIED")
        require(stat.S_ISDIR(info.st_mode), "R0_DIRECTORY_REQUIRED")
        records.append((item, info.st_dev, info.st_ino))
    return tuple(records)


def overlaps(left: Path, right: Path) -> bool:
    left_s, right_s = os.path.normcase(str(left)), os.path.normcase(str(right))
    try:
        return os.path.commonpath((left_s, right_s)) in (left_s, right_s)
    except ValueError:
        return False


def read_control(path: Path) -> bytes:
    """Bounded regular-file read; no directory traversal or asset opening."""
    path_syntax(path)
    before_dirs = ancestors(path.parent)
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
            and not (getattr(before, "st_file_attributes", 0) & 0x400), "R0_REGULAR_FILE_REQUIRED")
    require(before.st_size <= MAX_BYTES, "R0_INPUT_SIZE_LIMIT")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        data = stream.read(MAX_BYTES + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    require(ancestors(path.parent) == before_dirs, "R0_INPUT_CHANGED")
    marks = {(i.st_dev, i.st_ino, i.st_size, i.st_mtime_ns) for i in (before, opened, after, current)}
    require(len(marks) == 1 and len(data) == before.st_size, "R0_INPUT_CHANGED")
    return data


def git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(key, None)
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                          timeout=30, check=False, env=env)
    require(proc.returncode == 0, "R0_GIT_QUERY_FAILED")
    return proc.stdout


def source_identity(root: Path, expected: str | None = None, tree: str | None = None) -> dict[str, Any]:
    expected, tree = expected or BASE, tree or BASE_TREE
    ancestors(root)
    require(git(root, "rev-parse", "HEAD").decode().strip() == expected, "R0_SOURCE_CANDIDATE_MISMATCH")
    require(git(root, "rev-parse", "HEAD^{tree}").decode().strip() == tree, "R0_SOURCE_TREE_MISMATCH")
    require(git(root, "status", "--porcelain=v1", "--untracked-files=all") == b"", "R0_SOURCE_DIRTY")
    require(git(root, "rev-parse", "--is-shallow-repository").strip() == b"false", "R0_SHALLOW_SOURCE")
    rows, total = [], 0
    for entry in git(root, "ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0"):
        if not entry:
            continue
        meta, name = entry.split(b"\t", 1)
        mode, kind, oid = meta.decode("ascii").split()
        require(kind == "blob" and mode in {"100644", "100755"}, "R0_SOURCE_ENTRY_INVALID")
        size = int(git(root, "cat-file", "-s", oid))
        total += size
        require(0 <= size <= 8 * 1024 * 1024 and total <= 128 * 1024 * 1024
                and len(rows) < 5000, "R0_SOURCE_SIZE_LIMIT")
        data = git(root, "cat-file", "blob", oid)
        require(len(data) == size, "R0_SOURCE_CHANGED")
        rows.append({"path": name.decode("utf-8"), "mode": mode, "git_blob": oid,
                     "size_bytes": size, "sha256": sha(data)})
    require(bool(rows), "R0_SOURCE_EMPTY")
    rows.sort(key=lambda row: row["path"])
    state_git = git(root, "show", "HEAD:PROJECT_STATE.json")
    state_bytes = read_control(root / "PROJECT_STATE.json")
    state = parse(state_bytes)
    require(state == parse(state_git), "R0_STATE_CHECKOUT_DRIFT")
    require(isinstance(state.get("phase_status"), dict)
            and state["phase_status"].get("N2B2") == "LOCKED", "R0_STATE_NOT_LOCKED")
    require(git(root, "rev-parse", "HEAD").decode().strip() == expected
            and git(root, "status", "--porcelain=v1", "--untracked-files=all") == b"", "R0_SOURCE_CHANGED")
    return {"candidate_commit": expected, "candidate_tree": tree,
            "source_manifest_sha256": sha(canonical(rows)), "file_count": len(rows),
            "project_state_sha256": sha(state_bytes), "project_state_git_blob_sha256": sha(state_git)}


def relative_asset_path(value: object) -> str:
    require(isinstance(value, str) and bool(value) and len(value) <= 1024, "R0_ASSET_PATH_INVALID")
    windows = PureWindowsPath(value)
    require(not windows.drive and not windows.root, "R0_ASSET_PATH_INVALID")
    require(not any(ord(c) < 32 for c in value), "R0_ASSET_PATH_INVALID")
    parts = value.replace("\\", "/").split("/")
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)), *(f"LPT{i}" for i in range(10))}
    require(all(p not in {"", ".", ".."} and not p.endswith((".", " "))
                and not any(c in p for c in ':*?"<>|')
                and p.split(".")[0].upper() not in reserved for p in parts), "R0_ASSET_PATH_INVALID")
    return "/".join(parts).casefold()


def manifest_plan(data: bytes, expected_sha: str | None = None) -> dict[str, Any]:
    require(sha(data) == (expected_sha or G1_SHA), "R0_FROZEN_MANIFEST_MISMATCH")
    value = parse(data)
    require(MANIFEST_KEYS <= set(value) <= MANIFEST_KEYS | {"allowed_phases", "expires_at"}, "R0_MANIFEST_FIELDS")
    require(value["schema_version"] == "1.0" and value["data_gate"] == "G1_CALIBRATION_20"
            and type(value["max_assets"]) is int and value["max_assets"] == 20, "R0_MANIFEST_SCOPE")
    assets = value["assets"]
    require(isinstance(assets, list) and len(assets) == 20, "R0_EXACTLY_20_REQUIRED")
    names, refs, seen, output = set(), set(), {}, []
    for index, asset in enumerate(assets, 1):
        require(isinstance(asset, dict) and set(asset) == {
            "asset_ref", "source_relative_path", "expected_sha256", "size_bytes", "media_type"}, "R0_ASSET_FIELDS")
        name = relative_asset_path(asset["source_relative_path"])
        ref = asset["asset_ref"]
        require(isinstance(ref, str) and 1 <= len(ref) <= 128 and ref not in refs
                and name not in names, "R0_DUPLICATE_ASSET_REFERENCE")
        names.add(name)
        refs.add(ref)
        require(digest(asset["expected_sha256"]) and type(asset["size_bytes"]) is int
                and asset["size_bytes"] > 0 and isinstance(asset["media_type"], str)
                and re.fullmatch(r"image/[A-Za-z0-9.+-]+", asset["media_type"]) is not None, "R0_ASSET_METADATA_INVALID")
        image_sha = asset["expected_sha256"]
        alias = f"R20-{index:03d}"
        previous = seen.get(image_sha)
        if previous:
            require(previous[1:] == (asset["size_bytes"], asset["media_type"]), "R0_DUPLICATE_METADATA_CONFLICT")
        else:
            seen[image_sha] = (alias, asset["size_bytes"], asset["media_type"])
        output.append({"case_id": alias, "manifest_ordinal": index,
                       "expected_sha256": image_sha, "size_bytes": asset["size_bytes"],
                       "duplicate_of": previous[0] if previous else None,
                       "action": "REFERENCE_ONLY" if previous else "INFER_ONCE_AFTER_ADMISSION"})
    fingerprint = value["source_root_fingerprint"]
    require(isinstance(fingerprint, str) and 8 <= len(fingerprint) <= 256, "R0_SOURCE_FINGERPRINT_INVALID")
    return {"manifest_sha256": sha(data), "asset_count": 20, "canonical_count": len(seen),
            "duplicate_count": 20 - len(seen), "assets": output,
            "source_fingerprint_value_sha256": sha(fingerprint.encode("utf-8")),
            "historical_authorization_reused": False, "source_bytes_verified": False}


def zeros(value: object) -> None:
    require(isinstance(value, dict) and COUNTERS <= set(value)
            and all(isinstance(k, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", k)
                    and type(v) is int and v == 0 for k, v in value.items()), "R0_FORBIDDEN_COUNTERS_INVALID")


def h3_check(raw: dict[str, bytes], source: dict[str, Any], *,
             review_sha: str | None = None, lease_sha: str | None = None) -> dict[str, Any]:
    review_sha, lease_sha = review_sha or H3_REVIEW_SHA, lease_sha or H3_LEASE_SHA
    require(sha(raw["h3_review"]) == review_sha, "R0_H3_REVIEW_HASH_MISMATCH")
    require(sha(raw["h3_lease"]) == lease_sha, "R0_H3_LEASE_HASH_MISMATCH")
    lease, reservation, terminal, evidence, runner, s20 = (
        parse(raw[name]) for name in ("h3_lease", "h3_reservation", "h3_terminal",
                                     "h3_evidence", "h3_runner", "s20_summary"))
    require(lease.get("schema_version") == "npi-synthetic-execution-lease-v3"
            and lease.get("status") == "APPROVED" and lease.get("production_unlock") is False,
            "R0_H3_LEASE_INVALID")
    bindings = lease.get("bindings")
    require(isinstance(bindings, dict), "R0_H3_BINDINGS_MISSING")
    for key in ("candidate_commit", "candidate_tree", "source_manifest_sha256", "project_state_sha256"):
        require(bindings.get(key) == source[key], "R0_H3_SOURCE_BINDING_MISMATCH")
    require(reservation.get("status") == "RESERVED" and terminal.get("status") == "COMPLETE"
            and reservation.get("receipt_sha256") == terminal.get("receipt_sha256") == lease_sha
            and reservation.get("bindings_sha256") == sha(canonical(bindings))
            and terminal.get("reservation_sha256") == sha(raw["h3_reservation"]), "R0_H3_LEDGER_MISMATCH")
    require(terminal.get("evidence_sha256") == sha(canonical(evidence)), "R0_H3_EVIDENCE_BINDING_MISMATCH")
    require(evidence.get("schema_version") == "npi-controlled-execution-evidence-v1"
            and evidence.get("input_bindings") == bindings
            and evidence.get("execution_lease_sha256") == lease_sha, "R0_H3_EVIDENCE_INVALID")
    for key in ("candidate_commit", "candidate_tree", "source_manifest_sha256", "runtime_identity_sha256", "path_plan_sha256"):
        require(evidence.get(key) == bindings.get(key), "R0_H3_EVIDENCE_BINDING_MISMATCH")
    artifacts = evidence.get("artifacts", {})
    require(artifacts.get("runner_evidence") == sha(raw["h3_runner"])
            and artifacts.get("s20_summary") == sha(raw["s20_summary"]), "R0_H3_ARTIFACT_HASH_MISMATCH")
    zeros(evidence.get("forbidden_counters"))
    zeros(runner.get("forbidden_counters"))
    require(evidence["forbidden_counters"] == runner["forbidden_counters"], "R0_H3_COUNTER_CONTRADICTION")
    require(s20.get("bundle_count") == 20 and type(s20["bundle_count"]) is int
            and s20.get("result") == "N2B2_S20_SYNTHETIC_VALIDATION_COMPLETE_AWAITING_EXTERNAL_REVIEW"
            and s20.get("production_bundle_release") == "NOT_CREATED", "R0_H3_S20_INCOMPLETE")
    repeats = s20.get("facts_repeat", {})
    require(repeats.get("bytes_identical") is True and repeats.get("digest_identical") is True,
            "R0_H3_REPEATABILITY_INVALID")
    observations = runner.get("identity_observations")
    require(isinstance(observations, list) and len(observations) == 5
            and all(isinstance(row, dict) for row in observations)
            and [row.get("checkpoint") for row in observations] == CHECKPOINTS,
            "R0_H3_IDENTITY_OBSERVATIONS_INVALID")
    for row in observations:
        require(isinstance(row.get("identity"), dict)
                and sha(canonical(row["identity"])) == bindings.get("runtime_identity_sha256"), "R0_H3_IDENTITY_MISMATCH")
    resume = runner.get("resume", {})
    require(resume.get("resume_status") == "ALREADY_COMPLETE_VERIFIED"
            and type(resume.get("exit_code")) is int and resume["exit_code"] == 0
            and type(resume.get("model_load_count")) is int and resume["model_load_count"] == 0,
            "R0_H3_RESUME_INVALID")
    before, after = resume.get("before"), resume.get("after")
    require(isinstance(before, dict) and bool(before) and before == after
            and all(isinstance(k, str) and digest(v) for k, v in before.items()), "R0_H3_RESUME_FILES_CHANGED")
    return {"consistency": "SELECTED_CONTROL_ARTIFACTS_MATCH_NOT_A_NEW_REVIEW",
            "candidate": source["candidate_commit"], "review_sha256": review_sha,
            "lease_sha256": lease_sha, "ledger_status": "COMPLETE", "s20_cases": 20,
            "resume_file_count": len(before), "resume_model_load_count": 0,
            "identity_observations": 5, "artifact_sha256": {k: sha(v) for k, v in raw.items() if k != "manifest"},
            "review_semantics": "OWNER_REPORTED_PASS_REQUIRES_LOCAL_REVIEWER_CONFIRMATION",
            "full_s20_file_audit": "NOT_REPEATED", "lease_reused": False}


def environment() -> dict[str, Any]:
    packages = {}
    for name in ("torch", "torchvision", "Pillow", "PyYAML", "pydantic", "jsonschema"):
        try:
            packages[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            packages[name] = None
    supported = sys.version_info[:2] in {(3, 11), (3, 12)}
    return {"python": platform.python_version(), "supported_python": supported,
            "packages": packages, "missing": sorted(k for k, v in packages.items() if v is None),
            "method": "DISTRIBUTION_METADATA_ONLY_NO_TORCH_IMPORT",
            "cuda_and_native_operator_probe": "NOT_PERFORMED",
            "model_runtime_ready": False}


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_root, candidate = args.source_root, args.candidate_root
    path_syntax(source_root)  # Source itself is deliberately NOT stat-ed or traversed.
    require(not overlaps(source_root, candidate), "R0_SOURCE_PROJECT_OVERLAP")
    tool_root = Path(__file__).resolve().parent
    paths = {key: getattr(args, key) for key in INPUTS}
    for path in paths.values():
        path_syntax(path)
        require(not overlaps(path, source_root) and not overlaps(path, candidate)
                and not overlaps(path, tool_root), "R0_CONTROL_FILE_BOUNDARY")
    raw = {name: read_control(path) for name, path in paths.items()}
    source = source_identity(candidate)
    selection = manifest_plan(raw["manifest"])
    h3 = h3_check(raw, source)
    env = environment()
    blocks = ["REAL20_EXECUTOR_NOT_IN_THIS_DELIVERY", "FINAL_REAL20_EXECUTION_CANDIDATE_NOT_BOUND",
              "FRESH_REAL20_DATA_RECEIPT_AND_LEASE_NOT_MATERIALIZED", "OS_READ_ONLY_CAPABILITY_NOT_REVALIDATED",
              "RUNTIME_CUDA_OPERATOR_PROBE_REQUIRED"]
    if not env["supported_python"]:
        blocks.append("SUPPORTED_PYTHON_REQUIRED")
    if env["missing"]:
        blocks.append("MODEL_ENVIRONMENT_DEPENDENCIES_MISSING")
    if selection["canonical_count"] != 19 or selection["duplicate_count"] != 1:
        blocks.append("HISTORICAL_19_PLUS_1_PROFILE_CHANGED")
    result = {
        "schema_version": "npi-real20-transition-plan-v1",
        "status": "R0_METADATA_READY_EXECUTION_BLOCKED", "execution_authorized": False,
        "owner_intent": "REAL20_REQUEST_RECORDED_NOT_AN_EXECUTABLE_PERMIT",
        "h3_closeout": h3, "h3_source": source, "selection": selection,
        "environment": env, "blockers": blocks,
        "execution_draft": {"status": "DRAFT", "issued": False, "execution_candidate": None,
            "execution_tree": None, "source_manifest_sha256": None,
            "not_before_utc": None, "expires_at_utc": None,
            "source_read_authorized_now": False, "production_unlock": False,
            "requested_scope": {"max_manifest_assets": 20, "max_unique_inferences": selection["canonical_count"],
                "max_executions": 1, "originals_read_only": True,
                "non_sensitive_exif_allowlist": ["ExposureTime", "FNumber", "ISOSpeedRatings", "FocalLength", "Flash", "WhiteBalance"],
                "excluded": ["GPS", "DateTimeOriginal", "MakerNote", "SerialNumber", "OwnerName", "Artist", "UserComment"],
                "sqlite_write": False, "app_write": False, "production_bundle": False,
                "model_download": False, "source_permission_changes": False,
                "source_rename_move_delete": False, "global_phase_unlock": False}},
        "review_rows": [{"case_id": row["case_id"], "duplicate_of": row["duplicate_of"],
                         "person_count_correct": None, "pose_usable": None, "segmentation_usable": None,
                         "composition_facts_correct": None, "unsupported_claims": None,
                         "advice_actionable": None, "edit_minutes": None, "decision": "PENDING"}
                        for row in selection["assets"]],
        "review_execution_performed": False,
    }
    require(all(read_control(paths[k]) == data for k, data in raw.items()), "R0_CONTROL_FILE_CHANGED")
    require(source_identity(candidate) == source, "R0_SOURCE_CHANGED")
    return result


def write_new(path: Path, data: bytes, *, protected: list[Path]) -> None:
    path_syntax(path)
    require(path.suffix == ".json", "R0_OUTPUT_JSON_REQUIRED")
    require(all(not overlaps(path, item) for item in protected), "R0_OUTPUT_BOUNDARY")
    parent = ancestors(path.parent)
    require(not any((part / ".git").exists() for part, _, _ in parent), "R0_OUTPUT_IN_GIT")
    require(ancestors(path.parent) == parent, "R0_OUTPUT_PARENT_CHANGED")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, 0o600), "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    require(ancestors(path.parent) == parent and read_control(path) == data, "R0_OUTPUT_CHANGED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    for key in INPUTS:
        parser.add_argument("--" + key.replace("_", "-"), dest=key, type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        protected = [args.source_root, args.candidate_root, Path(__file__).resolve().parent]
        protected += [getattr(args, key).parent for key in INPUTS]
        # Reject output overlaps before processing any metadata.
        path_syntax(args.out)
        require(all(not overlaps(args.out, p) for p in protected), "R0_OUTPUT_BOUNDARY")
        packet = prepare(args)
        data = canonical(packet)
        write_new(args.out, data, protected=protected)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        code = str(exc) if isinstance(exc, PreparationError) else "R0_INVALID_OR_UNAVAILABLE_INPUT"
        print(json.dumps({"status": "R0_BLOCKED", "error_code": code, "execution_authorized": False}))
        return 1
    print(json.dumps({"status": packet["status"], "sha256": sha(data), "execution_authorized": False,
                      "blockers": packet["blockers"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
