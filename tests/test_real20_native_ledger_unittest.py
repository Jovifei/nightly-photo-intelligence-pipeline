"""Stdlib-only Windows acceptance probes for the append-only Real20 ledger."""
from __future__ import annotations

import ctypes
import hashlib
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path

from nightly_photo_intelligence_pipeline.domain.errors import NpiError
from nightly_photo_intelligence_pipeline.engineering.common import canonical
from nightly_photo_intelligence_pipeline.windows_bound_promotion import (
    _directory_access,
    _file_access,
    bind_existing_directory,
)


_FORBIDDEN_LEDGER_HANDLE_RIGHTS = 0x000D0040


def _reservation_bytes(credential_sha: str) -> bytes:
    return canonical(
        {
            "schema_version": "npi-real20-consumption-v1",
            "status": "RESERVED",
            "credential_sha256": credential_sha,
            "bindings_sha256": "b" * 64,
            "reserved_at_utc": "2026-09-24T00:00:00+00:00",
        }
    )


class _ObjectBasicInformation(ctypes.Structure):
    _fields_ = [
        ("Attributes", ctypes.c_ulong),
        ("GrantedAccess", ctypes.c_ulong),
        ("HandleCount", ctypes.c_ulong),
        ("PointerCount", ctypes.c_ulong),
        ("PagedPoolCharge", ctypes.c_ulong),
        ("NonPagedPoolCharge", ctypes.c_ulong),
        ("Reserved", ctypes.c_ulong * 3),
        ("NameInfoSize", ctypes.c_ulong),
        ("TypeInfoSize", ctypes.c_ulong),
        ("SecurityDescriptorSize", ctypes.c_ulong),
        ("CreateTime", ctypes.c_longlong),
    ]


def _granted_access(handle: int) -> int:
    ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
    query = ntdll.NtQueryObject
    query.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    query.restype = ctypes.c_long
    info = _ObjectBasicInformation()
    returned = ctypes.c_ulong()
    status = int(
        query(
            ctypes.c_void_p(handle),
            0,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(returned),
        )
    )
    if status < 0:
        raise OSError(status, "NtQueryObject(ObjectBasicInformation) failed")
    return int(info.GrantedAccess)


def _load_ledger_module():
    package_name = "nightly_photo_intelligence_pipeline.real20"
    try:
        return importlib.import_module(package_name + ".ledger")
    except ModuleNotFoundError as exc:
        if exc.name != "PIL":
            raise
        # Minimal local Python 3.12 lacks Pillow; load the pure ledger submodule
        # without importing the unrelated model runner. Full pytest imports use
        # the normal package path and do not take this branch.
        sys.modules.pop(package_name, None)
        package = types.ModuleType(package_name)
        package.__path__ = [
            str(
                Path(__file__).resolve().parents[1]
                / "src/nightly_photo_intelligence_pipeline/real20"
            )
        ]
        package.__package__ = package_name
        sys.modules[package_name] = package
        return importlib.import_module(package_name + ".ledger")


def _load_admission_module():
    package_name = "nightly_photo_intelligence_pipeline.real20.admission"
    try:
        return importlib.import_module(package_name)
    except ModuleNotFoundError as exc:
        if exc.name != "yaml":
            raise
        yaml = types.ModuleType("yaml")
        yaml.YAMLError = ValueError
        yaml.safe_load = lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("YAML parsing is outside this native ledger test")
        )
        sys.modules["yaml"] = yaml
        return importlib.import_module(package_name)


