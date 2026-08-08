"""N2B1P cache promotion for exact N2B1R local-research bytes only.

This module deliberately does not import Torch or any inference backend.  Its
only mutation is an atomic, Git-external copy from a prior N2B1R quarantine
run into a content-addressed cache entry after revalidating every control
document at the public action boundary.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from ._paths import find_project_root
from .domain.errors import GateNotAuthorizedError, PreflightUnsatisfiedError
from .json_strict import load_json_strict
from .n2b1p_integrity import (
    build_legacy_cache_manifest_bytes,
    build_manifest_binding_payload,
    canonical_json_bytes,
    compute_legacy_cache_manifest_sha256,
    compute_manifest_binding_sha256,
    load_n2b1p_runtime_configuration,
    sha256_bytes,
    validate_bound_cache_root,
)
from .windows_bound_promotion import (
    BoundDirectory,
    BoundFile,
    BoundStagingTransaction,
    bind_existing_directory,
)

DEFAULT_QUARANTINE_PARENT = Path(
    "E" + ":" + chr(92) + "Claude_allow" + chr(92) + "Download" + chr(92) + "npi-quarantine"
)
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PromotionArtifact:
    """One exact N2B1R evidence-bound artifact, not a reusable credential."""

    artifact_id: str
    revision: str
    filename: str
    byte_count: int
    local_sha256: str
    transfer_manifest_sha256: str
    cache_manifest_sha256: str = ""
    runtime_configuration_digest: str = ""


@dataclass(frozen=True)
class PromotionResult:
    """Path-redactable N2B1P result; callers must not print ``manifest_path``."""

    artifact_id: str
    cache_key: str
    byte_count: int
    local_sha256: str
    status: str
    manifest_path: Path
    manifest_sha256: str


def _deny(message: str) -> None:
    raise GateNotAuthorizedError(message)


def _integrity_failure(message: str) -> None:
    raise PreflightUnsatisfiedError(message)


def _mapping(value: object, message: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        _deny(message)
    return cast(Mapping[str, object], value)


def _strict_schema(project_root: Path, schema_name: str, document: object) -> None:
    try:
        schema = load_json_strict(project_root / "schemas" / schema_name)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    except Exception as exc:  # noqa: BLE001 - fixed control data must be usable
        raise GateNotAuthorizedError("N2B1P fixed schema is unavailable") from exc
    if list(validator.iter_errors(document)):
        _deny("N2B1P control document schema is invalid")


def _load_yaml_strict(path: Path) -> Mapping[str, object]:
    try:
        import yaml

        class UniqueKeyLoader(yaml.SafeLoader):  # type: ignore[misc]
            pass

        def construct_mapping(loader: Any, node: Any, deep: bool = False) -> dict[object, object]:
            pairs = loader.construct_pairs(node, deep=deep)
            result: dict[object, object] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("duplicate YAML member")
                result[key] = value
            return result

        UniqueKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
        )
        value = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    except Exception as exc:  # noqa: BLE001 - fail closed at the action boundary
        raise GateNotAuthorizedError("N2B1P approval or task cannot be loaded") from exc
    return _mapping(value, "N2B1P approval or task has invalid structure")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_filename(value: object) -> str:
    if not isinstance(value, str) or _SAFE_FILENAME.fullmatch(value) is None:
        _deny("N2B1P artifact filename is invalid")
    return cast(str, value)


def _safe_sha256(value: object) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        _deny("N2B1P artifact digest is invalid")
    return cast(str, value)


def _positive_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        _deny("N2B1P artifact byte count is invalid")
    return cast(int, value)


def _artifact_from_mapping(value: Mapping[str, object]) -> PromotionArtifact:
    artifact_id = value.get("id")
    revision = value.get("revision")
    if not isinstance(artifact_id, str) or not artifact_id or not isinstance(revision, str):
        _deny("N2B1P artifact identity is invalid")
    return PromotionArtifact(
        artifact_id=cast(str, artifact_id),
        revision=cast(str, revision),
        filename=_safe_filename(value.get("filename")),
        byte_count=_positive_int(value.get("byte_count")),
        local_sha256=_safe_sha256(value.get("local_sha256")),
        transfer_manifest_sha256=_safe_sha256(value.get("transfer_manifest_sha256")),
    )


def _artifact_map(values: object) -> dict[str, PromotionArtifact]:
    if not isinstance(values, list) or len(values) != 3:
        _deny("N2B1P artifact set is invalid")
    artifact_values = cast(list[object], values)
    items = [
        _artifact_from_mapping(_mapping(value, "N2B1P artifact set is invalid"))
        for value in artifact_values
    ]
    result = {item.artifact_id: item for item in items}
    if len(result) != 3:
        _deny("N2B1P artifact set has duplicate identifiers")
    return result


def _register_map(values: object) -> dict[str, tuple[str, str]]:
    if not isinstance(values, list) or len(values) != 3:
        _deny("N2B1P acquisition register is invalid")
    result: dict[str, tuple[str, str]] = {}
    register_values = cast(list[object], values)
    for raw in register_values:
        item = _mapping(raw, "N2B1P acquisition register is invalid")
        artifact_id = item.get("id")
        revision = item.get("revision")
        if not isinstance(artifact_id, str) or not isinstance(revision, str):
            _deny("N2B1P acquisition register is invalid")
        result[cast(str, artifact_id)] = (cast(str, revision), _safe_filename(item.get("filename")))
    if len(result) != 3:
        _deny("N2B1P acquisition register has duplicate identifiers")
    return result


def _validate_authorization(
    *,
    project_root: Path,
    state: Mapping[str, object],
    approval: Mapping[str, object],
    task: Mapping[str, object],
    evidence: Mapping[str, object],
    promotion_evidence: Mapping[str, object],
    register: Mapping[str, object],
    runtime_configuration_digest: str,
    cache_root_identity: str,
) -> dict[str, PromotionArtifact]:
    authorization = _mapping(state.get("authorization"), "N2B1P state is invalid")
    phase_status = _mapping(state.get("phase_status"), "N2B1P state is invalid")
    gates = _mapping(authorization.get("capability_gates"), "N2B1P state is invalid")
    active = authorization.get("active_execution")
    task_stop = _mapping(task.get("mandatory_stop"), "N2B1P task is invalid")
    evidence_actions = _mapping(evidence.get("prohibited_actions"), "N2B1P evidence is invalid")
    approval_evidence = _mapping(approval.get("n2b1r_evidence"), "N2B1P approval is invalid")
    approval_configuration = _mapping(
        approval.get("runtime_configuration"), "N2B1P approval is invalid"
    )
    task_approval = _mapping(task.get("approval"), "N2B1P task is invalid")
    promotion_actions = _mapping(
        promotion_evidence.get("prohibited_actions"), "N2B1P promotion evidence is invalid"
    )
    if not all(
        (
            state.get("schema_version") == "1.7",
            phase_status.get("N2B1R") == "ACQUISITION_COMPLETE",
            phase_status.get("N2B1P") == "AUTHORIZED",
            gates.get("N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION") == "ACQUISITION_COMPLETE",
            gates.get("N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION") == "AUTHORIZED",
            authorization.get("real_model_execution") == "NOT_AUTHORIZED",
            authorization.get("network_access") == "DENY_BY_DEFAULT",
            active
            == {
                "phase": "N2B1P",
                "capability": "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
                "source_photo_content_read": "NOT_AUTHORIZED",
                "source_photo_exif_read": "NOT_AUTHORIZED",
                "sqlite_ingest_write": "NOT_AUTHORIZED",
            },
            state.get("required_stop_after")
            == {
                "condition": "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
                "next_action": "EXTERNAL_REVIEW_N2B1P_REMEDIATION",
            },
            approval.get("status") == "APPROVED",
            task.get("capability") == "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
            task.get("phase")
            == {
                "id": "N2B1P",
                "title": "Local-research content-addressed cache promotion",
                "status": "AUTHORIZED",
            },
            task_stop.get("value") is True,
            evidence.get("result") == "N2B1R_ACQUISITION_COMPLETE_AWAITING_LOCAL_VERIFICATION",
            evidence.get("quarantine_storage") == "EXTERNAL_REDACTED_NON_REPARSE",
            evidence_actions.get("cache_promotion") == "NOT_PERFORMED",
            promotion_evidence.get("result")
            == "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
            promotion_evidence.get("n2b1r_evidence_sha256")
            == _sha256_file(project_root / "research" / "N2B1R_acquisition_evidence.json"),
            promotion_evidence.get("storage")
            == {
                "quarantine": "EXTERNAL_REDACTED_NON_REPARSE",
                "cache": "EXTERNAL_REDACTED_CONTENT_ADDRESSED_NON_REPARSE",
                "retained_quarantine": True,
                "cache_layout": "<local_sha256>/<approved_filename>",
            },
            all(value == "NOT_PERFORMED" for value in promotion_actions.values()),
            approval_evidence.get("path") == "research/N2B1R_acquisition_evidence.json",
            approval_evidence.get("sha256")
            == _sha256_file(project_root / "research" / "N2B1R_acquisition_evidence.json"),
            approval_configuration
            == {
                "path": "approvals/n2b1p_runtime_configuration.json",
                "configuration_digest": runtime_configuration_digest,
                "cache_root_identity": cache_root_identity,
            },
            task_approval.get("n2b1p_runtime_configuration")
            == "approvals/n2b1p_runtime_configuration.json",
        )
    ):
        _deny("N2B1P authorization is inactive or broadened")
    approved = _artifact_map(approval.get("allowed_artifacts"))
    evidenced = _artifact_map(evidence.get("artifacts"))
    if approved != evidenced:
        _deny("N2B1P approval does not exactly bind N2B1R evidence")
    registered = _register_map(register.get("artifacts"))
    if set(approved) != set(registered):
        _deny("N2B1P approval does not exactly bind the acquisition register")
    for artifact_id, artifact in approved.items():
        if registered[artifact_id] != (artifact.revision, artifact.filename):
            _deny("N2B1P approval differs from the acquisition register")
    promoted = promotion_evidence.get("artifacts")
    if not isinstance(promoted, list) or len(promoted) != 3:
        _deny("N2B1P promotion evidence has an invalid artifact set")
    promotion_bindings: dict[str, tuple[int, str, str]] = {}
    cache_manifest_hashes: dict[str, str] = {}
    promotion_artifacts = cast(list[object], promoted)
    for raw in promotion_artifacts:
        item = _mapping(raw, "N2B1P promotion evidence has invalid artifact data")
        promotion_id = item.get("id")
        if not isinstance(promotion_id, str):
            _deny("N2B1P promotion evidence has invalid artifact data")
        promotion_bindings[cast(str, promotion_id)] = (
            _positive_int(item.get("byte_count")),
            _safe_sha256(item.get("local_sha256")),
            _safe_sha256(item.get("transfer_manifest_sha256")),
        )
        cache_manifest_hashes[cast(str, promotion_id)] = _safe_sha256(
            item.get("cache_manifest_sha256")
        )
    expected_bindings = {
        artifact_id: (artifact.byte_count, artifact.local_sha256, artifact.transfer_manifest_sha256)
        for artifact_id, artifact in approved.items()
    }
    if promotion_bindings != expected_bindings:
        _deny("N2B1P promotion evidence does not exactly bind approved artifacts")
    runtime_evidence = _mapping(
        promotion_evidence.get("runtime_configuration"),
        "N2B1P runtime configuration evidence is invalid",
    )
    if runtime_evidence != {
        "path": "approvals/n2b1p_runtime_configuration.json",
        "configuration_digest": runtime_configuration_digest,
        "cache_root_identity": cache_root_identity,
    }:
        _deny("N2B1P promotion evidence is not bound to the runtime configuration")
    result: dict[str, PromotionArtifact] = {}
    for artifact_id, artifact in approved.items():
        expected_manifest_hash = compute_legacy_cache_manifest_sha256(
            artifact_id=artifact.artifact_id,
            revision=artifact.revision,
            filename=artifact.filename,
            byte_count=artifact.byte_count,
            local_sha256=artifact.local_sha256,
            transfer_manifest_sha256=artifact.transfer_manifest_sha256,
        )
        if cache_manifest_hashes.get(artifact_id) != expected_manifest_hash:
            _deny("N2B1P promotion evidence cache manifest hash is not canonical")
        item = next(
            _mapping(raw, "N2B1P promotion evidence has invalid artifact data")
            for raw in promotion_artifacts
            if _mapping(raw, "N2B1P promotion evidence has invalid artifact data").get("id")
            == artifact_id
        )
        binding = _mapping(
            item.get("legacy_cache_manifest_binding"),
            "N2B1P legacy cache manifest binding is invalid",
        )
        payload = _mapping(binding.get("payload"), "N2B1P legacy cache manifest binding is invalid")
        completed_at = payload.get("promotion_completed_at_utc")
        if not isinstance(completed_at, str) or not completed_at:
            _deny("N2B1P legacy cache manifest binding has no completion time")
        completed_at_text = cast(str, completed_at)
        expected_payload = build_manifest_binding_payload(
            artifact_id=artifact.artifact_id,
            approved_evidence_id=artifact.transfer_manifest_sha256,
            approved_payload_sha256=artifact.local_sha256,
            payload_size_bytes=artifact.byte_count,
            cache_relative_path=f"{artifact.local_sha256}/{artifact.filename}",
            cache_filename=artifact.filename,
            promotion_completed_at_utc=completed_at_text,
            cache_root_identity=cache_root_identity,
            runtime_configuration_digest=runtime_configuration_digest,
            raw_cache_manifest_sha256=expected_manifest_hash,
        )
        if payload != expected_payload or binding.get(
            "binding_payload_sha256"
        ) != compute_manifest_binding_sha256(expected_payload):
            _deny("N2B1P legacy cache manifest binding does not match approved evidence")
        result[artifact_id] = PromotionArtifact(
            artifact_id=artifact.artifact_id,
            revision=artifact.revision,
            filename=artifact.filename,
            byte_count=artifact.byte_count,
            local_sha256=artifact.local_sha256,
            transfer_manifest_sha256=artifact.transfer_manifest_sha256,
            cache_manifest_sha256=expected_manifest_hash,
            runtime_configuration_digest=runtime_configuration_digest,
        )
    return result


def load_authorized_promotion(
    artifact_id: str, *, project_root: Path | None = None
) -> PromotionArtifact:
    """Strict-load the N2B1P control plane and one exact approved artifact."""
    root = project_root or find_project_root()
    state = _mapping(load_json_strict(root / "PROJECT_STATE.json"), "N2B1P state is invalid")
    evidence = _mapping(
        load_json_strict(root / "research" / "N2B1R_acquisition_evidence.json"),
        "N2B1P evidence is invalid",
    )
    promotion_evidence = _mapping(
        load_json_strict(root / "research" / "N2B1P_cache_promotion_evidence.json"),
        "N2B1P promotion evidence is invalid",
    )
    register = _mapping(
        load_json_strict(root / "research" / "N2B1R_local_research_artifact_register.json"),
        "N2B1P acquisition register is invalid",
    )
    approval = _load_yaml_strict(root / "approvals" / "owner_n2b1p_cache_promotion.yaml")
    task = _load_yaml_strict(root / "tasks" / "phase_n2b1p_local_research_cache_promotion.yaml")
    _strict_schema(root, "project_state_v1_7.schema.json", state)
    _strict_schema(root, "n2b1r_acquisition_evidence_v1.schema.json", evidence)
    _strict_schema(root, "n2b1p_cache_promotion_evidence_v1.schema.json", promotion_evidence)
    _strict_schema(root, "n2b1r_artifact_register_v1.schema.json", register)
    _strict_schema(root, "owner_n2b1p_cache_promotion_v1_0.schema.json", approval)
    _strict_schema(root, "task_contract_n2b1p_v1_0.schema.json", task)
    runtime_configuration = load_n2b1p_runtime_configuration(root)
    artifacts = _validate_authorization(
        project_root=root,
        state=state,
        approval=approval,
        task=task,
        evidence=evidence,
        promotion_evidence=promotion_evidence,
        register=register,
        runtime_configuration_digest=runtime_configuration.configuration_digest,
        cache_root_identity=runtime_configuration.cache_root_identity,
    )
    try:
        return artifacts[artifact_id]
    except KeyError:
        _deny("N2B1P artifact is not approved")
    raise AssertionError("unreachable")


def _strict_mapping_bytes(raw: bytes, message: str) -> Mapping[str, object]:
    def reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON member")
            result[key] = value
        return result

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=reject_duplicate_pairs,
            parse_constant=lambda _value: (_ for _ in ()).throw(ValueError()),
        )
    except (UnicodeDecodeError, ValueError) as exc:
        raise PreflightUnsatisfiedError(message) from exc
    return _mapping(value, message)


def _read_bound_file(file: BoundFile, *, max_bytes: int) -> bytes:
    return file.read_all(max_bytes=max_bytes)


def _validate_transfer_manifest(run: BoundDirectory, artifact: PromotionArtifact) -> None:
    with run.open_file("transfer_manifest.json") as manifest:
        raw = _read_bound_file(manifest, max_bytes=64 * 1024)
    if sha256_bytes(raw) != artifact.transfer_manifest_sha256:
        _integrity_failure("N2B1P transfer manifest digest does not match evidence")
    value = _strict_mapping_bytes(raw, "N2B1P transfer manifest is invalid")
    expected = {
        "stage": "N2B1R",
        "artifact_id": artifact.artifact_id,
        "revision": artifact.revision,
        "filename": artifact.filename,
        "request_domain": "download.pytorch.org",
        "final_domain": "download.pytorch.org",
        "content_length_bytes": artifact.byte_count,
        "byte_count": artifact.byte_count,
        "sha256": artifact.local_sha256,
        "weights_rights": "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
        "use_restriction": "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION",
    }
    if any(value.get(key) != expected_value for key, expected_value in expected.items()):
        _integrity_failure("N2B1P transfer manifest does not match evidence")


def _verify_quarantine_payload(run: BoundDirectory, artifact: PromotionArtifact) -> None:
    """Rehash a handle-bound source before every copy and cache hit."""
    with run.open_file(artifact.filename) as source:
        digest, byte_count = source.sha256_and_size()
    if byte_count != artifact.byte_count or digest != artifact.local_sha256:
        _integrity_failure("N2B1P quarantine payload does not match approved digest")


def _copy_verified_payload(
    run: BoundDirectory, transaction: BoundStagingTransaction, artifact: PromotionArtifact
) -> None:
    source_digest = hashlib.sha256()
    byte_count = 0
    with (
        run.open_file(artifact.filename) as source,
        transaction.create_file(artifact.filename) as destination,
    ):
        for chunk in source.iter_chunks():
            byte_count += len(chunk)
            if byte_count > artifact.byte_count:
                _integrity_failure("N2B1P quarantine payload exceeds approved byte count")
            source_digest.update(chunk)
            destination.write(chunk)
        destination.flush()
    if byte_count != artifact.byte_count or source_digest.hexdigest() != artifact.local_sha256:
        _integrity_failure("N2B1P quarantine payload does not match approved digest")
    with transaction.staging.open_file(artifact.filename) as payload:
        digest, size = payload.sha256_and_size()
    if size != artifact.byte_count or digest != artifact.local_sha256:
        _integrity_failure("N2B1P cached payload reread digest mismatch")


def _cache_manifest(artifact: PromotionArtifact) -> bytes:
    return build_legacy_cache_manifest_bytes(
        artifact_id=artifact.artifact_id,
        revision=artifact.revision,
        filename=artifact.filename,
        byte_count=artifact.byte_count,
        local_sha256=artifact.local_sha256,
        transfer_manifest_sha256=artifact.transfer_manifest_sha256,
    )


def _validate_cache_entry(
    cache_root: BoundDirectory, artifact: PromotionArtifact
) -> PromotionResult:
    cache_entry: BoundDirectory | None = None
    try:
        cache_entry = cache_root.open_directory(artifact.local_sha256, writable=False)
        expected_names = {artifact.filename, "cache_manifest.json"}
        names = cache_entry.list_names()
        if names != expected_names:
            _integrity_failure("N2B1P cache entry has an unexpected file set")
        with cache_entry.open_file(artifact.filename) as payload:
            payload_digest, payload_size = payload.sha256_and_size()
        with cache_entry.open_file("cache_manifest.json") as manifest:
            raw_manifest = _read_bound_file(manifest, max_bytes=64 * 1024)
        if (
            payload_digest != artifact.local_sha256
            or payload_size != artifact.byte_count
            or sha256_bytes(raw_manifest) != artifact.cache_manifest_sha256
            or raw_manifest != _cache_manifest(artifact)
        ):
            _integrity_failure("N2B1P cache entry does not match approved evidence")
        if (
            canonical_json_bytes(
                _strict_mapping_bytes(raw_manifest, "N2B1P cache manifest is invalid")
            )
            != raw_manifest
        ):
            _integrity_failure("N2B1P cache manifest is not canonical")
    finally:
        if cache_entry is not None:
            cache_entry.close()
    if artifact.cache_manifest_sha256 != compute_legacy_cache_manifest_sha256(
        artifact_id=artifact.artifact_id,
        revision=artifact.revision,
        filename=artifact.filename,
        byte_count=artifact.byte_count,
        local_sha256=artifact.local_sha256,
        transfer_manifest_sha256=artifact.transfer_manifest_sha256,
    ):
        _integrity_failure("N2B1P cache entry does not match approved evidence")
    return PromotionResult(
        artifact_id=artifact.artifact_id,
        cache_key=artifact.local_sha256,
        byte_count=artifact.byte_count,
        local_sha256=artifact.local_sha256,
        status="CACHE_HIT",
        manifest_path=Path(artifact.local_sha256) / "cache_manifest.json",
        manifest_sha256=artifact.cache_manifest_sha256,
    )


def verify_promoted_artifact(
    artifact_id: str, *, project_root: Path | None = None
) -> PromotionResult:
    """Read-only, handle-bound verification of one already promoted cache entry."""
    root = project_root or find_project_root()
    artifact = load_authorized_promotion(artifact_id, project_root=root)
    configuration = load_n2b1p_runtime_configuration(root)
    if artifact.runtime_configuration_digest != configuration.configuration_digest:
        _deny("N2B1P artifact is not bound to the approved runtime configuration")
    with bind_existing_directory(configuration.cache_root, writable=False) as cache:
        validate_bound_cache_root(configuration, identity_digest=cache.identity.digest)
        return _validate_cache_entry(cache, artifact)


def promote_artifact(
    artifact: PromotionArtifact,
    *,
    quarantine_run_id: str,
    project_root: Path | None = None,
) -> PromotionResult:
    """Promote one approved quarantine payload without model loading or deletion."""
    root = project_root or find_project_root()
    current = load_authorized_promotion(artifact.artifact_id, project_root=root)
    if current != artifact:
        _deny("N2B1P caller artifact does not match current authorization")
    configuration = load_n2b1p_runtime_configuration(root)
    if artifact.runtime_configuration_digest != configuration.configuration_digest:
        _deny("N2B1P artifact is not bound to the approved runtime configuration")
    if _RUN_ID.fullmatch(quarantine_run_id) is None:
        _deny("N2B1P quarantine run identifier is invalid")
    with (
        bind_existing_directory(DEFAULT_QUARANTINE_PARENT, writable=False) as quarantine,
        bind_existing_directory(configuration.cache_root, writable=True) as cache,
    ):
        validate_bound_cache_root(configuration, identity_digest=cache.identity.digest)
        with quarantine.open_directory(quarantine_run_id, writable=False) as run:
            _validate_transfer_manifest(run, artifact)
            _verify_quarantine_payload(run, artifact)
            try:
                return _validate_cache_entry(cache, artifact)
            except FileNotFoundError:
                pass
            with BoundStagingTransaction.create(cache) as transaction:
                _copy_verified_payload(run, transaction, artifact)
                with transaction.create_file("cache_manifest.json") as manifest:
                    manifest.write(_cache_manifest(artifact))
                    manifest.flush()
                transaction.publish(artifact.local_sha256)
                verified = _validate_cache_entry(cache, artifact)
                return PromotionResult(
                    artifact_id=verified.artifact_id,
                    cache_key=verified.cache_key,
                    byte_count=verified.byte_count,
                    local_sha256=verified.local_sha256,
                    status="PROMOTED",
                    manifest_path=verified.manifest_path,
                    manifest_sha256=verified.manifest_sha256,
                )
