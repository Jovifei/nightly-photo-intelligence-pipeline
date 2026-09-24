"""Windows handle-bound filesystem primitives for N2B1P promotion.

The N2B1P cache is a security boundary.  These primitives intentionally do
not offer a path-based fallback: after a root is bound, every descendant is
opened or created through ``NtCreateFile`` relative to a live directory handle
and publication uses an NT handle-relative rename with that same root.
"""

from __future__ import annotations

import ctypes
import hashlib
import ntpath
import re
import secrets
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .domain.errors import (
    NpiError,
    PreflightUnsatisfiedError,
    PromotionPathSafetyError,
)

_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_ALREADY_EXISTS = 183
_ERROR_FILE_EXISTS = 80
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_ATTRIBUTE_TAG_INFO = 9
_FILE_ID_INFO = 18
_FILE_DISPOSITION_INFO = 4
_FILE_NAMES_INFORMATION = 12
_FILE_RENAME_INFORMATION = 10
_FILE_OPEN = 1
_FILE_CREATE = 2
_FILE_DIRECTORY_FILE = 0x00000001
_FILE_NON_DIRECTORY_FILE = 0x00000040
_FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
_FILE_OPEN_REPARSE_POINT = 0x00200000
_FILE_LIST_DIRECTORY = 0x00000001
_FILE_ADD_FILE = 0x00000002
_FILE_ADD_SUBDIRECTORY = 0x00000004
_FILE_DELETE_CHILD = 0x00000040
_FILE_READ_ATTRIBUTES = 0x00000080
_FILE_WRITE_ATTRIBUTES = 0x00000100
_READ_CONTROL = 0x00020000
_FILE_READ_DATA = 0x00000001
_FILE_WRITE_DATA = 0x00000002
_FILE_APPEND_DATA = 0x00000004
_DELETE = 0x00010000
_WRITE_DAC = 0x00040000
_WRITE_OWNER = 0x00080000
_SYNCHRONIZE = 0x00100000
_OBJ_CASE_INSENSITIVE = 0x00000040
_STATUS_NO_MORE_FILES = 0x80000006
_STATUS_OBJECT_NAME_NOT_FOUND = 0xC0000034
_STATUS_OBJECT_PATH_NOT_FOUND = 0xC000003A
_VOLUME_NAME_GUID = 0x00000001
_CHUNK_BYTES = 1024 * 1024
_REAL20_TERMINAL_FILE_NAME = re.compile(
    r"(?:terminal-v1|terminal-commit-v1)-[0-9a-f]{64}\.json"
)
_SE_FILE_OBJECT = 1
_SECURITY_INFORMATION = 0x00000007
_TOKEN_QUERY = 0x0008
_TOKEN_DUPLICATE = 0x0002
_ERROR_NO_TOKEN = 1008


def _failure(code: str) -> NpiError:
    if code == "NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE":
        return PreflightUnsatisfiedError(code, error_code=code)
    return PromotionPathSafetyError(code, error_code=code)


def _u32(value: int) -> int:
    return value & 0xFFFFFFFF


def _require_windows() -> None:
    if sys.platform != "win32":
        raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")


def _safe_component(name: str) -> str:
    if (
        not name
        or name in {".", ".."}
        or any(character in name for character in ("/", "\\", ":", "\x00"))
    ):
        raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")
    return name


def normalize_windows_path(path: Path | str) -> str:
    """Return a case-insensitive, prefix-stable absolute Windows path."""
    raw = str(path)
    if raw.startswith("\\\\?\\"):
        raw = raw[4:]
    normalized = ntpath.normpath(raw)
    drive, tail = ntpath.splitdrive(normalized)
    if not drive or not tail.startswith("\\"):
        raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")
    return (drive.upper() + tail).rstrip("\\").casefold()


def paths_overlap(left: Path | str, right: Path | str) -> bool:
    """Return whether normalized Windows paths are identical or nested."""
    first = normalize_windows_path(left)
    second = normalize_windows_path(right)
    return first == second or first.startswith(second + "\\") or second.startswith(first + "\\")


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ushort),
        ("MaximumLength", ctypes.c_ushort),
        ("Buffer", ctypes.c_wchar_p),
    ]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("Length", ctypes.c_ulong),
        ("RootDirectory", ctypes.c_void_p),
        ("ObjectName", ctypes.POINTER(_UnicodeString)),
        ("Attributes", ctypes.c_ulong),
        ("SecurityDescriptor", ctypes.c_void_p),
        ("SecurityQualityOfService", ctypes.c_void_p),
    ]


