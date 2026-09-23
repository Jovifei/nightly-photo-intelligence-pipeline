"""Owner-controlled, fixed-location admission for the public Real20 entry.

This module only reads explicit control documents. No source asset is opened.
The Owner creates the anchor and receipts externally after independent review.
"""

from __future__ import annotations

import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..engineering.common import canonical, sha256, strict_json
from ..engineering.evidence import quality_matrix
from ..engineering.path_policy import checked_path, overlaps
from ..ingest.g1_contract import path_fingerprint
from ..ingest.read_only_capability import (
    CapabilityDisposition,
    _windows_probe,
    verify_source_read_only_capability,
)
from ..windows_bound_promotion import BoundDirectory, bind_existing_directory
from .contracts import Real20Error, load_manifest, validate_data_receipt
from .identity import candidate_identity

FROZEN_G1 = "29eee5fdb8e16c85649752501c4b722d2b4d071950c8a989add040e895a75c47"
H3_REVIEW = "820f76ba48c5d55fd66b83f158afe7b12b62aad0315df710a57163ea407ffc33"


def control_bytes(path: Path) -> bytes:
    """Read a regular control through native bound directories; reject aliases."""
    try:
        checked_path(path.parent, must_exist=True)
        info = path.lstat()
        if info.st_nlink != 1 or not stat.S_ISREG(info.st_mode):
            raise Real20Error("REAL20_CONTROL_UNAVAILABLE")
        if ":" in path.name or path.name.endswith((".", " ")):
            raise Real20Error("REAL20_CONTROL_PATH_INVALID")
        with (
            bind_existing_directory(path.parent, writable=False) as parent,
            parent.open_file(path.name) as handle,
        ):
            return handle.read_all(max_bytes=16 * 1024 * 1024)
    except Real20Error:
        raise
    except Exception as exc:
        raise Real20Error("REAL20_CONTROL_UNAVAILABLE") from exc


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise Real20Error(code)


def protect_consumption(path: Path | BoundDirectory) -> None:
    """Require persistent claims to resist deletion and permission changes.

    Creation is allowed, but clearing old consumption is not. No ACL is changed.
    Unknown/platform/sharing errors fail closed.
    """
    if isinstance(path, BoundDirectory):
        path._verify()
        target_path = Path(path.identity.final_path)
    else:
        target_path = path
    for target, rights in (
        (target_path, (0x40, 0x10000, 0x40000, 0x80000)),
        (target_path.parent, (0x40,)),
    ):
        for right in rights:
            _require(
                _windows_probe(target, "directory", right) == CapabilityDisposition.DENIED,
                "REAL20_LEDGER_MUTATION_NOT_DENIED",
            )


