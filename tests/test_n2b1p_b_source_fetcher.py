from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from nightly_photo_intelligence_pipeline import n2b1p_b_source_fetcher as fetcher
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.errors import PromotionPathSafetyError


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

class _FakeBoundDirectory:
    def __init__(
        self,
        *,
        digest: str,
        final_path: str,
        volume: int = 1,
        names: set[str] | None = None,
    ) -> None:
        self.identity = SimpleNamespace(
            digest=digest,
            final_path=final_path,
            volume_serial_number=volume,
        )
        self._names = names or set()

    def list_names(self) -> set[str]:
        return set(self._names)

    def __enter__(self) -> _FakeBoundDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _admit_for_test(
    monkeypatch: pytest.MonkeyPatch,
    *,
    specs: list[fetcher.ArtifactSpec],
) -> None:
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
        lambda *_args, **_kwargs: {"status": "EXACT_PAYLOADS_ABSENT"},
    )
    monkeypatch.setattr(
        fetcher,
        "load_b_source_network_execution_binding",
        lambda _root: {
            "quarantine_root_ref": fetcher._QUARANTINE_REF,
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
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)


def test_quarantine_path_is_lexical_and_not_resolved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher.Path,
        "resolve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("quarantine path must not resolve before handle binding")
        ),
    )
    path = fetcher._resolve_bound_quarantine_path()
    assert str(path).casefold().endswith(fetcher._QUARANTINE_LEAF.casefold())


def test_handle_final_path_rejects_quarantine_moved_under_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved_parent_final = r"\\?\volume{approved}\claude_allow\download".casefold()
    quarantine_final = (
        approved_parent_final
        + chr(92)
        + fetcher._ROUTE_B_CACHE_LEAF.casefold()
        + chr(92)
        + "moved-quarantine"
    )
    route_cache_final = (
        approved_parent_final + chr(92) + fetcher._ROUTE_B_CACHE_LEAF.casefold()
    )
    root = _FakeBoundDirectory(
        digest=fetcher._QUARANTINE_IDENTITY,
        final_path=quarantine_final,
    )
    approved_parent = _FakeBoundDirectory(
        digest="a" * 64,
        final_path=approved_parent_final,
    )
    route_cache = _FakeBoundDirectory(
        digest="b" * 64,
        final_path=route_cache_final,
    )

    def bound(path: Path, *, writable: bool) -> _FakeBoundDirectory:
        text = str(path).casefold()
        if fetcher._QUARANTINE_LEAF.casefold() in text:
            return root
        if fetcher._ROUTE_B_CACHE_LEAF.casefold() in text:
            return route_cache
        return approved_parent

    monkeypatch.setattr(fetcher, "bind_existing_directory", bound)
    publisher = fetcher.WindowsBoundQuarantinePublisher(
        Path("repo"),
        Path("fixed-quarantine"),
        fetcher._QUARANTINE_IDENTITY,
    )
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="QUARANTINE_LOCATION_MISMATCH",
    ):
        publisher.validate_initial_state()


def test_parent_junction_safety_error_blocks_before_network(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(b"abcd")
    _admit_for_test(monkeypatch, specs=[spec])
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PromotionPathSafetyError("NPI_PROMOTION_REPARSE_POINT_REJECTED")
        ),
    )
    transport = FakeTransport({})
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_publisher_path_safety_error_is_terminal_with_request_count(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(b"abcd")
    _admit_for_test(monkeypatch, specs=[spec])
    transport = FakeTransport(
        {spec.url: [FakeResponse(b"abcd", content_length=4)]}
    )

    class UnsafePublisher(MemoryPublisher):
        def publish(
            self,
            spec: fetcher.ArtifactSpec,
            response: fetcher.DownloadResponse,
            **_kwargs: object,
        ) -> dict[str, object]:
            raise PromotionPathSafetyError("NPI_PROMOTION_RACE_DETECTED")

    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
        publisher=UnsafePublisher(),
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_FAILED"
    assert result["network_request_count"] == 1
    assert result["failure_code"] == "NPI_PROMOTION_RACE_DETECTED"


def test_cli_persists_aggregate_terminal_result(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal: dict[str, object] = {
        "status": "B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW",
        "network_request_count": 3,
    }
    persisted: list[dict[str, object]] = []
    monkeypatch.setattr(
        fetcher,
        "run_b_source_network_acquisition",
        lambda *_args, **_kwargs: terminal,
    )

    def persist(
        _root: Path,
        result: Mapping[str, object],
    ) -> dict[str, str]:
        persisted.append(dict(result))
        return {
            "terminal_evidence_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/"
                "b-source-network-acquisition-result-v1.json"
            ),
            "terminal_evidence_sha256": "c" * 64,
        }

    monkeypatch.setattr(fetcher, "persist_acquisition_result", persist)
    result = CliRunner().invoke(
        app,
        [
            "n2b1p",
            "network-acquire",
            "--project-root",
            str(project_root),
            "--review-receipt",
            "review.json",
            "--missing-payload-evidence",
            "missing.json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert persisted == [terminal]
    assert payload["terminal_evidence_sha256"] == "c" * 64
    assert payload["terminal_evidence_ref"].endswith(
        "b-source-network-acquisition-result-v1.json"
    )

