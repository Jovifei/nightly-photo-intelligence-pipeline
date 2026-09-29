"""Read-only validation for the B-source network reacquisition review packet.

This module validates tracked control documents only. It never contacts the
network, resolves external root references, or loads model/runtime components.
"""

from __future__ import annotations

import hashlib
import os
import stat
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import NoReturn, cast
from urllib.parse import urlsplit

import yaml
from jsonschema import (  # type: ignore[import-untyped]
    Draft202012Validator,
    FormatChecker,
    SchemaError,
)

from .domain.errors import DuplicateJsonMemberError, GateNotAuthorizedError
from .json_strict import load_json_strict
from .n2b1p_integrity import canonical_json_bytes, sha256_bytes

READY_STATUS = "B_SOURCE_NETWORK_REACQUISITION_READY_FOR_EXTERNAL_REVIEW"
INVALID_STATUS = "B_SOURCE_NETWORK_REACQUISITION_INVALID"
TASK_PATH = "tasks/phase_n2b1p_b_source_network_reacquisition_v1.yaml"
OWNER_PATH = "approvals/owner_n2b1p_b_source_network_reacquisition_v1.yaml"
RUNTIME_PATH = "approvals/n2b1p_b_source_network_runtime_configuration_v1.json"
RUNTIME_DIGEST = "a60178368e6d37dcf713dc004d9799048a0f9dfd957cc49e5c619753787c39d8"
STOP_POINT = "EXTERNAL_REVIEW_B_SOURCE_NETWORK_REACQUISITION_V1_PRE_DOWNLOAD"
_DOMAIN = "download.pytorch.org"
_ALLOWED_DOMAINS = [_DOMAIN]
_HISTORICAL_RUNTIME_SHA256 = "f8d6a2779f85a2944d60b2a94ff99c392f45fe5adefbfead3441a3ce72fa682b"
_HISTORICAL_RUNTIME_REF = "approvals/n2b1p_runtime_configuration.json"
_HISTORICAL_RUNTIME_CONFIG_DIGEST = (
    "462e999671c2073ef8d02cbeaccd561cbc1f4734c4f312baee079a8134040bfd"
)
_HISTORICAL_CACHE_IDENTITY = "15cb613d6ecb39247799adca13c6fcbfd9c9edb72c223db7cebf1ee975d7b2ba"
_QUARANTINE_REF = "E_CLAUDE_ALLOW_DOWNLOAD/npi-n2b1p-b-source-quarantine-20260930-e9110783"
_QUARANTINE_IDENTITY = "ff0fc35900d4f60d906e8dbcc8d806e8d1360aee4290326049925353667f9000"
_QUARANTINE_ATTESTATION_REF = f"{_QUARANTINE_REF}.attestation-v2.json"
_QUARANTINE_ATTESTATION_SHA256 = "27d298c6f7b2ea146f8668edd3c7a4af75b5b9a9cfae0a9ab767ce666acc37e0"
_HISTORICAL_CACHE_REF = "E_CLAUDE_ALLOW_DOWNLOAD/npi-model-cache"
_PHOTO_SOURCE_REF = "F_NPI_G1_SOURCE"
_B_CACHE_REF = "E_CLAUDE_ALLOW_DOWNLOAD/npi-n2b1p-cache-v2-20260929"
_B_CACHE_IDENTITY = "c030b04ce53a7bff949061c81178474576db62502013468ca967c11a646b9b6f"
_QUALITY_PYTHON_REF = "E_CLAUDE_ALLOW_DOWNLOAD/npi-py312-quality-venv-20260929"
_QUARANTINE_SCOPE_FLAGS = (
    "empty",
    "non_reparse",
    "outside_git",
    "outside_runtime",
    "outside_source",
    "outside_cache_root",
    "outside_cache",
    "outside_photo_source",
    "outside_python_venv",
    "outside_route_b_cache_root",
    "outside_quality_python_venv",
    "outside_historical_runtime_parent",
    "outside_historical_runtime_work",
    "outside_historical_cache_root",
    "outside_prior_quarantine",
)
_ALLOWED_CHANGE_CATEGORIES = [
    "task_contract",
    "owner_approval",
    "schema",
    "tests",
    "governance_tool",
    "control_plane_code",
    "manifest",
    "todo_status",
    "task_tracking",
]
_REPARSE_POINT_ATTRIBUTE = 0x400

