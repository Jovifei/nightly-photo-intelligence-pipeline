"""Strict loader for the external N2B2 S3 synthetic fixture set."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

S3_MANIFEST_NAME = "fixture_manifest.json"
S3_MANIFEST_VERSION = "n2b2-s3-fixture-manifest-v2"
EXPECTED_CASES = (
    ("n2b2-s3-01", "single_person"),
    ("n2b2-s3-02", "multi_person_or_occluded"),
    ("n2b2-s3-03", "negative_control"),
)


@dataclass(frozen=True)
class SyntheticFixture:
    """Immutable, bytes-backed fixture metadata used by the S3 runner."""

    case_id: str
    image_bytes: bytes
    width: int
    height: int
    case_type: str = ""
    image_sha256: str = ""
    generator_version: str = "synthetic-fixture-test"
    seed: int = 0
    generation_parameters: dict[str, Any] = field(default_factory=dict)
    expected_processability: str = "processable"
    person_expectation: str = "not_declared"

    def __post_init__(self) -> None:
        if not self.case_type:
            suffix = self.case_id.rsplit("-", maxsplit=1)[-1]
            inferred = {
                "01": "single_person",
                "02": "multi_person_or_occluded",
                "03": "negative_control",
            }
            object.__setattr__(self, "case_type", inferred.get(suffix, "single_person"))
        if not self.image_sha256:
            object.__setattr__(self, "image_sha256", hashlib.sha256(self.image_bytes).hexdigest())


def _fail(message: str) -> ValueError:
    return ValueError(f"N2B2_SYNTHETIC_FIXTURE_MANIFEST_INVALID: {message}")


def _safe_external_file(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise _fail(f"path escape rejected: {name!r}")
    if relative.parts and relative.parts[0] == ".":
        raise _fail(f"hidden path component rejected: {name!r}")
    candidate = root / relative
    if candidate.exists() and candidate.is_symlink():
        raise _fail(f"symlink rejected: {name!r}")
    try:
        resolved_root = root.resolve(strict=True)
        resolved = candidate.resolve(strict=True)
        if os.path.commonpath((str(resolved_root), str(resolved))) != str(resolved_root):
            raise _fail(f"resolved path escapes manifest directory: {name!r}")
    except FileNotFoundError as exc:
        raise _fail(f"missing image: {name!r}") from exc
    if not resolved.is_file():
        raise _fail(f"image is not a regular file: {name!r}")
    return resolved


def _load_png(path: Path) -> tuple[bytes, int, int]:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise _fail(f"non-PNG image rejected: {path.name!r}")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG":
                raise _fail(f"image format is not PNG: {path.name!r}")
            width, height = image.size
    except ValueError:
        raise
    except Exception as exc:
        raise _fail(f"invalid PNG image: {path.name!r}") from exc
    return data, int(width), int(height)


def load_s3_manifest(
    manifest_dir: Path, *, project_root: Path | None = None
) -> list[SyntheticFixture]:
    """Load exactly the frozen, Git-external three-case S3 manifest."""

    root = Path(manifest_dir).resolve(strict=True)
    if not root.is_dir():
        raise _fail("manifest directory is not a directory")
    if project_root is not None:
        project = Path(project_root).resolve(strict=True)
        try:
            inside_project = os.path.commonpath((str(project), str(root))) == str(project)
        except ValueError:
            # Windows drives cannot share a common path; an external runtime on
            # another drive is therefore not inside the Git project.
            inside_project = False
        if inside_project:
            raise _fail("manifest directory must be Git-external")
    manifest_path = root / S3_MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise _fail("fixture_manifest.json is missing or is a symlink")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise _fail("fixture_manifest.json is not valid JSON") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != S3_MANIFEST_VERSION:
        raise _fail("unexpected manifest schema_version")
    entries = manifest.get("fixtures")
    if not isinstance(entries, list) or len(entries) != len(EXPECTED_CASES):
        raise _fail("manifest must contain exactly three fixtures")

    seen: set[str] = set()
    loaded: list[SyntheticFixture] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise _fail("fixture entry must be an object")
        case_id = entry.get("case_id")
        case_type = entry.get("case_type")
        if not isinstance(case_id, str) or not isinstance(case_type, str):
            raise _fail("case_id and case_type must be strings")
        if (case_id, case_type) not in EXPECTED_CASES:
            raise _fail(f"unexpected case identity: {case_id!r}/{case_type!r}")
        if case_id in seen:
            raise _fail(f"duplicate case_id: {case_id!r}")
        seen.add(case_id)
        filename = entry.get("filename")
        expected_sha = entry.get("image_sha256")
        width_expected = entry.get("width")
        height_expected = entry.get("height")
        generator_version = entry.get("generator_version")
        seed = entry.get("seed")
        generation_parameters = entry.get("generation_parameters")
        expected_processability = entry.get("expected_processability")
        person_expectation = entry.get("person_expectation")
        if not isinstance(filename, str) or not filename.lower().endswith(".png"):
            raise _fail(f"PNG filename required for {case_id!r}")
        if not isinstance(expected_sha, str) or len(expected_sha) != 64:
            raise _fail(f"invalid image_sha256 for {case_id!r}")
        if not isinstance(width_expected, int) or not isinstance(height_expected, int):
            raise _fail(f"invalid dimensions for {case_id!r}")
        if not isinstance(generator_version, str) or not generator_version:
            raise _fail(f"generator_version required for {case_id!r}")
        if not isinstance(seed, int):
            raise _fail(f"integer seed required for {case_id!r}")
        if not isinstance(generation_parameters, dict):
            raise _fail(f"generation_parameters required for {case_id!r}")
        if expected_processability != "processable":
            raise _fail(f"fixture must be processable: {case_id!r}")
        if not isinstance(person_expectation, str) or not person_expectation:
            raise _fail(f"person_expectation required for {case_id!r}")
        image_path = _safe_external_file(root, filename)
        data, width, height = _load_png(image_path)
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != expected_sha:
            raise _fail(f"SHA-256 mismatch for {case_id!r}")
        if (width, height) != (width_expected, height_expected):
            raise _fail(f"dimension mismatch for {case_id!r}")
        loaded.append(
            SyntheticFixture(
                case_id=case_id,
                case_type=case_type,
                image_bytes=data,
                image_sha256=actual_sha,
                width=width,
                height=height,
                generator_version=generator_version,
                seed=seed,
                generation_parameters=dict(generation_parameters),
                expected_processability=expected_processability,
                person_expectation=person_expectation,
            )
        )
    if {item.case_id for item in loaded} != {case_id for case_id, _ in EXPECTED_CASES}:
        raise _fail("manifest case set is incomplete")
    return sorted(loaded, key=lambda item: item.case_id)