class _IoStatusBlock(ctypes.Structure):
    _fields_ = [("Status", ctypes.c_long), ("Information", ctypes.c_size_t)]


class _FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [("FileAttributes", ctypes.c_ulong), ("ReparseTag", ctypes.c_ulong)]


class _FileId128(ctypes.Structure):
    _fields_ = [("Identifier", ctypes.c_byte * 16)]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [("VolumeSerialNumber", ctypes.c_ulonglong), ("FileId", _FileId128)]


class _FileDispositionInfo(ctypes.Structure):
    _fields_ = [("DeleteFile", ctypes.c_int)]


class _FileRenameInfo(ctypes.Structure):
    _fields_ = [
        ("ReplaceIfExists", ctypes.c_int),
        ("RootDirectory", ctypes.c_void_p),
        ("FileNameLength", ctypes.c_ulong),
        ("FileName", ctypes.c_wchar * 1),
    ]


class _GenericMapping(ctypes.Structure):
    _fields_ = [
        ("GenericRead", ctypes.c_ulong),
        ("GenericWrite", ctypes.c_ulong),
        ("GenericExecute", ctypes.c_ulong),
        ("GenericAll", ctypes.c_ulong),
    ]


@dataclass(frozen=True)
class BoundObjectIdentity:
    """Handle-observed identity, without exposing the caller path."""

    volume_serial_number: int
    file_id_hex: str
    final_path: str

    @property
    def digest(self) -> str:
        payload = f"{self.volume_serial_number:016x}:{self.file_id_hex}".encode("ascii")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class _HandleDescription:
    identity: BoundObjectIdentity
    attributes: int
    reparse_tag: int


@dataclass(frozen=True)
class NativeAccessCheck:
    granted: bool | None
    win32_error: int | None


