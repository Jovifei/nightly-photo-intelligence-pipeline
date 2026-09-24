from contextlib import contextmanager
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from nightly_photo_intelligence_pipeline.real20.contracts import Real20Error
from nightly_photo_intelligence_pipeline.real20.exif import read_real20_exif
from nightly_photo_intelligence_pipeline.real20.runtime_probe import probe_worker


def test_nested_photographic_exif_is_preserved_without_text_identifiers():
    image = Image.new("RGB", (16, 16))
    exif = Image.Exif()
    exif[34665] = {
        33434: IFDRational(1, 125),
        33437: IFDRational(28, 10),
        34855: 400,
        42033: "PRIVATE_SERIAL",
        37510: b"PRIVATE_COMMENT",
    }
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    result = read_real20_exif(output.getvalue())
    assert result["fields"] == {
        "ExposureTime": "0.008",
        "FNumber": "2.8",
        "ISOSpeedRatings": "400.0",
    }
    assert "PRIVATE" not in str(result)


def test_worker_rejects_wrong_python_before_torch_import(monkeypatch):
    from nightly_photo_intelligence_pipeline.real20 import runtime_probe

    monkeypatch.setattr(runtime_probe.sys, "version_info", (3, 14, 0))
    with pytest.raises(Real20Error, match="PYTHON_UNSUPPORTED"):
        probe_worker()


def test_worker_rejects_operator_failure(monkeypatch):
    import sys

    def fail(*args, **kwargs):
        raise RuntimeError("operator unavailable")

    monkeypatch.setitem(
        sys.modules,
        "torch",
        SimpleNamespace(
            __version__="2.7.1+cu128", cuda=SimpleNamespace(is_available=lambda: True), tensor=fail
        ),
    )
    monkeypatch.setitem(sys.modules, "torchvision", SimpleNamespace(__version__="0.22.1+cu128"))
    with pytest.raises(Real20Error, match="RUNTIME_UNAVAILABLE"):
        probe_worker()


def test_consumption_requires_explicit_native_access_denials(tmp_path, monkeypatch):
    from nightly_photo_intelligence_pipeline.real20 import admission
    from nightly_photo_intelligence_pipeline.windows_bound_promotion import (
        BoundDirectory,
        NativeAccessCheck,
    )

    bound = object.__new__(BoundDirectory)
    bound._append_only = True
    bound._verify = lambda: None
    monkeypatch.setattr(
        bound,
        "access_check",
        lambda _right: NativeAccessCheck(True, None),
    )
    monkeypatch.setattr(
        bound,
        "parent_access_check",
        lambda _right: NativeAccessCheck(False, None),
    )

    @contextmanager
    def bind(*_args, **kwargs):
        assert kwargs == {"writable": True, "append_only": True, "security_check": True}
        yield bound

    monkeypatch.setattr(admission, "bind_existing_directory", bind)
    with pytest.raises(Real20Error, match="LEDGER_MUTATION_NOT_DENIED"):
        admission.protect_consumption(tmp_path)

    monkeypatch.setattr(
        bound,
        "access_check",
        lambda _right: NativeAccessCheck(None, 5),
    )
    with pytest.raises(Real20Error, match="LEDGER_MUTATION_NOT_DENIED"):
        admission.protect_consumption(tmp_path)

    monkeypatch.setattr(
        bound,
        "access_check",
        lambda _right: NativeAccessCheck(False, None),
    )
    monkeypatch.setattr(
        bound,
        "parent_access_check",
        lambda right: NativeAccessCheck(right == 0x00040000, None),
    )
    with pytest.raises(Real20Error, match="LEDGER_MUTATION_NOT_DENIED"):
        admission.protect_consumption(tmp_path)

    monkeypatch.setattr(
        bound,
        "parent_access_check",
        lambda _right: NativeAccessCheck(False, None),
    )
    admission.protect_consumption(tmp_path)


def test_manifest_hardlink_rejected_before_parsing(tmp_path):
    import os

    from nightly_photo_intelligence_pipeline.real20.contracts import load_manifest

    source = tmp_path / "synthetic-image"
    source.write_bytes(b"not a manifest")
    alias = tmp_path / "manifest.json"
    os.link(source, alias)
    with pytest.raises(Real20Error, match="CONTROL_UNAVAILABLE"):
        load_manifest(alias)