_ARTIFACTS: tuple[dict[str, object], ...] = (
    {
        "id": "torchvision-keypointrcnn-resnet50-fpn-coco-v1",
        "revision": "torchvision-v0.22.1",
        "filename": "keypointrcnn_resnet50_fpn_coco-fc266e95.pth",
        "url": "https://download.pytorch.org/models/keypointrcnn_resnet50_fpn_coco-fc266e95.pth",
        "byte_count": 237034793,
        "local_sha256": "fc266e953d2b302cdcbb9ae66f71f6b0d4649928bf02dc573961e361e4918926",
        "transfer_manifest_sha256": (
            "90da3eb000813841a980dcbaf8e1b31fdde15283a9d6b969156c5eb0ae21ce43"
        ),
    },
    {
        "id": "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
        "revision": "torchvision-v0.22.1",
        "filename": "lraspp_mobilenet_v3_large-d234d4ea.pth",
        "url": "https://download.pytorch.org/models/lraspp_mobilenet_v3_large-d234d4ea.pth",
        "byte_count": 13097061,
        "local_sha256": "d234d4eae9d55d5f76de18b77cf0dc62c66fe5c5482758209d00f950c92bb280",
        "transfer_manifest_sha256": (
            "d25cc430637cf19ebab31cd5aa99e344b4da58cd2b04db245c165181e3ff1f12"
        ),
    },
    {
        "id": "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1",
        "revision": "torchvision-v0.22.1",
        "filename": "deeplabv3_mobilenet_v3_large-fc3c493d.pth",
        "url": "https://download.pytorch.org/models/deeplabv3_mobilenet_v3_large-fc3c493d.pth",
        "byte_count": 44356159,
        "local_sha256": "fc3c493d68e89cc31ef488c803d5d7dd2f3190fb570598faa49fef69be8e5e70",
        "transfer_manifest_sha256": (
            "676054e8b2c366f591a1bbe1b4521e2ef7abdb08197534ca95eb11d434dd0cae"
        ),
    },
)
_ARTIFACTS_BY_ID = {str(item["id"]): item for item in _ARTIFACTS}
_ARTIFACT_IDS = frozenset(_ARTIFACTS_BY_ID)
_SCHEMA_FILES = (
    "n2b1p_b_source_network_reacquisition_v1.schema.json",
    "owner_n2b1p_b_source_network_reacquisition_v1.schema.json",
    "n2b1p_b_source_network_runtime_configuration_v1.schema.json",
    "n2b1p_b_source_network_evidence_v1.schema.json",
    "n2b1p_b_source_network_checkpoint_v1.schema.json",
)
_SCHEMA_SHA256 = dict(
    zip(
        (*_SCHEMA_FILES, "task_index_v1_2.schema.json"),
        (
            "7c9f71228c5c6ea1d8911b7cf9dc22ef33ec5e0148fce4752277501518ce7550",
            "f2ef4b215cf3dfb8f40b3966a222c416f888c7afc9874bd6a47c3235ddbf2214",
            "4b2aede6f3f9968517efb87230aeccfe718a4d1d67972bfb98d0ef4a0a205d12",
            "82dc82e61a5f9bcbc9784f378ddd5bfb9fb18f6d4896f60ba6f5d5422bb3a938",
            "7b5aa24b44a30b70906137b3a8ec0c77813e87381b213deee432a3fe306caaf3",
            "a253d59fa27c108ff801aab0d21c046efa6ed2cfed14ec3e896121375af4e49d",
        ),
        strict=True,
    )
)


def _deny(message: str) -> NoReturn:
    raise GateNotAuthorizedError(message)


def _is_reparse(st: os.stat_result) -> bool:
    return stat.S_ISLNK(st.st_mode) or bool(
        getattr(st, "st_file_attributes", 0) & _REPARSE_POINT_ATTRIBUTE
    )


def _repo_file(project_root: Path, relative: str) -> Path:
    """Return a regular tracked-root file without following reparse points."""
    relative_path = PurePosixPath(relative)
    if relative_path.is_absolute() or any(part in {"", ".", ".."} for part in relative_path.parts):
        _deny("control-document reference is not project-relative")
    supplied_root = Path(project_root)
    try:
        root_details = supplied_root.lstat()
    except OSError as exc:
        raise GateNotAuthorizedError("project root is unavailable") from exc
    if _is_reparse(root_details) or not stat.S_ISDIR(root_details.st_mode):
        _deny("project root is not a regular directory")
    root = supplied_root.resolve(strict=True)
    current = root
    parts = relative_path.parts
    for index, part in enumerate(parts):
        current = current / part
        try:
            details = current.lstat()
        except OSError as exc:
            raise GateNotAuthorizedError("control document unavailable") from exc
        if _is_reparse(details):
            _deny("control document path contains a reparse point")
        if index < len(parts) - 1 and not stat.S_ISDIR(details.st_mode):
            _deny("control document parent is not a directory")
    if not stat.S_ISREG(details.st_mode):
        _deny("control document is not a regular file")
    try:
        resolved = current.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise GateNotAuthorizedError("control document escaped the project root") from exc
    return current


