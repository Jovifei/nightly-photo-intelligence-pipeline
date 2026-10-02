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


class MemoryOneShotClaim:
    def __init__(self) -> None:
        self.terminal: dict[str, object] | None = None

    def persist_terminal(self, result: Mapping[str, object]) -> dict[str, str]:
        if self.terminal is not None:
            raise AssertionError("terminal overwritten")
        self.terminal = dict(result)
        payload = fetcher._canonical_json_bytes(result)
        return {
            "one_shot_lease_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/"
                "b-source-network-acquisition-one-shot-v1"
            ),
            "reservation_evidence_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/"
                "b-source-network-acquisition-one-shot-v1/"
                "reservation-v1/reservation.json"
            ),
            "terminal_evidence_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/"
                "b-source-network-acquisition-one-shot-v1/terminal-v1/terminal.json"
            ),
            "terminal_evidence_sha256": hashlib.sha256(payload).hexdigest(),
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
        historical_transfer_manifest_sha256=(good.historical_transfer_manifest_sha256),
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
                    location=("https://evil.test/models/artifact-a.pth"),
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
        lambda *_args, **_kwargs: {"status": "B_SOURCE_NETWORK_POST_REVIEW_ADMISSION_INVALID"},
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
        raise fetcher.BSourceAcquisitionError("NPI_B_SOURCE_MISSING_PRECONDITION_STALE")

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
        lambda *_args, **_kwargs: {"status": "EXACT_PAYLOADS_ABSENT"},
    )
    monkeypatch.setattr(
        fetcher,
        "load_b_source_network_execution_binding",
        lambda _root: {
            "quarantine_root_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/npi-n2b1p-b-source-quarantine-20260930-e9110783"
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
                    "transfer_manifest_sha256": (spec.historical_transfer_manifest_sha256),
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
    monkeypatch.setattr(
        fetcher,
        "claim_one_shot_execution",
        lambda *_args, **_kwargs: MemoryOneShotClaim(),
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("unused-review.json"),
        Path("unused-missing.json"),
        transport=transport,
        publisher=publisher,
        clock=lambda: "2026-10-01T00:00:00Z",
    )
    assert result["status"] == ("B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW")
    assert result["network_request_count"] == 3
    assert len(result["artifact_results"]) == 3
    assert result["cache_promotion"] == "NOT_AUTHORIZED"
    assert result["model_cuda_photo_exif_sqlite_real20"] == "NOT_AUTHORIZED"


def test_network_failure_is_terminal_and_not_retryable(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(b"abcd")
    _admit_for_test(
        monkeypatch,
        specs=_exact_three_test_specs(spec),
    )
    transport = FakeTransport({})
    publisher = MemoryPublisher()
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
    assert result["one_shot_state"] == "COMPLETED"
    assert transport.calls == [spec.url]
    assert result["mandatory_stop"] == ("EXTERNAL_REVIEW_B_SOURCE_ACQUISITION_FAILURE")


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


def _exact_three_test_specs(
    primary: fetcher.ArtifactSpec,
) -> list[fetcher.ArtifactSpec]:
    return [
        primary,
        _spec(b"test-two", artifact_id="artifact-two"),
        _spec(b"test-three", artifact_id="artifact-three"),
    ]


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
                    "transfer_manifest_sha256": (spec.historical_transfer_manifest_sha256),
                }
                for spec in specs
            ],
        },
    )
    monkeypatch.setattr(
        fetcher,
        "_validate_document",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        fetcher,
        "claim_one_shot_execution",
        lambda *_args, **_kwargs: MemoryOneShotClaim(),
    )


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
    separator = chr(92)
    approved_parent_final = separator.join(
        ("approved-volume", "claude_allow", "download")
    ).casefold()
    quarantine_final = (
        approved_parent_final
        + separator
        + fetcher._ROUTE_B_CACHE_LEAF.casefold()
        + separator
        + "moved-quarantine"
    )
    route_cache_final = approved_parent_final + separator + fetcher._ROUTE_B_CACHE_LEAF.casefold()
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
        del writable
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
    _admit_for_test(monkeypatch, specs=_exact_three_test_specs(spec))
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
    _admit_for_test(monkeypatch, specs=_exact_three_test_specs(spec))
    transport = FakeTransport({spec.url: [FakeResponse(b"abcd", content_length=4)]})

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


