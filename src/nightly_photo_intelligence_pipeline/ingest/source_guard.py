"""Read-only source protection guard.

Four layers (docs/13_read_only_source_protection.md):
  1. permission  - caller ensures OS-level read-only (out of scope for code)
  2. path        - source/runtime overlap, symlink/junction escape, containment
  3. API         - binary read-only open, no write/move/delete/chmod API exists
  4. evidence    - pre/post size, mtime_ns, sha256 fingerprint

Windows nuance: ``Path.is_symlink()`` returns False for NTFS junctions, so
reparse-point detection MUST also check ``st_file_attributes & 0x400``.
"""

from __future__ import annotations

import os
import sys
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import IO

from ..domain.errors import (
    NPI_UNSUPPORTED_MEDIA,
    NpiError,
    SourceChangedDuringReadError,
    SourceRuntimeOverlapError,
    SourceSymlinkEscapeError,
    UnsupportedMediaError,
)

# FILE_ATTRIBUTE_REPARSE_POINT (Windows).
_REPARSE_POINT_ATTR = 0x400


@dataclass(frozen=True)
class FileIdentity:
    """File identity captured from stat, used for TOCTOU comparison."""

    st_dev: int
    st_ino: int
    st_size: int
    st_mtime_ns: int

    @classmethod
    def from_stat(cls, st: os.stat_result) -> FileIdentity:
        return cls(st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)

    def same_identity(self, other: FileIdentity) -> bool:
        """True if dev/ino/size/mtime all match (catches swap and content change)."""
        return (
            self.st_dev == other.st_dev
            and self.st_ino == other.st_ino
            and self.st_size == other.st_size
            and self.st_mtime_ns == other.st_mtime_ns
        )

    def same_size_mtime(self, other: FileIdentity) -> bool:
        """True if size and mtime match (used for post-read integrity)."""
        return self.st_size == other.st_size and self.st_mtime_ns == other.st_mtime_ns


@dataclass(frozen=True)
class Fingerprint:
    """Integrity evidence recorded before and after reading a source file."""

    size_bytes: int
    mtime_ns: int
    sha256: str

    def matches_size_mtime(self, other: Fingerprint) -> bool:
        return self.size_bytes == other.size_bytes and self.mtime_ns == other.mtime_ns


def is_reparse_point(path: Path) -> bool:
    """True if *path* is a symlink or any reparse point (incl. NTFS junctions)."""
    try:
        if path.is_symlink():
            return True
    except OSError:
        # is_symlink may raise on broken links; treat as suspicious.
        return True
    if sys.platform == "win32":
        try:
            attr = getattr(path.lstat(), "st_file_attributes", 0) or 0
        except OSError:
            return True
        return bool(attr & _REPARSE_POINT_ATTR)
    return False


def strict_realpath(path: Path) -> Path:
    """Resolve symlinks/junctions and normalize the path.

    ``os.path.realpath`` follows symlinks and NTFS junctions to their target on
    Windows, which is what the containment check needs.
    """
    return Path(os.path.realpath(str(path)))


def _is_descendant(child: Path, root: Path) -> bool:
    """True if *child* is *root* or lives under it (both already resolved)."""
    try:
        child.relative_to(root)
        return True
    except ValueError:
        return False


def validate_roots(
    source_root: Path,
    runtime_root: Path,
    *,
    allow_source_symlink: bool = False,
    allow_file_symlink: bool = False,  # noqa: ARG001 - kept for API symmetry
) -> tuple[Path, Path]:
    """Validate source/runtime separation. Returns resolved (source, runtime).

    Raises SourceSymlinkEscapeError if the source root itself is a reparse
    point, or SourceRuntimeOverlapError if the roots are equal or nested.
    """
    src = Path(source_root)
    if not allow_source_symlink and is_reparse_point(src):
        raise SourceSymlinkEscapeError("source root is a symlink or reparse point")
    if not src.is_dir():
        raise SourceRuntimeOverlapError("source root is not a directory")

    rt = Path(runtime_root)
    sr = strict_realpath(src)
    rr = strict_realpath(rt)
    if sr == rr:
        raise SourceRuntimeOverlapError("source root and runtime root are identical")
    if _is_descendant(sr, rr) or _is_descendant(rr, sr):
        raise SourceRuntimeOverlapError("source root and runtime root overlap (nested)")
    return sr, rr