class _UniqueKeySafeLoader(yaml.SafeLoader):  # type: ignore[misc]
    pass


def _construct_unique_mapping(
    loader: _UniqueKeySafeLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[object, object]:
    loader.flatten_mapping(node)
    result: dict[object, object] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in result
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "unhashable mapping key",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_UniqueKeySafeLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_unique_mapping
)


def _mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        _deny(f"{label} is not an object")
    return cast(Mapping[str, object], value)


def _validate_quarantine_scope_flags(value: object) -> None:
    record = _mapping(value, "quarantine attestation scope")
    if any(record.get(flag) is not True for flag in _QUARANTINE_SCOPE_FLAGS):
        _deny("quarantine attestation is missing a required outside-boundary flag")


def _load_yaml(project_root: Path, relative: str) -> Mapping[str, object]:
    path = _repo_file(project_root, relative)
    try:
        raw = path.read_bytes().decode("utf-8")
        value = yaml.load(raw, Loader=_UniqueKeySafeLoader)
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise GateNotAuthorizedError("control YAML is invalid or unavailable") from exc
    return _mapping(value, "control YAML")


def _load_json(project_root: Path, relative: str) -> Mapping[str, object]:
    path = _repo_file(project_root, relative)
    try:
        value = load_json_strict(path)
    except (OSError, UnicodeError, ValueError, DuplicateJsonMemberError) as exc:
        raise GateNotAuthorizedError("control JSON is invalid or unavailable") from exc
    return _mapping(value, "control JSON")


def _load_schema(project_root: Path, filename: str) -> Mapping[str, object]:
    expected_digest = _SCHEMA_SHA256.get(filename)
    if (
        expected_digest is None
        or _sha256_file(project_root, f"schemas/{filename}") != expected_digest
    ):
        _deny("control schema bytes changed")
    schema = _load_json(project_root, f"schemas/{filename}")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise GateNotAuthorizedError("control schema is invalid") from exc
    return schema


def _validate_schema(schema: Mapping[str, object], value: object, label: str) -> None:
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda error: (list(error.absolute_path), error.message),
    )
    if errors:
        _deny(f"{label} does not match its closed schema")


def _sha256_file(project_root: Path, relative: str) -> str:
    path = _repo_file(project_root, relative)
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise GateNotAuthorizedError("historical control file is unavailable") from exc


def _artifact_records(value: object, label: str) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, list) or len(value) != len(_ARTIFACTS):
        _deny(f"{label} must contain exactly three artifacts")
    records: dict[str, Mapping[str, object]] = {}
    for item in value:
        record = _mapping(item, label)
        artifact_id = record.get("id")
        if not isinstance(artifact_id, str) or artifact_id in records:
            _deny(f"{label} contains a missing or duplicate artifact ID")
        records[artifact_id] = record
    if set(records) != _ARTIFACT_IDS:
        _deny(f"{label} artifact IDs do not match the fixed three-file set")
    return records


def _compare_artifact_fields(
    records: Mapping[str, Mapping[str, object]],
    *,
    label: str,
    fields: tuple[str, ...],
) -> None:
    for artifact_id, expected in _ARTIFACTS_BY_ID.items():
        record = records[artifact_id]
        for field in fields:
            if record.get(field) != expected.get(field):
                _deny(f"{label} historical artifact binding mismatch")


def _validate_url(url: object, filename: str) -> None:
    if not isinstance(url, str):
        _deny("historical source URL is invalid")
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname == _DOMAIN
            and parsed.port is None
            and parsed.username is None
            and parsed.password is None
            and parsed.path == f"/models/{filename}"
            and parsed.query == ""
            and parsed.fragment == ""
        )
    except ValueError:
        valid = False
    if not valid:
        _deny("historical URL is outside the exact HTTPS allowlist")