class _WindowsNative:
    """Narrow ctypes wrapper; every unavailable native operation fails closed."""

    def __init__(self) -> None:
        _require_windows()
        try:
            self._kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
            self._ntdll: Any = ctypes.WinDLL("ntdll", use_last_error=True)
            self._advapi32: Any = ctypes.WinDLL("advapi32", use_last_error=True)
        except Exception as exc:  # noqa: BLE001
            raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE") from exc
        self._configure()

    def _configure(self) -> None:
        self._kernel32.CreateFileW.argtypes = [
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
        ]
        self._kernel32.CreateFileW.restype = ctypes.c_void_p
        self._kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        self._kernel32.CloseHandle.restype = ctypes.c_int
        self._kernel32.GetCurrentProcess.argtypes = []
        self._kernel32.GetCurrentProcess.restype = ctypes.c_void_p
        self._kernel32.GetCurrentThread.argtypes = []
        self._kernel32.GetCurrentThread.restype = ctypes.c_void_p
        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p
        self._advapi32.GetSecurityInfo.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._advapi32.GetSecurityInfo.restype = ctypes.c_ulong
        self._advapi32.OpenThreadToken.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)
        ]
        self._advapi32.OpenThreadToken.restype = ctypes.c_int
        self._advapi32.OpenProcessToken.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)
        ]
        self._advapi32.OpenProcessToken.restype = ctypes.c_int
        self._advapi32.DuplicateToken.argtypes = [
            ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)
        ]
        self._advapi32.DuplicateToken.restype = ctypes.c_int
        self._advapi32.AccessCheck.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong,
            ctypes.POINTER(_GenericMapping), ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
        ]
        self._advapi32.AccessCheck.restype = ctypes.c_int
        self._kernel32.GetFileInformationByHandleEx.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self._kernel32.GetFileInformationByHandleEx.restype = ctypes.c_int
        self._kernel32.GetFinalPathNameByHandleW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_wchar_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
        ]
        self._kernel32.GetFinalPathNameByHandleW.restype = ctypes.c_ulong
        self._kernel32.SetFileInformationByHandle.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self._kernel32.SetFileInformationByHandle.restype = ctypes.c_int
        self._kernel32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
        self._kernel32.FlushFileBuffers.restype = ctypes.c_int
        self._kernel32.ReadFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
        ]
        self._kernel32.ReadFile.restype = ctypes.c_int
        self._kernel32.WriteFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.c_void_p,
        ]
        self._kernel32.WriteFile.restype = ctypes.c_int
        self._ntdll.NtCreateFile.argtypes = [
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_ulong,
            ctypes.POINTER(_ObjectAttributes),
            ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_ulong,
            ctypes.c_void_p,
            ctypes.c_ulong,
        ]
        self._ntdll.NtCreateFile.restype = ctypes.c_long
        self._ntdll.NtQueryDirectoryFile.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
            ctypes.c_ubyte,
            ctypes.c_void_p,
            ctypes.c_ubyte,
        ]
        self._ntdll.NtQueryDirectoryFile.restype = ctypes.c_long
        self._ntdll.NtSetInformationFile.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_IoStatusBlock),
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.c_int,
        ]
        self._ntdll.NtSetInformationFile.restype = ctypes.c_long

    def close(self, handle: int) -> None:
        if handle and handle != _INVALID_HANDLE_VALUE:
            self._kernel32.CloseHandle(ctypes.c_void_p(handle))

    def access_check(self, handle: int, desired_access: int) -> NativeAccessCheck:
        descriptor = ctypes.c_void_p()
        error = int(
            self._advapi32.GetSecurityInfo(
                ctypes.c_void_p(handle), _SE_FILE_OBJECT, _SECURITY_INFORMATION,
                None, None, None, None, ctypes.byref(descriptor),
            )
        )
        if error:
            return NativeAccessCheck(None, error)
        token = ctypes.c_void_p()
        try:
            ctypes.set_last_error(0)
            opened = self._advapi32.OpenThreadToken(
                self._kernel32.GetCurrentThread(), _TOKEN_QUERY, 1, ctypes.byref(token)
            )
            if not opened:
                error = int(ctypes.get_last_error())
                if error != _ERROR_NO_TOKEN:
                    return NativeAccessCheck(None, error)
                # AccessCheck requires an impersonation token, not this primary token.
                primary = ctypes.c_void_p()
                if not self._advapi32.OpenProcessToken(
                    self._kernel32.GetCurrentProcess(), _TOKEN_QUERY | _TOKEN_DUPLICATE,
                    ctypes.byref(primary),
                ):
                    return NativeAccessCheck(None, int(ctypes.get_last_error()))
                if not self._advapi32.DuplicateToken(primary, 2, ctypes.byref(token)):
                    error = int(ctypes.get_last_error())
                    self.close(int(primary.value))
                    return NativeAccessCheck(None, error)
                self.close(int(primary.value))
            mapping = _GenericMapping(0x00120089, 0x00120116, 0x001200A0, 0x001F01FF)
            privileges = ctypes.create_string_buffer(1024)
            privilege_bytes = ctypes.c_ulong(len(privileges))
            granted = ctypes.c_ulong()
            access_status = ctypes.c_int()
            ctypes.set_last_error(0)
            if not self._advapi32.AccessCheck(
                descriptor, token, desired_access, ctypes.byref(mapping), privileges,
                ctypes.byref(privilege_bytes), ctypes.byref(granted), ctypes.byref(access_status),
            ):
                return NativeAccessCheck(None, int(ctypes.get_last_error()))
            return NativeAccessCheck(
                bool(access_status.value and (granted.value & desired_access) == desired_access),
                None,
            )
        finally:
            if token.value:
                self.close(int(token.value))
            if descriptor.value:
                self._kernel32.LocalFree(descriptor)

    def _last_error(self) -> int:
        return int(ctypes.get_last_error())

    def open_volume_root(self, drive: str, *, writable: bool, read_control: bool = False) -> int:
        desired = _directory_access(writable, read_control=read_control)
        ctypes.set_last_error(0)
        handle = self._kernel32.CreateFileW(
            drive + "\\",
            desired,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_BACKUP_SEMANTICS | _FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        value = ctypes.c_void_p(handle).value
        if value in (None, _INVALID_HANDLE_VALUE):
            raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
        return int(value)

    def open_relative(
        self,
        parent_handle: int,
        name: str,
        *,
        directory: bool,
        create: bool,
        writable: bool,
        append_only: bool = False,
        read_control: bool = False,
        allow_subdirectories: bool = False,
    ) -> int:
        if append_only and not writable:
            raise _failure("NPI_PROMOTION_ACCESS_PROFILE_INVALID")
        safe_name = _safe_component(name)
        text = ctypes.create_unicode_buffer(safe_name)
        unicode = _UnicodeString(
            len(safe_name.encode("utf-16-le")),
            (len(safe_name) + 1) * ctypes.sizeof(ctypes.c_wchar),
            ctypes.cast(text, ctypes.c_wchar_p),
        )
        attributes = _ObjectAttributes(
            ctypes.sizeof(_ObjectAttributes),
            ctypes.c_void_p(parent_handle),
            ctypes.pointer(unicode),
            _OBJ_CASE_INSENSITIVE,
            None,
            None,
        )
        handle = ctypes.c_void_p()
        status = _IoStatusBlock()
        options = _FILE_SYNCHRONOUS_IO_NONALERT | _FILE_OPEN_REPARSE_POINT
        options |= _FILE_DIRECTORY_FILE if directory else _FILE_NON_DIRECTORY_FILE
        result = int(
            self._ntdll.NtCreateFile(
                ctypes.byref(handle),
                (
                    _directory_access(
                        writable,
                        append_only=append_only,
                        read_control=read_control,
                        allow_subdirectories=allow_subdirectories,
                    )
                    if directory
                    else _file_access(
                        writable, append_only=append_only, read_control=read_control
                    )
                ),
                ctypes.byref(attributes),
                ctypes.byref(status),
                None,
                0,
                _FILE_SHARE_READ | _FILE_SHARE_WRITE,
                _FILE_CREATE if create else _FILE_OPEN,
                options,
                None,
                0,
            )
        )
        if result >= 0 and handle.value not in (None, _INVALID_HANDLE_VALUE):
            return int(handle.value)
        status_code = _u32(result)
        if not create and status_code in {
            _STATUS_OBJECT_NAME_NOT_FOUND,
            _STATUS_OBJECT_PATH_NOT_FOUND,
        }:
            raise FileNotFoundError(safe_name)
        if create and status_code in {_STATUS_OBJECT_NAME_NOT_FOUND, _STATUS_OBJECT_PATH_NOT_FOUND}:
            raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")
        raise _failure("NPI_PROMOTION_RACE_DETECTED")

    def describe(self, handle: int) -> _HandleDescription:
        tag = _FileAttributeTagInfo()
        identity = _FileIdInfo()
        if not self._kernel32.GetFileInformationByHandleEx(
            ctypes.c_void_p(handle),
            _FILE_ATTRIBUTE_TAG_INFO,
            ctypes.byref(tag),
            ctypes.sizeof(tag),
        ):
            raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
        if not self._kernel32.GetFileInformationByHandleEx(
            ctypes.c_void_p(handle),
            _FILE_ID_INFO,
            ctypes.byref(identity),
            ctypes.sizeof(identity),
        ):
            raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
        final = self.final_path(handle)
        file_id = bytes(identity.FileId.Identifier).hex()
        return _HandleDescription(
            identity=BoundObjectIdentity(int(identity.VolumeSerialNumber), file_id, final),
            attributes=int(tag.FileAttributes),
            reparse_tag=int(tag.ReparseTag),
        )

    def final_path(self, handle: int) -> str:
        size = 512
        while size <= 32768:
            buffer = ctypes.create_unicode_buffer(size)
            result = int(
                self._kernel32.GetFinalPathNameByHandleW(
                    ctypes.c_void_p(handle), buffer, size, _VOLUME_NAME_GUID
                )
            )
            if result == 0:
                raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
            if result < size:
                return buffer.value.rstrip("\\").casefold()
            size = result + 1
        raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")

    def write(self, handle: int, data: bytes) -> None:
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + _CHUNK_BYTES]
            written = ctypes.c_ulong()
            buffer = ctypes.create_string_buffer(chunk)
            if not self._kernel32.WriteFile(
                ctypes.c_void_p(handle),
                buffer,
                len(chunk),
                ctypes.byref(written),
                None,
            ) or written.value != len(chunk):
                raise _failure("NPI_PROMOTION_RACE_DETECTED")
            offset += len(chunk)

    def read_chunks(self, handle: int) -> Iterator[bytes]:
        while True:
            buffer = ctypes.create_string_buffer(_CHUNK_BYTES)
            read = ctypes.c_ulong()
            if not self._kernel32.ReadFile(
                ctypes.c_void_p(handle), buffer, _CHUNK_BYTES, ctypes.byref(read), None
            ):
                error = self._last_error()
                if error == 38:  # ERROR_HANDLE_EOF
                    return
                raise _failure("NPI_PROMOTION_RACE_DETECTED")
            if read.value == 0:
                return
            yield buffer.raw[: read.value]

    def flush(self, handle: int) -> None:
        if not self._kernel32.FlushFileBuffers(ctypes.c_void_p(handle)):
            raise _failure("NPI_PROMOTION_RACE_DETECTED")

    def rename(self, handle: int, root_handle: int, destination_name: str) -> None:
        name = _safe_component(destination_name)
        name_bytes = name.encode("utf-16-le")
        size = _FileRenameInfo.FileName.offset + len(name_bytes)
        buffer = ctypes.create_string_buffer(size)
        info = ctypes.cast(buffer, ctypes.POINTER(_FileRenameInfo)).contents
        info.ReplaceIfExists = 0
        info.RootDirectory = root_handle
        info.FileNameLength = len(name_bytes)
        ctypes.memmove(
            ctypes.addressof(buffer) + _FileRenameInfo.FileName.offset, name_bytes, len(name_bytes)
        )
        status = _IoStatusBlock()
        result = int(
            self._ntdll.NtSetInformationFile(
                ctypes.c_void_p(handle),
                ctypes.byref(status),
                buffer,
                size,
                _FILE_RENAME_INFORMATION,
            )
        )
        if result >= 0:
            return
        # Sharing/identity failures are deliberately not distinguished for the
        # public caller; both are a race-safe refusal with no path disclosure.
        if _u32(result) in {0xC0000035, 0xC000000D}:
            raise FileExistsError(name)
        raise _failure("NPI_PROMOTION_RACE_DETECTED")

    def mark_delete(self, handle: int) -> None:
        info = _FileDispositionInfo(1)
        if not self._kernel32.SetFileInformationByHandle(
            ctypes.c_void_p(handle), _FILE_DISPOSITION_INFO, ctypes.byref(info), ctypes.sizeof(info)
        ):
            raise _failure("NPI_PROMOTION_RACE_DETECTED")

    def list_names(self, handle: int) -> set[str]:
        result: set[str] = set()
        restart = True
        while True:
            buffer = ctypes.create_string_buffer(65536)
            status = _IoStatusBlock()
            code = int(
                self._ntdll.NtQueryDirectoryFile(
                    ctypes.c_void_p(handle),
                    None,
                    None,
                    None,
                    ctypes.byref(status),
                    buffer,
                    len(buffer),
                    _FILE_NAMES_INFORMATION,
                    0,
                    None,
                    1 if restart else 0,
                )
            )
            restart = False
            if _u32(code) == _STATUS_NO_MORE_FILES:
                return result
            if code < 0:
                raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
            offset = 0
            total = int(status.Information)
            while offset < total:
                next_offset = int.from_bytes(buffer.raw[offset : offset + 4], "little")
                length = int.from_bytes(buffer.raw[offset + 8 : offset + 12], "little")
                name = buffer.raw[offset + 12 : offset + 12 + length].decode("utf-16-le")
                if name not in {".", ".."}:
                    result.add(name)
                if next_offset == 0:
                    break
                offset += next_offset


