"""G0 fixture manifest loader and authorization membership checks.

The data gate (G0) authorizes a specific set of assets via a manifest. Real
ingest may only process files listed in the active manifest; a file not in the
manifest must be rejected by the gate (this is the "4th asset rejected" rule).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


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
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    files = tuple(
        ManifestEntry(name=f["name"], sha256=f["sha256"], size_bytes=f["size_bytes"])
        for f in data.get("files", [])
    )
    return Manifest(fixture_set=data.get("fixture_set", ""), files=files)
