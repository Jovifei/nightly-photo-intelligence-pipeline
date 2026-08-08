"""Windows N2B1P promotion paths remain bound to live native handles."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.errors import NpiError, PromotionPathSafetyError
from nightly_photo_intelligence_pipeline.windows_bound_promotion import (
    BoundStagingTransaction,
    _install_test_hook,
    bind_existing_directory,
)


def _write_bound(transaction: BoundStagingTransaction, name: str = "payload.bin") -> None:
    with transaction.create_file(name) as payload:
        payload.write(b"bound-bytes")
        payload.flush()


def _assert_code(error: pytest.ExceptionInfo[NpiError], code: str) -> None:
    assert error.value.error_code == code


def test_handle_bound_staging_publishes_without_path_fallback(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with (
        bind_existing_directory(cache, writable=True) as root,
        BoundStagingTransaction.create(root) as transaction,
    ):
        _write_bound(transaction)
        transaction.publish("a" * 64)
    assert (cache / ("a" * 64) / "payload.bin").read_bytes() == b"bound-bytes"


@pytest.mark.parametrize(
    ("point", "publishes_before_abort"),
    [
        ("after_root_binding", False),
        ("after_staging_creation", False),
        ("before_payload_open", False),
        ("before_final_publication", False),
        ("after_publication_handle_creation", True),
    ],
)
def test_fault_injection_at_every_handle_boundary_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, point: str, publishes_before_abort: bool
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    try:
        with bind_existing_directory(cache, writable=True) as root:
            original_describe = root._native.describe

            def inject(candidate: str) -> None:
                if candidate != point:
                    return

                def replaced(handle: int):
                    description = original_describe(handle)
                    replace_non_root = point in {
                        "after_staging_creation",
                        "before_payload_open",
                        "before_final_publication",
                    }
                    if replace_non_root and handle != root._handle:
                        return replace(
                            description,
                            identity=replace(
                                description.identity,
                                file_id_hex=(
                                    "f" if description.identity.file_id_hex[0] != "f" else "e"
                                )
                                + description.identity.file_id_hex[1:],
                            ),
                        )
                    return replace(
                        description,
                        identity=replace(
                            description.identity,
                            file_id_hex=("f" if description.identity.file_id_hex[0] != "f" else "e")
                            + description.identity.file_id_hex[1:],
                        ),
                    )

                monkeypatch.setattr(root._native, "describe", replaced)

            _install_test_hook(inject)
            with (
                pytest.raises(PromotionPathSafetyError) as error,
                BoundStagingTransaction.create(root) as transaction,
            ):
                if point == "before_payload_open":
                    _write_bound(transaction)
                elif point in {"before_final_publication", "after_publication_handle_creation"}:
                    _install_test_hook(None)
                    _write_bound(transaction)
                    _install_test_hook(inject)
                    transaction.publish("b" * 64)
            _assert_code(error, "NPI_PROMOTION_BOUND_ROOT_IDENTITY_CHANGED")
    finally:
        _install_test_hook(None)
    final = cache / ("b" * 64)
    assert final.exists() is publishes_before_abort
    if publishes_before_abort:
        assert (final / "payload.bin").read_bytes() == b"bound-bytes"


def test_root_junction_is_rejected(tmp_path: Path, junction_factory) -> None:
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "cache-link"
    assert junction_factory(link, target), (
        "test environment could not create a temporary NTFS junction"
    )
    with pytest.raises(NpiError) as error:
        bind_existing_directory(link, writable=False)
    _assert_code(error, "NPI_PROMOTION_REPARSE_POINT_REJECTED")


def test_existing_parent_junction_is_rejected(tmp_path: Path, junction_factory) -> None:
    target = tmp_path / "target"
    (target / "cache").mkdir(parents=True)
    parent = tmp_path / "parent"
    parent.mkdir()
    link = parent / "junction"
    assert junction_factory(link, target), (
        "test environment could not create a temporary NTFS junction"
    )
    with pytest.raises(NpiError) as error:
        bind_existing_directory(link / "cache", writable=False)
    _assert_code(error, "NPI_PROMOTION_REPARSE_POINT_REJECTED")


def test_final_path_escape_and_volume_change_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with bind_existing_directory(cache, writable=False) as root:
        original = root._native.describe

        def escaped(handle: int):
            description = original(handle)
            if handle == root._handle:
                return replace(
                    description,
                    identity=replace(
                        description.identity,
                        final_path=description.identity.final_path + "\\escaped",
                    ),
                )
            return description

        monkeypatch.setattr(root._native, "describe", escaped)
        with pytest.raises(NpiError) as error:
            root.list_names()
        _assert_code(error, "NPI_PROMOTION_BOUND_ROOT_IDENTITY_CHANGED")


def test_unknown_reparse_tag_and_rename_failure_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with (
        bind_existing_directory(cache, writable=True) as root,
        BoundStagingTransaction.create(root) as transaction,
    ):
        _write_bound(transaction)
        original_rename = transaction.staging._native.rename

        def unavailable_rename(*_args: object) -> None:
            raise PromotionPathSafetyError(
                "rename refused", error_code="NPI_PROMOTION_RACE_DETECTED"
            )

        monkeypatch.setattr(transaction.staging._native, "rename", unavailable_rename)
        with pytest.raises(PromotionPathSafetyError) as error:
            transaction.publish("c" * 64)
        _assert_code(error, "NPI_PROMOTION_RACE_DETECTED")
        monkeypatch.setattr(transaction.staging._native, "rename", original_rename)
    assert not (cache / ("c" * 64)).exists()


@pytest.mark.parametrize(
    ("replacement", "expected_code"),
    [
        ("reparse", "NPI_PROMOTION_REPARSE_POINT_REJECTED"),
        ("volume", "NPI_PROMOTION_VOLUME_IDENTITY_CHANGED"),
    ],
)
def test_new_child_reparse_and_volume_changes_are_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str, expected_code: str
) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with bind_existing_directory(cache, writable=True) as root:
        original = root._native.describe

        def changed(handle: int):
            description = original(handle)
            if handle == root._handle:
                return description
            if replacement == "reparse":
                return replace(description, reparse_tag=0xA0000003)
            return replace(
                description,
                identity=replace(
                    description.identity,
                    volume_serial_number=description.identity.volume_serial_number + 1,
                ),
            )

        monkeypatch.setattr(root._native, "describe", changed)
        with pytest.raises(NpiError) as error:
            root.create_file("candidate.bin")
        _assert_code(error, expected_code)


def test_cleanup_never_recursively_deletes_a_non_owned_file(tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    with bind_existing_directory(cache, writable=True) as root:
        transaction = BoundStagingTransaction.create(root)
        _write_bound(transaction, "owned.bin")
        with transaction.staging.create_file("foreign.bin") as foreign:
            foreign.write(b"not-owned")
            foreign.flush()
        transaction.close()
    foreign_files = list((cache / ".staging").rglob("foreign.bin"))
    assert len(foreign_files) == 1
    assert foreign_files[0].read_bytes() == b"not-owned"


def test_native_handle_unavailability_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import nightly_photo_intelligence_pipeline.windows_bound_promotion as bound

    monkeypatch.setattr(bound.sys, "platform", "not-windows")
    with pytest.raises(NpiError) as error:
        bind_existing_directory(tmp_path, writable=False)
    _assert_code(error, "NPI_PROMOTION_RACE_RESISTANT_PATH_OPERATION_UNAVAILABLE")
