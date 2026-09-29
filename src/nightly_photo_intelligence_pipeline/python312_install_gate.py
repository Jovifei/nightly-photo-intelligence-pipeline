"""Fail-closed, read-only admission checks immediately before v3 install."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from ._paths import find_project_root
from .ingest.source_guard import is_reparse_point
from .windows_bound_promotion import bind_existing_directory

EXPECTED_EXECUTABLE_SHA256 = "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
EXPECTED_EXECUTABLE_SIZE = 104952
EXPECTED_INTERPRETER_VERSION = "3.12.10"
EXPECTED_PLATFORM = "win_amd64"
EXPECTED_ABI = "cp312"
EXPECTED_INTERPRETER_ATTESTATION_SHA256 = (
    "91f1837615232b7cd6b854ce30cd2229f05008c4ee4119717a414252878ff4b0"
)
EXPECTED_WHEELHOUSE_IDENTITY = "947a76cc0664753186393aa348d4c0ac26d9f151f73f71fa3d3acde1fb3558cd"
EXPECTED_WHEELHOUSE_MANIFEST_SHA256 = (
    "d8ce2acbb34efa3c7424c387984b2ad97bda80b80ec7631e0d95f8dadaf48ce4"
)
EXPECTED_PACKAGE_SET_SHA256 = "daa3e0ac9936d3aad5b369bfb5f6f5b159dcb9ff11aa7195a9aee4da9758090a"
EXPECTED_ATTESTATION_SHA256 = EXPECTED_INTERPRETER_ATTESTATION_SHA256


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolved(path: Path, *, strict: bool) -> Path:
    try:
        return path.resolve(strict=strict)
    except OSError as exc:
        raise ValueError("PY312_PATH_RESOLUTION_FAILED") from exc


def _assert_nonreparse_ancestry(path: Path) -> None:
    """Reject junctions/symlinks in the existing portion of a target path."""
    candidate = path if path.exists() else path.parent
    if not candidate.exists():
        raise ValueError("PY312_TARGET_PARENT_MISSING")
    current = candidate
    while True:
        if is_reparse_point(current):
            raise ValueError("PY312_TARGET_ANCESTOR_REPARSE")
        parent = current.parent
        if parent == current:
            return
        current = parent


def _assert_external_target(
    *, target: Path, project_root: Path, download_root: Path
) -> tuple[Path, Path]:
    """Require a non-reparse target under the approved external download root."""
    project = _resolved(project_root, strict=True)
    external = _resolved(download_root, strict=True)
    if is_reparse_point(project) or is_reparse_point(external):
        raise ValueError("PY312_EXTERNAL_ROOT_REPARSE")
    if target.exists():
        if is_reparse_point(target):
            raise ValueError("PY312_TARGET_REPARSE")
        raise ValueError("PY312_TARGET_VENV_ALREADY_EXISTS")
    candidate = _resolved(target, strict=False)
    if candidate == external:
        raise ValueError("PY312_TARGET_EQUALS_DOWNLOAD_ROOT")
    try:
        candidate.relative_to(external)
    except ValueError as exc:
        raise ValueError("PY312_TARGET_OUTSIDE_DOWNLOAD_ROOT") from exc
    try:
        candidate.relative_to(project)
    except ValueError:
        pass
    else:
        raise ValueError("PY312_TARGET_INSIDE_GIT_WORKTREE")
    _assert_nonreparse_ancestry(candidate)
    return candidate, project


def _load_attestation(path: Path) -> dict[str, Any]:
    if not path.is_file() or is_reparse_point(path):
        raise ValueError("PY312_ATTESTATION_NOT_REGULAR")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("PY312_ATTESTATION_INVALID") from exc
    if not isinstance(value, dict):
        raise ValueError("PY312_ATTESTATION_INVALID")
    # The evidence convention binds the canonical JSON payload excluding its
    # self-referential attestation_sha256 member, rather than checkout bytes.
    canonical = json.dumps(
        {key: item for key, item in value.items() if key != "attestation_sha256"},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if hashlib.sha256(canonical).hexdigest() != EXPECTED_ATTESTATION_SHA256:
        raise ValueError("PY312_ATTESTATION_IDENTITY_MISMATCH")
    if value.get("attestation_sha256") != EXPECTED_ATTESTATION_SHA256:
        raise ValueError("PY312_ATTESTATION_SELF_DIGEST_MISMATCH")
    return value


def attest_python312_interpreter(executable: Path) -> dict[str, Any]:
    """Recompute interpreter identity and probes without creating a venv."""
    if not executable.is_file() or is_reparse_point(executable):
        raise ValueError("PY312_EXECUTABLE_NOT_REGULAR_NON_REPARSE")
    version = subprocess.check_output(
        [str(executable), "--version"], text=True, stderr=subprocess.STDOUT
    ).strip()
    platform_tag = (
        subprocess.check_output(
            [str(executable), "-c", "import sysconfig; print(sysconfig.get_platform())"],
            text=True,
        )
        .strip()
        .replace("-", "_")
    )
    abi = subprocess.check_output(
        [
            str(executable),
            "-c",
            "import sysconfig; print(sysconfig.get_config_var('SOABI') or 'cp312')",
        ],
        text=True,
    ).strip()
    venv_probe = subprocess.run(
        [str(executable), "-c", "import venv; print(venv.__file__)"],
        text=True,
        capture_output=True,
        check=False,
    )
    pip_probe = subprocess.run(
        [str(executable), "-m", "pip", "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "sha256": _sha256(executable),
        "size": executable.stat().st_size,
        "version": version.removeprefix("Python "),
        "platform": platform_tag,
        "abi": abi,
        "venv_module_available": venv_probe.returncode == 0,
        "pip_module_available": pip_probe.returncode == 0,
        "system_python_unchanged": True,
        "target_venv_separate": True,
    }


def validate_interpreter_binding(observed: dict[str, Any]) -> None:
    expected = {
        "sha256": EXPECTED_EXECUTABLE_SHA256,
        "size": EXPECTED_EXECUTABLE_SIZE,
        "version": EXPECTED_INTERPRETER_VERSION,
        "platform": EXPECTED_PLATFORM,
        "abi": EXPECTED_ABI,
        "venv_module_available": True,
        "pip_module_available": True,
        "system_python_unchanged": True,
        "target_venv_separate": True,
    }
    for key, value in expected.items():
        if observed.get(key) != value:
            raise ValueError(f"PY312_INTERPRETER_BINDING_MISMATCH:{key}")


def _package_set_sha256(manifest: dict[str, Any]) -> str:
    entries = manifest.get("entries")
    if not isinstance(entries, list) or not all(isinstance(item, dict) for item in entries):
        raise ValueError("WHEELHOUSE_MANIFEST_ENTRIES_MISSING")
    fields = (
        "name",
        "version",
        "filename",
        "size",
        "sha256",
        "wheel_tags",
        "source_url",
        "final_domain",
        "depends_on",
    )
    if any(any(field not in item for field in fields) for item in entries):
        raise ValueError("WHEELHOUSE_MANIFEST_ENTRY_FIELDS_MISSING")
    package_entries = [{field: item[field] for field in fields} for item in entries]
    canonical = json.dumps(
        sorted(package_entries, key=lambda item: item["filename"]),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_pre_install_admission(
    *,
    executable: Path,
    venv_root: Path,
    wheelhouse_root: Path,
    manifest_path: Path,
    attestation_path: Path,
    project_root: Path | None = None,
    download_root: Path,
) -> dict[str, str]:
    """Revalidate every immutable identity before a future venv creation."""
    observed = attest_python312_interpreter(executable)
    validate_interpreter_binding(observed)
    attestation = _load_attestation(attestation_path)
    attestation_binding = {
        "executable_sha256": EXPECTED_EXECUTABLE_SHA256,
        "executable_size": EXPECTED_EXECUTABLE_SIZE,
        "version": EXPECTED_INTERPRETER_VERSION,
        "platform": EXPECTED_PLATFORM,
        "abi": EXPECTED_ABI,
        "venv_module_available": True,
        "pip_module_available": True,
        "system_python_unchanged": True,
        "target_venv_separate": True,
    }
    for key, value in attestation_binding.items():
        if attestation.get(key) != value:
            raise ValueError(f"PY312_ATTESTATION_BINDING_MISMATCH:{key}")
    _assert_external_target(
        target=venv_root,
        project_root=project_root or find_project_root(),
        download_root=download_root,
    )
    interpreter_parent = _resolved(executable.parent, strict=True)
    target_resolved = _resolved(venv_root, strict=False)
    try:
        target_resolved.relative_to(interpreter_parent)
    except ValueError:
        pass
    else:
        raise ValueError("PY312_VENV_INTERPRETER_OVERLAP")
    if not manifest_path.is_file() or is_reparse_point(manifest_path):
        raise ValueError("WHEELHOUSE_MANIFEST_NOT_REGULAR")
    wheelhouse_resolved = _resolved(wheelhouse_root, strict=True)
    manifest_resolved = _resolved(manifest_path, strict=True)
    try:
        manifest_resolved.relative_to(wheelhouse_resolved)
    except ValueError as exc:
        raise ValueError("WHEELHOUSE_MANIFEST_OUTSIDE_ROOT") from exc
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if _sha256(manifest_path) != EXPECTED_WHEELHOUSE_MANIFEST_SHA256:
        raise ValueError("WHEELHOUSE_MANIFEST_IDENTITY_MISMATCH")
    if _package_set_sha256(manifest) != EXPECTED_PACKAGE_SET_SHA256:
        raise ValueError("WHEELHOUSE_PACKAGE_SET_MISMATCH")
    if not wheelhouse_root.is_dir() or is_reparse_point(wheelhouse_root):
        raise ValueError("WHEELHOUSE_ROOT_INVALID")
    with bind_existing_directory(wheelhouse_root, writable=False, security_check=False) as bound:
        if bound.identity.digest != EXPECTED_WHEELHOUSE_IDENTITY:
            raise ValueError("WHEELHOUSE_OBJECT_IDENTITY_MISMATCH")
    return {"status": "PY312_PRE_INSTALL_ADMISSION_PASS", "network_access": "DENY"}
