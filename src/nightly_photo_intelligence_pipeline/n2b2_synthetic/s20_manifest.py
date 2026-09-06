"""Strict loader and frozen matrix for the N2B2 S20 synthetic set."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .fixture_manifest import SyntheticFixture

S20_MANIFEST_NAME = "fixture_manifest.json"
S20_MANIFEST_VERSION = "n2b2-s20-fixture-manifest-v1"
S20_MANIFEST_V2_VERSION = "n2b2-s20-fixture-manifest-v2"
S20_GENERATOR_VERSION = "npi-comfyui-0.19.5-sdxl-base-1.0-s20-v1"
S20_CASE17_GENERATOR_VERSION = "npi-comfyui-0.19.5-sdxl-base-1.0-s20-case17-v2"
S20_CASE17_REMEDIATION_SEEDS = (2026082117, 2026082118, 2026082119, 2026082120)
S20_V1_MANIFEST_SHA256 = "34d1ef3146b05982254d0613da5a5e6f0ca323d6f8f727fb1ae7cb17a30e64c6"
S20_CASE17_REMEDIATION_RECORD_NAME = "case17_remediation_record.json"


@dataclass(frozen=True)
class S20CaseSpec:
    case_id: str
    case_type: str
    seed: int
    width: int
    height: int
    expected_person_count: int
    acceptance_profile: str
    tags: tuple[str, ...]


S20_CASE_MATRIX: tuple[S20CaseSpec, ...] = (
    S20CaseSpec(
        "n2b2-s20-01",
        "single_person",
        2026082001,
        832,
        1216,
        1,
        "strict",
        ("single_person_full_body",),
    ),
    S20CaseSpec(
        "n2b2-s20-02",
        "single_person",
        2026082002,
        832,
        1216,
        1,
        "strict",
        ("single_person_half_body",),
    ),
    S20CaseSpec(
        "n2b2-s20-03",
        "single_person",
        2026082003,
        832,
        1216,
        1,
        "strict",
        ("single_person_seated",),
    ),
    S20CaseSpec(
        "n2b2-s20-04",
        "single_person",
        2026082004,
        832,
        1216,
        1,
        "strict",
        ("single_person_prop_interaction",),
    ),
    S20CaseSpec(
        "n2b2-s20-05", "multi_person", 2026082005, 1024, 768, 2, "strict", ("two_people_separated",)
    ),
    S20CaseSpec(
        "n2b2-s20-06", "multi_person", 2026082006, 1024, 768, 2, "strict", ("two_people_close",)
    ),
    S20CaseSpec(
        "n2b2-s20-07",
        "multi_person",
        2026082007,
        1024,
        768,
        2,
        "observation",
        ("partial_occlusion",),
    ),
    S20CaseSpec(
        "n2b2-s20-08",
        "multi_person",
        2026082008,
        1024,
        768,
        1,
        "observation",
        ("mirror_reflection",),
    ),
    S20CaseSpec(
        "n2b2-s20-09", "low_light", 2026082009, 832, 1216, 1, "observation", ("low_light_single",)
    ),
    S20CaseSpec(
        "n2b2-s20-10", "low_light", 2026082010, 1024, 768, 2, "observation", ("low_light_multi",)
    ),
    S20CaseSpec(
        "n2b2-s20-11", "low_light", 2026082011, 1024, 768, 1, "observation", ("night_silhouette",)
    ),
    S20CaseSpec(
        "n2b2-s20-12",
        "complex_background",
        2026082012,
        1024,
        768,
        1,
        "strict",
        ("complex_interior",),
    ),
    S20CaseSpec(
        "n2b2-s20-13",
        "complex_background",
        2026082013,
        1024,
        768,
        1,
        "strict",
        ("complex_exterior",),
    ),
    S20CaseSpec(
        "n2b2-s20-14",
        "complex_background",
        2026082014,
        1024,
        768,
        3,
        "observation",
        ("distracting_background_people",),
    ),
    S20CaseSpec(
        "n2b2-s20-15", "backlight", 2026082015, 832, 1216, 1, "observation", ("strong_backlight",)
    ),
    S20CaseSpec(
        "n2b2-s20-16", "backlight", 2026082016, 832, 1216, 1, "observation", ("silhouette",)
    ),
    S20CaseSpec(
        "n2b2-s20-17",
        "minimal_composition",
        2026082017,
        1024,
        768,
        1,
        "strict",
        ("large_negative_space",),
    ),
    S20CaseSpec(
        "n2b2-s20-18",
        "minimal_composition",
        2026082018,
        1024,
        768,
        1,
        "strict",
        ("offset_composition",),
    ),
    S20CaseSpec(
        "n2b2-s20-19",
        "negative_control",
        2026082019,
        1024,
        768,
        0,
        "negative",
        ("negative_control_no_person",),
    ),
    S20CaseSpec(
        "n2b2-s20-20",
        "unsupported_control",
        2026082020,
        1024,
        768,
        0,
        "unsupported",
        ("unsupported_collage_control",),
    ),
)

_EXPECTED = {item.case_id: item for item in S20_CASE_MATRIX}
_FORBIDDEN_KEYS = {
    "real_photo",
    "real_photo_path",
    "source_path",
    "original_path",
    "exif",
    "EXIF",
    "g1",
    "g1_source",
}


def _fail(message: str) -> ValueError:
    return ValueError(f"N2B2_S20_MANIFEST_INVALID: {message}")


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_forbidden(value: Any, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_KEYS:
                raise _fail(f"forbidden source field: {path}.{key}")
            _reject_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_forbidden(child, f"{path}[{index}]")


def _safe_file(root: Path, filename: str) -> Path:
    relative = Path(filename)
    if relative.is_absolute() or any(part == ".." for part in relative.parts):
        raise _fail(f"path escape rejected: {filename!r}")
    candidate = root / relative
    if candidate.is_symlink() or not candidate.is_file():
        raise _fail(f"missing, symlink or non-file fixture: {filename!r}")
    resolved_root = root.resolve(strict=True)
    resolved = candidate.resolve(strict=True)
    try:
        inside = os.path.commonpath((str(resolved_root), str(resolved))) == str(resolved_root)
    except ValueError:
        inside = False
    if not inside:
        raise _fail(f"resolved path escapes fixture directory: {filename!r}")
    return resolved


def _load_png(path: Path) -> tuple[bytes, int, int]:
    from io import BytesIO

    from PIL import Image

    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise _fail(f"non-PNG fixture: {path.name!r}")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format != "PNG":
                raise _fail(f"non-PNG fixture: {path.name!r}")
            return data, int(image.width), int(image.height)
    except ValueError:
        raise
    except Exception as exc:  # pragma: no cover - Pillow-specific corruption
        raise _fail(f"invalid PNG fixture: {path.name!r}") from exc


def load_s20_manifest(
    manifest_dir: Path,
    *,
    project_root: Path | None = None,
    baseline_manifest_dir: Path | None = None,
) -> list[SyntheticFixture]:
    """Load exactly the fixed, Git-external S20 matrix and freeze image bytes."""

    root = Path(manifest_dir).resolve(strict=True)
    if not root.is_dir():
        raise _fail("manifest directory is not a directory")
    if project_root is not None:
        project = Path(project_root).resolve(strict=True)
        try:
            if os.path.commonpath((str(project), str(root))) == str(project):
                raise _fail("manifest directory must be Git-external")
        except ValueError:
            pass
    manifest_path = root / S20_MANIFEST_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise _fail("fixture_manifest.json missing or symlink")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise _fail("manifest is not valid JSON") from exc
    _reject_forbidden(payload)
    if not isinstance(payload, dict):
        raise _fail("manifest must be an object")
    manifest_version = payload.get("schema_version")
    if manifest_version not in {S20_MANIFEST_VERSION, S20_MANIFEST_V2_VERSION}:
        raise _fail("unexpected schema_version")
    if payload.get("fixture_set") != "N2B2_S20_SYNTHETIC":
        raise _fail("unexpected fixture_set")
    is_v2 = manifest_version == S20_MANIFEST_V2_VERSION
    baseline_by_case: dict[str, SyntheticFixture] = {}
    if not is_v2:
        if payload.get("generator_version") != S20_GENERATOR_VERSION:
            raise _fail("generator_version does not match the fixed S20 generator")
    else:
        if payload.get("fixture_set_version") != "N2B2_S20_SYNTHETIC_V2":
            raise _fail("unexpected fixture_set_version")
        source_manifest_sha = payload.get("source_manifest_sha256")
        if source_manifest_sha != S20_V1_MANIFEST_SHA256:
            raise _fail("source_manifest_sha256 does not bind the frozen v1 manifest")
        if baseline_manifest_dir is None:
            raise _fail("baseline_manifest_dir is required for v2")
        baseline_root = Path(baseline_manifest_dir).resolve(strict=True)
        baseline_path = baseline_root / S20_MANIFEST_NAME
        if not baseline_path.is_file() or _sha_file(baseline_path) != S20_V1_MANIFEST_SHA256:
            raise _fail("frozen v1 baseline manifest is missing or drifted")
        baseline_by_case = {
            item.case_id: item
            for item in load_s20_manifest(baseline_root, project_root=project_root)
        }
        record_path = root / S20_CASE17_REMEDIATION_RECORD_NAME
        expected_record_digest = payload.get("case17_remediation_record_sha256")
        if not isinstance(expected_record_digest, str) or len(expected_record_digest) != 64:
            raise _fail("case17_remediation_record_sha256 is required")
        if not record_path.is_file() or record_path.is_symlink():
            raise _fail("case17 remediation record is missing or is a symlink")
        try:
            record_payload = json.loads(record_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise _fail("case17 remediation record is not valid JSON") from exc
        _reject_forbidden(record_payload, "case17_remediation_record")
        if _sha_file(record_path) != expected_record_digest:
            raise _fail("case17 remediation record hash mismatch")
    entries = payload.get("fixtures")
    if not isinstance(entries, list) or len(entries) != len(S20_CASE_MATRIX):
        raise _fail("manifest must contain exactly 20 fixtures")
    loaded: list[SyntheticFixture] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise _fail("fixture entry must be an object")
        case_id = entry.get("case_id")
        if not isinstance(case_id, str) or case_id not in _EXPECTED or case_id in seen_ids:
            raise _fail(f"unexpected or duplicate case_id: {case_id!r}")
        spec = _EXPECTED[case_id]
        seen_ids.add(case_id)
        expected_seed = spec.seed
        if is_v2 and case_id == "n2b2-s20-17":
            seed_value = entry.get("seed")
            if seed_value not in S20_CASE17_REMEDIATION_SEEDS:
                raise _fail(f"case17 seed is outside the predeclared remediation set: {case_id}")
            expected_seed = seed_value
        expected_fields = {
            "case_type": spec.case_type,
            "seed": expected_seed,
            "width": spec.width,
            "height": spec.height,
            "expected_person_count": spec.expected_person_count,
            "acceptance_profile": spec.acceptance_profile,
        }
        if any(entry.get(key) != value for key, value in expected_fields.items()):
            raise _fail(f"case matrix mismatch: {case_id}")
        if is_v2:
            entry_generator = entry.get("generator_version")
            if not isinstance(entry_generator, str) or not entry_generator:
                raise _fail(f"per-entry generator_version required: {case_id}")
            if case_id == "n2b2-s20-17" and entry_generator != S20_CASE17_GENERATOR_VERSION:
                raise _fail(f"case17 generator_version mismatch: {case_id}")
            if case_id != "n2b2-s20-17":
                baseline = baseline_by_case[case_id]
                if entry.get("image_sha256") != baseline.image_sha256:
                    raise _fail(f"preserved fixture SHA mismatch: {case_id}")
                if entry.get("seed") != baseline.seed:
                    raise _fail(f"preserved fixture seed mismatch: {case_id}")
            elif entry.get("image_sha256") == baseline_by_case[case_id].image_sha256:
                raise _fail("case17 replacement must differ from the frozen v1 image")
        else:
            entry_generator = str(payload["generator_version"])
        if entry.get("synthetic") is not True:
            raise _fail(f"synthetic=true required: {case_id}")
        expected_processability = entry.get("expected_processability")
        expected_processability_value = (
            "unsupported" if spec.acceptance_profile == "unsupported" else "processable"
        )
        if expected_processability != expected_processability_value:
            raise _fail(f"expected_processability mismatch: {case_id}")
        tags = entry.get("tags")
        if not isinstance(tags, list) or not all(isinstance(tag, str) and tag for tag in tags):
            raise _fail(f"tags required: {case_id}")
        filename = entry.get("filename")
        expected_sha = entry.get("image_sha256")
        if not isinstance(filename, str) or not filename.lower().endswith(".png"):
            raise _fail(f"PNG filename required: {case_id}")
        if (
            not isinstance(expected_sha, str)
            or len(expected_sha) != 64
            or expected_sha != expected_sha.lower()
        ):
            raise _fail(f"lowercase SHA-256 required: {case_id}")
        if expected_sha in seen_hashes:
            raise _fail(f"duplicate image SHA-256: {case_id}")
        params = entry.get("generation_parameters")
        required_params = (
            "prompt",
            "negative_prompt",
            "sampler",
            "scheduler",
            "steps",
            "cfg",
            "denoise",
            "checkpoint",
            "checkpoint_sha256",
            "vae",
            "vae_sha256",
            "comfyui_version",
            "port",
            "prompt_id",
        )
        if not isinstance(params, dict) or any(params.get(key) is None for key in required_params):
            raise _fail(f"complete generation parameters required: {case_id}")
        if (
            params.get("checkpoint") != "sd_xl_base_1.0.safetensors"
            or params.get("vae") != "sdxl_vae.safetensors"
        ):
            raise _fail(f"unexpected local SDXL model identity: {case_id}")
        if params.get("port") != 7865:
            raise _fail(f"unexpected ComfyUI port: {case_id}")
        path = _safe_file(root, filename)
        data, width, height = _load_png(path)
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != expected_sha:
            raise _fail(f"SHA-256 mismatch: {case_id}")
        if (width, height) != (spec.width, spec.height):
            raise _fail(f"dimension mismatch: {case_id}")
        seen_hashes.add(expected_sha)
        loaded.append(
            SyntheticFixture(
                case_id=case_id,
                case_type=spec.case_type,
                image_bytes=data,
                image_sha256=actual_sha,
                width=width,
                height=height,
                generator_version=entry_generator,
                seed=expected_seed,
                generation_parameters=dict(params),
                expected_processability=str(expected_processability),
                person_expectation=f"expected_person_count={spec.expected_person_count}",
                acceptance_profile=spec.acceptance_profile,
            )
        )
    if seen_ids != set(_EXPECTED):
        raise _fail("case matrix is incomplete")
    return sorted(loaded, key=lambda item: item.case_id)
