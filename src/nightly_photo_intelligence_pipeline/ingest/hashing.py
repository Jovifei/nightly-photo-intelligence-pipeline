"""Streaming SHA-256 over exact source bytes.

The hash is computed in fixed-size chunks so that large files never need to be
fully loaded into memory. N0 fixtures are tiny, but the interface is streaming
so N1 can reuse it on real photos without change.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class SupportsReadBytes(Protocol):
    """Minimal read protocol satisfied by binary file handles and SourceHandle."""

    def read(self, size: int = -1) -> bytes: ...


_DEFAULT_CHUNK = 1 << 20  # 1 MiB, matches config/execution_defaults.yaml.


def stream_sha256_from_handle(handle: SupportsReadBytes, chunk_bytes: int = _DEFAULT_CHUNK) -> str:
    """Stream SHA-256 from an already-open binary handle."""
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(chunk_bytes), b""):
        digest.update(chunk)
    return digest.hexdigest()


def stream_sha256(path: Path, chunk_bytes: int = _DEFAULT_CHUNK) -> str:
    """Open *path* binary-read-only and stream SHA-256 of its exact bytes."""
    with Path(path).open("rb") as handle:
        return stream_sha256_from_handle(handle, chunk_bytes=chunk_bytes)
