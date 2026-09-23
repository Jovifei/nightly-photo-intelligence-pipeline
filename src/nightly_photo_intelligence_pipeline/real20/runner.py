"""Real20 preparation and one-shot read-only evaluation."""

from __future__ import annotations

import os
import stat
from collections.abc import Callable, Mapping, Sequence
from contextlib import ExitStack
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, NoReturn, Protocol, cast

from ..engineering.common import canonical, sha256, strict_json
from ..engineering.path_policy import overlaps
from ..ingest.read_only_capability import verify_source_read_only_capability
from ..ingest.source_guard import FileIdentity, is_reparse_point, validate_roots
from ..n2b2_synthetic.config import TorchVisionRole
from ..n2b2_synthetic.vision_facts import build_vision_facts, compute_fact_digest
from ..windows_bound_promotion import BoundStagingTransaction
from .contracts import EXIF_ALLOWLIST, Real20Error, load_manifest, validate_credential
from .exif import read_real20_exif
from .identity import candidate_identity

H3_CANDIDATE = "ffc4130823c1308f089b835c766e341ec2173e82"
_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".heic", ".webp")


class VisionBackend(Protocol):
    def detect_pose(self, image_bytes: bytes) -> Any: ...

    def segment(self, image_bytes: bytes, role: TorchVisionRole) -> Any: ...

    def unload(self, role: TorchVisionRole | None = None) -> None: ...


def _write_new(path: Path, payload: Mapping[str, Any]) -> bytes:
    if path.exists():
        raise Real20Error("REAL20_OUTPUT_NOT_FRESH")
    if not path.parent.is_dir() or is_reparse_point(path.parent):
        raise Real20Error("REAL20_OUTPUT_PARENT_INVALID")
    data = canonical(dict(payload))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except OSError as exc:
        raise Real20Error("REAL20_OUTPUT_WRITE_FAILED") from exc
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return data


def _write_bound_new(directory: Any, name: str, payload: Mapping[str, Any]) -> bytes:
    data = canonical(dict(payload))
    try:
        with directory.create_file(name) as handle:
            handle.write(data)
            handle.flush()
    except Exception as exc:
        raise Real20Error("REAL20_OUTPUT_WRITE_FAILED") from exc
    try:
        with directory.open_file(name) as handle:
            if handle.read_all(max_bytes=len(data)) != data:
                raise Real20Error("REAL20_OUTPUT_INTEGRITY_FAILED")
    except Real20Error:
        raise
    except Exception as exc:
        raise Real20Error("REAL20_OUTPUT_INTEGRITY_FAILED") from exc
    return data


def _read_control(path: Path) -> dict[str, Any]:
    from .admission import control_bytes

    try:
        value = strict_json(control_bytes(path))
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_CONTROL_JSON_INVALID") from exc
    if not isinstance(value, dict):
        raise Real20Error("REAL20_CONTROL_OBJECT_REQUIRED")
    return value


def _external(path: Path, *, project_root: Path, source_root: Path, ledger_root: Path) -> None:
    if is_reparse_point(path):
        raise Real20Error("REAL20_REPARSE_PATH_DENIED")
    if overlaps(path, project_root) or overlaps(path, source_root) or overlaps(path, ledger_root):
        raise Real20Error("REAL20_EXTERNAL_OUTPUT_REQUIRED")


def _source_root_identity(path: Path) -> FileIdentity:
    try:
        info = path.lstat()
    except OSError as exc:
        raise Real20Error("REAL20_SOURCE_ROOT_UNAVAILABLE") from exc
    if not stat.S_ISDIR(info.st_mode) or is_reparse_point(path):
        raise Real20Error("REAL20_SOURCE_ROOT_INVALID")
    return FileIdentity.from_stat(info)


def _read_image(path: Path, source_root: Path, expected_sha: str) -> tuple[bytes, int, int]:
    try:
        from PIL import Image

        data = _source_bytes(path, source_root)
        if sha256(data) != expected_sha:
            raise Real20Error("REAL20_SOURCE_HASH_MISMATCH")
        with Image.open(BytesIO(data)) as image:
            width, height = image.size
        if width < 1 or height < 1:
            raise Real20Error("REAL20_IMAGE_DIMENSIONS_INVALID")
        return data, width, height
    except Real20Error:
        raise
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_IMAGE_READ_FAILED") from exc


