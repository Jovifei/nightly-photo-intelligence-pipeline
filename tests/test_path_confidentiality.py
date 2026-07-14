"""Path and filename confidentiality across error/redaction surfaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.cli import _emit_error
from nightly_photo_intelligence_pipeline.domain.errors import (
    GateNotAuthorizedError,
    SourceSymlinkEscapeError,
)
from nightly_photo_intelligence_pipeline.ingest.exif import read_exif_from_bytes
from nightly_photo_intelligence_pipeline.ingest.manifest import G1FrozenManifest
from nightly_photo_intelligence_pipeline.ingest.perceptual_hash import (
    PerceptualHashUnavailableError,
    analyze_image_bytes,
)
from nightly_photo_intelligence_pipeline.ingest.runner import (
    format_dry_run_text,
    run_dry_run_ingest,
)
from nightly_photo_intelligence_pipeline.ingest.source_guard import open_source_file
from nightly_photo_intelligence_pipeline.logging import setup_logging
from nightly_photo_intelligence_pipeline.redaction import redact_text


@pytest.mark.parametrize(
    "raw",
    [
        "F:\\PrivatePhotos\\真实姓名.jpg",
        "F:\\Private Photos\\真实 姓名.jpg",
        "\\\\server\\private-share\\真实姓名.jpg",
        "\\\\server\\private share\\真实 姓名.png",
        "/mnt/f/private/真实姓名.jpg",
        "/mnt/f/private photos/真实 姓名.heic",
        "John Doe.jpg",
    ],
)
def test_redaction_removes_drive_unc_wsl_and_unicode_filename(raw: str) -> None:
    output = redact_text(f"failure at {raw}")
    assert raw not in output
    assert "真实姓名" not in output
    assert "真实 姓名" not in output
    assert "John Doe.jpg" not in output
    assert "<SOURCE_ROOT>" in output or "<SOURCE_FILE>" in output


def test_source_guard_wraps_native_os_error_without_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "source"
    root.mkdir()
    candidate = root / "真实姓名.jpg"

    def fail_stat(*_args, **_kwargs):
        raise OSError("F:\\PrivatePhotos\\真实姓名.jpg access denied")

    monkeypatch.setattr("os.stat", fail_stat)
    with pytest.raises(SourceSymlinkEscapeError) as raised:
        open_source_file(candidate, root, allowed_extensions=(".jpg",))
    message = str(raised.value)
    assert "F:\\" not in message
    assert "真实姓名" not in message
    assert raised.value.__cause__ is None


def test_bare_unicode_image_filename_is_removed_from_stdout_and_stderr(capsys) -> None:
    secret_name = "真实姓名.jpg"
    print(redact_text(f"report item: {secret_name}"))
    _emit_error(GateNotAuthorizedError(f"asset rejected: {secret_name}"))
    captured = capsys.readouterr()
    assert secret_name not in captured.out
    assert secret_name not in captured.err
    assert "<SOURCE_FILE>" in captured.out
    assert "<SOURCE_FILE>" in captured.err


def test_unicode_filename_removed_from_log_and_dry_run_report(
    tmp_path: Path, runtime_root: Path, config
) -> None:
    from PIL import Image

    source = tmp_path / "source"
    source.mkdir()
    secret_name = "真实姓名.jpg"
    Image.new("RGB", (8, 8), (1, 2, 3)).save(source / secret_name)
    logger = setup_logging(runtime_root=runtime_root, source_root=source, console=False)
    logger.error("failed source item %s", secret_name)
    for handler in logger.handlers:
        handler.flush()
    log_text = (runtime_root / "logs" / "npi.log").read_text(encoding="utf-8")
    assert secret_name not in log_text

    result = run_dry_run_ingest(source, runtime_root, config)
    report = format_dry_run_text(result)
    assert secret_name not in report
    assert all(item.sanitized_name.startswith("scan-asset-") for item in result.files)


def test_pillow_and_exif_failures_do_not_expose_native_details(monkeypatch) -> None:
    import PIL.Image

    def fail_open(*_args, **_kwargs):
        raise OSError("F:\\private\\真实姓名.jpg decoder failed")

    monkeypatch.setattr(PIL.Image, "open", fail_open)
    with pytest.raises(PerceptualHashUnavailableError) as raised:
        analyze_image_bytes(b"synthetic")
    assert str(raised.value) == "image metadata analysis failed"
    assert raised.value.__cause__ is None

    exif = read_exif_from_bytes(b"synthetic")
    assert exif.parse_error
    assert "真实姓名" not in str(exif)


def test_manifest_native_failure_has_no_path_bearing_cause(tmp_path: Path) -> None:
    missing = tmp_path / "真实姓名.jpg"
    with pytest.raises(GateNotAuthorizedError) as raised:
        G1FrozenManifest.load(missing)
    assert "真实姓名" not in str(raised.value)
    assert raised.value.__cause__ is None
