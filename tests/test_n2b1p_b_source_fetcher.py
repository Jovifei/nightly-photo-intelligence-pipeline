from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline import n2b1p_b_source_fetcher as fetcher


@dataclass
class FakeResponse:
    body: bytes
    status: int = 200
    location: str | None = None
    content_length: int | None = None
    offset: int = 0
    closed: bool = False

    def getheader(self, name: str) -> str | None:
        if name.lower() == "location":
            return self.location
        if name.lower() == "content-length" and self.content_length is not None:
            return str(self.content_length)
        return None

    def read(self, amount: int) -> bytes:
        chunk = self.body[self.offset : self.offset + amount]
        self.offset += len(chunk)
        return chunk

    def close(self) -> None:
        self.closed = True


class FakeTransport:
    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def open(self, url: str) -> FakeResponse:
        self.calls.append(url)
        queue = self.responses.get(url)
        if not queue:
            raise OSError("unexpected URL")
        return queue.pop(0)


class MemoryPublisher:
    def __init__(self) -> None:
        self.initial_checked = False
        self.published: list[str] = []

    def validate_initial_state(self) -> None:
        self.initial_checked = True

    def publish(
        self,
        spec: fetcher.ArtifactSpec,
        response: fetcher.DownloadResponse,
        *,
        final_url: str,
        redirect_count: int,
        reviewed_head: str,
        reviewed_tree: str,
        completed_at_utc: str,
    ) -> dict[str, object]:
        data = bytearray()
        observed_sha256, observed_bytes = fetcher._stream_response(
            response,
            spec,
            data.extend,
        )
        assert bytes(data)
        assert observed_sha256 == spec.sha256
        assert observed_bytes == spec.byte_count
        self.published.append(spec.artifact_id)
        manifest = {
            "artifact_id": spec.artifact_id,
            "reviewed_head": reviewed_head,
            "reviewed_tree": reviewed_tree,
            "completed_at_utc": completed_at_utc,
        }
        manifest_sha256 = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return {
            "artifact_id": spec.artifact_id,
            "status": "PUBLISHED_VERIFIED",
            "filename": spec.filename,
            "requested_url": spec.url,
            "final_url": final_url,
            "redirect_count": redirect_count,
            "response_status": 200,
            "observed_byte_count": observed_bytes,
            "observed_sha256": observed_sha256,
            "transfer_manifest_sha256": manifest_sha256,
        }


def _spec(
    body: bytes,
    *,
    artifact_id: str = "artifact-a",
) -> fetcher.ArtifactSpec:
    filename = f"{artifact_id}.pth"
    return fetcher.ArtifactSpec(
        artifact_id=artifact_id,
        revision="torchvision-v0.22.1",
        url=f"https://download.pytorch.org/models/{filename}",
        filename=filename,
        byte_count=len(body),
        sha256=hashlib.sha256(body).hexdigest(),
        historical_transfer_manifest_sha256="a" * 64,
    )


def test_stream_rejects_short_long_and_hash_mismatch() -> None:
    good = _spec(b"abcd")
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="STREAM_TOO_SHORT",
    ):
        fetcher._stream_response(
            FakeResponse(b"abc"),
            good,
            lambda _chunk: None,
        )

    short = _spec(b"abc")
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="STREAM_TOO_LONG",
    ):
        fetcher._stream_response(
            FakeResponse(b"abcd"),
            short,
            lambda _chunk: None,
        )

    wrong_hash = fetcher.ArtifactSpec(
        artifact_id=good.artifact_id,
        revision=good.revision,
        url=good.url,
        filename=good.filename,
        byte_count=good.byte_count,
        sha256="0" * 64,
        historical_transfer_manifest_sha256=(
            good.historical_transfer_manifest_sha256
        ),
    )
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="SHA256_MISMATCH",
    ):
        fetcher._stream_response(
            FakeResponse(b"abcd"),
            wrong_hash,
            lambda _chunk: None,
        )


def test_redirect_rejects_other_domain() -> None:
    spec = _spec(b"abcd")
    transport = FakeTransport(
        {
            spec.url: [
                FakeResponse(
                    b"",
                    status=302,
                    location=(
                        "https://evil.test/models/"
                        "artifact-a.pth"
                    ),
                )
            ]
        }
    )
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="URL_REJECTED",
    ):
        fetcher._open_final_response(
            transport,
            spec,
            [0],
        )
    assert transport.calls == [spec.url]