def _validate_historical_artifacts(
    project_root: Path,
    register: Mapping[str, object],
    acquisition: Mapping[str, object],
    owner: Mapping[str, object],
    promotion: Mapping[str, object],
) -> None:
    if (
        acquisition.get("stage") != "N2B1R"
        or acquisition.get("result") != "N2B1R_ACQUISITION_COMPLETE_AWAITING_LOCAL_VERIFICATION"
        or acquisition.get("artifact_count") != 3
    ):
        _deny("historical N2B1R acquisition evidence changed")
    rights = register.get("weights_rights")
    if (
        not isinstance(rights, Mapping)
        or rights.get("status") != "UNKNOWN_NOT_COMMERCIAL_CLEARANCE"
    ):
        _deny("historical weight-rights status changed")
    register_records = _artifact_records(register.get("artifacts"), "N2B1R register")
    for artifact_id, expected in _ARTIFACTS_BY_ID.items():
        item = register_records[artifact_id]
        filename = str(expected["filename"])
        _validate_url(item.get("official_url"), filename)
        if (
            item.get("kind") != "MODEL_WEIGHT"
            or item.get("revision") != expected["revision"]
            or item.get("filename") != filename
            or item.get("official_url") != expected["url"]
            or item.get("allowed_request_domains") != _ALLOWED_DOMAINS
            or item.get("allowed_final_domains") != _ALLOWED_DOMAINS
            or item.get("official_sha256") is not None
            or item.get("local_sha256_required") is not True
        ):
            _deny("N2B1R register binding changed")

    acquisition_records = _artifact_records(acquisition.get("artifacts"), "N2B1R evidence")
    _compare_artifact_fields(
        acquisition_records,
        label="N2B1R evidence",
        fields=("revision", "filename", "byte_count", "local_sha256", "transfer_manifest_sha256"),
    )
    for item in acquisition_records.values():
        if (
            item.get("official_domain") != _DOMAIN
            or item.get("weights_rights") != "UNKNOWN_NOT_COMMERCIAL_CLEARANCE"
            or item.get("use_restriction") != "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION"
        ):
            _deny("N2B1R source-domain or rights binding changed")

    approval_records = _artifact_records(owner.get("allowed_artifacts"), "N2B1P Owner approval")
    _compare_artifact_fields(
        approval_records,
        label="N2B1P Owner approval",
        fields=("revision", "filename", "byte_count", "local_sha256", "transfer_manifest_sha256"),
    )
    if (
        owner.get("approval_type") != "N2B1P_CACHE_PROMOTION_ONLY"
        or owner.get("status") != "APPROVED"
    ):
        _deny("historical N2B1P cache approval changed")
    evidence_binding = owner.get("n2b1r_evidence")
    if (
        not isinstance(evidence_binding, Mapping)
        or evidence_binding.get("path") != "research/N2B1R_acquisition_evidence.json"
        or evidence_binding.get("sha256")
        != _sha256_file(project_root, "research/N2B1R_acquisition_evidence.json")
        or evidence_binding.get("result")
        != "N2B1R_ACQUISITION_COMPLETE_AWAITING_LOCAL_VERIFICATION"
    ):
        _deny("historical N2B1P approval does not bind the N2B1R evidence")

    promotion_records = _artifact_records(promotion.get("artifacts"), "N2B1P promotion evidence")
    _compare_artifact_fields(
        promotion_records,
        label="N2B1P promotion evidence",
        fields=("byte_count", "local_sha256", "transfer_manifest_sha256"),
    )
    if promotion.get("result") != "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW":
        _deny("historical N2B1P promotion evidence changed")


def _validate_runtime_digest(runtime: Mapping[str, object]) -> str:
    digest = runtime.get("configuration_digest")
    payload = {key: value for key, value in runtime.items() if key != "configuration_digest"}
    if not isinstance(digest, str) or digest != sha256_bytes(canonical_json_bytes(payload)):
        _deny("B-source runtime configuration digest mismatch")
    if digest != RUNTIME_DIGEST:
        _deny("B-source runtime configuration digest is not the reviewed value")
    return digest


