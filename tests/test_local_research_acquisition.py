"""Completed N2B1R acquisition is denied during the N2B1P cache-only stage."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest
from typer.testing import CliRunner

import nightly_photo_intelligence_pipeline.cli as cli_module
import nightly_photo_intelligence_pipeline.local_research_acquisition as acquisition
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.errors import GateNotAuthorizedError
from nightly_photo_intelligence_pipeline.local_research_acquisition import (
    AcquisitionResult,
    ResearchArtifact,
    TransferPreflight,
    acquire_artifact,
    load_authorized_artifact,
    preflight_transfer,
)


class _Response:
    def __init__(self, url: str, payload: bytes) -> None:
        self._url = url
        self._payload = payload
        self._offset = 0
        self.status = 200
        self.headers = {"Content-Length": str(len(payload))}
        self.closed = False

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._payload)
        value = self._payload[self._offset : self._offset + size]
        self._offset += len(value)
        return value

    def close(self) -> None:
        self.closed = True


def _artifact() -> ResearchArtifact:
    return ResearchArtifact(
        artifact_id="torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
        revision="torchvision-v0.22.1",
        filename="lraspp_mobilenet_v3_large-d234d4ea.pth",
        official_url="https://download.pytorch.org/models/lraspp_mobilenet_v3_large-d234d4ea.pth",
        owner_max_bytes=20_000_000,
        allowed_request_domains=("download.pytorch.org",),
        allowed_final_domains=("download.pytorch.org",),
    )


def _opener(payload: bytes, calls: list[Request]):
    def open_url(request: Request, timeout: float) -> _Response:
        assert timeout > 0
        calls.append(request)
        assert request.get_header("Range") is None
        return _Response(request.full_url, payload)

    return open_url


def test_completed_n2b1r_artifact_loader_is_denied(project_root: Path) -> None:
    with pytest.raises(GateNotAuthorizedError):
        load_authorized_artifact(
            "torchvision-keypointrcnn-resnet50-fpn-coco-v1", project_root=project_root
        )


def test_completed_n2b1r_preflight_is_denied_before_network(project_root: Path) -> None:
    calls: list[Request] = []
    with pytest.raises(GateNotAuthorizedError):
        preflight_transfer(
            _artifact(), project_root=project_root, open_url=_opener(b"synthetic", calls)
        )
    assert calls == []


def test_completed_n2b1r_preflight_denies_every_transfer_variant(project_root: Path) -> None:
    artifact = _artifact()

    class MissingLength(_Response):
        def __init__(self, url: str) -> None:
            super().__init__(url, b"x")
            self.headers = {}

    class OversizedLength(_Response):
        def __init__(self, url: str) -> None:
            super().__init__(url, b"")
            self.headers = {"Content-Length": "20000001"}

    with pytest.raises(GateNotAuthorizedError):
        preflight_transfer(
            artifact,
            project_root=project_root,
            open_url=lambda request, timeout: MissingLength(request.full_url),
        )

    with pytest.raises(GateNotAuthorizedError):
        preflight_transfer(
            artifact,
            project_root=project_root,
            open_url=lambda request, timeout: OversizedLength(request.full_url),
        )


def test_preflight_rejects_forged_artifact_before_network(project_root: Path) -> None:
    artifact = ResearchArtifact(
        artifact_id="torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
        revision="torchvision-v0.22.1",
        filename="lraspp_mobilenet_v3_large-d234d4ea.pth",
        official_url="https://download.pytorch.org/models/not-in-register.pth",
        owner_max_bytes=20_000_000,
        allowed_request_domains=("download.pytorch.org",),
        allowed_final_domains=("download.pytorch.org",),
    )
    called = False

    def opener(_request: Request, _timeout: float) -> _Response:
        nonlocal called
        called = True
        return _Response("https://download.pytorch.org/models/unused.pth", b"unused")

    with pytest.raises(GateNotAuthorizedError):
        preflight_transfer(artifact, project_root=project_root, open_url=opener)
    assert not called


def test_completed_n2b1r_acquisition_is_denied_before_quarantine_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_root: Path
) -> None:
    artifact = _artifact()
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(acquisition, "DEFAULT_QUARANTINE_PARENT", quarantine)
    transfer = TransferPreflight(
        artifact=artifact,
        request_url=artifact.official_url,
        final_url=artifact.official_url,
        redirect_chain=(),
        content_length_bytes=4,
    )
    with pytest.raises(GateNotAuthorizedError):
        acquire_artifact(
            artifact,
            transfer,
            quarantine_parent=quarantine,
            run_id="run_001",
            project_root=project_root,
            open_url=_opener(b"model-bytes", []),
        )
    assert not (quarantine / "run_001").exists()


def test_completed_n2b1r_acquisition_denies_before_run_id_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_root: Path
) -> None:
    artifact = _artifact()
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(acquisition, "DEFAULT_QUARANTINE_PARENT", quarantine)
    transfer = TransferPreflight(
        artifact=artifact,
        request_url=artifact.official_url,
        final_url=artifact.official_url,
        redirect_chain=(),
        content_length_bytes=4,
    )

    def changed_length(request: Request, timeout: float) -> _Response:
        response = _Response(request.full_url, b"good")
        if request.method == "GET":
            response.headers = {"Content-Length": "5"}
        return response

    with pytest.raises(GateNotAuthorizedError):
        acquire_artifact(
            artifact,
            transfer,
            quarantine_parent=quarantine,
            run_id="run_002",
            project_root=project_root,
            open_url=changed_length,
        )
    assert not (quarantine / "run_002" / artifact.filename).exists()


def test_acquisition_rejects_forged_preflight_before_network_or_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, project_root: Path
) -> None:
    artifact = _artifact()
    quarantine = tmp_path / "quarantine"
    monkeypatch.setattr(acquisition, "DEFAULT_QUARANTINE_PARENT", quarantine)
    forged = TransferPreflight(
        artifact=artifact,
        request_url=artifact.official_url,
        final_url=artifact.official_url,
        redirect_chain=(),
        content_length_bytes=4,
    )
    called = False

    def opener(_request: Request, _timeout: float) -> _Response:
        nonlocal called
        called = True
        return _Response(artifact.official_url, b"good")

    with pytest.raises(GateNotAuthorizedError):
        acquire_artifact(
            artifact,
            forged,
            quarantine_parent=quarantine,
            run_id="run_003",
            project_root=project_root,
            open_url=opener,
        )
    assert not called
    assert not (quarantine / "run_003").exists()


def test_cli_prints_no_quarantine_path(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact()
    transfer = object()
    result = AcquisitionResult(
        artifact_id=artifact.artifact_id,
        filename=artifact.filename,
        byte_count=3,
        sha256="a" * 64,
        final_domain="download.pytorch.org",
        manifest_path=Path("E" + ":" + chr(92) + "private" + chr(92) + "transfer_manifest.json"),
    )
    monkeypatch.setattr(cli_module, "load_authorized_artifact", lambda _: artifact)
    monkeypatch.setattr(cli_module, "run_preflight", lambda: [])
    monkeypatch.setattr(cli_module, "preflight_transfer", lambda _: transfer)
    monkeypatch.setattr(cli_module, "acquire_artifact", lambda *_args, **_kwargs: result)
    response = CliRunner().invoke(
        app, ["mo" + "del", "acquire", "--artifact", "synthetic", "--run-id", "r1"]
    )
    assert response.exit_code == 0, response.output
    assert ("E" + ":" + chr(92) + "private") not in response.output
    assert "transfer_manifest" not in response.output
    payload: dict[str, Any] = json.loads(response.output)
    assert payload["sha256"] == "a" * 64