def _verify_source_bytes(source_root: Path, assets: Sequence[Any]) -> None:
    for asset in assets:
        path = source_root / asset.relative_path
        try:
            if sha256(_source_bytes(path, source_root)) != asset.sha256:
                raise Real20Error("REAL20_SOURCE_INTEGRITY_CHANGED")
        except Real20Error:
            raise
        except Exception as exc:  # noqa: BLE001
            raise Real20Error("REAL20_SOURCE_INTEGRITY_CHANGED") from exc


def _source_bytes(path: Path, source_root: Path) -> bytes:
    from ..windows_bound_promotion import bind_existing_directory

    relative = path.relative_to(source_root)
    if path.suffix.lower() not in _IMAGE_EXTENSIONS:
        raise Real20Error("REAL20_IMAGE_TYPE_INVALID")
    with ExitStack() as stack:
        directory = stack.enter_context(bind_existing_directory(source_root, writable=False))
        for component in relative.parts[:-1]:
            directory = stack.enter_context(directory.open_directory(component, writable=False))
        handle = stack.enter_context(directory.open_file(relative.name))
        return handle.read_all(max_bytes=64 * 1024 * 1024)


def _reservation(ledger_root: Any, credential_sha: str, bindings_sha: str, now: datetime) -> Any:
    try:
        target = ledger_root.create_directory(credential_sha)
    except FileExistsError as exc:
        raise Real20Error("REAL20_CREDENTIAL_ALREADY_CONSUMED") from exc
    except Exception as exc:
        try:
            consumed = credential_sha in ledger_root.list_names()
        except Exception:
            consumed = False
        if consumed:
            raise Real20Error("REAL20_CREDENTIAL_ALREADY_CONSUMED") from exc
        raise Real20Error("REAL20_LEDGER_RESERVATION_FAILED") from exc
    record = {
        "schema_version": "npi-real20-consumption-v1",
        "status": "RESERVED",
        "credential_sha256": credential_sha,
        "bindings_sha256": bindings_sha,
        "reserved_at_utc": now.astimezone(UTC).isoformat(),
    }
    data = canonical(record)
    try:
        with target.create_file("reservation.json") as handle:
            handle.write(data)
            handle.flush()
        with target.open_file("reservation.json") as handle:
            if handle.read_all(max_bytes=4096) != data:
                raise Real20Error("REAL20_RESERVATION_WRITE_INVALID")
    except BaseException as record_error:
        # The directory creation already consumed the allowance. Never remove it.
        # Even an interrupted/failed reservation-record write attempts a terminal.
        with ExitStack() as cleanup:
            cleanup.callback(target.close)
            try:
                _finish(
                    target, status="FAILED", evidence_sha=None,
                    evidence_status="RESERVATION_RECORD_FAILED",
                )
            except BaseException as terminal_error:
                raise BaseExceptionGroup(
                    "REAL20_RESERVATION_AND_TERMINAL_WRITE_FAILED",
                    [record_error, terminal_error],
                ) from None
        raise
    return target


def _finish(
    reservation: Any, *, status: str, evidence_sha: str | None, evidence_status: str
) -> None:
    data = canonical(
        {
            "schema_version": "npi-real20-consumption-v1",
            "status": status,
            "evidence_status": evidence_status,
            "evidence_sha256": evidence_sha,
            "finished_at_utc": datetime.now(UTC).isoformat(),
        }
    )
    with BoundStagingTransaction.create(reservation) as transaction:
        with transaction.create_file("record.json") as handle:
            handle.write(data)
            handle.flush()
        with transaction.staging.open_file("record.json") as handle:
            if handle.read_all(max_bytes=4096) != data:
                raise Real20Error("REAL20_TERMINAL_WRITE_INVALID")
        transaction.publish("terminal")