class TestAppendOnlyAccessMask(unittest.TestCase):
    def test_append_only_profile_requests_creation_and_write_without_delete(self) -> None:
        directory_mask = _directory_access(
            True, append_only=True, allow_subdirectories=True
        )
        claim_mask = _directory_access(True, append_only=True, allow_subdirectories=False)
        file_mask = _file_access(True, append_only=True)

        self.assertEqual(directory_mask, 0x00120087)
        self.assertEqual(claim_mask, 0x00120083)
        self.assertEqual(file_mask, 0x00100085)
        self.assertEqual(file_mask & 0x00000002, 0)
        self.assertNotEqual(file_mask & 0x00000004, 0)
        self.assertEqual(directory_mask & 0x00010040, 0)
        self.assertEqual(file_mask & 0x00010000, 0)

    def test_existing_mutable_profile_remains_available_for_cache_staging(self) -> None:
        self.assertEqual(_directory_access(True), 0x001101C7)
        self.assertEqual(_file_access(True), 0x00110183)

    def test_secured_append_file_refuses_mutable_inherited_file_dacl(self) -> None:
        with tempfile.TemporaryDirectory(prefix="npi-real20-file-dacl-") as temp:
            ledger_path = Path(temp) / "ledger"
            ledger_path.mkdir()
            with bind_existing_directory(
                ledger_path, writable=True, append_only=True, security_check=True
            ) as ledger:
                with ledger.create_directory("a" * 64) as claim:
                    with self.assertRaisesRegex(NpiError, "APPEND_ONLY_DACL_NOT_DENIED"):
                        claim.create_file("reservation.json")
                    self.assertIn("reservation.json", claim.list_names())
                    with claim.open_file("reservation.json") as empty_file:
                        self.assertEqual(empty_file.read_all(max_bytes=16), b"")

    def test_bound_append_only_claim_writes_and_reopens_without_delete_rights(self) -> None:
        with tempfile.TemporaryDirectory(prefix="npi-real20-append-only-") as temp:
            ledger_path = Path(temp) / "ledger"
            ledger_path.mkdir()
            claim_name = "a" * 64
            reservation_bytes = _reservation_bytes(claim_name)
            with bind_existing_directory(ledger_path, writable=True, append_only=True) as ledger:
                self.assertEqual(_granted_access(ledger._handle) & _FORBIDDEN_LEDGER_HANDLE_RIGHTS, 0)
                with self.assertRaisesRegex(NpiError, "APPEND_ONLY_NAME_DENIED"):
                    ledger.create_file("unscoped.json")
                with ledger.create_directory(claim_name) as claim:
                    self.assertEqual(_granted_access(claim._handle) & _FORBIDDEN_LEDGER_HANDLE_RIGHTS, 0)
                    self.assertEqual(_granted_access(claim._handle) & 0x00000004, 0)
                    with self.assertRaises(NpiError):
                        claim.create_directory("nested")
                    with self.assertRaisesRegex(NpiError, "APPEND_ONLY_NAME_DENIED"):
                        claim.create_file("unscoped.json")
                    with claim.create_file("reservation.json") as reservation:
                        access = _granted_access(reservation._handle)
                        self.assertEqual(access & 0x00010000, 0)
                        self.assertEqual(access & 0x00000002, 0)
                        self.assertNotEqual(access & 0x00000004, 0)
                        reservation.write(reservation_bytes)
                        reservation.flush()
                    with claim.open_file("reservation.json") as reservation:
                        self.assertEqual(reservation.read_all(max_bytes=4096), reservation_bytes)
                    with self.assertRaises(NpiError):
                        claim.delete_owned_empty()
                    with self.assertRaises(NpiError):
                        claim.rename_to(ledger, "renamed-claim")
                    claim_identity = claim.identity
                with ledger.open_directory(claim_name, writable=True) as reopened:
                    self.assertEqual(reopened.identity, claim_identity)
                    with reopened.open_file("reservation.json") as reservation:
                        self.assertEqual(reservation.read_all(max_bytes=4096), reservation_bytes)
            self.assertEqual(
                (ledger_path / claim_name / "reservation.json").read_bytes(), reservation_bytes
            )

    def test_bound_effective_access_query_checks_target_and_parent_handles(self) -> None:
        with tempfile.TemporaryDirectory(prefix="npi-real20-access-check-") as temp:
            ledger_path = Path(temp) / "ledger"
            ledger_path.mkdir()
            credential_sha = "e" * 64
            parent_security = self._open_security_handle(Path(temp))
            ledger_security = self._open_security_handle(ledger_path)
            claim_security = None
            claim = None
            try:
                self._set_dacl(
                    parent_security,
                    "D:P(D;;0x00000040;;;WD)(D;;0x00080000;;;WD)"
                    "(D;;0x00040000;;;OW)(A;;0x00120087;;;WD)",
                )
                self._set_dacl(
                    ledger_security,
                    "D:P(D;;0x000D0040;;;WD)(D;;0x00040000;;;OW)"
                    "(D;CI;0x00090040;;;WD)"
                    "(D;OIIO;0x000D0002;;;WD)(D;OIIO;0x00040000;;;OW)"
                    "(A;;0x00120087;;;WD)(A;CI;0x00120083;;;WD)"
                    "(A;OIIO;0x00120085;;;WD)",
                )
                with bind_existing_directory(
                    ledger_path, writable=True, append_only=True, security_check=True
                ) as ledger:
                    for right in (0x00000040, 0x00010000, 0x00040000, 0x00080000):
                        result = ledger.access_check(right)
                        self.assertIs(result.granted, False, msg=f"right={right:#x} result={result!r}")
                        self.assertIsNone(result.win32_error)
                    for right in (0x00000040, 0x00040000, 0x00080000):
                        parent = ledger.parent_access_check(right)
                        self.assertIs(parent.granted, False)
                        self.assertIsNone(parent.win32_error)
                    _load_admission_module().protect_consumption(ledger)
                    ledger_api = _load_ledger_module()
                    claim = ledger.create_directory(credential_sha)
                    claim_write_dac = claim.access_check(0x00040000)
                    self.assertIs(claim_write_dac.granted, True)
                    self.assertIsNone(claim_write_dac.win32_error)
                    claim_security = self._open_security_handle(ledger_path / credential_sha)
                    # Simulate the Owner-provisioned per-claim ACL; the runner never changes ACLs.
                    self._set_dacl(
                        claim_security,
                        "D:P(D;;0x000D0040;;;WD)(D;;0x00040000;;;OW)"
                        "(D;OIIO;0x000D0002;;;WD)(D;OIIO;0x00040000;;;OW)"
                        "(A;;0x00120083;;;WD)(A;OIIO;0x00120085;;;WD)",
                    )
                    self.assertEqual(
                        _granted_access(claim._handle) & _FORBIDDEN_LEDGER_HANDLE_RIGHTS, 0
                    )
                    self.assertEqual(_granted_access(claim._handle) & 0x00000004, 0)
                    for right in (0x00000040, 0x00010000, 0x00040000, 0x00080000):
                        result = claim.access_check(right)
                        self.assertIs(result.granted, False, msg=f"claim right={right:#x}")
                        self.assertIsNone(result.win32_error)
                    _load_admission_module().protect_consumption(claim)
                    reservation_bytes = _reservation_bytes(credential_sha)
                    claim_parent = claim.parent_access_check(0x00000040)
                    self.assertIs(claim_parent.granted, False)
                    self.assertIsNone(claim_parent.win32_error)
                    with claim.create_file("reservation.json") as handle:
                        access = _granted_access(handle._handle)
                        self.assertEqual(access & 0x00000002, 0)
                        self.assertNotEqual(access & 0x00000004, 0)
                        self.assertNotEqual(access & 0x00020000, 0)
                        for right in (0x00000002, 0x00010000, 0x00040000, 0x00080000):
                            result = handle.access_check(right)
                            self.assertIs(result.granted, False)
                            self.assertIsNone(result.win32_error)
                        handle.write(reservation_bytes)
                        handle.flush()
                    terminal = ledger_api.append_terminal_record(
                        ledger,
                        claim,
                        credential_sha,
                        status="COMPLETE",
                        evidence_sha="f" * 64,
                        evidence_status="PERSISTED",
                    )
                    self.assertEqual(terminal["status"], "COMPLETE")
                    with ledger.open_directory(credential_sha, writable=True) as reopened:
                        self.assertEqual(
                            ledger_api.read_terminal_record(reopened, credential_sha), terminal
                        )
            finally:
                if claim is not None:
                    claim.close()
                if claim_security is not None:
                    self._set_dacl(claim_security, "D:P(A;OICI;GA;;;WD)")
                self._set_dacl(ledger_security, "D:P(A;OICI;GA;;;WD)")
                self._set_dacl(parent_security, "D:P(A;OICI;GA;;;WD)")
                kernel = ctypes.WinDLL("kernel32", use_last_error=True)
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel.CloseHandle.restype = ctypes.c_int
                kernel.CloseHandle(ledger_security)
                if claim_security is not None:
                    kernel.CloseHandle(claim_security)
                kernel.CloseHandle(parent_security)

    @staticmethod
    def _open_security_handle(path: Path) -> int:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateFileW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
            ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p,
        ]
        kernel.CreateFileW.restype = ctypes.c_void_p
        handle = kernel.CreateFileW(str(path), 0x00040000, 7, None, 3, 0x02000000, None)
        if handle in (None, ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(handle)

    @staticmethod
    def _set_dacl(handle: int, sddl: str) -> None:
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        descriptor = ctypes.c_void_p()
        convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
        convert.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        convert.restype = ctypes.c_int
        set_security = advapi.SetKernelObjectSecurity
        set_security.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
        set_security.restype = ctypes.c_int
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree.restype = ctypes.c_void_p
        if not convert(sddl, 1, ctypes.byref(descriptor), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            if not set_security(handle, 0x00000004, descriptor):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.LocalFree(descriptor)

    def test_versioned_terminal_writer_reopens_and_rejects_uncommitted_record(self) -> None:
        ledger_api = _load_ledger_module()
        with tempfile.TemporaryDirectory(prefix="npi-real20-terminal-") as temp:
            ledger_path = Path(temp) / "ledger"
            ledger_path.mkdir()
            credential_sha = "a" * 64
            evidence_sha = "b" * 64
            with bind_existing_directory(ledger_path, writable=True, append_only=True) as ledger:
                claim = ledger.create_directory(credential_sha)
                with claim.create_file("reservation.json") as reservation:
                    reservation.write(_reservation_bytes(credential_sha))
                    reservation.flush()
                with self.assertRaisesRegex(ValueError, "TERMINAL_EVIDENCE_INVALID"):
                    ledger_api.append_terminal_record(
                        ledger,
                        claim,
                        credential_sha,
                        status="COMPLETE",
                        evidence_sha=None,
                        evidence_status="PERSISTENCE_FAILED",
                    )
                terminal = ledger_api.append_terminal_record(
                    ledger,
                    claim,
                    credential_sha,
                    status="COMPLETE",
                    evidence_sha=evidence_sha,
                    evidence_status="PERSISTED",
                )
                self.assertEqual(terminal["status"], "COMPLETE")
                self.assertEqual(terminal["schema_version"], "npi-real20-ledger-terminal-v1")
                self.assertTrue(claim._closed, "terminal writer must close before reopen verification")
                with ledger.open_directory(credential_sha, writable=True) as reopened:
                    self.assertEqual(ledger_api.read_terminal_record(reopened, credential_sha), terminal)
                    with self.assertRaisesRegex(ValueError, "TERMINAL_ALREADY_STARTED"):
                        ledger_api.append_terminal_record(
                            ledger,
                            reopened,
                            credential_sha,
                            status="FAILED",
                            evidence_sha=None,
                            evidence_status="PERSISTENCE_FAILED",
                        )

                failed_credential = "c" * 64
                partial_reservation = b'{"credential_sha256":'
                failed_claim = ledger.create_directory(failed_credential)
                with failed_claim.create_file("reservation.json") as reservation:
                    reservation.write(partial_reservation)
                    reservation.flush()
                failed = ledger_api.append_terminal_record(
                    ledger,
                    failed_claim,
                    failed_credential,
                    status="FAILED",
                    evidence_sha=None,
                    evidence_status="RESERVATION_RECORD_FAILED",
                )
                self.assertEqual(failed["status"], "FAILED")
                self.assertEqual(
                    failed["reservation_sha256"], hashlib.sha256(partial_reservation).hexdigest()
                )

                partial_claim = ledger.create_directory("d" * 64)
                try:
                    partial_name = "terminal-v1-" + ("c" * 64) + ".json"
                    with partial_claim.create_file(partial_name) as partial:
                        partial.write(b'{"schema_version":"npi-real20-ledger-terminal-v1"')
                        partial.flush()
                    with self.assertRaisesRegex(ValueError, "TERMINAL_COMMIT_MISSING"):
                        ledger_api.read_terminal_record(partial_claim, "d" * 64)
                finally:
                    partial_claim.close()

    def test_terminal_reader_rejects_complete_without_persisted_evidence(self) -> None:
        from nightly_photo_intelligence_pipeline.engineering.common import canonical, sha256

        ledger_api = _load_ledger_module()
        with tempfile.TemporaryDirectory(prefix="npi-real20-terminal-evidence-") as temp:
            ledger_path = Path(temp) / "ledger"
            ledger_path.mkdir()
            credential_sha = "a" * 64
            with bind_existing_directory(ledger_path, writable=True, append_only=True) as ledger:
                with ledger.create_directory(credential_sha) as claim:
                    reservation_bytes = _reservation_bytes(credential_sha)
                    with claim.create_file("reservation.json") as reservation:
                        reservation.write(reservation_bytes)
                        reservation.flush()
                    record = {
                        "schema_version": "npi-real20-ledger-terminal-v1",
                        "credential_sha256": credential_sha,
                        "reservation_sha256": sha256(reservation_bytes),
                        "status": "COMPLETE",
                        "evidence_status": "PERSISTENCE_FAILED",
                        "evidence_sha256": None,
                        "finished_at_utc": "2026-09-24T00:00:00+00:00",
                    }
                    record_bytes = canonical(record)
                    record_sha = sha256(record_bytes)
                    record_name = "terminal-v1-" + record_sha + ".json"
                    commit = {
                        "schema_version": "npi-real20-ledger-terminal-commit-v1",
                        "credential_sha256": credential_sha,
                        "record_name": record_name,
                        "record_sha256": record_sha,
                    }
                    with claim.create_file(record_name) as handle:
                        handle.write(record_bytes)
                        handle.flush()
                    with claim.create_file("terminal-commit-v1-" + record_sha + ".json") as handle:
                        handle.write(canonical(commit))
                        handle.flush()
                    with self.assertRaisesRegex(ValueError, "TERMINAL_EVIDENCE_INVALID"):
                        ledger_api.read_terminal_record(claim, credential_sha)

    def test_terminal_reader_rejects_complete_without_reservation(self) -> None:
        from nightly_photo_intelligence_pipeline.engineering.common import sha256

        ledger_api = _load_ledger_module()
        with tempfile.TemporaryDirectory(prefix="npi-real20-terminal-reservation-") as temp:
            ledger_path = Path(temp) / "ledger"
            ledger_path.mkdir()
            credential_sha = "a" * 64
            with bind_existing_directory(ledger_path, writable=True, append_only=True) as ledger:
                with ledger.create_directory(credential_sha) as claim:
                    record = {
                        "schema_version": "npi-real20-ledger-terminal-v1",
                        "credential_sha256": credential_sha,
                        "reservation_sha256": None,
                        "status": "COMPLETE",
                        "evidence_status": "PERSISTED",
                        "evidence_sha256": "f" * 64,
                        "finished_at_utc": "2026-09-24T00:00:00+00:00",
                    }
                    record_bytes = canonical(record)
                    record_sha = sha256(record_bytes)
                    record_name = "terminal-v1-" + record_sha + ".json"
                    commit = {
                        "schema_version": "npi-real20-ledger-terminal-commit-v1",
                        "credential_sha256": credential_sha,
                        "record_name": record_name,
                        "record_sha256": record_sha,
                    }
                    with claim.create_file(record_name) as handle:
                        handle.write(record_bytes)
                        handle.flush()
                    with claim.create_file("terminal-commit-v1-" + record_sha + ".json") as handle:
                        handle.write(canonical(commit))
                        handle.flush()
                    with self.assertRaisesRegex(ValueError, "TERMINAL_RESERVATION_INVALID"):
                        ledger_api.read_terminal_record(claim, credential_sha)


if __name__ == "__main__":
    unittest.main()