def sanitize_source_name(name: str) -> str:
    """Strip path separators so a source filename is safe to store/display."""
    cleaned = name.replace("\\", "/").split("/")[-1]
    cleaned = cleaned.strip()
    if not cleaned:
        raise NpiError("sanitized source name is empty", error_code=NPI_UNSUPPORTED_MEDIA)
    return cleaned


class SourceHandle(AbstractContextManager["SourceHandle"]):
    """A read-only file handle with pre/post integrity evidence.

    The file is opened exactly once in binary read-only mode. Pre-stat is taken
    on the path before open; an fstat on the descriptor is compared to it to
    detect a swap between stat and open (TOCTOU). On close, a second fstat is
    compared to detect changes during the read.
    """

    def __init__(
        self,
        candidate: Path,
        source_root: Path,
        fd: IO[bytes],
        pre_path_identity: FileIdentity,
    ) -> None:
        self._candidate = candidate
        self._source_root = source_root
        self._fd = fd
        self._pre_path = pre_path_identity
        self._fd_identity: FileIdentity | None = None
        self._closed = False

    @property
    def candidate(self) -> Path:
        return self._candidate

    def read(self, size: int = -1) -> bytes:
        return self._fd.read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return self._fd.seek(offset, whence)

    def fileno(self) -> int:
        return self._fd.fileno()

    def capture_fd_identity(self) -> FileIdentity:
        """Snapshot the descriptor's identity right after open (TOCTOU check)."""
        if self._fd_identity is None:
            self._fd_identity = FileIdentity.from_stat(os.fstat(self.fileno()))
            if not self._fd_identity.same_identity(self._pre_path):
                self._close_unsafe()
                raise SourceChangedDuringReadError(
                    "source file identity changed between stat and open",
                )
        return self._fd_identity

    def pre_fingerprint(self, sha256: str | None = None) -> Fingerprint:
        ident = self.capture_fd_identity()
        return Fingerprint(
            size_bytes=ident.st_size,
            mtime_ns=ident.st_mtime_ns,
            sha256=sha256 or "",
        )

    def post_fingerprint(self, sha256: str | None = None) -> Fingerprint:
        post = FileIdentity.from_stat(os.fstat(self.fileno()))
        fd_ident = self._fd_identity or self.capture_fd_identity()
        if not post.same_size_mtime(fd_ident):
            self._close_unsafe()
            raise SourceChangedDuringReadError(
                "source file size or mtime changed during read",
            )
        return Fingerprint(
            size_bytes=post.st_size,
            mtime_ns=post.st_mtime_ns,
            sha256=sha256 or "",
        )

    def _close_unsafe(self) -> None:
        if not self._closed:
            self._closed = True
            with suppress(OSError):
                self._fd.close()

    def close(self) -> None:
        if self._closed:
            return
        # Final integrity check before closing.
        try:
            self.post_fingerprint()
        finally:
            self._close_unsafe()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()


def open_source_file(
    candidate: Path,
    source_root: Path,
    *,
    allowed_extensions: tuple[str, ...] = (),
    allow_file_symlink: bool = False,
    sniff_media_type: bool = False,  # noqa: ARG001 - reserved for N1
) -> SourceHandle:
    """Validate and open a source file in binary read-only mode.

    Rejects: disallowed extension, symlink/junction/reparse-point candidates,
    paths whose realpath escapes the source root, and files whose identity
    changes between stat and open.
    """
    cand = Path(candidate)
    ext = cand.suffix.lower()
    if allowed_extensions and ext not in allowed_extensions:
        raise UnsupportedMediaError("source extension is not allowed")
    if not allow_file_symlink and is_reparse_point(cand):
        raise SourceSymlinkEscapeError("source entry is a symlink or reparse point")
    sr = strict_realpath(Path(source_root))
    cr = strict_realpath(cand)
    if not _is_descendant(cr, sr):
        raise SourceSymlinkEscapeError(
            "candidate path escapes the source root after resolution",
        )
    # Pre-stat on the path (follows to the real file; symlinks already rejected).
    try:
        pre = FileIdentity.from_stat(os.stat(cand))
        fd = open(cand, "rb")  # noqa: SIM115 - binary read-only; closed via handle
    except OSError:
        raise SourceSymlinkEscapeError("source entry metadata or open failed") from None
    handle = SourceHandle(cand, sr, fd, pre)
    handle.capture_fd_identity()  # raises on TOCTOU swap
    return handle