def _record_failed_attempt(
    reservation: Any,
    output_bound: Any,
    credential_sha: str,
    *,
    primary: BaseException,
    checks: Sequence[Callable[[], None]],
) -> NoReturn:
    """Persist a truthful failure; one cleanup failure cannot skip the rest.

    Python 3.11+ ExceptionGroup preserves independent failures without hiding
    the original runner exception. A terminal I/O failure stays visible; this
    is not a promise of successful persistence after disk/process failure.
    """
    failures: list[BaseException] = [primary]
    for check in checks:
        try:
            check()
        except BaseException as check_error:
            failures.append(check_error)
    failure = {
        "schema_version": "npi-real20-evaluation-v1",
        "status": "REAL20_FAILED",
        "credential_sha256": credential_sha,
        "error_code": next(
            (error.code for error in reversed(failures) if isinstance(error, Real20Error)),
            "REAL20_WORKER_FAILED",
        ),
        "failure_types": [type(error).__name__ for error in failures],
        "project_state_n2b2": "LOCKED",
    }
    failure_bytes = None
    try:
        failure_bytes = _write_bound_new(output_bound, "real20_failure.json", failure)
    except BaseException as evidence_error:
        failures.append(evidence_error)
    try:
        _finish(
            reservation, status="FAILED",
            evidence_sha=sha256(failure_bytes) if failure_bytes is not None else None,
            evidence_status="PERSISTED" if failure_bytes is not None else "PERSISTENCE_FAILED",
        )
    except BaseException as terminal_error:
        failures.append(terminal_error)
    if len(failures) == 1:
        raise primary
    raise BaseExceptionGroup("REAL20_ATTEMPT_FAILED", failures) from None


def _manifest_selection(manifest: Any) -> list[dict[str, Any]]:
    aliases = {
        asset.asset_id: f"real20-{index:03d}" for index, asset in enumerate(manifest.assets, 1)
    }
    return [
        {
            "case_id": aliases[asset.asset_id],
            "expected_sha256": asset.sha256,
            "duplicate_of": aliases.get(asset.duplicate_of),
            "action": "REFERENCE_ONLY" if asset.duplicate_of else "INFER_ONCE",
        }
        for asset in manifest.assets
    ]


def prepare_real20(
    *,
    project_root: Path,
    manifest_path: Path,
    h3_provenance_path: Path,
    output_path: Path,
    h3_candidate: str = H3_CANDIDATE,
) -> dict[str, Any]:
    """Create a redacted non-executable worksheet from metadata only."""
    missing = [
        label
        for label, path in (
            ("MANIFEST", manifest_path),
            ("H3_PROVENANCE", h3_provenance_path),
        )
        if not path.is_file()
    ]
    if missing:
        result = {
            "schema_version": "npi-real20-preparation-v1",
            "status": "REAL20_PREPARATION_INCOMPLETE",
            "execution_authorized": False,
            "blockers": ["REAL20_" + label + "_MISSING" for label in missing]
            + [
                "REAL20_DATA_RECEIPT_REQUIRED",
                "REAL20_INDEPENDENT_REVIEW_REQUIRED",
                "REAL20_WORKER_RUNTIME_PROBE_REQUIRED",
                "REAL20_OWNER_ANCHOR_REQUIRED",
            ],
            "execution_draft": {"issued": False, "source_read_authorized_now": False},
        }
        if overlaps(output_path, project_root):
            raise Real20Error("REAL20_EXTERNAL_OUTPUT_REQUIRED")
        _write_new(output_path, result)
        return result
    manifest = load_manifest(manifest_path)
    h3 = _read_control(h3_provenance_path)
    h3_source = h3.get("h3_source")
    h3_closeout = h3.get("h3_closeout")
    if (
        not isinstance(h3_source, dict)
        or h3_source.get("candidate_commit", h3_source.get("candidate")) != h3_candidate
    ):
        raise Real20Error("REAL20_H3_PROVENANCE_MISMATCH")
    if not isinstance(h3_closeout, dict) or h3_closeout.get("ledger_status") != "COMPLETE":
        raise Real20Error("REAL20_H3_CLOSEOUT_INCOMPLETE")
    identity = candidate_identity(project_root)
    if (
        output_path.exists()
        or not output_path.parent.is_dir()
        or is_reparse_point(output_path.parent)
    ):
        raise Real20Error("REAL20_OUTPUT_NOT_FRESH")
    if overlaps(output_path, project_root):
        raise Real20Error("REAL20_EXTERNAL_OUTPUT_REQUIRED")
    result = {
        "schema_version": "npi-real20-preparation-v1",
        "status": "REAL20_PREPARATION_READY_AWAITING_CREDENTIAL",
        "execution_authorized": False,
        "production_n2b2": "LOCKED",
        "candidate": {
            "commit": identity["candidate_commit"],
            "tree": identity["candidate_tree"],
            "source_manifest_sha256": identity["source_manifest_sha256"],
            "project_state_sha256": identity["project_state_sha256"],
        },
        "h3_provenance": {"candidate": h3_candidate, "ledger_status": "COMPLETE"},
        "selection": {
            "manifest_sha256": manifest.sha256,
            "source_fingerprint_sha256": sha256(manifest.source_fingerprint.encode("utf-8")),
            "asset_count": 20,
            "canonical_count": manifest.canonical_count,
            "duplicate_count": 1,
            "assets": _manifest_selection(manifest),
        },
        "exif_allowlist": list(EXIF_ALLOWLIST),
        "blockers": [
            "REAL20_CREDENTIAL_NOT_MATERIALIZED",
            "REAL20_SOURCE_READ_ONLY_CAPABILITY_PENDING",
            "REAL20_WORKER_RUNTIME_PROBE_PENDING",
            "REAL20_HUMAN_REVIEW_PENDING",
        ],
        "execution_draft": {
            "issued": False,
            "execution_candidate": None,
            "not_before_utc": None,
            "expires_at_utc": None,
            "max_runs": 1,
            "max_unique_inferences": 19,
            "source_read_authorized_now": False,
        },
    }
    _write_new(output_path, result)
    return result


