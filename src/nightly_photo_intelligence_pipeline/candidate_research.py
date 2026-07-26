"""Fail-closed validation for N2B0.6 metadata-only candidate research.

This module intentionally performs no network, filesystem, cache, model, or
photo operation.  It verifies that a *record* has enough immutable,
per-file evidence to explain a qualification result; it cannot authorize a
download, an install, conversion, execution, or a later phase.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from functools import cache
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlparse, urlsplit

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from .domain.errors import GateNotAuthorizedError
from .json_strict import loads_json_strict

STATUS_VALUES = frozenset({"PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"})
QUALIFICATION_MATRIX_KEYS = (
    "CODE_LICENSE_CONFIRMED",
    "WEIGHTS_LICENSE_CONFIRMED",
    "COMMERCIAL_USE_CONFIRMED",
    "ARTIFACT_IDENTITY_CONFIRMED",
    "BUNDLE_COMPLETENESS_CONFIRMED",
    "IMMUTABLE_REVISION_CONFIRMED",
    "OFFICIAL_SHA384_CONFIRMED",
    "OFFICIAL_SHA256_CONFIRMED",
    "OFFICIAL_SIZE_CONFIRMED",
    "REQUEST_DOMAIN_CONFIRMED",
    "FINAL_DOMAIN_CONFIRMED",
    "REDIRECT_CHAIN_CONFIRMED",
    "LOCAL_OFFLINE_PATH_CONFIRMED",
)
# Retained as a public alias for callers that previously imported this name.
REQUIRED_STATUS_KEYS = QUALIFICATION_MATRIX_KEYS
READY_STATUS_KEY = "ready_for_owner_artifact_selection"
HISTORICAL_ARTIFACT_IDS = frozenset(
    {
        "rtmpose-m-wholebody",
        "rtmw-m-wholebody-fallback",
        "pp-humansegv2-lite",
        "mediapipe-selfie-segmentation-general",
    }
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SHA384 = re.compile(r"^[0-9a-f]{96}$")
_GIT_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_GIT_BLOB_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_REVISION_KINDS = frozenset({"GIT_COMMIT", "RELEASE_ASSET_VERSION", "OBJECT_VERSION"})
_BUNDLE_TYPES = frozenset({"PRECONVERTED_RUNTIME", "SOURCE_AND_CONVERSION"})
_PRECONVERTED_ROLES = frozenset({"MODEL_GRAPH", "MODEL_WEIGHTS"})
_EVIDENCE_TYPES = frozenset(
    {
        "MODEL_CONFIGURATION",
        "CHECKSUM_METADATA",
        "CODE_LICENSE",
        "MODEL_LICENSE",
        "COMMERCIAL_USE_TERMS",
    }
)
_LICENSE_EVIDENCE_TYPES = frozenset({"CODE_LICENSE", "MODEL_LICENSE", "COMMERCIAL_USE_TERMS"})
_LICENSE_MATRIX_KEYS = frozenset(
    {
        "CODE_LICENSE_CONFIRMED",
        "WEIGHTS_LICENSE_CONFIRMED",
        "COMMERCIAL_USE_CONFIRMED",
    }
)
_OMZ_PROJECT = "openvinotoolkit/open_model_zoo"
_OMZ_REVISION = "7cc29a91472b4cb1289a11e655ba3e188e1d4a31"
_OMZ_SOURCE_URL = f"https://github.com/{_OMZ_PROJECT}/commit/{_OMZ_REVISION}"
_OMZ_DOMAINS = frozenset({"github.com", "raw.githubusercontent.com", "storage.openvinotoolkit.org"})
_MODEL_CONFIG_PATHS = {
    "human-pose-estimation-0001": "models/intel/human-pose-estimation-0001/model.yml",
    "human-pose-estimation-0005": "models/intel/human-pose-estimation-0005/model.yml",
    "instance-segmentation-person-0007": "models/intel/instance-segmentation-person-0007/model.yml",
    "modnet-webcam-portrait-matting": "models/public/modnet-webcam-portrait-matting/model.yml",
}
_EXPECTED_DIRECT_URLS = {
    "human-pose-estimation-0001": {
        "human-pose-estimation-0001.xml": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/human-pose-estimation-0001/FP32/human-pose-estimation-0001.xml",
        "human-pose-estimation-0001.bin": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/human-pose-estimation-0001/FP32/human-pose-estimation-0001.bin",
    },
    "human-pose-estimation-0005": {
        "human-pose-estimation-0005.xml": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/human-pose-estimation-0005/FP32/human-pose-estimation-0005.xml",
        "human-pose-estimation-0005.bin": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/human-pose-estimation-0005/FP32/human-pose-estimation-0005.bin",
    },
    "instance-segmentation-person-0007": {
        "instance-segmentation-person-0007.xml": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/instance-segmentation-person-0007/FP16/instance-segmentation-person-0007.xml",
        "instance-segmentation-person-0007.bin": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/instance-segmentation-person-0007/FP16/instance-segmentation-person-0007.bin",
    },
    "modnet-webcam-portrait-matting": {
        "modnet_webcam_portrait_matting.ckpt": "https://storage.openvinotoolkit.org/repositories/open_model_zoo/public/2022.2/modnet-webcam-portrait-matting/modnet_webcam_portrait_matting.ckpt",
    },
}


def _failure(message: str, *, error_code: str | None = None) -> GateNotAuthorizedError:
    """Return a generic, non-sensitive validation failure."""
    return GateNotAuthorizedError(
        f"N2B0.6 candidate record invalid: {message}", error_code=error_code
    )


def _require_mapping(value: object, field: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise _failure(f"{field} must be an object")
    return value


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise _failure(f"{field} must be a non-empty string")
    return value


def _require_exact_keys(
    value: Mapping[str, object],
    required: frozenset[str],
    optional: frozenset[str],
    field: str,
) -> None:
    missing = required.difference(value)
    unexpected = set(value).difference(required | optional)
    if missing or unexpected:
        raise _failure(f"{field} has an incomplete or non-closed shape")


def _https_host(url: object, field: str) -> str:
    value = _require_string(url, field)
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise _failure(f"{field} must be official HTTPS")
    return parsed.hostname.lower().rstrip(".")


def canonical_artifact_url_basename(url: object) -> str:
    """Return the exact canonical filename segment for an official artifact URL.

    This intentionally performs one percent decode only.  It never repairs,
    trims, case-folds, or resolves a value: any ambiguous path separator or
    control character is rejected before it can become an artifact identity.
    """

    value = _require_string(url, "artifact URL")
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise _failure("artifact URL cannot be parsed") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise _failure("artifact URL must be HTTPS without userinfo")
    if not parsed.path or parsed.path.endswith("/"):
        raise _failure("artifact URL must name a file")
    raw_basename = parsed.path.rsplit("/", 1)[-1]
    try:
        basename = unicodedata.normalize("NFC", unquote(raw_basename, errors="strict"))
    except UnicodeDecodeError as exc:
        raise _failure("artifact URL basename is not valid UTF-8") from exc
    if (
        not basename
        or basename in {".", ".."}
        or "/" in basename
        or "\\" in basename
        or "\x00" in basename
        or any(ord(character) < 32 or ord(character) == 127 for character in basename)
    ):
        raise _failure("artifact URL basename is unsafe")
    return basename


def _validate_revision(value: object, domains: frozenset[str], field: str) -> Mapping[str, object]:
    revision = _require_mapping(value, field)
    _require_exact_keys(
        revision,
        frozenset({"kind", "value", "source_url"}),
        frozenset(),
        field,
    )
    kind = _require_string(revision.get("kind"), f"{field}.kind")
    revision_value = _require_string(revision.get("value"), f"{field}.value")
    if kind not in _REVISION_KINDS or revision_value.lower() in {
        "latest",
        "main",
        "master",
        "head",
    }:
        raise _failure(f"{field} is floating or unsupported")
    if kind == "GIT_COMMIT" and not _GIT_COMMIT.fullmatch(revision_value):
        raise _failure(f"{field} Git commit is not immutable")
    if _https_host(revision.get("source_url"), f"{field}.source_url") not in domains:
        raise _failure(f"{field} source is not declared official")
    return revision


def _require_relative_path(value: object, field: str) -> str:
    raw = _require_string(value, field)
    if "\\" in raw or raw.startswith("/") or ":" in raw:
        raise _failure(f"{field} must be a relative POSIX path")
    path = PurePosixPath(raw)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise _failure(f"{field} escapes its local bundle")
    return raw


def _validate_head_metadata(
    value: object,
    *,
    direct_url: str,
    filename: str,
    expected_domain: str,
    redirect_count: int,
    size_bytes: int,
    content_type: str,
    field: str,
) -> None:
    metadata = _require_mapping(value, field)
    _require_exact_keys(
        metadata,
        frozenset(
            {
                "status_code",
                "final_url",
                "observed_final_domain",
                "redirect_count",
                "content_length",
                "content_type",
                "etag",
                "last_modified",
                "accept_ranges",
            }
        ),
        frozenset(),
        field,
    )
    if metadata.get("status_code") != 200:
        raise _failure(f"{field} must record HTTP 200")
    final_url = _require_string(metadata.get("final_url"), f"{field}.final_url")
    try:
        final_basename = canonical_artifact_url_basename(final_url)
    except GateNotAuthorizedError as exc:
        raise _failure(
            f"{field} final URL has an unsafe artifact basename",
            error_code="NPI_CANDIDATE_FINAL_URL_FILENAME_MISMATCH",
        ) from exc
    if final_basename != filename:
        raise _failure(
            f"{field} final URL basename does not match artifact filename",
            error_code="NPI_CANDIDATE_FINAL_URL_FILENAME_MISMATCH",
        )
    if final_url != direct_url:
        raise _failure(f"{field} final response must be the direct URL")
    if metadata.get("observed_final_domain") != expected_domain:
        raise _failure(f"{field} final domain does not match")
    if (
        type(metadata.get("redirect_count")) is not int
        or metadata["redirect_count"] != redirect_count
    ):
        raise _failure(f"{field} redirect count does not match")
    if type(metadata.get("content_length")) is not int or metadata["content_length"] != size_bytes:
        raise _failure(f"{field} content length does not match")
    if metadata.get("content_type") != content_type:
        raise _failure(f"{field} content type does not match")
    if not _require_string(metadata.get("etag"), f"{field}.etag"):
        raise _failure(f"{field} must record ETag")
    if not _require_string(metadata.get("last_modified"), f"{field}.last_modified"):
        raise _failure(f"{field} must record Last-Modified")
    if _require_string(metadata.get("accept_ranges"), f"{field}.accept_ranges") != "bytes":
        raise _failure(f"{field} must record byte range capability")


def _validate_project(candidate: Mapping[str, object]) -> frozenset[str]:
    project = _require_mapping(candidate.get("source_project"), "source_project")
    _require_exact_keys(
        project,
        frozenset(
            {
                "project_id",
                "name",
                "official_project_url",
                "official_domains",
            }
        ),
        frozenset(),
        "source_project",
    )
    raw_domains = project.get("official_domains")
    if not isinstance(raw_domains, Sequence) or isinstance(raw_domains, (str, bytes)):
        raise _failure("source_project.official_domains must be an array")
    domains = frozenset(
        _require_string(item, "source_project.official_domains") for item in raw_domains
    )
    if (
        project.get("project_id") != _OMZ_PROJECT
        or project.get("official_project_url") != f"https://github.com/{_OMZ_PROJECT}"
        or domains != _OMZ_DOMAINS
    ):
        raise _failure("candidate source project is not the fixed Open Model Zoo source")
    _require_string(project.get("name"), "source_project.name")
    return domains


def _github_evidence_location(url: object, field: str) -> tuple[str, str, tuple[str, ...]]:
    """Parse only immutable GitHub raw/blob evidence links, never floating refs."""

    value = _require_string(url, field)
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise _failure("evidence URL cannot be parsed") from exc
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise _failure("evidence URL must be a canonical HTTPS document")
    parts = tuple(part for part in parsed.path.split("/") if part)
    host = (parsed.hostname or "").lower().rstrip(".")
    if host == "github.com" and len(parts) >= 5 and parts[2] == "blob":
        project = f"{parts[0]}/{parts[1]}"
        revision = parts[3]
        document_path = parts[4:]
    elif host == "raw.githubusercontent.com" and len(parts) >= 4:
        project = f"{parts[0]}/{parts[1]}"
        revision = parts[2]
        document_path = parts[3:]
    else:
        raise _failure(
            "evidence URL is not an immutable official GitHub blob or raw document",
            error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
        )
    if not _GIT_COMMIT.fullmatch(revision) or not document_path:
        raise _failure(
            "evidence URL lacks an exact forty-character revision and document path",
            error_code="NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED",
        )
    return project, revision, document_path


def _validate_evidence_applicability(
    value: object, *, candidate_id: str, file_ids: frozenset[str], field: str
) -> None:
    applies_to = _require_mapping(value, field)
    _require_exact_keys(
        applies_to,
        frozenset({"candidate_id", "bundle", "artifact_file_ids"}),
        frozenset(),
        field,
    )
    if applies_to.get("candidate_id") != candidate_id or applies_to.get("bundle") is not True:
        raise _failure(
            "evidence applicability is not bound to the current candidate bundle",
            error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
        )
    artifact_file_ids = applies_to.get("artifact_file_ids")
    if (
        not isinstance(artifact_file_ids, Sequence)
        or isinstance(artifact_file_ids, (str, bytes))
        or any(not isinstance(item, str) or not item for item in artifact_file_ids)
        or len(set(artifact_file_ids)) != len(artifact_file_ids)
        or frozenset(artifact_file_ids) != file_ids
    ):
        raise _failure(
            "evidence applicability does not cover the exact candidate payload bundle",
            error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
        )


def _validate_license_terms(value: object, field: str) -> None:
    terms = _require_mapping(value, field)
    _require_exact_keys(
        terms,
        frozenset({"license_identifier", "scope", "commercial_use"}),
        frozenset(),
        field,
    )
    _require_string(terms.get("license_identifier"), f"{field}.license_identifier")
    _require_string(terms.get("scope"), f"{field}.scope")
    _require_string(terms.get("commercial_use"), f"{field}.commercial_use")


def _validate_evidence_files(
    value: object,
    *,
    candidate_id: str,
    model_id: str,
    source_revision: Mapping[str, object],
    file_ids: frozenset[str],
) -> dict[str, Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise _failure("evidence_files must be a non-empty array")
    evidence_by_id: dict[str, Mapping[str, object]] = {}
    required_types = {
        "MODEL_CONFIGURATION",
        "CHECKSUM_METADATA",
        "CODE_LICENSE",
        "MODEL_LICENSE",
        "COMMERCIAL_USE_TERMS",
    }
    expected_model_path = _MODEL_CONFIG_PATHS.get(model_id)
    if expected_model_path is None:
        raise _failure("candidate model has no fixed Open Model Zoo configuration path")
    for index, raw in enumerate(value):
        field = f"evidence_files[{index}]"
        evidence = _require_mapping(raw, field)
        _require_exact_keys(
            evidence,
            frozenset(
                {
                    "evidence_id",
                    "evidence_type",
                    "applies_to",
                    "source_project",
                    "source_revision",
                    "official_url",
                    "document_role",
                    "required",
                }
            ),
            frozenset({"license_terms", "artifact_assertions"}),
            field,
        )
        evidence_id = _require_string(evidence.get("evidence_id"), f"{field}.evidence_id")
        evidence_type = _require_string(evidence.get("evidence_type"), f"{field}.evidence_type")
        if evidence_id in evidence_by_id or evidence_type not in _EVIDENCE_TYPES:
            raise _failure("evidence files have a duplicate identifier or unsupported type")
        if evidence.get("required") is not True:
            raise _failure("evidence must be explicitly required")
        _validate_evidence_applicability(
            evidence.get("applies_to"),
            candidate_id=candidate_id,
            file_ids=file_ids,
            field=f"{field}.applies_to",
        )
        source_project = _require_string(evidence.get("source_project"), f"{field}.source_project")
        try:
            revision = _validate_revision(
                evidence.get("source_revision"),
                frozenset({"github.com", "raw.githubusercontent.com"}),
                f"{field}.source_revision",
            )
        except GateNotAuthorizedError as exc:
            raise _failure(
                "evidence requires an immutable official source revision",
                error_code="NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED",
            ) from exc
        revision_value = str(revision["value"])
        revision_source_url = str(revision["source_url"])
        expected_revision_url = f"https://github.com/{source_project}/commit/{revision_value}"
        if revision.get("kind") != "GIT_COMMIT" or revision_source_url != expected_revision_url:
            raise _failure(
                "evidence revision is not exactly bound to its official project commit",
                error_code="NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED",
            )
        url_project, url_revision, document_path = _github_evidence_location(
            evidence.get("official_url"), f"{field}.official_url"
        )
        if url_project != source_project or url_revision != revision_value:
            raise _failure(
                "evidence URL project or revision does not match its declaration",
                error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
            )
        document_role = _require_string(evidence.get("document_role"), f"{field}.document_role")
        if evidence_type in _LICENSE_EVIDENCE_TYPES:
            _validate_license_terms(evidence.get("license_terms"), f"{field}.license_terms")
        elif "license_terms" in evidence:
            raise _failure("non-license evidence must not carry license terms")
        if evidence_type == "MODEL_CONFIGURATION":
            if (
                source_project != _OMZ_PROJECT
                or revision != source_revision
                or revision_value != _OMZ_REVISION
                or document_path != tuple(expected_model_path.split("/"))
                or document_role != "MODEL_YAML"
            ):
                raise _failure(
                    "model configuration evidence is not the candidate's fixed OMZ model.yml",
                    error_code="NPI_CANDIDATE_MODEL_CONFIGURATION_REVISION_MISMATCH",
                )
        elif evidence_type == "CHECKSUM_METADATA":
            if (
                source_project != _OMZ_PROJECT
                or revision != source_revision
                or document_path != tuple(expected_model_path.split("/"))
                or document_role != "MODEL_YAML_CHECKSUM_METADATA"
            ):
                raise _failure(
                    "checksum metadata is not the candidate's fixed Open Model Zoo model.yml",
                    error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
                )
            _validate_checksum_assertions(
                evidence.get("artifact_assertions"),
                file_ids=file_ids,
                field=f"{field}.artifact_assertions",
            )
        elif document_path != ("LICENSE",) or document_role != "LICENSE_TEXT":
            raise _failure(
                "license evidence must name the immutable official LICENSE document",
                error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
            )
        elif "artifact_assertions" in evidence:
            raise _failure("only checksum metadata may carry artifact assertions")
        evidence_by_id[evidence_id] = evidence
    observed_types = {str(evidence["evidence_type"]) for evidence in evidence_by_id.values()}
    if not required_types.issubset(observed_types):
        raise _failure(
            "evidence_files lacks required typed provenance",
            error_code="NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING",
        )
    return evidence_by_id


def _validate_checksum_assertions(value: object, *, file_ids: frozenset[str], field: str) -> None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise _failure("checksum metadata must contain artifact assertions")
    seen: set[str] = set()
    for index, raw in enumerate(value):
        assertion = _require_mapping(raw, f"{field}[{index}]")
        _require_exact_keys(
            assertion,
            frozenset(
                {
                    "file_id",
                    "filename",
                    "size_bytes",
                    "checksum_algorithm",
                    "official_checksum",
                    "direct_official_url",
                }
            ),
            frozenset(),
            f"{field}[{index}]",
        )
        file_id = _require_string(assertion.get("file_id"), f"{field}[{index}].file_id")
        if file_id in seen:
            raise _failure("checksum metadata has duplicate artifact assertions")
        seen.add(file_id)
    if seen != file_ids:
        raise _failure("checksum metadata does not cover the exact candidate payload files")


def _validate_artifact_files(
    value: object, domains: frozenset[str], model_id: str
) -> list[Mapping[str, object]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise _failure("artifact_files must be a non-empty array")
    files: list[Mapping[str, object]] = []
    file_ids: set[str] = set()
    filenames: set[str] = set()
    local_paths: set[str] = set()
    required = frozenset(
        {
            "file_id",
            "role",
            "required",
            "filename",
            "size_bytes",
            "direct_official_url",
            "request_domain",
            "expected_final_domain",
            "expected_redirect_count",
            "content_type",
            "checksum_algorithm",
            "official_checksum",
            "source_evidence_ids",
            "checksum_evidence_ids",
            "license_evidence_ids",
            "local_bundle_relative_path",
            "head_metadata",
        }
    )
    optional = frozenset(
        {
            "precision",
            "format",
            "generated_or_downloaded",
            "conversion_dependency",
            "official_sha256",
            "official_sha256_source_url",
        }
    )
    for index, raw in enumerate(value):
        item = _require_mapping(raw, f"artifact_files[{index}]")
        _require_exact_keys(item, required, optional, f"artifact_files[{index}]")
        file_id = _require_string(item.get("file_id"), "artifact_files.file_id")
        filename = _require_string(item.get("filename"), "artifact_files.filename")
        if "/" in filename or "\\" in filename or filename in {".", ".."}:
            raise _failure("artifact filename contains a path")
        if file_id in file_ids or filename in filenames:
            raise _failure("artifact_files contains duplicate file identifiers")
        file_ids.add(file_id)
        filenames.add(filename)
        if type(item.get("required")) is not bool or item["required"] is not True:
            raise _failure("artifact file must explicitly be required")
        size_bytes = item.get("size_bytes")
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise _failure("artifact size must be a positive integer, not boolean")
        direct_url = _require_string(item.get("direct_official_url"), "artifact direct URL")
        try:
            direct_basename = canonical_artifact_url_basename(direct_url)
        except GateNotAuthorizedError as exc:
            raise _failure(
                "artifact direct URL has an unsafe artifact basename",
                error_code="NPI_CANDIDATE_FILENAME_URL_MISMATCH",
            ) from exc
        if direct_basename != filename:
            raise _failure(
                "artifact direct URL basename does not match artifact filename",
                error_code="NPI_CANDIDATE_FILENAME_URL_MISMATCH",
            )
        expected_direct_url = _EXPECTED_DIRECT_URLS.get(model_id, {}).get(filename)
        if direct_url != expected_direct_url:
            raise _failure(
                "artifact direct URL is not the fixed official source URL for this file",
                error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
            )
        request_domain = _require_string(item.get("request_domain"), "artifact request domain")
        final_domain = _require_string(item.get("expected_final_domain"), "artifact final domain")
        if (
            _https_host(direct_url, "artifact direct URL") != request_domain
            or request_domain != final_domain
            or request_domain not in domains
        ):
            raise _failure("artifact direct URL/domain binding is invalid")
        redirect_count = item.get("expected_redirect_count")
        if (
            not isinstance(redirect_count, int)
            or isinstance(redirect_count, bool)
            or redirect_count != 0
        ):
            raise _failure("artifact must use a direct zero-redirect official URL")
        content_type = _require_string(item.get("content_type"), "artifact content type")
        if item.get("checksum_algorithm") != "SHA384" or not _SHA384.fullmatch(
            _require_string(item.get("official_checksum"), "artifact official checksum")
        ):
            raise _failure("artifact requires canonical official SHA-384")
        for evidence_field in (
            "source_evidence_ids",
            "checksum_evidence_ids",
            "license_evidence_ids",
        ):
            evidence_ids = item.get(evidence_field)
            if (
                not isinstance(evidence_ids, Sequence)
                or isinstance(evidence_ids, (str, bytes))
                or not evidence_ids
                or any(
                    not isinstance(evidence_id, str) or not evidence_id
                    for evidence_id in evidence_ids
                )
                or len(set(evidence_ids)) != len(evidence_ids)
            ):
                raise _failure(
                    f"artifact {evidence_field} must be a non-empty unique evidence-ID array",
                    error_code="NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING",
                )
        local_path = _require_relative_path(
            item.get("local_bundle_relative_path"), "artifact local bundle path"
        )
        if local_path in local_paths:
            raise _failure("artifact local bundle path is duplicated")
        local_paths.add(local_path)
        if item.get("generated_or_downloaded", "DOWNLOAD_REQUIRED") != "DOWNLOAD_REQUIRED":
            raise _failure("artifact file cannot claim a generated output")
        if type(item.get("conversion_dependency", False)) is not bool:
            raise _failure("artifact conversion_dependency must be a boolean")
        optional_sha256 = item.get("official_sha256")
        if optional_sha256 is not None:
            if not isinstance(optional_sha256, str) or not _SHA256.fullmatch(optional_sha256):
                raise _failure("artifact official SHA-256 is not canonical")
            if (
                _https_host(item.get("official_sha256_source_url"), "artifact SHA-256 source")
                not in domains
            ):
                raise _failure("artifact SHA-256 source is not declared official")
        elif (
            "official_sha256_source_url" in item and item["official_sha256_source_url"] is not None
        ):
            raise _failure("artifact SHA-256 source cannot exist without SHA-256")
        _validate_head_metadata(
            item.get("head_metadata"),
            direct_url=direct_url,
            filename=filename,
            expected_domain=final_domain,
            redirect_count=redirect_count,
            size_bytes=size_bytes,
            content_type=content_type,
            field="artifact head metadata",
        )
        files.append(item)
    return files


def _validate_artifact_evidence_links(
    files: Sequence[Mapping[str, object]], evidence_by_id: Mapping[str, Mapping[str, object]]
) -> None:
    """Require every payload to point to matching source/checksum/license evidence."""

    expected_types = {
        "source_evidence_ids": "MODEL_CONFIGURATION",
        "checksum_evidence_ids": "CHECKSUM_METADATA",
        "license_evidence_ids": "MODEL_LICENSE",
    }
    for artifact in files:
        file_id = str(artifact["file_id"])
        for field, expected_type in expected_types.items():
            evidence_ids = artifact[field]
            if not isinstance(evidence_ids, Sequence):
                raise _failure("artifact evidence references have an invalid shape")
            for evidence_id in evidence_ids:
                evidence = evidence_by_id.get(str(evidence_id))
                if evidence is None or evidence.get("evidence_type") != expected_type:
                    raise _failure(
                        "artifact evidence reference is missing or has the wrong type",
                        error_code="NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING",
                    )
                applies_to = _require_mapping(evidence.get("applies_to"), "evidence applicability")
                applicable_ids = applies_to.get("artifact_file_ids")
                if not isinstance(applicable_ids, Sequence) or file_id not in applicable_ids:
                    raise _failure(
                        "artifact evidence does not apply to the referenced payload",
                        error_code="NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING",
                    )
        checksum_evidence_ids = artifact.get("checksum_evidence_ids")
        if not isinstance(checksum_evidence_ids, Sequence):
            raise _failure("checksum evidence references have an invalid shape")
        for evidence_id in checksum_evidence_ids:
            evidence = evidence_by_id[str(evidence_id)]
            assertions = evidence.get("artifact_assertions")
            if not isinstance(assertions, Sequence):
                raise _failure("checksum evidence lacks artifact assertions")
            matching = [
                item
                for item in assertions
                if isinstance(item, Mapping) and item.get("file_id") == file_id
            ]
            if len(matching) != 1:
                raise _failure("checksum evidence lacks exactly one payload assertion")
            assertion = matching[0]
            for key in (
                "filename",
                "size_bytes",
                "checksum_algorithm",
                "official_checksum",
                "direct_official_url",
            ):
                if assertion.get(key) != artifact.get(key):
                    raise _failure(
                        "checksum evidence does not exactly bind payload identity metadata",
                        error_code="NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
                    )


def _validate_source_dependency(
    value: object, domains: frozenset[str], field: str
) -> Mapping[str, object]:
    dependency = _require_mapping(value, field)
    _require_exact_keys(
        dependency,
        frozenset(
            {
                "filename",
                "repository_relative_path",
                "fixed_git_revision",
                "official_source_url",
                "content_checksum",
                "checksum_algorithm",
                "role",
                "required",
                "local_bundle_relative_path",
            }
        ),
        frozenset({"source_license_reference"}),
        field,
    )
    filename = _require_string(dependency.get("filename"), f"{field}.filename")
    if "/" in filename or "\\" in filename:
        raise _failure(f"{field}.filename contains a path")
    repository_path = _require_relative_path(
        dependency.get("repository_relative_path"), f"{field}.repository_relative_path"
    )
    revision = _require_string(dependency.get("fixed_git_revision"), f"{field}.fixed_git_revision")
    if not _GIT_COMMIT.fullmatch(revision):
        raise _failure(f"{field}.fixed_git_revision is not a fixed Git commit")
    source_url = _require_string(
        dependency.get("official_source_url"), f"{field}.official_source_url"
    )
    if (
        _https_host(source_url, f"{field}.official_source_url") not in domains
        or revision not in source_url
    ):
        raise _failure(f"{field}.official_source_url is not bound to its fixed revision")
    algorithm = dependency.get("checksum_algorithm")
    checksum = _require_string(dependency.get("content_checksum"), f"{field}.content_checksum")
    if algorithm == "SHA384":
        valid_checksum = _SHA384.fullmatch(checksum)
    elif algorithm == "GIT_BLOB_SHA1":
        valid_checksum = _GIT_BLOB_SHA1.fullmatch(checksum)
    else:
        valid_checksum = None
    if not valid_checksum:
        raise _failure(f"{field} lacks valid source-content identity")
    if not _require_string(dependency.get("role"), f"{field}.role"):
        raise _failure(f"{field}.role missing")
    if type(dependency.get("required")) is not bool or dependency["required"] is not True:
        raise _failure(f"{field}.required must be true boolean")
    _require_relative_path(
        dependency.get("local_bundle_relative_path"), f"{field}.local_bundle_relative_path"
    )
    license_reference = dependency.get("source_license_reference")
    if (
        license_reference is not None
        and _https_host(license_reference, f"{field}.source_license") not in domains
    ):
        raise _failure(f"{field}.source_license is not declared official")
    if not repository_path.endswith(filename):
        raise _failure(f"{field}.repository_relative_path does not end in filename")
    return dependency


def _validate_conversion_contract(value: object, domains: frozenset[str], model_id: str) -> None:
    contract = _require_mapping(value, "bundle_variant.conversion_contract")
    _require_exact_keys(
        contract,
        frozenset(
            {
                "configuration_repository_relative_path",
                "converter_repository_relative_path",
                "dependencies",
                "commands",
                "converter_runtime",
                "expected_outputs",
            }
        ),
        frozenset(),
        "bundle_variant.conversion_contract",
    )
    configuration_path = _require_relative_path(
        contract.get("configuration_repository_relative_path"), "conversion configuration path"
    )
    converter_path = _require_relative_path(
        contract.get("converter_repository_relative_path"), "conversion converter path"
    )
    dependencies = contract.get("dependencies")
    if not isinstance(dependencies, Sequence) or isinstance(dependencies, (str, bytes)):
        raise _failure("conversion dependencies must be an array")
    paths: set[str] = set()
    for index, dependency in enumerate(dependencies):
        checked = _validate_source_dependency(dependency, domains, f"conversion dependency {index}")
        path = str(checked["repository_relative_path"])
        if path in paths:
            raise _failure("conversion dependencies contain a duplicate source path")
        paths.add(path)
    if configuration_path not in paths or converter_path not in paths:
        raise _failure("conversion config or converter is missing from dependencies")
    if model_id == "modnet-webcam-portrait-matting":
        required_paths = {
            "models/public/modnet-webcam-portrait-matting/model.py",
            "tools/model_tools/src/omz_tools/internal_scripts/pytorch_to_onnx.py",
            "onnx/modnet_onnx.py",
            "src/models/backbones/__init__.py",
            "src/models/backbones/mobilenetv2.py",
            "src/models/backbones/wrapper.py",
        }
        if not required_paths.issubset(paths):
            raise _failure("MODNet conversion dependency closure is incomplete")
    commands = _require_mapping(contract.get("commands"), "conversion commands")
    _require_exact_keys(
        commands,
        frozenset({"pytorch_to_onnx", "model_optimizer"}),
        frozenset(),
        "conversion commands",
    )
    if not all(_require_string(command, "conversion command") for command in commands.values()):
        raise _failure("conversion command missing")
    converter_runtime = _require_mapping(contract.get("converter_runtime"), "converter runtime")
    _require_exact_keys(
        converter_runtime,
        frozenset({"tool_name", "fixed_recipe_revision", "runtime_version_status"}),
        frozenset(),
        "converter runtime",
    )
    _require_string(converter_runtime.get("tool_name"), "converter runtime tool name")
    _validate_revision(
        converter_runtime.get("fixed_recipe_revision"), domains, "converter runtime fixed recipe"
    )
    if converter_runtime.get("runtime_version_status") != "NOT_INSTALLED_NOT_VERIFIED":
        raise _failure("converter runtime status must not imply installation")
    expected_outputs = contract.get("expected_outputs")
    if not isinstance(expected_outputs, Sequence) or isinstance(expected_outputs, (str, bytes)):
        raise _failure("conversion expected outputs must be an array")
    output_names: set[str] = set()
    for output in expected_outputs:
        output_object = _require_mapping(output, "conversion expected output")
        _require_exact_keys(
            output_object,
            frozenset(
                {"filename", "format", "generated_or_downloaded", "local_bundle_relative_path"}
            ),
            frozenset(),
            "conversion expected output",
        )
        output_filename = _require_string(
            output_object.get("filename"), "conversion output filename"
        )
        if "/" in output_filename or "\\" in output_filename or output_filename in output_names:
            raise _failure("conversion output filename is invalid or duplicated")
        output_names.add(output_filename)
        _require_string(output_object.get("format"), "conversion output format")
        if output_object.get("generated_or_downloaded") != "NOT_GENERATED":
            raise _failure("conversion output must remain NOT_GENERATED")
        _require_relative_path(
            output_object.get("local_bundle_relative_path"), "conversion output local bundle path"
        )
    if not {
        "modnet_webcam_portrait_matting.onnx",
        "modnet_webcam_portrait_matting.xml",
        "modnet_webcam_portrait_matting.bin",
    }.issubset(output_names):
        raise _failure("conversion expected output list is incomplete")


def _validate_bundle(
    candidate: Mapping[str, object], files: list[Mapping[str, object]], domains: frozenset[str]
) -> None:
    bundle_type = _require_string(candidate.get("bundle_type"), "bundle_type")
    if bundle_type not in _BUNDLE_TYPES:
        raise _failure("bundle_type is not permitted")
    variant = _require_mapping(candidate.get("bundle_variant"), "bundle_variant")
    if bundle_type == "PRECONVERTED_RUNTIME":
        _require_exact_keys(
            variant,
            frozenset({"runtime_format", "precision", "input_shape", "target_runtime"}),
            frozenset(),
            "preconverted bundle_variant",
        )
        if variant.get("runtime_format") != "OPENVINO_IR":
            raise _failure("preconverted bundle must specify OPENVINO_IR")
        precision = _require_string(variant.get("precision"), "preconverted precision")
        if precision not in {"FP16", "FP32"}:
            raise _failure("preconverted precision is not permitted")
        _require_string(variant.get("input_shape"), "preconverted input shape")
        _require_string(variant.get("target_runtime"), "preconverted target runtime")
        if {str(file["role"]) for file in files} != _PRECONVERTED_ROLES or len(files) != 2:
            raise _failure("preconverted IR must contain exactly XML graph and BIN weights")
        if any(file.get("precision") != precision for file in files):
            raise _failure("preconverted IR files mix precision variants")
        if any(file.get("format") != "OPENVINO_IR" for file in files):
            raise _failure("preconverted IR files have the wrong format")
        return
    _require_exact_keys(
        variant,
        frozenset(
            {
                "source_framework",
                "input_shape",
                "target_runtime",
                "conversion_contract",
            }
        ),
        frozenset(),
        "source-and-conversion bundle_variant",
    )
    if {str(file["role"]) for file in files} != {"CHECKPOINT"} or len(files) != 1:
        raise _failure("source-and-conversion bundle must contain exactly its checkpoint")
    _require_string(variant.get("source_framework"), "source framework")
    _require_string(variant.get("input_shape"), "source conversion input shape")
    _require_string(variant.get("target_runtime"), "source conversion target runtime")
    _validate_conversion_contract(
        variant.get("conversion_contract"), domains, str(candidate["model_id"])
    )


def _computed_matrix(files: Sequence[Mapping[str, object]]) -> dict[str, str]:
    """Compute the matrix only after every required structural check has run."""
    all_sha256 = all(isinstance(file.get("official_sha256"), str) for file in files)

    return {
        "ARTIFACT_IDENTITY_CONFIRMED": "PASS",
        "BUNDLE_COMPLETENESS_CONFIRMED": "PASS",
        "IMMUTABLE_REVISION_CONFIRMED": "PASS",
        "OFFICIAL_SHA384_CONFIRMED": "PASS",
        "OFFICIAL_SHA256_CONFIRMED": "PASS" if all_sha256 else "FAIL",
        "OFFICIAL_SIZE_CONFIRMED": "PASS",
        "REQUEST_DOMAIN_CONFIRMED": "PASS",
        "FINAL_DOMAIN_CONFIRMED": "PASS",
        "REDIRECT_CHAIN_CONFIRMED": "PASS",
        "LOCAL_OFFLINE_PATH_CONFIRMED": "PASS",
    }


def _matrix_status(value: object, field: str) -> str:
    if field in _LICENSE_MATRIX_KEYS:
        decision = _require_mapping(value, field)
        return _require_string(decision.get("status"), f"{field}.status")
    return _require_string(value, field)


def _validate_license_decision(
    value: object,
    *,
    field: str,
    evidence_by_id: Mapping[str, Mapping[str, object]],
) -> str:
    decision = _require_mapping(value, field)
    _require_exact_keys(
        decision,
        frozenset({"status", "evidence_ids", "decision_reason"}),
        frozenset(),
        field,
    )
    status = _require_string(decision.get("status"), f"{field}.status")
    if status not in STATUS_VALUES:
        raise _failure("license decision has an invalid status")
    evidence_ids = decision.get("evidence_ids")
    if (
        not isinstance(evidence_ids, Sequence)
        or isinstance(evidence_ids, (str, bytes))
        or any(not isinstance(item, str) or not item for item in evidence_ids)
        or len(set(evidence_ids)) != len(evidence_ids)
    ):
        raise _failure("license decision evidence IDs must be a unique array")
    _require_string(decision.get("decision_reason"), f"{field}.decision_reason")
    if status != "PASS":
        return status
    required_types = {
        "CODE_LICENSE_CONFIRMED": {"CODE_LICENSE"},
        "WEIGHTS_LICENSE_CONFIRMED": {"MODEL_LICENSE"},
        "COMMERCIAL_USE_CONFIRMED": {"MODEL_LICENSE", "COMMERCIAL_USE_TERMS"},
    }[field]
    referenced_types: set[str] = set()
    for evidence_id in evidence_ids:
        evidence = evidence_by_id.get(evidence_id)
        if evidence is None:
            raise _failure(
                "license decision references missing evidence",
                error_code="NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING",
            )
        evidence_type = evidence.get("evidence_type")
        if evidence_type not in required_types:
            raise _failure(
                "license decision references evidence with an inapplicable type",
                error_code="NPI_CANDIDATE_LICENSE_EVIDENCE_INSUFFICIENT",
            )
        referenced_types.add(str(evidence_type))
    if not required_types.issubset(referenced_types):
        raise _failure(
            "PASS license decision lacks the required typed evidence coverage",
            error_code="NPI_CANDIDATE_LICENSE_EVIDENCE_INSUFFICIENT",
        )
    return status


def _validate_one_candidate(candidate: Mapping[str, object]) -> None:
    _require_exact_keys(
        candidate,
        frozenset(
            {
                "candidate_id",
                "category",
                "model_id",
                "source_project",
                "source_revision",
                "bundle_type",
                "bundle_variant",
                "artifact_files",
                "evidence_files",
                "qualification_matrix",
                READY_STATUS_KEY,
            }
        ),
        frozenset(),
        "candidate",
    )
    candidate_id = _require_string(candidate.get("candidate_id"), "candidate_id")
    if candidate_id in HISTORICAL_ARTIFACT_IDS:
        raise _failure("historical candidate identity is excluded")
    category = _require_string(candidate.get("category"), "category")
    if category not in {"pose", "segmentation"}:
        raise _failure("candidate category is not permitted")
    _require_string(candidate.get("model_id"), "model_id")
    domains = _validate_project(candidate)
    source_revision = _validate_revision(
        candidate.get("source_revision"), domains, "source_revision"
    )
    if source_revision != {
        "kind": "GIT_COMMIT",
        "value": _OMZ_REVISION,
        "source_url": _OMZ_SOURCE_URL,
    }:
        raise _failure("candidate source revision is not the fixed Open Model Zoo commit")
    files = _validate_artifact_files(
        candidate.get("artifact_files"), domains, str(candidate["model_id"])
    )
    evidence_by_id = _validate_evidence_files(
        candidate.get("evidence_files"),
        candidate_id=candidate_id,
        model_id=str(candidate["model_id"]),
        source_revision=source_revision,
        file_ids=frozenset(str(file["file_id"]) for file in files),
    )
    _validate_artifact_evidence_links(files, evidence_by_id)
    _validate_bundle(candidate, files, domains)
    matrix = _require_mapping(candidate.get("qualification_matrix"), "qualification_matrix")
    _require_exact_keys(
        matrix, frozenset(QUALIFICATION_MATRIX_KEYS), frozenset(), "qualification_matrix"
    )
    license_statuses = {
        key: _validate_license_decision(matrix.get(key), field=key, evidence_by_id=evidence_by_id)
        for key in _LICENSE_MATRIX_KEYS
    }
    expected = _computed_matrix(files)
    for key, expected_status in expected.items():
        if _matrix_status(matrix.get(key), key) != expected_status:
            raise _failure("qualification matrix does not match verified evidence")
    ready = candidate.get(READY_STATUS_KEY)
    if ready not in STATUS_VALUES:
        raise _failure("candidate readiness has an invalid status")
    expected_ready = (
        "PASS"
        if all(value == "PASS" for value in expected.values())
        and all(value == "PASS" for value in license_statuses.values())
        else "FAIL"
    )
    if ready != expected_ready:
        raise _failure("candidate readiness does not match the qualification matrix")


def _validate_candidate_list(candidates: Sequence[Mapping[str, object]]) -> None:
    categories: Counter[str] = Counter()
    candidate_ids: set[str] = set()
    failures: list[GateNotAuthorizedError] = []
    for candidate in candidates:
        try:
            _validate_one_candidate(candidate)
            candidate_id = str(candidate["candidate_id"])
            category = str(candidate["category"])
            if candidate_id in candidate_ids:
                raise _failure("candidate identity is duplicated")
            candidate_ids.add(candidate_id)
            categories[category] += 1
        except GateNotAuthorizedError as exc:
            failures.append(exc)
    if any(count > 2 for count in categories.values()):
        failures.append(_failure("per-category candidate cap exceeded"))
    if failures:
        raise failures[0]


@cache
def _candidate_schema_validator() -> Draft202012Validator:
    root = Path(__file__).resolve().parents[2]
    catalog = loads_json_strict(
        (root / "schemas" / "current_stage_schema_catalog.json").read_bytes()
    )
    if not isinstance(catalog, Mapping) or not isinstance(catalog.get("schemas"), Sequence):
        raise _failure("current-stage schema catalog is invalid")
    if not any(
        isinstance(entry, Mapping) and entry.get("file") == "n2b0_6_candidate_record_v2.schema.json"
        for entry in catalog["schemas"]
    ):
        raise _failure("N2B0.6 candidate schema is absent from the current-stage catalog")
    schema = loads_json_strict(
        (root / "schemas" / "n2b0_6_candidate_record_v2.schema.json").read_bytes()
    )
    if not isinstance(schema, Mapping):
        raise _failure("N2B0.6 candidate schema is invalid")
    return Draft202012Validator(schema)


def _validate_document_schema(document: Mapping[str, object]) -> None:
    errors = sorted(
        _candidate_schema_validator().iter_errors(document), key=lambda error: list(error.path)
    )
    if not errors:
        return
    error = errors[0]
    path = tuple(str(part) for part in error.path)
    if "evidence_files" in path and "official_url" in str(error.message):
        error_code = "NPI_CANDIDATE_EVIDENCE_URL_REQUIRED"
    elif "evidence_files" in path and "source_revision" in str(error.message):
        error_code = "NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED"
    else:
        error_code = None
    raise _failure("candidate record violates the closed N2B0.6 schema", error_code=error_code)


def validate_candidate_record(document: Mapping[str, object]) -> None:
    """Validate the fixed N2B0.6 record and its no-expansion candidate pool."""
    _validate_document_schema(document)
    _require_exact_keys(
        document,
        frozenset({"schema_version", "phase_id", "candidates"}),
        frozenset(),
        "candidate record",
    )
    if document.get("schema_version") != "2.0" or document.get("phase_id") != "N2B0_6":
        raise _failure("candidate record identity is not current")
    candidates = document.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise _failure("candidate record candidates must be an array")
    candidate_mappings = [_require_mapping(candidate, "candidate") for candidate in candidates]
    _validate_candidate_list(candidate_mappings)
    categories = Counter(str(candidate["category"]) for candidate in candidate_mappings)
    if len(candidate_mappings) != 4 or categories != Counter({"pose": 2, "segmentation": 2}):
        raise _failure(
            "candidate record must retain exactly two pose and two segmentation candidates"
        )


def validate_candidate_record_bytes(payload: str | bytes | bytearray) -> None:
    """Strictly parse and validate a raw candidate record without duplicate members."""

    document = loads_json_strict(payload)
    validate_candidate_record(_require_mapping(document, "candidate record"))


def validate_alternative_candidates(document: Mapping[str, object]) -> None:
    """Compatibility entry point with the same complete-record gate as production.

    It intentionally no longer accepts an arbitrary partial candidate list;
    allowing that bypass would omit the bounded-pool Schema and cross-candidate
    constraints that make the research record fail closed.
    """

    validate_candidate_record(document)
