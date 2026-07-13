"""Dry-run ingest runner.

Read-only: enumerates source files, fingerprints them (streaming SHA-256 +
versioned perceptual hash), groups exact duplicates, and returns a structured,
deterministic summary. Never writes to the database or to runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..domain.models import PipelineConfig
from ..redaction import REDACT_RUNTIME_ROOT, redact_path
from .hashing import stream_sha256_from_handle
from .perceptual_hash import analyze_image_from_handle
from .source_guard import open_source_file

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
    source_root_for_redaction: Path | None = None,
) -> IngestDryRunResult:
    """Run a read-only dry-run ingest over *source_root*.

    Validates source/runtime separation, fingerprints every allowed file, groups
    exact duplicates by SHA-256, and returns a deterministic summary. The
    database is never opened or written.
    """
    from .source_guard import validate_roots

    # Re-validate roots (the CLI also validates, but this keeps the runner safe
    # to call directly from tests).
    validate_roots(source_root, runtime_root)

    redact_src = source_root_for_redaction or source_root
    files = _enumerate_source_files(source_root, config.allowed_extensions)

    scanned: list[ScannedFile] = []
    for path in files:
        with open_source_file(
            path, source_root, allowed_extensions=config.allowed_extensions
        ) as handle:
            sha = stream_sha256_from_handle(handle, chunk_bytes=config.ingest.hash_chunk_bytes)
            handle.seek(0)
            facts = analyze_image_from_handle(handle)
            pre = handle.pre_fingerprint(sha)
        scanned.append(
            ScannedFile(
                sanitized_name=path.name,
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
