"""Non-mutating Windows effective-access capability checks."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.errors import SourceReadOnlyNotVerifiedError
from nightly_photo_intelligence_pipeline.ingest.read_only_capability import (
    CapabilityDisposition,
    verify_source_read_only_capability,
)


def _source(tmp_path: Path) -> tuple[Path, list[Path]]:
    root = tmp_path / "source"
    root.mkdir()
    files = []
    for index in range(20):
        path = root / f"synthetic-{index:02d}.bin"
        path.write_bytes(f"fixture-{index}".encode())
        files.append(path)
    return root, files


def test_all_mutating_capabilities_denied_is_verified(tmp_path: Path) -> None:
    root, files = _source(tmp_path)
    calls: list[tuple[str, int]] = []

    def denied(_path: Path, kind: str, mask: int) -> CapabilityDisposition:
        calls.append((kind, mask))
        return CapabilityDisposition.DENIED

    result = verify_source_read_only_capability(root, files, probe=denied)
    assert result.verified
    assert result.checked_entries == 20
    assert result.granted == ()
    assert result.unknown == ()
    assert any(kind == "file" for kind, _ in calls)
    assert any(kind == "directory" for kind, _ in calls)


@pytest.mark.parametrize(
    ("grant_kind", "expected_status"),
    [("file", "FAIL"), ("directory", "FAIL")],
)
def test_any_grant_fails_closed(tmp_path: Path, grant_kind: str, expected_status: str) -> None:
    root, files = _source(tmp_path)

    def partly_granted(_path: Path, kind: str, _mask: int) -> CapabilityDisposition:
        if kind == grant_kind:
            return CapabilityDisposition.GRANTED
        return CapabilityDisposition.DENIED

    result = verify_source_read_only_capability(root, files, probe=partly_granted)
    assert result.status == expected_status
    with pytest.raises(SourceReadOnlyNotVerifiedError):
        result.require_verified()


def test_unknown_or_missing_entry_is_not_verified(tmp_path: Path) -> None:
    root, files = _source(tmp_path)

    def unknown(_path: Path, _kind: str, _mask: int) -> CapabilityDisposition:
        return CapabilityDisposition.NOT_VERIFIED

    assert verify_source_read_only_capability(root, files, probe=unknown).status == "NOT_VERIFIED"
    files[-1].unlink()
    result = verify_source_read_only_capability(
        root,
        files,
        probe=lambda *_: CapabilityDisposition.DENIED,
    )
    assert result.status == "NOT_VERIFIED"
    assert result.checked_entries == 19


def test_probe_exception_is_not_verified_without_leaking_native_error(tmp_path: Path) -> None:
    root, files = _source(tmp_path)

    def indeterminate(*_args):
        raise OSError("F:\\private\\real-name.jpg access check failed")

    result = verify_source_read_only_capability(root, files, probe=indeterminate)
    assert result.status == "NOT_VERIFIED"
    assert result.unknown
    assert "private" not in str(result)
    assert "real-name" not in str(result)


@pytest.mark.parametrize("malformed", [None, "DENIED", "GRANTED", object()])
def test_malformed_probe_result_is_not_verified(tmp_path: Path, malformed: object) -> None:
    root, files = _source(tmp_path)
    result = verify_source_read_only_capability(
        root,
        files,
        probe=lambda *_: malformed,  # type: ignore[return-value]
    )
    assert result.status == "NOT_VERIFIED"
    assert not result.verified


def test_nested_parent_chain_gets_complete_directory_rights(tmp_path: Path) -> None:
    root = tmp_path / "source"
    nested = root / "level-a" / "level-b"
    nested.mkdir(parents=True)
    candidate = nested / "synthetic.bin"
    candidate.write_bytes(b"synthetic")
    calls: list[tuple[Path, str, int]] = []

    def denied(path: Path, kind: str, mask: int) -> CapabilityDisposition:
        calls.append((path, kind, mask))
        return CapabilityDisposition.DENIED

    result = verify_source_read_only_capability(root, [candidate], probe=denied)
    assert result.verified
    directory_masks = {
        path: {
            mask for called_path, kind, mask in calls if kind == "directory" and called_path == path
        }
        for path in (root, root / "level-a", nested)
    }
    assert all(len(masks) == 8 for masks in directory_masks.values())


@pytest.mark.skipif(sys.platform != "win32", reason="Windows CreateFileW access check")
def test_native_probe_does_not_modify_writable_synthetic_source(tmp_path: Path) -> None:
    root, files = _source(tmp_path)
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    result = verify_source_read_only_capability(root, files)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    assert result.status == "FAIL", "temporary source is writable and must not verify read-only"
    assert result.granted
    assert before == after
    assert sorted(path.name for path in root.iterdir()) == sorted(before)
