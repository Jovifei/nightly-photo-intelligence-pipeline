"""Non-mutating effective-access checks for a Windows source tree."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ..domain.errors import SourceReadOnlyNotVerifiedError

_ACCESS_DENIED = 5
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_OPEN_EXISTING = 3
_FILE_SHARE_READ = 0x1
_FILE_SHARE_WRITE = 0x2
_FILE_SHARE_DELETE = 0x4
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000

_FILE_RIGHTS = {
    "write_data": 0x0002,
    "append_data": 0x0004,
    "write_extended_attributes": 0x0010,
    "write_attributes": 0x0100,
    "delete": 0x00010000,
    "write_acl": 0x00040000,
    "take_ownership": 0x00080000,
}
_DIRECTORY_RIGHTS = {
    "create_file": 0x0002,
    "create_directory": 0x0004,
    "delete_child": 0x0040,
    "write_extended_attributes": 0x0010,
    "write_attributes": 0x0100,
    "delete": 0x00010000,
    "write_acl": 0x00040000,
    "take_ownership": 0x00080000,
}


class CapabilityDisposition(str, Enum):
    DENIED = "DENIED"
    GRANTED = "GRANTED"
    NOT_VERIFIED = "NOT_VERIFIED"


@dataclass(frozen=True)
class CapabilityProbe:
    target_kind: str
    capability: str
    disposition: CapabilityDisposition


@dataclass(frozen=True)
class ReadOnlyCapabilityResult:
    status: str
    checked_entries: int
    granted: tuple[str, ...] = ()
    unknown: tuple[str, ...] = ()

    @property
    def verified(self) -> bool:
        return self.status == "OS_ENFORCED_READ_ONLY_VERIFIED"

    def require_verified(self) -> None:
        if not self.verified:
            reason = "mutating capability granted" if self.granted else "capability not verified"
            raise SourceReadOnlyNotVerifiedError(reason)


ProbeFunction = Callable[[Path, str, int], CapabilityDisposition]


def _windows_probe(path: Path, target_kind: str, desired_access: int) -> CapabilityDisposition:
    if sys.platform != "win32":
        return CapabilityDisposition.NOT_VERIFIED
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    ]
    create_file.restype = ctypes.c_void_p
    flags = _FILE_FLAG_OPEN_REPARSE_POINT
    if target_kind == "directory":
        flags |= _FILE_FLAG_BACKUP_SEMANTICS
    ctypes.set_last_error(0)
    handle = create_file(
        str(path),
        desired_access,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE | _FILE_SHARE_DELETE,
        None,
        _OPEN_EXISTING,
        flags,
        None,
    )
    if handle not in (None, _INVALID_HANDLE_VALUE):
        kernel32.CloseHandle(ctypes.c_void_p(handle))
        return CapabilityDisposition.GRANTED
    if ctypes.get_last_error() == _ACCESS_DENIED:
        return CapabilityDisposition.DENIED
    return CapabilityDisposition.NOT_VERIFIED


def _probe_target(
    path: Path,
    target_kind: str,
    rights: dict[str, int],
    probe: ProbeFunction,
) -> list[CapabilityProbe]:
    results: list[CapabilityProbe] = []
    for name, mask in rights.items():
        try:
            disposition = probe(path, target_kind, mask)
        except Exception:  # noqa: BLE001 - an indeterminate probe must fail closed
            disposition = CapabilityDisposition.NOT_VERIFIED
        if not isinstance(disposition, CapabilityDisposition):
            disposition = CapabilityDisposition.NOT_VERIFIED
        results.append(CapabilityProbe(target_kind, name, disposition))
    return results


def verify_source_read_only_capability(
    source_root: Path,
    authorized_files: Sequence[Path],
    *,
    probe: ProbeFunction = _windows_probe,
) -> ReadOnlyCapabilityResult:
    """Prove mutating access is denied without writing to the source tree.

    Only an explicit access-denied result counts as denial. Missing files,
    sharing violations, unsupported platforms, and probe errors fail closed.
    Parent ``delete_child`` is checked because it can permit rename/delete even
    when DELETE is denied on the child itself.
    """
    if sys.platform != "win32" and probe is _windows_probe:
        return ReadOnlyCapabilityResult("NOT_VERIFIED", 0, unknown=("platform",))
    root = Path(source_root)
    if not root.is_dir():
        return ReadOnlyCapabilityResult("NOT_VERIFIED", 0, unknown=("source_root",))

    probes = _probe_target(root, "directory", _DIRECTORY_RIGHTS, probe)
    probes.extend(_probe_target(root.parent, "directory", {"delete_child": 0x0040}, probe))
    checked = 0
    directory_paths: set[Path] = {root}
    for candidate in authorized_files:
        path = Path(candidate)
        if not path.is_file():
            probes.append(CapabilityProbe("file", "exists", CapabilityDisposition.NOT_VERIFIED))
            continue
        checked += 1
        probes.extend(_probe_target(path, "file", _FILE_RIGHTS, probe))
        try:
            relative_parent = path.parent.relative_to(root)
        except ValueError:
            probes.append(
                CapabilityProbe("directory", "containment", CapabilityDisposition.NOT_VERIFIED)
            )
            continue
        cursor = root
        for part in relative_parent.parts:
            cursor = cursor / part
            directory_paths.add(cursor)
    for parent in sorted(directory_paths - {root}, key=lambda item: str(item).casefold()):
        if not parent.is_dir():
            probes.append(
                CapabilityProbe("directory", "exists", CapabilityDisposition.NOT_VERIFIED)
            )
            continue
        probes.extend(_probe_target(parent, "directory", _DIRECTORY_RIGHTS, probe))

    granted = tuple(
        sorted(
            {
                f"{item.target_kind}:{item.capability}"
                for item in probes
                if item.disposition == CapabilityDisposition.GRANTED
            }
        )
    )
    unknown = tuple(
        sorted(
            {
                f"{item.target_kind}:{item.capability}"
                for item in probes
                if item.disposition == CapabilityDisposition.NOT_VERIFIED
            }
        )
    )
    if granted:
        status = "FAIL"
    elif unknown or checked != len(authorized_files):
        status = "NOT_VERIFIED"
    else:
        status = "OS_ENFORCED_READ_ONLY_VERIFIED"
    return ReadOnlyCapabilityResult(status, checked, granted=granted, unknown=unknown)
