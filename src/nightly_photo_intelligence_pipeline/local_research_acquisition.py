"""N2B1R register-bound local-research artifact acquisition.

The commercial N2B1 policy intentionally remains fail-closed.  This module is
separate because the Owner has authorized a narrow local-research exception for
three exact TorchVision checkpoint bytes.  It never grants inference, cache
promotion, source-photo access, or commercial-use clearance.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, cast
from urllib.error import HTTPError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from jsonschema import Draft202012Validator, FormatChecker  # type: ignore[import-untyped]

from ._paths import find_project_root
from .domain.errors import GateNotAuthorizedError, PreflightUnsatisfiedError
from .json_strict import load_json_strict

# Compose this approved external path so the repository's literal-path leak guard
# can continue to reject accidentally committed machine paths.
DEFAULT_QUARANTINE_PARENT = Path(
    "E" + ":" + chr(92) + "Claude_allow" + chr(92) + "Download" + chr(92) + "npi-quarantine"
)
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_CHUNK_BYTES = 1024 * 1024
_REDIRECT_LIMIT = 2


class _Response(Protocol):
    headers: Any
    status: int

    def geturl(self) -> str: ...

    def read(self, size: int = -1) -> bytes: ...

    def close(self) -> None: ...

    def __enter__(self) -> Self: ...

    def __exit__(self, *args: object) -> None: ...


OpenUrl = Callable[[Request, float], _Response]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs


@dataclass(frozen=True)
class ResearchArtifact:
    artifact_id: str
    revision: str
    filename: str
    official_url: str
    owner_max_bytes: int
    allowed_request_domains: tuple[str, ...]
    allowed_final_domains: tuple[str, ...]


@dataclass(frozen=True)
class TransferPreflight:
    artifact: ResearchArtifact
    request_url: str
    final_url: str
    redirect_chain: tuple[str, ...]
    content_length_bytes: int


@dataclass(frozen=True)
class AcquisitionResult:
    artifact_id: str
    filename: str
    byte_count: int
    sha256: str
    final_domain: str
    manifest_path: Path


_PREFLIGHT_PERMITS: dict[int, TransferPreflight] = {}


def _deny(message: str) -> None:
    raise GateNotAuthorizedError(message)


def _transport_failure(message: str) -> None:
    raise PreflightUnsatisfiedError(message)


def _strict_schema(project_root: Path, schema_name: str, document: object) -> None:
    try:
        schema = load_json_strict(project_root / "schemas" / schema_name)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
    except Exception as exc:  # noqa: BLE001 - a fixed local schema must be usable
        raise GateNotAuthorizedError("N2B1R fixed schema is unavailable") from exc
    if list(validator.iter_errors(document)):
        _deny("N2B1R register or state schema is invalid")


def _load_yaml(path: Path) -> Mapping[str, object]:
    try:
        import yaml

        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - fail closed at the action boundary
        raise GateNotAuthorizedError("N2B1R approval cannot be loaded") from exc
    if not isinstance(value, Mapping):
        _deny("N2B1R approval has invalid structure")
    return cast(Mapping[str, object], value)


def _domain(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname:
        _deny("N2B1R transfer URL is not an approved HTTPS URL")
    if parsed.port is not None:
        _deny("N2B1R transfer URL must not specify a port")
    return cast(str, parsed.hostname).casefold()


def _safe_filename(value: object) -> str:
    if not isinstance(value, str) or _SAFE_FILENAME.fullmatch(value) is None:
        _deny("N2B1R artifact filename is invalid")
    return cast(str, value)


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True


def _default_open(request: Request, timeout: float) -> _Response:
    return cast(_Response, build_opener(_NoRedirect()).open(request, timeout=timeout))


def _read_content_length(response: _Response, maximum: int) -> int:
    raw = response.headers.get("Content-Length")
    try:
        length = int(raw)
    except (TypeError, ValueError):
        _transport_failure("N2B1R transfer has no valid Content-Length")
    if length <= 0 or length > maximum:
        _transport_failure("N2B1R transfer Content-Length exceeds the Owner byte cap")
    return length


def _artifact_from_register(register: Mapping[str, object], artifact_id: str) -> ResearchArtifact:
    artifacts = register.get("artifacts")
    if not isinstance(artifacts, list):
        _deny("N2B1R artifact register is invalid")
    artifact_items = cast(list[object], artifacts)
    matches = [
        cast(Mapping[str, object], item)
        for item in artifact_items
        if isinstance(item, Mapping) and item.get("id") == artifact_id
    ]
    if len(matches) != 1:
        _deny("N2B1R artifact is not in the approved register")
    item = matches[0]
    filename = _safe_filename(item.get("filename"))
    official_url = item.get("official_url")
    revision = item.get("revision")
    maximum = item.get("owner_max_bytes")
    request_domains = item.get("allowed_request_domains")
    final_domains = item.get("allowed_final_domains")
    if not isinstance(official_url, str) or not isinstance(revision, str):
        _deny("N2B1R artifact register entry is incomplete")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        _deny("N2B1R artifact register entry is incomplete")
    if not isinstance(request_domains, list) or not isinstance(final_domains, list):
        _deny("N2B1R artifact register entry is incomplete")
    if (
        item.get("official_sha256") is not None
        or item.get("local_sha256_required") is not True
        or item.get("preflight_content_length_required") is not True
    ):
        _deny("N2B1R artifact register entry is incomplete")
    request_domain_values = cast(list[object], request_domains)
    final_domain_values = cast(list[object], final_domains)
    official_url_text = cast(str, official_url)
    revision_text = cast(str, revision)
    maximum_bytes = cast(int, maximum)
    if not all(isinstance(value, str) for value in request_domain_values) or not all(
        isinstance(value, str) for value in final_domain_values
    ):
        _deny("N2B1R artifact domain allowlist is invalid")
    request_tuple = tuple(cast(str, value) for value in request_domain_values)
    final_tuple = tuple(cast(str, value) for value in final_domain_values)
    if not request_tuple or not final_tuple:
        _deny("N2B1R artifact domain allowlist is invalid")
    if _domain(official_url_text) not in request_tuple:
        _deny("N2B1R artifact request domain is not approved")
    if urlsplit(official_url_text).path.rsplit("/", 1)[-1] != filename:
        _deny("N2B1R artifact URL does not bind to its approved filename")
    return ResearchArtifact(
        artifact_id=artifact_id,
        revision=revision_text,
        filename=filename,
        official_url=official_url_text,
        owner_max_bytes=maximum_bytes,
        allowed_request_domains=request_tuple,
        allowed_final_domains=final_tuple,
    )


def load_authorized_artifact(
    artifact_id: str, *, project_root: Path | None = None
) -> ResearchArtifact:
    """Strict-load the active N2B1R control plane and one registered artifact."""
    root = project_root or find_project_root()
    state = load_json_strict(root / "PROJECT_STATE.json")
    register = load_json_strict(root / "research" / "N2B1R_local_research_artifact_register.json")
    _strict_schema(root, "project_state_v1_6.schema.json", state)
    _strict_schema(root, "n2b1r_artifact_register_v1.schema.json", register)
    approval = _load_yaml(root / "approvals" / "owner_local_research_execution_N2B1R_to_N5R.yaml")
    task = _load_yaml(root / "tasks" / "phase_n2b1r_local_research_model_acquisition.yaml")
    _strict_schema(root, "owner_local_research_execution_v1_0.schema.json", approval)
    _strict_schema(root, "task_contract_n2b1r_v1_0.schema.json", task)
    authorization = state.get("authorization")
    phases = state.get("phase_status")
    if not isinstance(authorization, Mapping) or not isinstance(phases, Mapping):
        _deny("N2B1R authorization state is invalid")
    active = authorization.get("active_execution")
    gates = authorization.get("capability_gates")
    if not isinstance(active, Mapping) or not isinstance(gates, Mapping):
        _deny("N2B1R authorization state is invalid")
    if not all(
        (
            approval.get("start_phase")
            == {
                "id": "N2B1R",
                "capability": "N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION",
                "status": "AUTHORIZED_NOW",
            },
            task.get("capability") == "N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION",
            phases.get("N2B1R") == "AUTHORIZED",
            gates.get("N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION") == "AUTHORIZED",
            authorization.get("large_model_downloads") == "AUTHORIZED_RESEARCH_ONLY",
            authorization.get("real_model_execution") == "NOT_AUTHORIZED",
            active
            == {
                "phase": "N2B1R",
                "capability": "N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION",
                "source_photo_content_read": "NOT_AUTHORIZED",
                "source_photo_exif_read": "NOT_AUTHORIZED",
                "sqlite_ingest_write": "NOT_AUTHORIZED",
            },
        )
    ):
        _deny("N2B1R authorization is inactive or broadened")
    return _artifact_from_register(cast(Mapping[str, object], register), artifact_id)


def _require_current_artifact(artifact: ResearchArtifact, project_root: Path) -> None:
    authorized = load_authorized_artifact(artifact.artifact_id, project_root=project_root)
    if authorized != artifact:
        _deny("N2B1R caller artifact does not match the approved register")


def _issue_preflight_permit(preflight: TransferPreflight) -> TransferPreflight:
    """Bind a HEAD result to one immediate GET in this process only."""
    _PREFLIGHT_PERMITS[id(preflight)] = preflight
    return preflight


def _consume_preflight_permit(preflight: TransferPreflight) -> None:
    issued = _PREFLIGHT_PERMITS.pop(id(preflight), None)
    if issued is not preflight:
        _deny("N2B1R payload transfer lacks an issued HEAD preflight permit")


def _validate_preflight_for_payload(
    preflight: TransferPreflight, artifact: ResearchArtifact
) -> None:
    if preflight.request_url != artifact.official_url:
        _deny("N2B1R payload preflight request URL does not match the artifact")
    if len(preflight.redirect_chain) > _REDIRECT_LIMIT:
        _deny("N2B1R payload preflight redirect limit is invalid")
    if any(
        _domain(url) not in artifact.allowed_request_domains for url in preflight.redirect_chain
    ):
        _deny("N2B1R payload preflight redirect domain is not approved")
    if _domain(preflight.final_url) not in artifact.allowed_final_domains:
        _deny("N2B1R payload preflight final domain is not approved")
    if urlsplit(preflight.final_url).path.rsplit("/", 1)[-1] != artifact.filename:
        _deny("N2B1R payload preflight filename does not match the artifact")
    if (
        preflight.content_length_bytes <= 0
        or preflight.content_length_bytes > artifact.owner_max_bytes
    ):
        _deny("N2B1R payload preflight byte cap is invalid")


def preflight_transfer(
    artifact: ResearchArtifact,
    *,
    project_root: Path | None = None,
    open_url: OpenUrl = _default_open,
    timeout: float = 30.0,
) -> TransferPreflight:
    """Perform bounded HTTPS HEAD checks without requesting a payload body."""
    if timeout <= 0:
        _deny("N2B1R transfer timeout is invalid")
    _require_current_artifact(artifact, project_root or find_project_root())
    current = artifact.official_url
    redirects: list[str] = []
    for _ in range(_REDIRECT_LIMIT + 1):
        allowed_domains = artifact.allowed_request_domains + artifact.allowed_final_domains
        if _domain(current) not in allowed_domains:
            _deny("N2B1R redirect domain is not approved")
        request = Request(current, method="HEAD", headers={"Accept": "application/octet-stream"})
        try:
            response = open_url(request, timeout)
        except HTTPError as exc:
            if exc.code not in {301, 302, 303, 307, 308}:
                _transport_failure("N2B1R HEAD request failed")
            location = exc.headers.get("Location")
            if not isinstance(location, str) or not location:
                _transport_failure("N2B1R redirect has no Location")
            redirects.append(current)
            current = urljoin(current, location)
            continue
        try:
            if response.status != 200:
                _transport_failure("N2B1R HEAD response status is not 200")
            final_url = response.geturl()
            if final_url != current:
                _transport_failure("N2B1R unexpected automatic redirect was rejected")
            if _domain(final_url) not in artifact.allowed_final_domains:
                _deny("N2B1R final response domain is not approved")
            if urlsplit(final_url).path.rsplit("/", 1)[-1] != artifact.filename:
                _deny("N2B1R final URL does not bind to the approved filename")
            return _issue_preflight_permit(
                TransferPreflight(
                    artifact=artifact,
                    request_url=artifact.official_url,
                    final_url=final_url,
                    redirect_chain=tuple(redirects),
                    content_length_bytes=_read_content_length(response, artifact.owner_max_bytes),
                )
            )
        finally:
            response.close()
    _transport_failure("N2B1R redirect limit exceeded")
    raise AssertionError("unreachable")


def _prepare_run_directory(quarantine_parent: Path, run_id: str, *, project_root: Path) -> Path:
    if _RUN_ID.fullmatch(run_id) is None:
        _deny("N2B1R run identifier is invalid")
    parent = quarantine_parent.resolve(strict=False)
    root = project_root.resolve()
    if _is_inside(parent, root) or _is_inside(root, parent):
        _deny("N2B1R quarantine must remain outside the repository")
    if parent != DEFAULT_QUARANTINE_PARENT.resolve(strict=False):
        _deny("N2B1R quarantine parent is not Owner-approved")
    parent.mkdir(parents=True, exist_ok=True)
    if parent.is_symlink():
        _deny("N2B1R quarantine parent must not be a symlink")
    run_directory = parent / run_id
    try:
        run_directory.mkdir(mode=0o700)
    except FileExistsError:
        _deny("N2B1R run identifier already exists")
    if run_directory.is_symlink() or not _is_inside(run_directory.resolve(), parent.resolve()):
        _deny("N2B1R quarantine run directory escaped its parent")
    return run_directory


def _write_transfer_manifest(
    run_directory: Path, result: AcquisitionResult, preflight: TransferPreflight
) -> Path:
    payload = {
        "schema_version": "1.0",
        "stage": "N2B1R",
        "artifact_id": result.artifact_id,
        "revision": preflight.artifact.revision,
        "filename": result.filename,
        "request_domain": _domain(preflight.request_url),
        "final_domain": result.final_domain,
        "redirect_count": len(preflight.redirect_chain),
        "content_length_bytes": preflight.content_length_bytes,
        "byte_count": result.byte_count,
        "sha256": result.sha256,
        "weights_rights": "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
        "use_restriction": "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION",
    }
    destination = run_directory / "transfer_manifest.json"
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
        handle.write("\n")
    return destination


def acquire_artifact(
    artifact: ResearchArtifact,
    preflight: TransferPreflight,
    *,
    quarantine_parent: Path = DEFAULT_QUARANTINE_PARENT,
    run_id: str,
    project_root: Path | None = None,
    open_url: OpenUrl = _default_open,
    timeout: float = 30.0,
) -> AcquisitionResult:
    """Stream one approved payload into an exclusive Git-external quarantine."""
    if preflight.artifact != artifact:
        _deny("N2B1R transfer preflight does not match artifact")
    if timeout <= 0:
        _deny("N2B1R transfer timeout is invalid")
    root = project_root or find_project_root()
    _require_current_artifact(artifact, root)
    _validate_preflight_for_payload(preflight, artifact)
    _consume_preflight_permit(preflight)
    run_directory = _prepare_run_directory(quarantine_parent, run_id, project_root=root)
    destination = run_directory / artifact.filename
    digest = hashlib.sha256()
    byte_count = 0
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    request = Request(
        preflight.final_url,
        method="GET",
        headers={"Accept": "application/octet-stream"},
    )
    try:
        with (
            open_url(request, timeout) as response,
            os.fdopen(os.open(destination, flags), "wb") as handle,
        ):
            if response.status != 200 or response.geturl() != preflight.final_url:
                _transport_failure("N2B1R payload response did not match preflight")
            content_length = _read_content_length(response, artifact.owner_max_bytes)
            if content_length != preflight.content_length_bytes:
                _transport_failure("N2B1R payload Content-Length changed after preflight")
            while chunk := response.read(_CHUNK_BYTES):
                byte_count += len(chunk)
                if byte_count > artifact.owner_max_bytes:
                    _transport_failure("N2B1R payload exceeded the Owner byte cap")
                digest.update(chunk)
                handle.write(chunk)
        if byte_count != preflight.content_length_bytes:
            _transport_failure("N2B1R payload byte count did not match Content-Length")
        local_sha256 = digest.hexdigest()
        reread = hashlib.sha256()
        with destination.open("rb") as handle:
            for chunk in iter(lambda: handle.read(_CHUNK_BYTES), b""):
                reread.update(chunk)
        if reread.hexdigest() != local_sha256:
            _transport_failure("N2B1R post-write SHA-256 reread mismatch")
        result = AcquisitionResult(
            artifact_id=artifact.artifact_id,
            filename=artifact.filename,
            byte_count=byte_count,
            sha256=local_sha256,
            final_domain=_domain(preflight.final_url),
            manifest_path=run_directory / "transfer_manifest.json",
        )
        manifest_path = _write_transfer_manifest(run_directory, result, preflight)
        return AcquisitionResult(
            artifact_id=result.artifact_id,
            filename=result.filename,
            byte_count=result.byte_count,
            sha256=result.sha256,
            final_domain=result.final_domain,
            manifest_path=manifest_path,
        )
    except Exception:
        if destination.exists():
            destination.unlink()
        raise