def _directory_access(
    writable: bool, *, append_only: bool = False, read_control: bool = False,
    allow_subdirectories: bool = False,
) -> int:
    base = _FILE_LIST_DIRECTORY | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE
    if writable:
        if append_only:
            base |= _FILE_ADD_FILE | _READ_CONTROL
            if allow_subdirectories:
                base |= _FILE_ADD_SUBDIRECTORY
        else:
            base |= _FILE_ADD_FILE | _FILE_ADD_SUBDIRECTORY | _FILE_DELETE_CHILD
            base |= _FILE_WRITE_ATTRIBUTES | _DELETE
    return base | (_READ_CONTROL if read_control else 0)


def _file_access(
    writable: bool, *, append_only: bool = False, read_control: bool = False
) -> int:
    base = _FILE_READ_DATA | _FILE_READ_ATTRIBUTES | _SYNCHRONIZE
    if writable:
        if append_only:
            return base | _FILE_APPEND_DATA | (_READ_CONTROL if read_control else 0)
        return base | _FILE_WRITE_DATA | _FILE_WRITE_ATTRIBUTES | _DELETE
    return base | (_READ_CONTROL if read_control else 0)


_TestHook = Callable[[str], None]
_test_hook: list[_TestHook | None] = [None]


def _install_test_hook(hook: _TestHook | None) -> None:
    """Private deterministic fault seam; production callers cannot pass it."""
    _test_hook[0] = hook