def admit(
    *,
    project_root: Path,
    source_root: Path,
    manifest_path: Path,
    credential_path: Path,
    anchor_path: Path,
    ledger_root: Path,
    output_root: Path,
    cache_root: Path,
    runtime_identity_path: Path,
    model_identity_path: Path,
    bound_ledger: BoundDirectory | None = None,
) -> dict[str, Any]:
    controls = (
        manifest_path,
        credential_path,
        anchor_path,
        runtime_identity_path,
        model_identity_path,
    )
    for path in controls:
        _require(
            path.is_absolute() and not overlaps(path, source_root), "REAL20_CONTROL_SOURCE_OVERLAP"
        )
        checked_path(path.parent, must_exist=True)
    identity = candidate_identity(project_root)
    config = strict_json(control_bytes(project_root / "approvals/n2b1p_runtime_configuration.json"))
    runtime = Path(config["runtime_parent"])
    trusted = runtime / "owner-approvals"
    for actual, name in (
        (credential_path, "real20_lease.json"),
        (manifest_path, "real20_manifest.json"),
        (runtime_identity_path, "real20_runtime_identity.json"),
        (model_identity_path, "real20_model_identity.json"),
    ):
        _require(actual == trusted / name, "REAL20_UNTRUSTED_CONTROL_PATH")
    expected_anchor = trusted / "real20_execution_anchor.json"
    _require(anchor_path == expected_anchor, "REAL20_UNTRUSTED_ANCHOR_PATH")
    # Paths belong in hashes/lexical checks; live handles belong in object checks.
    # Never stringify BoundDirectory (its repr is not an Owner-approved path).
    _require(isinstance(ledger_root, Path), "REAL20_LEDGER_PATH_REQUIRED")
    ledger_path = runtime / "real20-execution-ledger"
    _require(ledger_root == ledger_path, "REAL20_LEDGER_BINDING_INVALID")
    with bind_existing_directory(ledger_path, writable=False) as configured_ledger:
        if bound_ledger is not None:
            _require(isinstance(bound_ledger, BoundDirectory), "REAL20_LEDGER_HANDLE_REQUIRED")
            bound_ledger._verify()
            _require(
                bound_ledger.identity == configured_ledger.identity,
                "REAL20_LEDGER_OBJECT_CHANGED",
            )
            protect_consumption(bound_ledger)
        else:
            protect_consumption(configured_ledger)
    _require(cache_root == Path(config["cache_root"]), "REAL20_CACHE_BINDING_INVALID")
    protected_files = [
        expected_anchor,
        *(
            trusted / ("real20_" + label + ".json")
            for label in ("data_receipt", "code_review", "quality")
        ),
        trusted / "real20_frozen_manifest.txt",
        *controls,
    ]
    _require(not overlaps(trusted, source_root), "REAL20_CONTROL_SOURCE_OVERLAP")
    _require(
        verify_source_read_only_capability(trusted, protected_files).verified,
        "REAL20_OWNER_CONTROLS_NOT_PROTECTED",
    )
    anchor_raw = control_bytes(expected_anchor)
    anchor = strict_json(anchor_raw)
    from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

    schema = strict_json(
        control_bytes(project_root / "schemas/n2b2_real20_owner_anchor_v1.schema.json")
    )
    _require(not list(Draft202012Validator(schema).iter_errors(anchor)), "REAL20_ANCHOR_INVALID")
    _require(isinstance(anchor, dict), "REAL20_ANCHOR_INVALID")
    _require(
        anchor.get("status") == "APPROVED"
        and anchor.get("owner_id") == "Jovi"
        and anchor.get("purpose") == "REAL20_READ_ONLY_EVALUATION"
        and anchor.get("production_unlock") is False,
        "REAL20_ANCHOR_NOT_APPROVED",
    )
    for key in ("candidate_commit", "candidate_tree", "source_manifest_sha256"):
        _require(anchor.get(key) == identity[key], "REAL20_REVIEWED_SOURCE_MISMATCH")
    documents = {}
    for label in ("data_receipt", "code_review", "quality"):
        raw = control_bytes(trusted / ("real20_" + label + ".json"))
        _require(sha256(raw) == anchor.get(label + "_sha256"), "REAL20_RECEIPT_BINDING_INVALID")
        documents[label] = strict_json(raw)
    review = documents["code_review"]
    _require(
        review.get("verdict") == "PASS_FOR_REAL20_EVALUATION"
        and all(
            review.get(key) == identity[key]
            for key in ("candidate_commit", "candidate_tree", "source_manifest_sha256")
        ),
        "REAL20_INDEPENDENT_REVIEW_REQUIRED",
    )
    quality = documents["quality"]
    _require(
        quality_matrix(quality.get("checks", []), python_supported=quality.get("python_supported"))[
            "complete"
        ],
        "REAL20_FINAL_QUALITY_REQUIRED",
    )
    _require(
        quality.get("candidate_commit") == identity["candidate_commit"]
        and quality.get("status") == "PASS",
        "REAL20_FINAL_QUALITY_REQUIRED",
    )
    data = documents["data_receipt"]
    validate_data_receipt(data)
    try:
        start = datetime.fromisoformat(data["not_before_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(data["expires_at_utc"].replace("Z", "+00:00"))
        _require(
            start.tzinfo is not None
            and end.tzinfo is not None
            and start <= datetime.now(UTC) < end,
            "REAL20_DATA_OUTSIDE_WINDOW",
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise Real20Error("REAL20_DATA_OUTSIDE_WINDOW") from exc
    _require(
        data.get("source_root_fingerprint") == path_fingerprint(source_root),
        "REAL20_SOURCE_ROOT_BINDING_INVALID",
    )
    _require(
        anchor.get("credential_sha256") == sha256(control_bytes(credential_path)),
        "REAL20_ANCHOR_CREDENTIAL_MISMATCH",
    )
    frozen = control_bytes(trusted / "real20_frozen_manifest.txt")
    _require(
        sha256(frozen) == FROZEN_G1 and data.get("frozen_manifest_sha256") == FROZEN_G1,
        "REAL20_FROZEN_SELECTION_MISMATCH",
    )
    manifest = load_manifest(manifest_path)
    _require(data.get("manifest_sha256") == manifest.sha256, "REAL20_MANIFEST_BINDING_INVALID")
    names = [
        line.strip().replace("\\", "/").casefold()
        for line in frozen.decode("utf-8-sig").splitlines()
        if line.strip()
    ]
    _require(
        names == [asset.relative_path.casefold() for asset in manifest.assets],
        "REAL20_FROZEN_SELECTION_MISMATCH",
    )
    _require(
        data.get("source_root_fingerprint")
        == manifest.source_fingerprint
        == path_fingerprint(source_root),
        "REAL20_SOURCE_ROOT_BINDING_INVALID",
    )
    _require(anchor.get("h3_review_sha256") == H3_REVIEW, "REAL20_H3_BINDING_INVALID")
    plan = {
        key: str(value)
        for key, value in {
            "source_root": source_root,
            "output_root": output_root,
            "ledger_root": ledger_root,
            "cache_root": cache_root,
        }.items()
    }
    _require(
        anchor.get("path_plan_sha256") == sha256(canonical(plan)),
        "REAL20_PATH_PLAN_BINDING_INVALID",
    )
    for root in (source_root, ledger_root, output_root, cache_root, trusted):
        checked_path(root, must_exist=True)
    _require(
        not overlaps(output_root, trusted) and not overlaps(source_root, trusted),
        "REAL20_CONTROL_SOURCE_OVERLAP",
    )
    return {
        "anchor_sha256": sha256(anchor_raw),
        "source": identity,
        "control_digests": {str(path): sha256(control_bytes(path)) for path in controls},
    }
