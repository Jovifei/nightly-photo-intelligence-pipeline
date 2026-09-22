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


def test_consumption_requires_denied_delete_and_acl_rights(tmp_path, monkeypatch):
    from nightly_photo_intelligence_pipeline.ingest.read_only_capability import (
        CapabilityDisposition,
    )
    from nightly_photo_intelligence_pipeline.real20 import admission

    monkeypatch.setattr(admission, "_windows_probe", lambda *args: CapabilityDisposition.GRANTED)
    with pytest.raises(Real20Error, match="LEDGER_MUTATION_NOT_DENIED"):
        admission.protect_consumption(tmp_path)
    monkeypatch.setattr(
        admission, "_windows_probe", lambda *args: CapabilityDisposition.NOT_VERIFIED
    )
    with pytest.raises(Real20Error, match="LEDGER_MUTATION_NOT_DENIED"):
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