def _run_real20(
    *,
    project_root: Path,
    source_root: Path,
    manifest_path: Path,
    credential_path: Path,
    anchor_path: Path,
    runtime_identity_path: Path,
    model_identity_path: Path,
    ledger_root: Path,
    output_root: Path,
    backend_factory: Callable[[], VisionBackend] | None = None,
    runtime_probe: Callable[[], dict[str, Any]] | None = None,
    capability_probe: Callable[[Path, Sequence[Path]], object] | None = None,
    reasoning: Callable[[bytes, dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    revalidate: Callable[[Any], None] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Run one exact, credential-bound, read-only Real20 evaluation."""

    current = (now or datetime.now(UTC)).astimezone(UTC)
    from .admission import control_bytes

    manifest = load_manifest(manifest_path)
    identity = candidate_identity(project_root)
    runtime_identity = _read_control(runtime_identity_path)
    model_identity = _read_control(model_identity_path)
    credential_raw = control_bytes(credential_path)
    anchor = _read_control(anchor_path)
    expected = {
        "candidate_commit": identity["candidate_commit"],
        "candidate_tree": identity["candidate_tree"],
        "project_state_sha256": identity["project_state_sha256"],
        "manifest_sha256": manifest.sha256,
        "source_fingerprint_sha256": sha256(manifest.source_fingerprint.encode("utf-8")),
        "runtime_identity_sha256": sha256(canonical(runtime_identity)),
        "model_identity_sha256": sha256(canonical(model_identity)),
    }
    credential_sha = validate_credential(
        credential_raw,
        anchor=anchor,
        expected=expected,
        runtime_identity=runtime_identity,
        model_identity=model_identity,
        now=current,
    )
    if not output_root.is_dir() or any(output_root.iterdir()):
        raise Real20Error("REAL20_OUTPUT_NOT_FRESH")
    _external(
        output_root, project_root=project_root, source_root=source_root, ledger_root=ledger_root
    )
    if (
        not ledger_root.is_dir()
        or overlaps(ledger_root, project_root)
        or overlaps(ledger_root, source_root)
    ):
        raise Real20Error("REAL20_LEDGER_ROOT_INVALID")
    try:
        source_resolved, _ = validate_roots(source_root, output_root)
    except Exception as exc:  # noqa: BLE001
        raise Real20Error("REAL20_SOURCE_RUNTIME_BOUNDARY_INVALID") from exc
    assets = [source_resolved / asset.relative_path for asset in manifest.assets]
    capability_result = (
        capability_probe(source_resolved, assets)
        if capability_probe is not None
        else verify_source_read_only_capability(source_resolved, assets)
    )
    verified = capability_result is True or bool(getattr(capability_result, "verified", False))
    if not verified:
        raise Real20Error("REAL20_SOURCE_READ_ONLY_NOT_VERIFIED")

    def post_source_check() -> None:
        _verify_source_bytes(source_resolved, manifest.assets)
        capability = (
            capability_probe(source_resolved, assets)
            if capability_probe is not None
            else verify_source_read_only_capability(source_resolved, assets)
        )
        if not (capability is True or bool(getattr(capability, "verified", False))):
            raise Real20Error("REAL20_SOURCE_READ_ONLY_NOT_VERIFIED")

    if runtime_probe is None:
        raise Real20Error("REAL20_RUNTIME_PROBE_REQUIRED")
    observed_runtime = runtime_probe()
    if sha256(canonical(observed_runtime)) != expected["runtime_identity_sha256"]:
        raise Real20Error("REAL20_RUNTIME_IDENTITY_DRIFT")
    if revalidate is not None and model_identity != observed_runtime.get("models"):
        raise Real20Error("REAL20_MODEL_IDENTITY_DRIFT")
    root_before = _source_root_identity(source_resolved)
    latest_raw = control_bytes(credential_path)
    latest_anchor = _read_control(anchor_path)
    if latest_raw != credential_raw or latest_anchor != anchor:
        raise Real20Error("REAL20_CREDENTIAL_CHANGED")
    latest_sha = validate_credential(
        latest_raw,
        anchor=latest_anchor,
        expected=expected,
        runtime_identity=runtime_identity,
        model_identity=model_identity,
        now=now or datetime.now(UTC),
    )
    if latest_sha != credential_sha:
        raise Real20Error("REAL20_CREDENTIAL_CHANGED")
    from ..windows_bound_promotion import bind_existing_directory

    with ExitStack() as resources:
        output_bound = resources.enter_context(bind_existing_directory(output_root, writable=True))
        if output_bound.list_names():
            raise Real20Error("REAL20_OUTPUT_NOT_FRESH")
        ledger_bound = resources.enter_context(bind_existing_directory(ledger_root, writable=True))
        if revalidate is not None:
            revalidate(ledger_bound)
        latest_raw = control_bytes(credential_path)
        latest_anchor = _read_control(anchor_path)
        if latest_raw != credential_raw or latest_anchor != anchor:
            raise Real20Error("REAL20_CREDENTIAL_CHANGED")
        latest_sha = validate_credential(
            latest_raw,
            anchor=latest_anchor,
            expected=expected,
            runtime_identity=runtime_identity,
            model_identity=model_identity,
            now=now or datetime.now(UTC),
        )
        if latest_sha != credential_sha:
            raise Real20Error("REAL20_CREDENTIAL_CHANGED")
        reservation = resources.enter_context(
            _reservation(ledger_bound, credential_sha, sha256(canonical(expected)), current)
        )
        backend: VisionBackend | None = None
        source_admitted = False
        evidence: dict[str, Any] = {}
        try:
            if revalidate is not None:
                from .admission import protect_consumption

                protect_consumption(reservation)
            source_admitted = True
            backend = backend_factory() if backend_factory is not None else None
            if backend is None:
                raise Real20Error("REAL20_BACKEND_NOT_CONFIGURED")
            rows: list[dict[str, Any]] = []
            facts_by_id: dict[str, dict[str, Any]] = {}
            aliases = {
                asset.asset_id: f"real20-{index:03d}" for index, asset in enumerate(manifest.assets, 1)
            }
            for ordinal, asset in enumerate(manifest.assets, 1):
                if not root_before.same_identity(_source_root_identity(source_resolved)):
                    raise Real20Error("REAL20_SOURCE_ROOT_CHANGED")
                if asset.duplicate_of:
                    rows.append(
                        {
                            "case_id": aliases[asset.asset_id],
                            "action": "REFERENCE_ONLY",
                            "duplicate_of": aliases[asset.duplicate_of],
                        }
                    )
                    continue
                image_path = source_resolved / asset.relative_path
                data, width, height = _read_image(image_path, source_resolved, asset.sha256)
                pose = backend.detect_pose(data)
                backend.unload(TorchVisionRole.POSE_BASELINE_SMOKE)
                primary = backend.segment(data, TorchVisionRole.SEGMENTATION_PRIMARY)
                backend.unload(TorchVisionRole.SEGMENTATION_PRIMARY)
                comparator = backend.segment(data, TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR)
                backend.unload(TorchVisionRole.SEGMENTATION_QUALITY_COMPARATOR)
                facts = build_vision_facts(
                    case_id=f"real20-{ordinal:03d}",
                    image_sha256=asset.sha256,
                    generator_version="real20-runtime-v1",
                    seed=None,
                    width=width,
                    height=height,
                    pose=pose,
                    seg_primary=primary,
                    seg_comparator=comparator,
                )
                if facts.get("schema_version") != "1.2" or facts.get(
                    "fact_digest"
                ) != compute_fact_digest(facts):
                    raise Real20Error("REAL20_FACT_CONTRACT_INVALID")
                facts_by_id[asset.asset_id] = facts
                if revalidate is not None:
                    from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

                    schema = strict_json(
                        (
                            project_root / "schemas/n2b2_vision_fact_contract_v1_2.schema.json"
                        ).read_bytes()
                    )
                    schema["properties"]["case_id"] = {"const": facts["case_id"]}
                    if list(Draft202012Validator(schema).iter_errors(facts)):
                        raise Real20Error("REAL20_FACT_CONTRACT_INVALID")
                interpretation = (
                    reasoning(data, facts, runtime_identity) if reasoning is not None else None
                )
                rows.append(
                    {
                        "case_id": aliases[asset.asset_id],
                        "action": "INFER_ONCE",
                        "source_sha256": asset.sha256,
                        "facts": facts,
                        "exif": read_real20_exif(data),
                        "interpretation": interpretation,
                    }
                )
            backend.unload()
            post_source_check()
            if revalidate is not None:
                revalidate(ledger_bound)
            root_after = _source_root_identity(source_resolved)
            if not root_before.same_identity(root_after):
                raise Real20Error("REAL20_SOURCE_ROOT_CHANGED")
            evidence = {
                "schema_version": "npi-real20-evaluation-v1",
                "status": "REAL20_COMPLETE",
                "candidate_commit": identity["candidate_commit"],
                "candidate_tree": identity["candidate_tree"],
                "source_manifest_sha256": manifest.sha256,
                "source_fingerprint_sha256": expected["source_fingerprint_sha256"],
                "runtime_identity_sha256": expected["runtime_identity_sha256"],
                "model_identity_sha256": expected["model_identity_sha256"],
                "credential_sha256": credential_sha,
                "project_state_n2b2": "LOCKED",
                "facts_schema_version": "1.2",
                "asset_count": 20,
                "unique_inference_count": len(facts_by_id),
                "exif_allowlist": list(EXIF_ALLOWLIST),
                "assets": rows,
                "review_decision": "PENDING_HUMAN_REVIEW",
                "sqlite_write": False,
                "app_write": False,
                "production_bundle": False,
            }
            evidence_bytes = _write_bound_new(output_bound, "real20_result.json", evidence)
            _finish(
                reservation,
                status="COMPLETE",
                evidence_sha=sha256(evidence_bytes),
                evidence_status="PERSISTED",
            )
            return {
                "status": "REAL20_COMPLETE",
                "credential_sha256": credential_sha,
                "output_sha256": sha256(evidence_bytes),
                "asset_count": 20,
                "unique_inference_count": len(facts_by_id),
                "facts_schema_version": "1.2",
            }
        except BaseException as exc:
            checks: list[Callable[[], None]] = []
            if backend is not None:
                checks.append(backend.unload)
            if source_admitted:
                checks.append(post_source_check)

                def root_check() -> None:
                    if not root_before.same_identity(_source_root_identity(source_resolved)):
                        raise Real20Error("REAL20_SOURCE_ROOT_CHANGED")

                checks.append(root_check)
            if revalidate is not None:
                checks.append(lambda: revalidate(ledger_bound))
            _record_failed_attempt(
                reservation, output_bound, credential_sha, primary=exc, checks=checks
            )


def default_runtime_probe(cache_root: Path, *, device: str) -> dict[str, Any]:
    from dataclasses import asdict

    from ..n2b2_synthetic.config import ROLE_MODEL_MAP, N2B2RunConfig
    from ..n2b2_synthetic.ollama_client import OllamaClient
    from ..n2b2_synthetic.torchvision_loader import load_backend, verify_cache_hit
    from ..windows_bound_promotion import bind_existing_directory
    from .runtime_probe import probe_worker

    if device != "cuda":
        raise Real20Error("REAL20_DEVICE_INVALID")
    worker = probe_worker()
    selected_device = cast(Literal["cpu", "cuda"], device)
    config = N2B2RunConfig(
        project_root=Path.cwd(),
        cache_root=cache_root,
        fixtures_dir=Path.cwd(),
        runtime_out_dir=Path.cwd(),
        backend="real",
        device=selected_device,
    )
    verify_cache_hit(cache_root, config.cache_subdirs)
    model_digests = {}
    with bind_existing_directory(cache_root, writable=False) as root:
        for role, (model_id, filename) in ROLE_MODEL_MAP.items():
            with (
                root.open_directory(config.cache_subdirs[role], writable=False) as directory,
                directory.open_file(filename) as file,
            ):
                digest, _ = file.sha256_and_size()
                if digest != config.cache_subdirs[role]:
                    raise Real20Error("REAL20_MODEL_BYTES_CHANGED")
                model_digests[model_id] = digest
    backend = load_backend("real", cache_root, config.cache_subdirs, device=device)
    try:
        client = OllamaClient()
        if client.ps_snapshot():
            raise Real20Error("REAL20_MODEL_ALREADY_RESIDENT")
        return {
            "models": model_digests,
            "worker": worker,
            "vision": backend.runtime_attestation(),
            "qwen": asdict(client.verify_identity()),
        }
    finally:
        backend.unload()


def default_backend_factory(cache_root: Path, *, device: str) -> Callable[[], VisionBackend]:
    from ..n2b2_synthetic.config import N2B2RunConfig
    from .backend import BoundTorchVisionBackend

    if device not in {"cpu", "cuda"}:
        raise Real20Error("REAL20_DEVICE_INVALID")
    selected_device = cast(Literal["cpu", "cuda"], device)
    config = N2B2RunConfig(
        project_root=Path.cwd(),
        cache_root=cache_root,
        fixtures_dir=Path.cwd(),
        runtime_out_dir=Path.cwd(),
        backend="real",
        device=selected_device,
    )
    return lambda: BoundTorchVisionBackend(cache_root, config.cache_subdirs, device=device)


def run_real20(
    *,
    project_root: Path,
    source_root: Path,
    manifest_path: Path,
    credential_path: Path,
    anchor_path: Path,
    runtime_identity_path: Path,
    model_identity_path: Path,
    ledger_root: Path,
    output_root: Path,
    cache_root: Path | None = None,
    device: str = "cuda",
) -> dict[str, Any]:
    """Public entry: bind executing code and Owner controls before source access."""
    from .admission import admit

    executing_root = Path(__file__).resolve().parents[3]
    if project_root.resolve() != executing_root:
        raise Real20Error("REAL20_EXECUTING_SOURCE_MISMATCH")
    if device != "cuda" or cache_root is None:
        raise Real20Error("REAL20_CUDA_CACHE_REQUIRED")

    # Static authority must be established before runtime/CUDA/Ollama probes,
    # backend factory construction, capability probes, and any source reads.
    admission_baseline = admit(
        project_root=executing_root,
        source_root=source_root,
        manifest_path=manifest_path,
        credential_path=credential_path,
        anchor_path=anchor_path,
        ledger_root=ledger_root,
        output_root=output_root,
        cache_root=cache_root,
        runtime_identity_path=runtime_identity_path,
        model_identity_path=model_identity_path,
    )

    def revalidate(ledger_handle: Any) -> None:
        current = admit(
            project_root=executing_root,
            source_root=source_root,
            manifest_path=manifest_path,
            credential_path=credential_path,
            anchor_path=anchor_path,
            ledger_root=ledger_root,
            bound_ledger=ledger_handle,
            output_root=output_root,
            cache_root=cache_root,
            runtime_identity_path=runtime_identity_path,
            model_identity_path=model_identity_path,
        )
        if current != admission_baseline:
            raise Real20Error("REAL20_ADMISSION_CHANGED")

    from .reasoning import interpret

    return _run_real20(
        project_root=executing_root,
        source_root=source_root,
        manifest_path=manifest_path,
        credential_path=credential_path,
        anchor_path=anchor_path,
        runtime_identity_path=runtime_identity_path,
        model_identity_path=model_identity_path,
        ledger_root=ledger_root,
        output_root=output_root,
        backend_factory=default_backend_factory(cache_root, device=device),
        runtime_probe=lambda: default_runtime_probe(cache_root, device=device),
        reasoning=lambda data, facts, runtime_identity: interpret(
            data,
            facts,
            project_root=executing_root,
            expected_identity=runtime_identity["qwen"],
        ),
        revalidate=revalidate,
    )