def test_cli_reports_terminal_evidence_persisted_by_executor(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal: dict[str, object] = {
        "status": "B_SOURCE_BYTES_READY_AWAITING_EXTERNAL_REVIEW",
        "network_request_count": 3,
        "one_shot_lease_ref": (
            "E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/"
            "b-source-network-acquisition-one-shot-v1"
        ),
        "terminal_evidence_ref": (
            "E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/"
            "b-source-network-acquisition-one-shot-v1/terminal-v1/terminal.json"
        ),
        "terminal_evidence_sha256": "c" * 64,
    }
    monkeypatch.setattr(
        fetcher,
        "run_b_source_network_acquisition",
        lambda *_args, **_kwargs: terminal,
    )
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
    assert json.loads(result.output) == terminal


def test_same_runtime_second_execution_is_zero_network_and_preserves_first_terminal(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(b"abcd")
    _admit_for_test(
        monkeypatch,
        specs=_exact_three_test_specs(spec),
    )
    state: dict[str, object] = {"claimed": False, "terminal": None}

    class StatefulClaim(MemoryOneShotClaim):
        def persist_terminal(self, result: Mapping[str, object]) -> dict[str, str]:
            evidence = super().persist_terminal(result)
            state["terminal"] = dict(result)
            return evidence

    def claim_once(*_args: object, **_kwargs: object) -> StatefulClaim:
        if state["claimed"]:
            raise fetcher.BSourceAcquisitionError("NPI_B_SOURCE_ONE_SHOT_ALREADY_CLAIMED")
        state["claimed"] = True
        return StatefulClaim()

    monkeypatch.setattr(fetcher, "claim_one_shot_execution", claim_once)
    transport = FakeTransport({})

    first = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
        publisher=MemoryPublisher(),
    )
    first_terminal = state["terminal"]
    second = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
        publisher=MemoryPublisher(),
    )

    assert isinstance(first_terminal, dict)
    assert first["status"] == "B_SOURCE_NETWORK_ACQUISITION_FAILED"
    assert first["network_request_count"] == 1
    assert second["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert second["network_request_count"] == 0
    assert second["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_ALREADY_CLAIMED"
    assert transport.calls == [spec.url]
    assert state["terminal"] == first_terminal


class _MemoryRecordFile:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> _MemoryRecordFile:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read_all(self, *, max_bytes: int) -> bytes:
        assert len(self.payload) <= max_bytes
        return self.payload


class _MemoryRecordDirectory:
    def __init__(self, payload_name: str, record: Mapping[str, object]) -> None:
        self.payload_name = payload_name
        self.payload = fetcher._canonical_json_bytes(record)

    def __enter__(self) -> _MemoryRecordDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def list_names(self) -> set[str]:
        return {self.payload_name}

    def open_file(self, name: str) -> _MemoryRecordFile:
        if name != self.payload_name:
            raise FileNotFoundError(name)
        return _MemoryRecordFile(self.payload)


class _MemoryLeaseDirectory:
    def __init__(self, identity: str = "d" * 64) -> None:
        self.identity = SimpleNamespace(digest=identity)
        self.records: dict[str, tuple[str, dict[str, object]]] = {}
        self.closed = False

    def __enter__(self) -> _MemoryLeaseDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True

    def list_names(self) -> set[str]:
        return set(self.records)

    def open_directory(
        self,
        name: str,
        *,
        writable: bool,
    ) -> _MemoryRecordDirectory:
        del writable
        try:
            payload_name, record = self.records[name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc
        return _MemoryRecordDirectory(payload_name, record)


class _MemoryEvidenceParent:
    def __init__(self) -> None:
        self.lease: _MemoryLeaseDirectory | None = None

    def __enter__(self) -> _MemoryEvidenceParent:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def list_names(self) -> set[str]:
        return {fetcher._LEASE_DIRNAME} if self.lease is not None else set()

    def create_directory(self, name: str) -> _MemoryLeaseDirectory:
        assert name == fetcher._LEASE_DIRNAME
        if self.lease is not None:
            raise PromotionPathSafetyError("already exists")
        self.lease = _MemoryLeaseDirectory()
        return self.lease

    def open_directory(
        self,
        name: str,
        *,
        writable: bool,
    ) -> _MemoryLeaseDirectory:
        del writable
        if name != fetcher._LEASE_DIRNAME or self.lease is None:
            raise FileNotFoundError(name)
        self.lease.closed = False
        return self.lease


def _reservation_record(
    lease: _MemoryLeaseDirectory,
    *,
    nonce: str = "a" * 32,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "evidence_type": "B_SOURCE_NETWORK_ONE_SHOT_RESERVATION_V1",
        "status": "CLAIMED",
        "reviewed_head": "a" * 40,
        "reviewed_tree": "b" * 40,
        "lease_identity_sha256": lease.identity.digest,
        "nonce": nonce,
        "retry_authorized": False,
    }


def _terminal_record() -> dict[str, object]:
    return {
        "terminal": True,
        "retry_authorized": False,
        "one_shot_state": "COMPLETED",
    }


def _install_existing_lease_for_run(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    parent: _MemoryEvidenceParent,
) -> tuple[fetcher.DownloadTransport, fetcher.QuarantinePublisher]:
    actual_claim = fetcher.claim_one_shot_execution
    spec = _spec(b"abcd")
    _admit_for_test(monkeypatch, specs=_exact_three_test_specs(spec))
    monkeypatch.setattr(fetcher, "claim_one_shot_execution", actual_claim)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )
    return FakeTransport({}), MemoryPublisher()


def test_crash_after_lease_create_before_reservation_is_incomplete_and_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    class SimulatedCrash(RuntimeError):
        pass

    def crash(stage: str) -> None:
        if stage == "after_lease_create_before_reservation":
            raise SimulatedCrash(stage)

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", crash)
    with pytest.raises(SimulatedCrash):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)

    assert parent.lease is not None
    assert parent.lease.records == {}
    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", None)
    transport, publisher = _install_existing_lease_for_run(
        project_root,
        monkeypatch,
        parent,
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
        publisher=publisher,
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_crash_after_reservation_before_terminal_is_claimed_and_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    def publish_record(
        root: _MemoryLeaseDirectory,
        *,
        final_name: str,
        payload_name: str,
        record: Mapping[str, object],
    ) -> str:
        root.records[final_name] = (payload_name, dict(record))
        return hashlib.sha256(fetcher._canonical_json_bytes(record)).hexdigest()

    monkeypatch.setattr(fetcher, "_atomic_publish_json_record", publish_record)

    class SimulatedCrash(RuntimeError):
        pass

    def crash(stage: str) -> None:
        if stage == "after_reservation_publish_before_transport":
            raise SimulatedCrash(stage)

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", crash)
    with pytest.raises(SimulatedCrash):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)

    assert parent.lease is not None
    assert fetcher._RESERVATION_DIRNAME in parent.lease.records
    assert fetcher._TERMINAL_DIRNAME not in parent.lease.records
    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", None)
    transport, publisher = _install_existing_lease_for_run(
        project_root,
        monkeypatch,
        parent,
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
        publisher=publisher,
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_CLAIMED"
    assert result["one_shot_state"] == "CLAIMED"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_completed_lease_second_run_is_zero_http_and_does_not_overwrite(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory()
    reservation = _reservation_record(parent.lease)
    terminal = _terminal_record()
    parent.lease.records[fetcher._RESERVATION_DIRNAME] = (
        fetcher._RESERVATION_FILENAME,
        reservation,
    )
    parent.lease.records[fetcher._TERMINAL_DIRNAME] = (
        fetcher._TERMINAL_FILENAME,
        terminal,
    )
    before = dict(parent.lease.records)

    transport, publisher = _install_existing_lease_for_run(
        project_root,
        monkeypatch,
        parent,
    )
    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
        publisher=publisher,
    )
    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_COMPLETED"
    assert result["one_shot_state"] == "COMPLETED"
    assert result["network_request_count"] == 0
    assert transport.calls == []
    assert parent.lease.records == before


def test_terminal_rejects_replaced_lease_identity_and_nonce(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="e" * 64)
    parent.lease.records[fetcher._RESERVATION_DIRNAME] = (
        fetcher._RESERVATION_FILENAME,
        _reservation_record(parent.lease, nonce="b" * 32),
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)
    claim = fetcher.OneShotExecutionClaim(
        project_root=project_root,
        reviewed_head="a" * 40,
        reviewed_tree="b" * 40,
        evidence_parent_path=Path("fixed-evidence-parent"),
        lease_identity_sha256="d" * 64,
        nonce="a" * 32,
    )
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="LEASE_IDENTITY_MISMATCH",
    ):
        claim.persist_terminal(
            {
                "terminal": True,
                "retry_authorized": False,
                "one_shot_state": "CLAIMED",
            }
        )
