"""Build a deterministic, non-authorizing synthetic lease request packet."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
HISTORICAL_RECEIPT = "approvals/owner_n2b2_ollama_runtime_identity_revalidation_20260906.yaml"
HISTORICAL_BLOCKER = "N2B2_S20_RESUME_BINDING_MISMATCH: model_identity"
REQUIRED_PATH_PLAN = {
    "inputs": {"old_s3", "old_s20", "s3_manifest", "s20_manifest", "baseline_manifest"},
    "outputs": {"s3_out", "s20_out", "evidence_out"},
    "protected": {
        "project_root",
        "ledger_root",
        "cache_root",
        "owner_anchor_root",
        "candidate_review_root",
        "historical_review_root",
        "lease_root",
        "quality_root",
        "prior_review_root",
    },
}
BOUNDARIES = {
    "real_photo": False,
    "real_exif": False,
    "g1_source": False,
    "sqlite_ingest": False,
    "app": False,
    "production_bundle": False,
    "model_download": False,
    "model_replacement": False,
    "project_state_mutation": False,
}


class RequestError(ValueError):
    pass


def require(ok: bool, code: str) -> None:
    if not ok:
        raise RequestError(code)


def canonical(value: object) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strict_json(data: bytes) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            require(key not in result, "H0_DUPLICATE_JSON_MEMBER")
            result[key] = value
        return result

    def bad(_: str) -> None:
        raise RequestError("H0_NONFINITE_JSON")

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise RequestError("H0_INVALID_JSON") from None


def run_git(root: Path, *args: str) -> bytes:
    env = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    for name in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(name, None)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
            timeout=30,
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RequestError("H0_GIT_UNAVAILABLE") from exc
    require(proc.returncode == 0, "H0_GIT_QUERY_FAILED")
    return proc.stdout


def source_identity(root: Path, expected_candidate: str) -> dict[str, Any]:
    require(HEX40.fullmatch(expected_candidate) is not None, "H0_EXPECTED_CANDIDATE_INVALID")
    head = run_git(root, "rev-parse", "HEAD").decode().strip()
    tree = run_git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    require(head == expected_candidate, "H0_CANDIDATE_MISMATCH")
    require(HEX40.fullmatch(tree) is not None, "H0_TREE_INVALID")
    require(
        run_git(root, "status", "--porcelain=v1", "--untracked-files=all") == b"",
        "H0_WORKTREE_DIRTY",
    )
    require(
        run_git(root, "rev-parse", "--is-shallow-repository").strip() == b"false",
        "H0_SHALLOW_REPOSITORY",
    )
    rows: list[dict[str, Any]] = []
    total = 0
    for entry in run_git(root, "ls-tree", "-rz", "--full-tree", "HEAD").split(b"\0"):
        if not entry:
            continue
        try:
            meta, raw_path = entry.split(b"\t", 1)
            mode, kind, oid = meta.decode("ascii").split()
            path = raw_path.decode("utf-8")
        except (ValueError, UnicodeError):
            raise RequestError("H0_GIT_TREE_INVALID") from None
        require(kind == "blob" and mode in {"100644", "100755"}, "H0_UNSUPPORTED_GIT_ENTRY")
        require(
            not path.startswith("/")
            and ".." not in path.split("/")
            and "\n" not in path
            and "\r" not in path,
            "H0_GIT_PATH_INVALID",
        )
        size = int(run_git(root, "cat-file", "-s", oid))
        require(0 <= size <= 8 * 1024 * 1024, "H0_SOURCE_BLOB_SIZE_LIMIT")
        total += size
        require(total <= 128 * 1024 * 1024 and len(rows) < 5000, "H0_SOURCE_SIZE_LIMIT")
        data = run_git(root, "cat-file", "blob", oid)
        require(len(data) == size, "H0_SOURCE_BLOB_CHANGED")
        rows.append(
            {"path": path, "mode": mode, "git_blob": oid, "size_bytes": size, "sha256": sha(data)}
        )
    require(bool(rows), "H0_EMPTY_SOURCE_TREE")
    rows.sort(key=lambda item: item["path"])
    require(run_git(root, "rev-parse", "HEAD").decode().strip() == head, "H0_SOURCE_CHANGED")
    return {
        "candidate_commit": head,
        "candidate_tree": tree,
        "source_manifest_sha256": sha(canonical(rows)),
        "file_count": len(rows),
    }


def digest_file(path: Path, code: str) -> str:
    try:
        info = path.lstat()
        data = path.read_bytes()
    except OSError as exc:
        raise RequestError(code) from exc
    require(path.is_file() and not path.is_symlink() and info.st_nlink == 1, code)
    return sha(data)


def validate_candidate_review(path: Path, *, candidate: dict[str, Any]) -> str:
    digest = digest_file(path, "H0_CANDIDATE_REVIEW_MISSING")
    try:
        payload = strict_json(path.read_bytes())
    except OSError as exc:
        raise RequestError("H0_CANDIDATE_REVIEW_MISSING") from exc
    except RequestError as exc:
        raise RequestError("H0_CANDIDATE_REVIEW_INVALID") from exc
    require(isinstance(payload, dict), "H0_CANDIDATE_REVIEW_INVALID")
    require(
        payload.get("schema_version") == "npi-independent-review-v1"
        and payload.get("reviewed_commit") == candidate["candidate_commit"]
        and payload.get("reviewed_tree") == candidate["candidate_tree"]
        and payload.get("independent") is True
        and payload.get("verdict") == "PASS_FOR_EXTERNAL_REVIEW"
        and payload.get("ready_to_merge_or_publish") is True,
        "H0_CANDIDATE_REVIEW_BINDING_INVALID",
    )
    return digest


def validate_historical_review(path: Path, *, candidate_root: Path) -> str:
    digest = digest_file(path, "H0_HISTORICAL_REVIEW_MISSING")
    try:
        review_text = path.read_text(encoding="utf-8")
        receipt_text = (candidate_root / HISTORICAL_RECEIPT).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise RequestError("H0_HISTORICAL_REVIEW_BINDING_INVALID") from exc
    match = re.search(
        r"^external_review_sha256:\s*[\"']?([0-9a-f]{64})[\"']?\s*$",
        receipt_text,
        flags=re.MULTILINE,
    )
    require(
        match is not None and match.group(1) == digest,
        "H0_HISTORICAL_REVIEW_BINDING_INVALID",
    )
    require(
        "INCONCLUSIVE" in review_text and HISTORICAL_BLOCKER in review_text,
        "H0_HISTORICAL_REVIEW_INVALID",
    )
    return digest


def load_runtime_identity(path: Path) -> tuple[dict[str, Any], str]:
    try:
        payload = strict_json(path.read_bytes())
    except OSError as exc:
        raise RequestError("H0_RUNTIME_IDENTITY_MISSING") from exc
    required = {
        "model_name",
        "full_local_digest",
        "size_bytes",
        "quantization_level",
        "capabilities",
        "ollama_version",
    }
    require(isinstance(payload, dict) and set(payload) == required, "H0_RUNTIME_IDENTITY_INVALID")
    require(payload["model_name"] == "qwen3.5:9b", "H0_RUNTIME_IDENTITY_INVALID")
    require(
        isinstance(payload["full_local_digest"], str)
        and HEX64.fullmatch(payload["full_local_digest"]),
        "H0_RUNTIME_IDENTITY_INVALID",
    )
    require(
        type(payload["size_bytes"]) is int and payload["size_bytes"] > 0,
        "H0_RUNTIME_IDENTITY_INVALID",
    )
    require(payload["quantization_level"] == "Q4_K_M", "H0_RUNTIME_IDENTITY_INVALID")
    capabilities = payload["capabilities"]
    require(
        isinstance(capabilities, list)
        and all(isinstance(value, str) and value for value in capabilities)
        and "vision" in capabilities,
        "H0_RUNTIME_IDENTITY_INVALID",
    )
    require(
        isinstance(payload["ollama_version"], str) and bool(payload["ollama_version"]),
        "H0_RUNTIME_IDENTITY_INVALID",
    )
    normalized = {key: payload[key] for key in sorted(required)}
    return normalized, sha(canonical(normalized))


def _path(value: object) -> Path:
    require(isinstance(value, str) and bool(value), "H0_PATH_PLAN_INVALID")
    path = Path(value)
    require(path.is_absolute() and ".." not in path.parts, "H0_PATH_PLAN_INVALID")
    require(not str(path).startswith(("\\\\", "//")), "H0_PATH_PLAN_INVALID")
    return path


def load_path_plan(path: Path) -> tuple[dict[str, dict[str, str]], str]:
    try:
        payload = strict_json(path.read_bytes())
    except OSError as exc:
        raise RequestError("H0_PATH_PLAN_MISSING") from exc
    require(
        isinstance(payload, dict) and set(payload) == set(REQUIRED_PATH_PLAN),
        "H0_PATH_PLAN_INVALID",
    )
    normalized: dict[str, dict[str, str]] = {}
    all_paths: list[Path] = []
    for section, labels in REQUIRED_PATH_PLAN.items():
        value = payload.get(section)
        require(isinstance(value, dict) and set(value) == labels, "H0_PATH_PLAN_INVALID")
        normalized[section] = {}
        for label in sorted(labels):
            item = _path(value[label])
            normalized[section][label] = str(item)
            all_paths.append(item)
    for index, left in enumerate(all_paths):
        for right in all_paths[index + 1 :]:
            try:
                common = os.path.commonpath(
                    (os.path.normcase(str(left)), os.path.normcase(str(right)))
                )
            except ValueError:
                common = ""
            require(
                common not in {os.path.normcase(str(left)), os.path.normcase(str(right))},
                "H0_PATH_PLAN_COLLISION",
            )
    return normalized, sha(canonical(normalized))


def _load_state(root: Path) -> str:
    state_path = root / "PROJECT_STATE.json"
    try:
        data = state_path.read_bytes()
    except OSError as exc:
        raise RequestError("H0_PROJECT_STATE_MISSING") from exc
    payload = strict_json(data)
    require(isinstance(payload, dict), "H0_PROJECT_STATE_INVALID")
    phase_status = payload.get("phase_status")
    require(
        isinstance(phase_status, Mapping) and phase_status.get("N2B2") == "LOCKED",
        "H0_N2B2_NOT_LOCKED",
    )
    return sha(data)


def build_request(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.candidate_root)
    source = source_identity(root, args.expected_candidate)
    state_sha = _load_state(root)
    candidate_review_sha = validate_candidate_review(
        Path(args.candidate_review_artifact), candidate=source
    )
    historical_review_sha = validate_historical_review(
        Path(args.historical_review_artifact), candidate_root=root
    )
    prior_review_sha = digest_file(Path(args.prior_s20_review), "H0_PRIOR_REVIEW_MISSING")
    quality_sha = digest_file(Path(args.quality_evidence), "H0_QUALITY_EVIDENCE_MISSING")
    identity, identity_sha = load_runtime_identity(Path(args.runtime_identity))
    s3_sha = digest_file(Path(args.s3_manifest), "H0_S3_MANIFEST_MISSING")
    s20_sha = digest_file(Path(args.s20_manifest), "H0_S20_MANIFEST_MISSING")
    require(
        HEX64.fullmatch(args.model_cache_binding_sha256) is not None, "H0_CACHE_BINDING_INVALID"
    )
    path_plan, path_sha = load_path_plan(Path(args.path_plan))
    bindings = {
        "candidate_commit": source["candidate_commit"],
        "candidate_tree": source["candidate_tree"],
        "source_manifest_sha256": source["source_manifest_sha256"],
        "project_state_sha256": state_sha,
        "candidate_review_sha256": candidate_review_sha,
        "historical_review_sha256": historical_review_sha,
        "prior_s20_review_sha256": prior_review_sha,
        "quality_evidence_sha256": quality_sha,
        "runtime_identity_sha256": identity_sha,
        "s3_manifest_sha256": s3_sha,
        "s20_manifest_sha256": s20_sha,
        "model_cache_binding_sha256": args.model_cache_binding_sha256,
        "path_plan_sha256": path_sha,
    }
    proposed_lease = {
        "schema_version": "npi-synthetic-execution-lease-v3",
        "status": "DRAFT",
        "owner_id": "Jovi",
        "purpose": "SYNTHETIC_S3_S20_ENGINEERING_VALIDATION",
        "not_before_utc": None,
        "expires_at_utc": None,
        "bindings": bindings,
        "boundaries": BOUNDARIES,
        "max_fresh_s3_runs": 1,
        "max_fresh_s20_runs": 1,
        "production_unlock": False,
    }
    return {
        "schema_version": "npi-synthetic-lease-request-v1",
        "status": "DRAFT_OWNER_REVIEW_REQUIRED",
        "execution_authorized": False,
        "owner_anchor_created": False,
        "approved_lease_created": False,
        "candidate": source,
        "project_state_sha256": state_sha,
        "project_state_n2b2": "LOCKED",
        "candidate_review_artifact_sha256": candidate_review_sha,
        "historical_review_artifact_sha256": historical_review_sha,
        "prior_s20_review_sha256": prior_review_sha,
        "quality_evidence_sha256": quality_sha,
        "runtime_identity": identity,
        "runtime_identity_sha256": identity_sha,
        "s3_manifest_sha256": s3_sha,
        "s20_manifest_sha256": s20_sha,
        "model_cache_binding_sha256": args.model_cache_binding_sha256,
        "path_plan": path_plan,
        "path_plan_sha256": path_sha,
        "proposed_lease": proposed_lease,
        "owner_actions_required": [
            "independently inspect this DRAFT request",
            "select a validity window and create exact APPROVED lease bytes outside Git",
            "create the separate Owner anchor for those exact lease bytes",
        ],
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--expected-candidate", required=True)
    parser.add_argument("--candidate-review-artifact", type=Path, required=True)
    parser.add_argument("--historical-review-artifact", type=Path, required=True)
    parser.add_argument("--prior-s20-review", type=Path, required=True)
    parser.add_argument("--quality-evidence", type=Path, required=True)
    parser.add_argument("--runtime-identity", type=Path, required=True)
    parser.add_argument("--s3-manifest", type=Path, required=True)
    parser.add_argument("--s20-manifest", type=Path, required=True)
    parser.add_argument("--model-cache-binding-sha256", required=True)
    parser.add_argument("--path-plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv)
        packet = build_request(args)
        args.out.write_bytes(canonical(packet))
    except (OSError, RequestError) as exc:
        print(
            json.dumps(
                {"result": "H0_REQUEST_INVALID", "error": str(exc), "execution_authorized": False}
            )
        )
        return 1
    print("H1_DRAFT_REQUEST_READY_FOR_OWNER_REVIEW")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
