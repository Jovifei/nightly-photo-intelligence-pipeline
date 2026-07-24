"""G0 fixture manifest loader and authorization membership checks.

The data gate (G0) authorizes a specific set of assets via a manifest. Real
ingest may only process files listed in the active manifest; a file not in the
manifest must be rejected by the gate (this is the "4th asset rejected" rule).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Self

from ..domain.errors import NPI_GATE_NOT_AUTHORIZED, GateNotAuthorizedError
from ..json_strict import load_json_strict


@dataclass(frozen=True)
class ManifestEntry:
    name: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class Manifest:
    fixture_set: str
    files: tuple[ManifestEntry, ...]

    @property
    def allowed_names(self) -> frozenset[str]:
        return frozenset(f.name for f in self.files)

    def entry_for(self, name: str) -> ManifestEntry | None:
        for f in self.files:
            if f.name == name:
                return f
        return None


def load_manifest(path: Path | str) -> Manifest:
    """Load a fixture/data-gate manifest from JSON."""
    data = load_json_strict(path)
    files = tuple(
        ManifestEntry(name=f["name"], sha256=f["sha256"], size_bytes=f["size_bytes"])
        for f in data.get("files", [])
    )
    return Manifest(fixture_set=data.get("fixture_set", ""), files=files)


@dataclass(frozen=True)
class G1FrozenEntry:
    """One owner-frozen G1 asset entry.

    ``relative_path`` is local-sensitive configuration and must not be written
    to Git reports. ``asset_ref`` is the opaque identifier safe for DB/report
    surfaces.
    """

    index: int
    relative_path: Path
    asset_ref: str


@dataclass(frozen=True)
class G1FrozenManifest:
    path: Path
    sha256: str
    entries: tuple[G1FrozenEntry, ...]

    @classmethod
    def load(
        cls,
        path: Path | str,
        *,
        expected_sha256: str | None = None,
        expected_count: int = 20,
    ) -> Self:
        manifest_path = Path(path)
        try:
            data = manifest_path.read_bytes()
        except OSError:
            raise GateNotAuthorizedError("G1 frozen manifest is unavailable") from None
        actual_sha = hashlib.sha256(data).hexdigest()
        if expected_sha256 is not None and actual_sha.lower() != expected_sha256.lower():
            raise GateNotAuthorizedError(
                "G1 frozen manifest SHA-256 does not match approval",
            )
        try:
            decoded = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise GateNotAuthorizedError("G1 frozen manifest encoding is invalid") from None
        lines = [line.strip() for line in decoded.splitlines() if line.strip()]
        if len(lines) != expected_count:
            raise GateNotAuthorizedError(
                f"G1 frozen manifest must contain exactly {expected_count} entries; "
                f"found {len(lines)}",
            )
        comparison_keys = [line.replace("\\", "/").casefold() for line in lines]
        if len(set(comparison_keys)) != len(lines):
            raise GateNotAuthorizedError("G1 frozen manifest contains duplicate entries")

        entries: list[G1FrozenEntry] = []
        for i, raw in enumerate(lines, start=1):
            rel = Path(raw)
            windows_rel = PureWindowsPath(raw)
            if (
                rel.is_absolute()
                or windows_rel.drive
                or windows_rel.root
                or ".." in rel.parts
                or ".." in windows_rel.parts
            ):
                raise GateNotAuthorizedError(
                    "G1 frozen manifest entry must be a source-relative path",
                )
            entries.append(
                G1FrozenEntry(
                    index=i,
                    relative_path=rel,
                    asset_ref=f"g1-asset-{i:02d}",
                )
            )
        return cls(path=manifest_path, sha256=actual_sha, entries=tuple(entries))

    @property
    def count(self) -> int:
        return len(self.entries)

    def contains(self, relative_path: Path | str) -> bool:
        key = Path(relative_path).as_posix().casefold()
        return any(entry.relative_path.as_posix().casefold() == key for entry in self.entries)


def require_g1_manifest_member(relative_path: Path | str, manifest: G1FrozenManifest) -> None:
    """Reject an asset not explicitly listed in the frozen G1 manifest."""
    rel = Path(relative_path)
    if not manifest.contains(rel):
        raise GateNotAuthorizedError(
            "asset is not authorized by the frozen G1 manifest",
            error_code=NPI_GATE_NOT_AUTHORIZED,
        )