def _emit_test_hook(point: str) -> None:
    if _test_hook[0] is not None:
        _test_hook[0](point)


@dataclass
class BoundDirectory(AbstractContextManager["BoundDirectory"]):
    """An existing directory whose object identity is held live by a handle."""

    _native: _WindowsNative
    _handle: int
    _root: BoundDirectory | None
    _identity: BoundObjectIdentity
    _writable: bool
    _retained_ancestors: list[int] = field(default_factory=list)
    _closed: bool = False
    _append_only: bool = False
    _security_check: bool = False
    _allow_subdirectories: bool = False
    _parent: BoundDirectory | None = None

    @property
    def identity(self) -> BoundObjectIdentity:
        return self._identity

    def _verify(self) -> None:
        if self._closed:
            raise _failure("NPI_PROMOTION_BOUND_ROOT_IDENTITY_CHANGED")
        current = self._native.describe(self._handle)
        if current.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or current.reparse_tag:
            raise _failure("NPI_PROMOTION_REPARSE_POINT_REJECTED")
        if current.identity != self._identity:
            raise _failure("NPI_PROMOTION_BOUND_ROOT_IDENTITY_CHANGED")
        root = self._root or self
        if current.identity.volume_serial_number != root.identity.volume_serial_number:
            raise _failure("NPI_PROMOTION_VOLUME_IDENTITY_CHANGED")
        if self is not root and not current.identity.final_path.startswith(
            root.identity.final_path + "\\"
        ):
            raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")

    def open_directory(self, name: str, *, writable: bool | None = None) -> BoundDirectory:
        self._verify()
        child_writable = self._writable if writable is None else writable
        child_append_only = child_writable and self._append_only
        handle = self._native.open_relative(
            self._handle,
            name,
            directory=True,
            create=False,
            writable=child_writable,
            append_only=child_append_only,
            read_control=self._security_check,
        )
        return self._child_directory(
            handle, child_writable, append_only=child_append_only,
            security_check=self._security_check,
        )

    def create_directory(self, name: str) -> BoundDirectory:
        self._verify()
        if not self._writable:
            raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
        if self._append_only and not self._allow_subdirectories:
            raise _failure("NPI_PROMOTION_APPEND_ONLY_MUTATION_DENIED")
        handle = self._native.open_relative(
            self._handle, name, directory=True, create=True, writable=True,
            append_only=self._append_only,
            read_control=self._security_check,
        )
        return self._child_directory(
            handle, True, append_only=self._append_only, security_check=self._security_check
        )

    def _child_directory(
        self, handle: int, writable: bool, *, append_only: bool = False,
        security_check: bool = False,
    ) -> BoundDirectory:
        description = self._native.describe(handle)
        if description.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or description.reparse_tag:
            self._native.close(handle)
            raise _failure("NPI_PROMOTION_REPARSE_POINT_REJECTED")
        root = self._root or self
        if (
            description.identity.volume_serial_number != root.identity.volume_serial_number
            or not description.identity.final_path.startswith(root.identity.final_path + "\\")
        ):
            self._native.close(handle)
            raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")
        return BoundDirectory(
            self._native, handle, root, description.identity, writable,
            _append_only=append_only, _security_check=security_check,
            _parent=self,
        )

    def open_file(self, name: str) -> BoundFile:
        self._verify()
        handle = self._native.open_relative(
            self._handle, name, directory=False, create=False, writable=False
        )
        return self._child_file(handle, False)

    def create_file(self, name: str) -> BoundFile:
        self._verify()
        if not self._writable:
            raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
        if self._append_only and (
            self._allow_subdirectories
            or not isinstance(name, str)
            or (name != "reservation.json" and _REAL20_TERMINAL_FILE_NAME.fullmatch(name) is None)
        ):
            raise _failure("NPI_PROMOTION_APPEND_ONLY_NAME_DENIED")
        handle = self._native.open_relative(
            self._handle, name, directory=False, create=True, writable=True,
            append_only=self._append_only,
            read_control=self._security_check,
        )
        file = self._child_file(handle, True, append_only=self._append_only)
        if self._append_only and self._security_check:
            try:
                for right in (_FILE_WRITE_DATA, _DELETE, _WRITE_DAC, _WRITE_OWNER):
                    result = file.access_check(right)
                    if result.granted is not False or result.win32_error is not None:
                        raise _failure("NPI_PROMOTION_APPEND_ONLY_DACL_NOT_DENIED")
            except BaseException:
                file.close()
                raise
        return file

    def _child_file(
        self, handle: int, writable: bool, *, append_only: bool = False
    ) -> BoundFile:
        description = self._native.describe(handle)
        root = self._root or self
        if description.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or description.reparse_tag:
            self._native.close(handle)
            raise _failure("NPI_PROMOTION_REPARSE_POINT_REJECTED")
        if description.identity.volume_serial_number != root.identity.volume_serial_number:
            self._native.close(handle)
            raise _failure("NPI_PROMOTION_VOLUME_IDENTITY_CHANGED")
        if not description.identity.final_path.startswith(root.identity.final_path + "\\"):
            self._native.close(handle)
            raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")
        return BoundFile(
            self._native, handle, root, description.identity, writable,
            _append_only=append_only,
        )

    def list_names(self) -> set[str]:
        self._verify()
        return self._native.list_names(self._handle)

    def access_check(self, desired_access: int) -> NativeAccessCheck:
        self._verify()
        return self._native.access_check(self._handle, desired_access)

    def parent_access_check(self, desired_access: int) -> NativeAccessCheck:
        self._verify()
        if self._parent is not None:
            self._parent._verify()
            handle = self._parent._handle
        elif self._root is None and self._retained_ancestors:
            handle = self._retained_ancestors[-1]
        else:
            return NativeAccessCheck(None, 87)
        return self._native.access_check(handle, desired_access)

    def rename_to(self, destination_root: BoundDirectory, destination_name: str) -> None:
        self._verify()
        destination_root._verify()
        if self._append_only or destination_root._append_only:
            raise _failure("NPI_PROMOTION_APPEND_ONLY_MUTATION_DENIED")
        source_root = self._root or self
        target_root = destination_root._root or destination_root
        if source_root is not target_root:
            raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")
        if self.identity.volume_serial_number != destination_root.identity.volume_serial_number:
            raise _failure("NPI_PROMOTION_VOLUME_IDENTITY_CHANGED")
        self._native.rename(self._handle, destination_root._handle, destination_name)
        published = self._native.describe(self._handle)
        if published.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or published.reparse_tag:
            raise _failure("NPI_PROMOTION_REPARSE_POINT_REJECTED")
        if (
            published.identity.volume_serial_number
            != destination_root.identity.volume_serial_number
        ):
            raise _failure("NPI_PROMOTION_VOLUME_IDENTITY_CHANGED")
        if published.identity.file_id_hex != self.identity.file_id_hex:
            raise _failure("NPI_PROMOTION_BOUND_ROOT_IDENTITY_CHANGED")
        if not published.identity.final_path.startswith(
            destination_root.identity.final_path + "\\"
        ):
            raise _failure("NPI_PROMOTION_PATH_ESCAPED_BOUND_ROOT")
        self._identity = published.identity

    def delete_owned_empty(self) -> None:
        """Delete only this already-bound, empty transaction directory."""
        self._verify()
        if self._append_only:
            raise _failure("NPI_PROMOTION_APPEND_ONLY_MUTATION_DENIED")
        if self.list_names():
            raise _failure("NPI_PROMOTION_RACE_DETECTED")
        self._native.mark_delete(self._handle)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._native.close(self._handle)
        for ancestor in reversed(self._retained_ancestors):
            self._native.close(ancestor)
        self._retained_ancestors.clear()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