def _validate_route_b_cache_stays_locked(
    project_root: Path,
    task: Mapping[str, object],
    runtime: Mapping[str, object],
) -> None:
    old_task = _load_yaml(project_root, "tasks/phase_n2b1p_cache_reprovision_v2.yaml")
    old_owner = _load_yaml(project_root, "approvals/owner_n2b1p_cache_reprovision_v2.yaml")
    old_runtime = _load_json(
        project_root, "approvals/n2b1p_reprovision_runtime_configuration_v2.json"
    )
    task_authorities = old_task.get("authorities")
    owner_authority = old_owner.get("execution_authority")
    b_cache = task_authorities.get("b_cache") if isinstance(task_authorities, Mapping) else None
    b_source = task_authorities.get("b_source") if isinstance(task_authorities, Mapping) else None
    if (
        old_task.get("status") != "DRAFT_NOT_AUTHORIZED"
        or old_owner.get("status") != "DRAFT_NOT_AUTHORIZED"
        or not isinstance(b_cache, Mapping)
        or b_cache.get("status") != "NOT_AUTHORIZED"
        or b_cache.get("network_access") != "DENY"
        or not isinstance(b_source, Mapping)
        or b_source.get("status") != "NOT_AUTHORIZED"
        or not isinstance(owner_authority, Mapping)
        or owner_authority.get("b_cache") != "NOT_AUTHORIZED"
        or owner_authority.get("b_source") != "NOT_AUTHORIZED"
        or owner_authority.get("network") != "DENY"
        or old_runtime.get("status") != "DRAFT_NOT_AUTHORIZED"
        or old_runtime.get("cache_root_ref") != _B_CACHE_REF
        or old_runtime.get("cache_root_identity") != _B_CACHE_IDENTITY
    ):
        _deny("existing Route B cache authority is no longer locked")

    current_binding = task.get("existing_b_cache_control")
    runtime_binding = _mapping(current_binding, "current B-cache binding")
    if (
        runtime_binding.get("task_status") != old_task.get("status")
        or runtime_binding.get("b_cache_status") != b_cache.get("status")
        or runtime_binding.get("network_access") != b_cache.get("network_access")
        or runtime_binding.get("destination_ref") != old_runtime.get("cache_root_ref")
        or runtime_binding.get("destination_identity_sha256")
        != old_runtime.get("cache_root_identity")
        or runtime.get("existing_b_cache_root_ref") != old_runtime.get("cache_root_ref")
        or runtime.get("existing_b_cache_root_identity_sha256")
        != old_runtime.get("cache_root_identity")
        or runtime.get("existing_b_cache_destination_authorized") is not False
    ):
        _deny("new control packet changed the existing B-cache binding")


