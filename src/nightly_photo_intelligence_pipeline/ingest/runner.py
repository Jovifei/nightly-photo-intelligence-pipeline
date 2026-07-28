"""Dry-run ingest runner.

Read-only: enumerates source files, fingerprints them (streaming SHA-256 +
versioned perceptual hash), groups exact duplicates, and returns a structured,
deterministic summary. Never writes to the database or to runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..domain.authorization import AuthorizationSnapshot
from ..domain.errors import NPI_INTERNAL_ERROR, GateNotAuthorizedError, NpiError
from ..domain.models import PipelineConfig
from ..persistence.sqlite import StateStore
from ..redaction import REDACT_RUNTIME_ROOT, redact_path
from .exif import ExifSnapshot, read_exif
from .g1_contract import G1ExecutionPermit, path_fingerprint
from .hashing import stream_sha256_from_handle
from .manifest import G1FrozenManifest, Manifest, require_g1_manifest_member
from .perceptual_hash import (
    HASH_SIZE_BITS,
    PerceptualHashResult,
    analyze_image_from_handle,
    hamming_distance,
)
from .source_guard import open_source_file, validate_roots

_EXT_TO_MEDIA = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".heic": "image/heic",
}


@dataclass(frozen=True)
class ScannedFile:
    sanitized_name: str
    source_sha256: str
    perceptual_hash: str
    perceptual_hash_algorithm: str
    perceptual_hash_impl_version: str
    media_type: str
    width: int
    height: int
    size_bytes: int
    mtime_ns: int


@dataclass(frozen=True)
class IngestDryRunResult:
    source_root_redacted: str
    runtime_root_redacted: str
    files_scanned: int
    unique_assets: int
    duplicate_group_count: int
    files: list[ScannedFile] = field(default_factory=list)
    duplicate_groups: list[list[str]] = field(default_factory=list)
    database_mutated: bool = False


def _enumerate_source_files(source_root: Path, allowed_extensions: tuple[str, ...]) -> list[Path]:
    """Return sorted allowed files under *source_root* (non-recursive top level + nested)."""
    exts = {e.lower() for e in allowed_extensions}
    found: list[Path] = []
    for p in sorted(source_root.rglob("*")):
        if p.is_file() and p.suffix.lower() in exts:
            found.append(p)
    return found


def run_dry_run_ingest(
    source_root: Path,
    runtime_root: Path,
    config: PipelineConfig,
    *,
    auth: AuthorizationSnapshot,
    source_root_for_redaction: Path | None = None,
) -> IngestDryRunResult:
    """Run a read-only dry-run ingest over *source_root*.

    Validates source/runtime separation, fingerprints every allowed file, groups
    exact duplicates by SHA-256, and returns a deterministic summary. The
    database is never opened or written.
    """
    auth.require_source_content_read_authorized()
    # Re-validate roots (the CLI also validates, but this keeps the runner safe
    # to call directly from tests).
    validate_roots(source_root, runtime_root)

    redact_src = source_root_for_redaction or source_root
    files = _enumerate_source_files(source_root, config.allowed_extensions)

    scanned: list[ScannedFile] = []
    for index, path in enumerate(files, start=1):
        asset_ref = f"scan-asset-{index:04d}"
        with open_source_file(
            path, source_root, allowed_extensions=config.allowed_extensions
        ) as handle:
            sha = stream_sha256_from_handle(handle, chunk_bytes=config.ingest.hash_chunk_bytes)
            handle.seek(0)
            facts = analyze_image_from_handle(handle)
            pre = handle.pre_fingerprint(sha)
        scanned.append(
            ScannedFile(
                sanitized_name=asset_ref,
                source_sha256=sha,
                perceptual_hash=facts.perceptual_hash.value,
                perceptual_hash_algorithm=facts.perceptual_hash.algorithm,
                perceptual_hash_impl_version=facts.perceptual_hash.implementation_version,
                media_type=_EXT_TO_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
                width=facts.width,
                height=facts.height,
                size_bytes=pre.size_bytes,
                mtime_ns=pre.mtime_ns,
            )
        )

    # Deterministic: sort by sanitized name (already sorted by path, but be explicit).
    scanned.sort(key=lambda f: f.sanitized_name)

    # Group exact duplicates by source_sha256, preserving name-sorted order.
    by_sha: dict[str, list[str]] = {}
    for f in scanned:
        by_sha.setdefault(f.source_sha256, []).append(f.sanitized_name)
    duplicate_groups = [sorted(names) for names in by_sha.values() if len(names) > 1]
    duplicate_groups.sort()

    return IngestDryRunResult(
        source_root_redacted=redact_path(source_root, source_root=redact_src),
        runtime_root_redacted=REDACT_RUNTIME_ROOT,
        files_scanned=len(scanned),
        unique_assets=len(by_sha),
        duplicate_group_count=len(duplicate_groups),
        files=scanned,
        duplicate_groups=duplicate_groups,
        database_mutated=False,
    )


def format_dry_run_text(result: IngestDryRunResult) -> str:
    """Render the dry-run result as redacted, deterministic text."""
    lines = [
        "NPI dry-run ingest summary",
        "=" * 40,
        f"source: {result.source_root_redacted}",
        f"runtime: {result.runtime_root_redacted}",
        f"files_scanned: {result.files_scanned}",
        f"unique_assets: {result.unique_assets}",
        f"duplicate_groups: {result.duplicate_group_count}",
        f"database_mutated: {result.database_mutated}",
        "",
        "files (sorted, redacted):",
    ]
    for f in result.files:
        lines.append(
            f"  - {f.sanitized_name}  sha={f.source_sha256[:12]}...  "
            f"phash={f.perceptual_hash} ({f.perceptual_hash_algorithm}/"
            f"{f.perceptual_hash_impl_version})  {f.media_type}  "
            f"{f.width}x{f.height}  size={f.size_bytes}"
        )
    if result.duplicate_groups:
        lines.append("")
        lines.append("duplicate groups (exact SHA-256 match):")
        for i, group in enumerate(result.duplicate_groups):
            lines.append(f"  group {i + 1} ({len(group)} files): {', '.join(group)}")
    lines.append("")
    lines.append("no asset rows, stage runs, or outputs were written (dry-run)")
    return "\n".join(lines)


# ---- N1: real (non-dry-run) ingest ---------------------------------------


@dataclass(frozen=True)
class IngestedAsset:
    sanitized_name: str
    source_sha256: str
    asset_id: str
    created: bool
    duplicate: bool
    perceptual_hash: str
    perceptual_hash_algorithm: str
    media_type: str
    width: int
    height: int
    size_bytes: int


@dataclass(frozen=True)
class RealIngestResult:
    source_root_redacted: str
    runtime_root_redacted: str
    manifest_fixture_set: str
    files_scanned: int
    assets_created: int
    duplicates_seen: int
    assets: list[IngestedAsset] = field(default_factory=list)
    database_mutated: bool = True


@dataclass(frozen=True)
class G1IngestedAsset:
    asset_ref: str
    source_sha256_before: str
    source_sha256_after: str
    asset_id: str
    created: bool
    duplicate: bool
    perceptual_hash: str
    perceptual_hash_algorithm: str
    media_type: str
    width: int
    height: int
    size_bytes: int
    exif: ExifSnapshot

    @property
    def integrity_unchanged(self) -> bool:
        return self.source_sha256_before == self.source_sha256_after


@dataclass(frozen=True)
class NearDuplicateCandidate:
    asset_ref: str
    candidate_asset_ref: str
    hamming_distance: int
    algorithm_id: str


@dataclass(frozen=True)
class G1CalibrationResult:
    source_root_redacted: str
    runtime_root_redacted: str
    frozen_manifest_sha256: str
    files_scanned: int
    assets_created: int
    duplicates_seen: int
    exact_duplicate_groups: list[list[str]] = field(default_factory=list)
    near_duplicate_candidates: list[NearDuplicateCandidate] = field(default_factory=list)
    assets: list[G1IngestedAsset] = field(default_factory=list)
    database_mutated: bool = True


def run_real_ingest(
    source_root: Path,
    runtime_root: Path,
    config: PipelineConfig,
    auth: AuthorizationSnapshot,
    store: StateStore,
    manifest: Manifest,
    *,
    source_root_for_redaction: Path | None = None,
) -> RealIngestResult:
    """Run a real (non-dry-run, mutating) ingest over *source_root*.

    N1/G0 rules:
      * phase N1 + data gate G0 must be authorized;
      * only files listed in the G0 manifest may be ingested (4th asset rejected);
      * the asset cap (max_assets) bounds unique assets;
      * exact duplicates (same SHA) are merged into one asset with multiple
        sources (idempotent: re-ingest creates no new asset row);
      * the DB stores only redacted source paths, never absolute photo paths.
    """
    auth.require_ingest_authorized(dry_run=False)
    auth.require_source_content_read_authorized()
    auth.require_sqlite_ingest_write_authorized()
    validate_roots(source_root, runtime_root)
    redact_src = source_root_for_redaction or source_root
    allowed = manifest.allowed_names
    asset_refs = {
        entry.name: f"g0-asset-{index:02d}" for index, entry in enumerate(manifest.files, 1)
    }
    files = _enumerate_source_files(source_root, config.allowed_extensions)

    ingested: list[IngestedAsset] = []
    created = 0
    dups = 0
    for path in files:
        if path.name not in allowed:
            raise GateNotAuthorizedError("asset is not authorized by the G0 manifest")
        asset_ref = asset_refs[path.name]
        with open_source_file(
            path, source_root, allowed_extensions=config.allowed_extensions
        ) as handle:
            sha = stream_sha256_from_handle(handle, chunk_bytes=config.ingest.hash_chunk_bytes)
            handle.seek(0)
            facts = analyze_image_from_handle(handle)
            pre = handle.pre_fingerprint(sha)
        existing = store.get_asset_by_sha(sha)
        if existing is None:
            # Cap check only when a NEW unique asset would be created.
            auth.require_asset_within_cap(store.asset_count(), added=1)
        res = store.ingest_asset(
            source_sha256=sha,
            sanitized_source_name=asset_ref,
            local_path_protected=f"<SOURCE_ROOT>/{asset_ref}",
            observed_size_bytes=pre.size_bytes,
            observed_mtime_ns=pre.mtime_ns,
            perceptual_hash=facts.perceptual_hash.value,
            perceptual_hash_algorithm=facts.perceptual_hash.algorithm_id,
            media_type=_EXT_TO_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
            width=facts.width,
            height=facts.height,
        )
        if res.created:
            created += 1
        if res.duplicate:
            dups += 1
        ingested.append(
            IngestedAsset(
                sanitized_name=asset_ref,
                source_sha256=sha,
                asset_id=res.asset_id,
                created=res.created,
                duplicate=res.duplicate,
                perceptual_hash=facts.perceptual_hash.value,
                perceptual_hash_algorithm=facts.perceptual_hash.algorithm_id,
                media_type=_EXT_TO_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
                width=facts.width,
                height=facts.height,
                size_bytes=pre.size_bytes,
            )
        )
    ingested.sort(key=lambda a: a.sanitized_name)
    return RealIngestResult(
        source_root_redacted=redact_path(source_root, source_root=redact_src),
        runtime_root_redacted=REDACT_RUNTIME_ROOT,
        manifest_fixture_set=manifest.fixture_set,
        files_scanned=len(ingested),
        assets_created=created,
        duplicates_seen=dups,
        assets=ingested,
        database_mutated=True,
    )


def _require_g1_authorized(auth: AuthorizationSnapshot) -> None:
    auth.require_ingest_authorized(dry_run=False)
    auth.require_source_content_read_authorized()
    auth.require_sqlite_ingest_write_authorized()
    if auth.data_gate_id != "G1_CALIBRATION_20":
        raise GateNotAuthorizedError("G1 ingest requires data gate G1_CALIBRATION_20")
    if auth.real_photo_access != "AUTHORIZED":
        raise GateNotAuthorizedError("G1 ingest requires real_photo_access AUTHORIZED")
    if auth.exif_real_data_read not in {"AUTHORIZED", "AUTHORIZED_NON_SENSITIVE_ONLY"}:
        raise GateNotAuthorizedError("G1 ingest requires non-sensitive EXIF authorization")
    if auth.max_assets != 20:
        raise GateNotAuthorizedError("G1 ingest requires max_assets=20")


def _append_near_duplicate_candidates(
    store: StateStore,
    assets: list[G1IngestedAsset],
    phashes: dict[str, PerceptualHashResult],
) -> list[NearDuplicateCandidate]:
    out: list[NearDuplicateCandidate] = []
    for i, left in enumerate(assets):
        for right in assets[i + 1 :]:
            distance = hamming_distance(phashes[left.asset_ref], phashes[right.asset_ref])
            if distance > 5:
                continue
            if left.asset_id == right.asset_id:
                continue
            store.insert_duplicate_candidate(
                asset_id=left.asset_id,
                candidate_asset_id=right.asset_id,
                distance=float(distance),
                algorithm_id=phashes[left.asset_ref].algorithm_id,
                algorithm_version=phashes[left.asset_ref].algorithm_version,
                hash_size=HASH_SIZE_BITS,
            )
            out.append(
                NearDuplicateCandidate(
                    asset_ref=left.asset_ref,
                    candidate_asset_ref=right.asset_ref,
                    hamming_distance=distance,
                    algorithm_id=phashes[left.asset_ref].algorithm_id,
                )
            )
    return out


def run_g1_calibration_ingest(
    source_root: Path,
    runtime_root: Path,
    config: PipelineConfig,
    auth: AuthorizationSnapshot,
    store: StateStore,
    frozen_manifest: G1FrozenManifest,
    *,
    permit: G1ExecutionPermit,
    source_root_for_redaction: Path | None = None,
) -> G1CalibrationResult:
    """Run G1 over exactly the owner-frozen 20-entry manifest.

    No directory enumeration is performed. Each manifest entry is resolved under
    ``source_root`` and opened once via ``source_guard``. Reports and DB rows use
    opaque asset refs, not real filenames or absolute paths.
    """
    _require_g1_authorized(auth)
    permit.require_valid(frozen_manifest)
    if permit.source_root_fingerprint_sha256 != path_fingerprint(source_root):
        raise GateNotAuthorizedError("G1 execution permit source mismatch")
    if permit.runtime_child_fingerprint_sha256 != path_fingerprint(runtime_root):
        raise GateNotAuthorizedError("G1 execution permit runtime mismatch")
    if frozen_manifest.count != 20:
        raise GateNotAuthorizedError("G1 frozen manifest must contain exactly 20 assets")
    validate_roots(source_root, runtime_root)
    redact_src = source_root_for_redaction or source_root

    ingested: list[G1IngestedAsset] = []
    phashes: dict[str, PerceptualHashResult] = {}
    created = 0
    dups = 0
    for entry in frozen_manifest.entries:
        require_g1_manifest_member(entry.relative_path, frozen_manifest)
        path = source_root / entry.relative_path
        with open_source_file(
            path, source_root, allowed_extensions=config.allowed_extensions
        ) as handle:
            sha_before = stream_sha256_from_handle(
                handle, chunk_bytes=config.ingest.hash_chunk_bytes
            )
            handle.seek(0)
            facts = analyze_image_from_handle(handle)
            phashes[entry.asset_ref] = facts.perceptual_hash
            handle.seek(0)
            exif = read_exif(handle)
            pre = handle.pre_fingerprint(sha_before)
            handle.seek(0)
            sha_after = stream_sha256_from_handle(
                handle, chunk_bytes=config.ingest.hash_chunk_bytes
            )
            handle.post_fingerprint(sha_after)
        if sha_before != sha_after:
            raise NpiError(
                "source SHA-256 changed during G1 ingest",
                error_code=NPI_INTERNAL_ERROR,
            )
        existing = store.get_asset_by_sha(sha_before)
        if existing is None:
            auth.require_asset_within_cap(store.asset_count(), added=1)
        res = store.ingest_asset(
            source_sha256=sha_before,
            sanitized_source_name=entry.asset_ref,
            local_path_protected=f"<SOURCE_ROOT>/{entry.asset_ref}",
            observed_size_bytes=pre.size_bytes,
            observed_mtime_ns=pre.mtime_ns,
            perceptual_hash=facts.perceptual_hash.value,
            perceptual_hash_algorithm=facts.perceptual_hash.algorithm_id,
            media_type=_EXT_TO_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
            width=facts.width,
            height=facts.height,
        )
        if res.created:
            created += 1
        if res.duplicate:
            dups += 1
        ingested.append(
            G1IngestedAsset(
                asset_ref=entry.asset_ref,
                source_sha256_before=sha_before,
                source_sha256_after=sha_after,
                asset_id=res.asset_id,
                created=res.created,
                duplicate=res.duplicate,
                perceptual_hash=facts.perceptual_hash.value,
                perceptual_hash_algorithm=facts.perceptual_hash.algorithm_id,
                media_type=_EXT_TO_MEDIA.get(path.suffix.lower(), "application/octet-stream"),
                width=facts.width,
                height=facts.height,
                size_bytes=pre.size_bytes,
                exif=exif,
            )
        )

    by_sha: dict[str, list[str]] = {}
    for asset in ingested:
        by_sha.setdefault(asset.source_sha256_before, []).append(asset.asset_ref)
    exact_groups = [refs for refs in by_sha.values() if len(refs) > 1]
    exact_groups.sort()
    near = _append_near_duplicate_candidates(store, ingested, phashes)
    return G1CalibrationResult(
        source_root_redacted=redact_path(source_root, source_root=redact_src),
        runtime_root_redacted=REDACT_RUNTIME_ROOT,
        frozen_manifest_sha256=frozen_manifest.sha256,
        files_scanned=len(ingested),
        assets_created=created,
        duplicates_seen=dups,
        exact_duplicate_groups=exact_groups,
        near_duplicate_candidates=near,
        assets=ingested,
        database_mutated=True,
    )


def format_real_ingest_text(result: RealIngestResult) -> str:
    """Render the real ingest result as redacted, deterministic text."""
    lines = [
        "NPI real ingest summary",
        "=" * 40,
        f"source: {result.source_root_redacted}",
        f"runtime: {result.runtime_root_redacted}",
        f"manifest: {result.manifest_fixture_set}",
        f"files_scanned: {result.files_scanned}",
        f"assets_created: {result.assets_created}",
        f"duplicates_seen: {result.duplicates_seen}",
        f"database_mutated: {result.database_mutated}",
        "",
        "assets (sorted, redacted):",
    ]
    for a in result.assets:
        kind = "created" if a.created else "duplicate"
        lines.append(
            f"  - {a.sanitized_name}  sha={a.source_sha256[:12]}...  "
            f"asset={a.asset_id[:16]}  {kind}  phash={a.perceptual_hash} "
            f"({a.perceptual_hash_algorithm})  {a.media_type}  "
            f"{a.width}x{a.height}  size={a.size_bytes}"
        )
    return "\n".join(lines)