@dataclass
class BoundFile(AbstractContextManager["BoundFile"]):
    _native: _WindowsNative
    _handle: int
    _root: BoundDirectory
    _identity: BoundObjectIdentity
    _writable: bool
    _closed: bool = False
    _append_only: bool = False

    @property
    def identity(self) -> BoundObjectIdentity:
        return self._identity

    def _verify(self) -> None:
        if self._closed:
            raise _failure("NPI_PROMOTION_BOUND_ROOT_IDENTITY_CHANGED")
        self._root._verify()
        current = self._native.describe(self._handle)
        if current.identity != self._identity:
            raise _failure("NPI_PROMOTION_BOUND_ROOT_IDENTITY_CHANGED")
        if current.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or current.reparse_tag:
            raise _failure("NPI_PROMOTION_REPARSE_POINT_REJECTED")
        if current.identity.volume_serial_number != self._root.identity.volume_serial_number:
            raise _failure("NPI_PROMOTION_VOLUME_IDENTITY_CHANGED")

    def write(self, data: bytes) -> None:
        self._verify()
        if not self._writable:
            raise _failure("NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
        self._native.write(self._handle, data)

    def access_check(self, desired_access: int) -> NativeAccessCheck:
        self._verify()
        return self._native.access_check(self._handle, desired_access)

    def flush(self) -> None:
        self._verify()
        self._native.flush(self._handle)

    def sha256_and_size(self) -> tuple[str, int]:
        self._verify()
        digest = hashlib.sha256()
        size = 0
        for chunk in self.iter_chunks():
            digest.update(chunk)
            size += len(chunk)
        return digest.hexdigest(), size

    def iter_chunks(self) -> Iterator[bytes]:
        self._verify()
        yield from self._native.read_chunks(self._handle)
        self._verify()

    def read_all(self, *, max_bytes: int) -> bytes:
        chunks: list[bytes] = []
        size = 0
        for chunk in self.iter_chunks():
            size += len(chunk)
            if size > max_bytes:
                raise _failure("NPI_PROMOTION_RACE_DETECTED")
            chunks.append(chunk)
        return b"".join(chunks)

    def delete_owned(self) -> None:
        self._verify()
        if self._append_only:
            raise _failure("NPI_PROMOTION_APPEND_ONLY_MUTATION_DENIED")
        self._native.mark_delete(self._handle)

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._native.close(self._handle)

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


def bind_existing_directory(
    path: Path, *, writable: bool, append_only: bool = False, security_check: bool = False
) -> BoundDirectory:
    """Bind every existing component of an absolute local path by handle."""
    _require_windows()
    if append_only and not writable:
        raise _failure("NPI_PROMOTION_ACCESS_PROFILE_INVALID")
    normalized = normalize_windows_path(path)
    drive, tail = ntpath.splitdrive(normalized)
    parts = [part for part in tail.split("\\") if part]
    native = _WindowsNative()
    handles: list[int] = []
    try:
        # The volume and every ancestor are only traversal anchors.  Requesting
        # write access there is both unnecessary and liable to fail under a
        # correctly restricted parent ACL; only the final bound root can write.
        volume = native.open_volume_root(drive, writable=False, read_control=security_check)
        handles.append(volume)
        current = volume
        for index, part in enumerate(parts):
            current = native.open_relative(
                current,
                part,
                directory=True,
                create=False,
                writable=writable and index == len(parts) - 1,
                append_only=append_only and index == len(parts) - 1,
                read_control=security_check,
                allow_subdirectories=append_only and index == len(parts) - 1,
            )
            description = native.describe(current)
            if description.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or description.reparse_tag:
                native.close(current)
                raise _failure("NPI_PROMOTION_REPARSE_POINT_REJECTED")
            handles.append(current)
        description = native.describe(current)
        if description.attributes & _FILE_ATTRIBUTE_REPARSE_POINT or description.reparse_tag:
            raise _failure("NPI_PROMOTION_REPARSE_POINT_REJECTED")
        return BoundDirectory(
            native,
            current,
            None,
            description.identity,
            writable,
            _retained_ancestors=handles[:-1],
            _append_only=append_only,
            _security_check=security_check,
            _allow_subdirectories=append_only,
        )
    except Exception:
        for handle in reversed(handles):
            native.close(handle)
        raise


@dataclass
class BoundStagingTransaction(AbstractContextManager["BoundStagingTransaction"]):
    """A random, handle-bound staging directory under one cache root."""

    cache_root: BoundDirectory
    staging_parent: BoundDirectory
    staging: BoundDirectory
    _staging_parent_owned: bool = False
    _published: bool = False
    _owned_file_names: set[str] = field(default_factory=set)

    @classmethod
    def create(cls, cache_root: BoundDirectory) -> BoundStagingTransaction:
        cache_root._verify()
        staging_parent_owned = False
        try:
            staging_parent = cache_root.open_directory(".staging", writable=True)
        except FileNotFoundError:
            staging_parent = cache_root.create_directory(".staging")
            staging_parent_owned = True
        staging: BoundDirectory | None = None
        try:
            _emit_test_hook("after_root_binding")
            cache_root._verify()
            staging_parent._verify()
            transaction_name = secrets.token_hex(16)
            staging = staging_parent.create_directory(transaction_name)
            _emit_test_hook("after_staging_creation")
            cache_root._verify()
            staging_parent._verify()
            staging._verify()
            return cls(cache_root, staging_parent, staging, staging_parent_owned)
        except Exception:
            if staging is not None:
                with suppress(NpiError):
                    staging.delete_owned_empty()
                staging.close()
            if staging_parent_owned:
                try:
                    if not staging_parent.list_names():
                        staging_parent.delete_owned_empty()
                except NpiError:
                    pass
            staging_parent.close()
            raise

    def create_file(self, name: str) -> BoundFile:
        _emit_test_hook("before_payload_open")
        self.cache_root._verify()
        self.staging_parent._verify()
        self.staging._verify()
        created = self.staging.create_file(name)
        self._owned_file_names.add(name)
        return created

    def publish(self, final_name: str) -> None:
        _emit_test_hook("before_final_publication")
        self.cache_root._verify()
        self.staging_parent._verify()
        self.staging._verify()
        self.staging.rename_to(self.cache_root, final_name)
        self._published = True
        self.staging._verify()
        _emit_test_hook("after_publication_handle_creation")
        self.cache_root._verify()
        self.staging.close()

    def close(self) -> None:
        if not self._published:
            try:
                for name in sorted(self._owned_file_names):
                    with self.staging.open_file(name) as file:
                        file.delete_owned()
                if not self.staging.list_names():
                    self.staging.delete_owned_empty()
            except NpiError:
                pass
        self.staging.close()
        if self._staging_parent_owned:
            try:
                if not self.staging_parent.list_names():
                    self.staging_parent.delete_owned_empty()
            except NpiError:
                pass
        self.staging_parent.close()
        self.cache_root.close()

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()