def test_exact_sha_admission_failure_makes_zero_network_calls(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = FakeTransport({})
    publisher = MemoryPublisher()
    monkeypatch.setattr(
        fetcher,
        "check_external_exact_sha_review_receipt",
        lambda *_args, **_kwargs: {
            "status": "B_SOURCE_NETWORK_POST_REVIEW_ADMISSION_INVALID"
        },
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("unused-review.json"),
        Path("unused-missing.json"),
        transport=transport,
        publisher=publisher,
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert result["network_request_count"] == 0
    assert transport.calls == []
    assert publisher.initial_checked is False


def test_missing_payload_gate_failure_makes_zero_network_calls(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    transport = FakeTransport({})
    publisher = MemoryPublisher()
    monkeypatch.setattr(
        fetcher,
        "check_external_exact_sha_review_receipt",
        lambda *_args, **_kwargs: {
            "status": fetcher.POST_REVIEW_ADMISSION_STATUS,
            "reviewed_head": "a" * 40,
            "reviewed_tree": "b" * 40,
        },
    )

    def rejected(
        *_args: object,
        **_kwargs: object,
    ) -> dict[str, object]:
        raise fetcher.BSourceAcquisitionError(
            "NPI_B_SOURCE_MISSING_PRECONDITION_STALE"
        )

    monkeypatch.setattr(
        fetcher,
        "load_missing_payload_precondition",
        rejected,
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("unused-review.json"),
        Path("unused-missing.json"),
        transport=transport,
        publisher=publisher,
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_injected_exact_three_success_stops_before_cache(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bodies = [b"one", b"two-two", b"three-three-three"]
    specs = [
        _spec(
            body,
            artifact_id=f"artifact-{index}",
        )
        for index, body in enumerate(
            bodies,
            start=1,
        )
    ]
    monkeypatch.setattr(
        fetcher,
        "check_external_exact_sha_review_receipt",
        lambda *_args, **_kwargs: {
            "status": fetcher.POST_REVIEW_ADMISSION_STATUS,
            "reviewed_head": "a" * 40,
            "reviewed_tree": "b" * 40,
        },
    )
    monkeypatch.setattr(
        fetcher,
        "load_missing_payload_precondition",
        lambda *_args, **_kwargs: {
            "status": "EXACT_PAYLOADS_ABSENT"
        },
    )
    monkeypatch.setattr(
        fetcher,
        "load_b_source_network_execution_binding",
        lambda _root: {
            "quarantine_root_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/"
                "npi-n2b1p-b-source-quarantine-"
                "20260930-e9110783"
            ),
            "quarantine_root_identity_sha256": "f" * 64,
            "artifacts": [
                {
                    "id": spec.artifact_id,
                    "revision": spec.revision,
                    "url": spec.url,
                    "filename": spec.filename,
                    "byte_count": spec.byte_count,
                    "local_sha256": spec.sha256,
                    "transfer_manifest_sha256": (
                        spec.historical_transfer_manifest_sha256
                    ),
                }
                for spec in specs
            ],
        },
    )
    responses = {
        spec.url: [
            FakeResponse(
                body,
                content_length=len(body),
            )
        ]
        for spec, body in zip(
            specs,
            bodies,
            strict=True,
        )
    }
    transport = FakeTransport(responses)
    publisher = MemoryPublisher()
    monkeypatch.setattr(
        fetcher,
        "_validate_document",
        lambda *_args, **_kwargs: None,
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("unused-review.json"),
        Path("unused-missing.json"),
        transport=transport,
        publisher=publisher,
        clock=lambda: "2026-10-01T00:00:00Z",
    )
    assert result["status"] == (
        "B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW"
    )
    assert result["network_request_count"] == 3
    assert len(result["artifact_results"]) == 3
    assert result["cache_promotion"] == "NOT_AUTHORIZED"
    assert (
        result["model_cuda_photo_exif_sqlite_real20"]
        == "NOT_AUTHORIZED"
    )


def test_network_failure_is_terminal_and_not_retryable(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(b"abcd")
    monkeypatch.setattr(
        fetcher,
        "check_external_exact_sha_review_receipt",
        lambda *_args, **_kwargs: {
            "status": fetcher.POST_REVIEW_ADMISSION_STATUS,
            "reviewed_head": "a" * 40,
            "reviewed_tree": "b" * 40,
        },
    )
    monkeypatch.setattr(
        fetcher,
        "load_missing_payload_precondition",
        lambda *_args, **_kwargs: {
            "status": "EXACT_PAYLOADS_ABSENT"
        },
    )
    monkeypatch.setattr(
        fetcher,
        "load_b_source_network_execution_binding",
        lambda _root: {
            "quarantine_root_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/"
                "npi-n2b1p-b-source-quarantine-"
                "20260930-e9110783"
            ),
            "quarantine_root_identity_sha256": "f" * 64,
            "artifacts": [
                {
                    "id": spec.artifact_id,
                    "revision": spec.revision,
                    "url": spec.url,
                    "filename": spec.filename,
                    "byte_count": spec.byte_count,
                    "local_sha256": spec.sha256,
                    "transfer_manifest_sha256": (
                        spec.historical_transfer_manifest_sha256
                    ),
                }
            ],
        },
    )
    transport = FakeTransport({})
    publisher = MemoryPublisher()
    monkeypatch.setattr(
        fetcher,
        "_validate_document",
        lambda *_args, **_kwargs: None,
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("unused-review.json"),
        Path("unused-missing.json"),
        transport=transport,
        publisher=publisher,
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_FAILED"
    assert result["retry_authorized"] is False
    assert result["network_request_count"] == 1
    assert result["mandatory_stop"] == (
        "EXTERNAL_REVIEW_B_SOURCE_ACQUISITION_FAILURE"
    )
