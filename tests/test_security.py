"""AT-N0-SEC-01..04: source guard security. AT-N0-LOG-01: log path redaction."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.errors import (
    SourceRuntimeOverlapError,
    SourceSymlinkEscapeError,
    UnsupportedMediaError,
)
from nightly_photo_intelligence_pipeline.ingest.source_guard import (
    is_reparse_point,
    open_source_file,
    strict_realpath,
    validate_roots,
)

pytestmark = pytest.mark.acceptance


# ---------------- AT-N0-SEC-01: source/runtime overlap refused ----------------


def test_at_n0_sec_01_equal_roots_rejected(fixture_dir: Path) -> None:
    with pytest.raises(SourceRuntimeOverlapError):
        validate_roots(fixture_dir, fixture_dir)


def test_at_n0_sec_01_runtime_inside_source_rejected(fixture_dir: Path) -> None:
    with pytest.raises(SourceRuntimeOverlapError):
        validate_roots(fixture_dir, fixture_dir / "sub")


def test_at_n0_sec_01_source_inside_runtime_rejected(fixture_dir: Path) -> None:
    with pytest.raises(SourceRuntimeOverlapError):
        validate_roots(fixture_dir.parent, fixture_dir)


def test_at_n0_sec_01_separated_roots_accepted(tmp_path: Path) -> None:
    src = tmp_path / "src"
    rt = tmp_path / "runtime"
    src.mkdir()
    rt.mkdir()
    validate_roots(src, rt)  # must not raise


# ---------------- AT-N0-SEC-02: symlink / reparse escape refused ----------------


def test_at_n0_sec_02_path_escape_via_dotdot_rejected(tmp_path: Path, config) -> None:
    """A candidate whose realpath escapes source (via ..) is refused."""
    src = tmp_path / "src"
    src.mkdir()
    outside = tmp_path / "escape.png"
    shutil.copy(__file__, outside)  # any file; extension irrelevant here
    outside_png = tmp_path / "escape_target.png"
    # Build a real png outside source to test with an allowed extension.
    fx = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "three_image_smoke_set"
        / "fixture_b_tonal_abstract.png"
    )
    shutil.copy(fx, outside_png)
    cand = src / "sub" / ".." / ".." / "escape_target.png"
    assert not strict_realpath(cand).is_relative_to(strict_realpath(src))
    with pytest.raises(SourceSymlinkEscapeError):
        open_source_file(cand, src, allowed_extensions=config.allowed_extensions)


def test_at_n0_sec_02_junction_escape_rejected(tmp_path: Path, junction_factory, config) -> None:
    """An NTFS junction under source pointing outside is refused."""
    src = tmp_path / "src"
    src.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    fx = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "three_image_smoke_set"
        / "fixture_b_tonal_abstract.png"
    )
    shutil.copy(fx, outside / "real.png")
    link = src / "junc"
    if not junction_factory(link, outside):
        pytest.skip("junction creation unavailable on this platform (non-Windows or denied)")
    # A junction is a reparse point that is_symlink() does NOT detect.
    assert is_reparse_point(link), "junction must be detected as a reparse point"
    assert not link.is_symlink(), "junction is not is_symlink() on Windows"
    with pytest.raises(SourceSymlinkEscapeError):
        open_source_file(link / "real.png", src, allowed_extensions=config.allowed_extensions)


def test_at_n0_sec_02_disallowed_extension_rejected(fixture_dir: Path, config) -> None:
    p = fixture_dir / "fixture_a_corridor_abstract.png"
    with pytest.raises(UnsupportedMediaError):
        open_source_file(p, fixture_dir, allowed_extensions=(".jpg",))


# ---------------- AT-N0-SEC-03: fixture pre/post integrity ----------------


def test_at_n0_sec_03_fixture_unchanged_after_read(
    fixture_dir: Path, fixture_manifest: dict, config
) -> None:
    """Reading a fixture via the guard leaves size, mtime_ns, and sha256 unchanged."""
    exts = config.allowed_extensions
    for entry in fixture_manifest["files"]:
        p = fixture_dir / entry["name"]
        pre_stat = p.stat()
        with open_source_file(p, fixture_dir, allowed_extensions=exts) as handle:
            handle.read()  # drain
            pre_fp = handle.pre_fingerprint(entry["sha256"])
        post_stat = p.stat()
        assert pre_stat.st_size == post_stat.st_size
        assert pre_stat.st_mtime_ns == post_stat.st_mtime_ns
        assert pre_fp.size_bytes == post_stat.st_size
        # Hash still matches manifest after the read.
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]


# ---------------- AT-N0-SEC-04: git sensitive / large file scan ----------------


def test_at_n0_sec_04_sensitive_file_scan_clean(project_root: Path) -> None:
    """AT-N0-SEC-04: the sensitive-file scanner reports zero violations."""
    proc = subprocess.run(
        [sys.executable, "tools/sensitive_file_scan.py"],
        capture_output=True,
        text=True,
        cwd=project_root,
        timeout=60,
        check=False,
    )
    assert proc.returncode == 0, f"scanner found violations:\n{proc.stdout}\n{proc.stderr}"
    assert "0 violation" in proc.stdout


# ---------------- AT-N0-LOG-01: log path redaction ----------------


def test_at_n0_log_01_fixture_root_redacted(fixture_dir: Path, runtime_root: Path) -> None:
    """AT-N0-LOG-01: logs must not contain the fixture root absolute path."""
    from nightly_photo_intelligence_pipeline.logging import setup_logging

    logger = setup_logging(runtime_root=runtime_root, source_root=fixture_dir, console=False)
    logger.info("scanning source at %s", str(fixture_dir))
    # Flush handlers.
    for handler in logger.handlers:
        handler.flush()
    log_file = runtime_root / "logs" / "npi.log"
    assert log_file.is_file(), "log file must be written under runtime/logs"
    content = log_file.read_text(encoding="utf-8")
    assert str(fixture_dir) not in content, "fixture root absolute path leaked into log"
    assert "<SOURCE_ROOT>" in content, "source root must be redacted to <SOURCE_ROOT>"