def _validate_packet(
    project_root: Path,
    *,
    task: Mapping[str, object],
    owner: Mapping[str, object],
    runtime: Mapping[str, object],
    schemas: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    _validate_schema(schemas[_SCHEMA_FILES[0]], task, "B-source task")
    _validate_schema(schemas[_SCHEMA_FILES[1]], owner, "B-source Owner record")
    _validate_schema(schemas[_SCHEMA_FILES[2]], runtime, "B-source runtime configuration")

    register = _load_json(project_root, "research/N2B1R_local_research_artifact_register.json")
    acquisition = _load_json(project_root, "research/N2B1R_acquisition_evidence.json")
    historic_owner = _load_yaml(project_root, "approvals/owner_n2b1p_cache_promotion.yaml")
    promotion = _load_json(project_root, "research/N2B1P_cache_promotion_evidence.json")
    historic_runtime = _load_json(project_root, "approvals/n2b1p_runtime_configuration.json")

    review_candidate = _mapping(task.get("review_candidate"), "review candidate")
    baseline = _load_yaml(project_root, "approvals/phase_completion_N2B1P.yaml")
    baseline_record = _mapping(baseline.get("baseline"), "immutable N2B1P baseline")
    if (
        review_candidate.get("status") != "REVIEW_CANDIDATE"
        or review_candidate.get("class") != "CONTROL_PLANE_ONLY"
        or review_candidate.get("task_id") != "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
        or review_candidate.get("review_scope")
        != "B_SOURCE_NETWORK_REACQUISITION_V1_CONTROL_PACKET_ONLY"
        or review_candidate.get("task_schema_ref")
        != "schemas/n2b1p_b_source_network_reacquisition_v1.schema.json"
        or review_candidate.get("owner_approval_ref") != OWNER_PATH
        or review_candidate.get("owner_approval_schema_ref")
        != "schemas/owner_n2b1p_b_source_network_reacquisition_v1.schema.json"
        or review_candidate.get("runtime_configuration_ref") != RUNTIME_PATH
        or review_candidate.get("runtime_configuration_schema_ref")
        != "schemas/n2b1p_b_source_network_runtime_configuration_v1.schema.json"
        or review_candidate.get("baseline_approval_ref") != "approvals/phase_completion_N2B1P.yaml"
        or review_candidate.get("immutable_baseline_ref") != "approvals/phase_completion_N2B1P.yaml"
        or review_candidate.get("external_exact_sha_review_required") is not True
        or review_candidate.get("execution_before_review") is not False
        or review_candidate.get("allowed_change_categories") != _ALLOWED_CHANGE_CATEGORIES
        or baseline.get("phase_id") != "N2B1P"
        or baseline.get("status") != "APPROVED"
        or baseline_record.get("immutable") is not True
    ):
        _deny("B-source review candidate baseline or review scope changed")

    _validate_historical_artifacts(project_root, register, acquisition, historic_owner, promotion)

    acquisition_sha256 = _sha256_file(project_root, "research/N2B1R_acquisition_evidence.json")
    approval_evidence = historic_owner.get("n2b1r_evidence")
    promotion_runtime = promotion.get("runtime_configuration")
    historic_approval_runtime = historic_owner.get("runtime_configuration")
    if (
        not isinstance(approval_evidence, Mapping)
        or approval_evidence.get("path") != "research/N2B1R_acquisition_evidence.json"
        or approval_evidence.get("sha256") != acquisition_sha256
        or approval_evidence.get("result")
        != "N2B1R_ACQUISITION_COMPLETE_AWAITING_LOCAL_VERIFICATION"
        or not isinstance(promotion_runtime, Mapping)
        or not isinstance(historic_approval_runtime, Mapping)
        or promotion_runtime.get("configuration_digest") != _HISTORICAL_RUNTIME_CONFIG_DIGEST
        or promotion_runtime.get("cache_root_identity") != _HISTORICAL_CACHE_IDENTITY
        or historic_approval_runtime.get("configuration_digest")
        != _HISTORICAL_RUNTIME_CONFIG_DIGEST
        or historic_approval_runtime.get("cache_root_identity") != _HISTORICAL_CACHE_IDENTITY
        or historic_approval_runtime.get("path") != "approvals/n2b1p_runtime_configuration.json"
        or promotion_runtime.get("path") != "approvals/n2b1p_runtime_configuration.json"
        or promotion.get("n2b1r_evidence_sha256") != acquisition_sha256
        or historic_runtime.get("configuration_digest") != _HISTORICAL_RUNTIME_CONFIG_DIGEST
        or historic_runtime.get("cache_root_identity") != _HISTORICAL_CACHE_IDENTITY
        or _sha256_file(project_root, "approvals/n2b1p_runtime_configuration.json")
        != _HISTORICAL_RUNTIME_SHA256
    ):
        _deny("historical N2B1P runtime or N2B1R evidence binding changed")

    digest = _validate_runtime_digest(runtime)
    task_runtime = _mapping(task.get("runtime_configuration"), "task runtime binding")
    task_phase = _mapping(task.get("phase"), "task phase")
    if (
        task_runtime.get("configuration_digest") != digest
        or owner.get("runtime_configuration_digest") != digest
        or task_phase.get("id") != "N2B1P"
        or task.get("capability") != "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
        or owner.get("approval_type") != "OWNER_N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
        or task.get("status") != "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"
        or owner.get("status") != "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"
        or runtime.get("status") != "DRAFT_NOT_AUTHORIZED"
        or task.get("scope_status") != "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"
        or owner.get("scope_status") != task.get("scope_status")
        or task.get("owner_authorized") is not True
        or owner.get("owner_authorized") is not True
        or task.get("execution_status") != "NOT_RUN"
        or owner.get("execution_status") != "NOT_RUN"
        or runtime.get("execution_status") != "NOT_RUN"
        or task.get("execution_authority") != "NOT_AUTHORIZED"
        or owner.get("execution_authority") != "NOT_AUTHORIZED"
        or runtime.get("execution_authority") != "NOT_AUTHORIZED"
        or task.get("network_download_before_external_review") is not False
        or owner.get("network_download_before_external_review") is not False
        or task.get("pre_download_external_review") != "PASS_REQUIRED"
        or owner.get("pre_download_external_review") != "PASS_REQUIRED"
        or task.get("network_policy")
        != {
            "access": "DENY",
            "allowed_schemes": ["https"],
            "allowed_request_domains": [_DOMAIN],
            "allowed_final_domains": [_DOMAIN],
            "executed_request_count": 0,
            "future_download_count_exact": 3,
        }
        or runtime.get("network_access") != "DENY"
        or owner.get("network_access") != "DENY"
    ):
        _deny("B-source review candidate is not fail-closed")

    task_artifacts = _artifact_records(task.get("artifacts"), "B-source task")
    owner_artifacts = _artifact_records(owner.get("artifacts"), "B-source Owner record")
    _compare_artifact_fields(
        task_artifacts,
        label="B-source task",
        fields=(
            "revision",
            "filename",
            "url",
            "byte_count",
            "local_sha256",
            "transfer_manifest_sha256",
        ),
    )
    _compare_artifact_fields(
        owner_artifacts,
        label="B-source Owner record",
        fields=(
            "revision",
            "filename",
            "url",
            "byte_count",
            "local_sha256",
            "transfer_manifest_sha256",
        ),
    )
    for records in (task_artifacts, owner_artifacts):
        for artifact in records.values():
            if artifact.get("sha256_kind") != "HISTORICAL_LOCAL_SHA256_NOT_OFFICIAL_SHA256":
                _deny("local SHA-256 provenance label changed")
            _validate_url(
                artifact.get("url"),
                cast(str, artifact.get("filename")),
            )

    for document in (task, owner):
        if document.get("network_download_before_external_review") is not False:
            _deny("network access before external review is prohibited")
    if (
        runtime.get("allowed_request_domains") != _ALLOWED_DOMAINS
        or runtime.get("allowed_final_domains") != _ALLOWED_DOMAINS
        or runtime.get("allowed_scheme") != "https"
        or runtime.get("download_source_root_check") != "NOT_RUN"
        or runtime.get("download_source_root_ref") != "E_CLAUDE_ALLOW_DOWNLOAD"
        or runtime.get("download_target_quarantine_root_ref") != _QUARANTINE_REF
        or runtime.get("quarantine_root_identity_sha256") != _QUARANTINE_IDENTITY
        or runtime.get("quarantine_attestation_version") != "V2"
        or runtime.get("quarantine_attestation_ref") != _QUARANTINE_ATTESTATION_REF
        or runtime.get("quarantine_attestation_sha256") != _QUARANTINE_ATTESTATION_SHA256
        or runtime.get("quarantine_attestation_empty") is not True
        or runtime.get("quarantine_attestation_non_reparse") is not True
        or runtime.get("quarantine_attestation_root_bound") is not True
        or runtime.get("existing_b_cache_root_ref") != _B_CACHE_REF
        or runtime.get("existing_b_cache_root_identity_sha256") != _B_CACHE_IDENTITY
        or runtime.get("runtime_boundary_configuration_sha256") != _HISTORICAL_RUNTIME_SHA256
        or runtime.get("quality_python_environment_ref") != _QUALITY_PYTHON_REF
        or runtime.get("torch_or_cuda_usage") != "DENY"
    ):
        _deny("B-source runtime path, identity, or domain binding changed")

    task_quarantine = _mapping(task.get("quarantine"), "task quarantine binding")
    owner_quarantine = _mapping(owner.get("quarantine"), "Owner quarantine binding")
    _validate_quarantine_scope_flags(task_quarantine)
    _validate_quarantine_scope_flags(owner_quarantine)
    _validate_quarantine_scope_flags({flag: runtime.get(flag) for flag in _QUARANTINE_SCOPE_FLAGS})
    nested_attestation_bindings = {
        "attestation_version": "V2",
        "attestation_ref": _QUARANTINE_ATTESTATION_REF,
        "attestation_sha256": _QUARANTINE_ATTESTATION_SHA256,
        "historical_runtime_configuration_ref": "approvals/n2b1p_runtime_configuration.json",
        "historical_runtime_configuration_sha256": _HISTORICAL_RUNTIME_SHA256,
        "historical_cache_root_ref": _HISTORICAL_CACHE_REF,
        "historical_cache_root_identity_sha256": _HISTORICAL_CACHE_IDENTITY,
        "route_b_cache_root_ref": _B_CACHE_REF,
        "route_b_cache_root_identity_sha256": _B_CACHE_IDENTITY,
        "quality_python_environment_ref": _QUALITY_PYTHON_REF,
        "photo_source_ref": _PHOTO_SOURCE_REF,
    }
    runtime_attestation_bindings = {
        "quarantine_attestation_version": "V2",
        "quarantine_attestation_ref": _QUARANTINE_ATTESTATION_REF,
        "quarantine_attestation_sha256": _QUARANTINE_ATTESTATION_SHA256,
        "attestation_historical_runtime_configuration_ref": _HISTORICAL_RUNTIME_REF,
        "attestation_historical_runtime_configuration_sha256": _HISTORICAL_RUNTIME_SHA256,
        "attestation_historical_cache_root_ref": _HISTORICAL_CACHE_REF,
        "attestation_historical_cache_root_identity_sha256": _HISTORICAL_CACHE_IDENTITY,
        "attestation_route_b_cache_root_ref": _B_CACHE_REF,
        "attestation_route_b_cache_root_identity_sha256": _B_CACHE_IDENTITY,
        "attestation_quality_python_environment_ref": _QUALITY_PYTHON_REF,
        "attestation_photo_source_ref": _PHOTO_SOURCE_REF,
    }
    if (
        task_quarantine.get("root_ref") != _QUARANTINE_REF
        or task_quarantine.get("object_identity_sha256") != _QUARANTINE_IDENTITY
        or owner_quarantine.get("root_ref") != _QUARANTINE_REF
        or owner_quarantine.get("object_identity_sha256") != _QUARANTINE_IDENTITY
        or any(
            task_quarantine.get(key) != value for key, value in nested_attestation_bindings.items()
        )
        or any(
            owner_quarantine.get(key) != value for key, value in nested_attestation_bindings.items()
        )
        or any(runtime.get(key) != value for key, value in runtime_attestation_bindings.items())
        or task_quarantine.get("attested_empty") is not True
        or task_quarantine.get("attested_non_reparse") is not True
        or task_quarantine.get("attested_root_bound") is not True
        or owner_quarantine.get("attested_empty") is not True
        or owner_quarantine.get("attested_non_reparse") is not True
        or owner_quarantine.get("attested_root_bound") is not True
    ):
        _deny("B-source quarantine root binding changed")

    task_index = _load_json(project_root, "tasks/index.json")
    index_schema = _load_schema(project_root, "task_index_v1_2.schema.json")
    _validate_schema(index_schema, task_index, "task index")
    candidates = task_index.get("review_candidates")
    if not isinstance(candidates, list):
        _deny("task index review candidates are missing")
    matching = [
        item
        for item in candidates
        if isinstance(item, Mapping)
        and item.get("capability") == "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
    ]
    if len(matching) != 1:
        _deny("task index must contain exactly one B-source review candidate")
    indexed = _mapping(matching[0], "task index B-source candidate")
    if (
        indexed.get("kind") != "BOUNDED_B_SOURCE_NETWORK_REACQUISITION_REVIEW_CANDIDATE"
        or indexed.get("phase") != "N2B1P"
        or indexed.get("file") != "phase_n2b1p_b_source_network_reacquisition_v1.yaml"
        or indexed.get("approval_record") != OWNER_PATH
        or indexed.get("project_state") != "LOCKED"
        or indexed.get("candidate_status") != "REVIEW_CANDIDATE"
        or indexed.get("contract_status") != "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"
        or indexed.get("execution_status") != "NOT_RUN"
        or indexed.get("network_access") != "DENY"
    ):
        _deny("task index B-source candidate is not explicitly locked")

    _validate_route_b_cache_stays_locked(project_root, task, runtime)
    return {
        "task_status": task["status"],
        "owner_status": owner["status"],
        "runtime_status": runtime["status"],
        "scope_status": task["scope_status"],
        "execution_status": "NOT_RUN",
        "execution_authority": "NOT_AUTHORIZED",
        "network_access": "DENY",
        "pre_download_external_review": "PASS_REQUIRED",
        "mandatory_stop": STOP_POINT,
        "artifact_count": len(_ARTIFACTS),
    }


def load_b_source_network_control_packet(project_root: Path) -> dict[str, object]:
    """Strictly validate tracked controls and return redacted review facts."""
    schemas = {name: _load_schema(project_root, name) for name in _SCHEMA_FILES}
    task = _load_yaml(project_root, TASK_PATH)
    owner = _load_yaml(project_root, OWNER_PATH)
    runtime = _load_json(project_root, RUNTIME_PATH)
    facts = _validate_packet(
        project_root,
        task=task,
        owner=owner,
        runtime=runtime,
        schemas=schemas,
    )
    return {
        "status": READY_STATUS,
        "review_state": "READY_FOR_EXTERNAL_REVIEW_ONLY",
        **facts,
    }


def check_b_source_network_control_packet(project_root: Path) -> dict[str, object]:
    """Return a fail-closed result; this check never enables network access."""
    try:
        return load_b_source_network_control_packet(project_root)
    except (
        DuplicateJsonMemberError,
        GateNotAuthorizedError,
        KeyError,
        OSError,
        SchemaError,
        TypeError,
        UnicodeError,
        ValueError,
        yaml.YAMLError,
    ) as exc:
        return {
            "status": INVALID_STATUS,
            "error_code": type(exc).__name__,
            "task_status": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW",
            "owner_status": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW",
            "execution_status": "NOT_RUN",
            "execution_authority": "NOT_AUTHORIZED",
            "network_access": "DENY",
            "pre_download_external_review": "PASS_REQUIRED",
            "mandatory_stop": STOP_POINT,
        }


__all__ = [
    "check_b_source_network_control_packet",
    "load_b_source_network_control_packet",
]
