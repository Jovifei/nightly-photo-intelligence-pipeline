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
    _next_identity = 0

    def __init__(self, payload: bytes = b"", identity: str | None = None) -> None:
        self.payload = payload
        if identity is None:
            type(self)._next_identity += 1
            identity = hashlib.sha256(f"memory-file-{self._next_identity}".encode()).hexdigest()
        self.identity = SimpleNamespace(digest=identity)

    def write(self, payload: bytes) -> None:
        self.payload += payload

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None

    def sha256_and_size(self) -> tuple[str, int]:
        return hashlib.sha256(self.payload).hexdigest(), len(self.payload)

    def __enter__(self) -> _MemoryRecordFile:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read_all(self, *, max_bytes: int) -> bytes:
        assert len(self.payload) <= max_bytes
        return self.payload


class _MemoryRecordDirectory:
    def __init__(
        self,
        payload_name: str,
        record: Mapping[str, object],
        *,
        directory_identity: str = "f" * 64,
        file_identity: str = "e" * 64,
    ) -> None:
        self.payload_name = payload_name
        self.identity = SimpleNamespace(digest=directory_identity)
        self.files = {
            payload_name: _MemoryRecordFile(
                fetcher._canonical_json_bytes(record),
                identity=file_identity,
            )
        }

    def __enter__(self) -> _MemoryRecordDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def list_names(self) -> set[str]:
        return set(self.files)

    def open_file(self, name: str) -> _MemoryRecordFile:
        try:
            return self.files[name]
        except KeyError:
            raise FileNotFoundError(name) from None


class _MemoryLeaseDirectory:
    _next_identity = 0

    def __init__(self, identity: str = "d" * 64) -> None:
        self.identity = SimpleNamespace(digest=identity)
        self.records: dict[str, tuple[str, dict[str, object]]] = {}
        self.directories: dict[str, _MemoryLeaseDirectory] = {}
        self.files: dict[str, _MemoryRecordFile] = {}
        self.closed = False
        self._parent: _MemoryLeaseDirectory | None = None
        self._name: str | None = None

    def __enter__(self) -> _MemoryLeaseDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self.closed = True

    def list_names(self) -> set[str]:
        return set(self.records) | set(self.directories) | set(self.files)

    def create_directory(self, name: str) -> _MemoryLeaseDirectory:
        if name in self.list_names():
            raise FileExistsError(name)
        type(self)._next_identity += 1
        identity = hashlib.sha256(f"memory-directory-{self._next_identity}".encode()).hexdigest()
        child = _MemoryLeaseDirectory(identity=identity)
        child._parent = self
        child._name = name
        self.directories[name] = child
        return child

    def open_directory(
        self,
        name: str,
        *,
        writable: bool,
    ) -> _MemoryLeaseDirectory | _MemoryRecordDirectory:
        del writable
        if name in self.directories:
            directory = self.directories[name]
            directory.closed = False
            return directory
        try:
            payload_name, record = self.records[name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc
        return _MemoryRecordDirectory(payload_name, record)

    def create_file(self, name: str) -> _MemoryRecordFile:
        if name in self.list_names():
            raise FileExistsError(name)
        file = _MemoryRecordFile()
        self.files[name] = file
        return file

    def open_file(self, name: str) -> _MemoryRecordFile:
        try:
            return self.files[name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    def rename_to(self, destination: _MemoryLeaseDirectory, name: str) -> None:
        if name in destination.list_names():
            raise FileExistsError(name)
        if self._parent is None or self._name is None:
            raise AssertionError("memory staging directory has no parent")
        del self._parent.directories[self._name]
        destination.directories[name] = self
        self._parent = destination
        self._name = name

    def snapshot(self) -> dict[str, object]:
        return {
            "files": {name: file.payload for name, file in self.files.items()},
            "directories": {
                name: directory.snapshot() for name, directory in self.directories.items()
            },
            "records": dict(self.records),
        }


class _MemoryEvidenceParent:
    def __init__(self) -> None:
        self.root = _MemoryLeaseDirectory(identity="c" * 64)

    @property
    def lease(self) -> _MemoryLeaseDirectory | None:
        return self.root.directories.get(fetcher._LEASE_DIRNAME)

    @lease.setter
    def lease(self, value: _MemoryLeaseDirectory | None) -> None:
        if value is None:
            self.root.directories.pop(fetcher._LEASE_DIRNAME, None)
        else:
            value._parent = self.root
            value._name = fetcher._LEASE_DIRNAME
            self.root.directories[fetcher._LEASE_DIRNAME] = value

    def __enter__(self) -> _MemoryEvidenceParent:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def list_names(self) -> set[str]:
        return self.root.list_names()

    def create_directory(self, name: str) -> _MemoryLeaseDirectory:
        return self.root.create_directory(name)

    def open_directory(
        self,
        name: str,
        *,
        writable: bool,
    ) -> _MemoryLeaseDirectory | _MemoryRecordDirectory:
        return self.root.open_directory(name, writable=writable)


class _MemoryStagingTransaction:
    def __init__(self, root: _MemoryEvidenceParent | _MemoryLeaseDirectory) -> None:
        self.root = root.root if isinstance(root, _MemoryEvidenceParent) else root
        if ".staging" in self.root.directories:
            self.staging_parent = self.root.directories[".staging"]
        else:
            self.staging_parent = self.root.create_directory(".staging")
        type(self.root)._next_identity += 1
        self.staging_name = f"stage-{type(self.root)._next_identity}"
        self.staging = self.staging_parent.create_directory(self.staging_name)
        self._published = False

    @classmethod
    def create(
        cls,
        root: _MemoryEvidenceParent | _MemoryLeaseDirectory,
    ) -> _MemoryStagingTransaction:
        return cls(root)

    def create_file(self, name: str) -> _MemoryRecordFile:
        return self.staging.create_file(name)

    def publish(self, final_name: str) -> None:
        self.staging.rename_to(self.root, final_name)
        self._published = True

    def __enter__(self) -> _MemoryStagingTransaction:
        return self

    def __exit__(self, exc_type: object, *_args: object) -> None:
        # On a simulated process crash, leave staging behind for recovery tests.
        if exc_type is None and not self._published and not self.staging.list_names():
            del self.staging_parent.directories[self.staging_name]


def _use_memory_staging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        fetcher.BoundStagingTransaction,
        "create",
        classmethod(lambda _cls, root: _MemoryStagingTransaction.create(root)),
    )


def _reservation_record(
    lease: _MemoryLeaseDirectory,
    *,
    nonce: str = "a" * 32,
    reservation_directory_identity_sha256: str = "1" * 64,
    reservation_file_identity_sha256: str = "2" * 64,
    lease_identity_sha256: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "evidence_type": "B_SOURCE_NETWORK_ONE_SHOT_RESERVATION_V1",
        "status": "CLAIMED",
        "reviewed_head": "a" * 40,
        "reviewed_tree": "b" * 40,
        "lease_identity_sha256": lease_identity_sha256 or lease.identity.digest,
        "reservation_directory_identity_sha256": reservation_directory_identity_sha256,
        "reservation_file_identity_sha256": reservation_file_identity_sha256,
        "nonce": nonce,
        "retry_authorized": False,
    }


def _install_reservation(
    lease: _MemoryLeaseDirectory,
    *,
    nonce: str = "a" * 32,
) -> dict[str, object]:
    reservation_directory = lease.create_directory(fetcher._RESERVATION_DIRNAME)
    reservation_file = reservation_directory.create_file(fetcher._RESERVATION_FILENAME)
    record = _reservation_record(
        lease,
        nonce=nonce,
        reservation_directory_identity_sha256=reservation_directory.identity.digest,
        reservation_file_identity_sha256=reservation_file.identity.digest,
    )
    reservation_file.write(fetcher._canonical_json_bytes(record))
    reservation_file.flush()
    return record


def _install_record(
    lease: _MemoryLeaseDirectory,
    directory_name: str,
    file_name: str,
    record: Mapping[str, object],
) -> tuple[_MemoryLeaseDirectory, _MemoryRecordFile]:
    directory = lease.create_directory(directory_name)
    record_file = directory.create_file(file_name)
    record_file.write(fetcher._canonical_json_bytes(record))
    record_file.flush()
    return directory, record_file


def _terminal_record() -> dict[str, object]:
    return {
        "terminal": True,
        "retry_authorized": False,
        "one_shot_state": "COMPLETED",
    }


def _valid_terminal_result(reservation: Mapping[str, object]) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "evidence_type": "B_SOURCE_NETWORK_ACQUISITION_RESULT_V1",
        "status": "B_SOURCE_NETWORK_ACQUISITION_FAILED",
        "failure_code": "TEST_NETWORK_FAILURE",
        "reviewed_head": reservation["reviewed_head"],
        "reviewed_tree": reservation["reviewed_tree"],
        "quarantine_root_ref": fetcher._QUARANTINE_REF,
        "quarantine_root_identity_sha256": fetcher._QUARANTINE_IDENTITY,
        "network_request_count": 1,
        "artifact_results": [],
        "one_shot_state": "COMPLETED",
        "terminal": True,
        "retry_authorized": False,
        "cache_promotion": "NOT_AUTHORIZED",
        "model_cuda_photo_exif_sqlite_real20": "NOT_AUTHORIZED",
        "mandatory_stop": "EXTERNAL_REVIEW_B_SOURCE_ACQUISITION_FAILURE",
    }


def _install_valid_terminal_bundle(
    lease: _MemoryLeaseDirectory,
    reservation: Mapping[str, object],
) -> None:
    reservation_directory = lease.directories[fetcher._RESERVATION_DIRNAME]
    reservation_file = reservation_directory.files[fetcher._RESERVATION_FILENAME]
    terminal_directory = lease.create_directory(fetcher._TERMINAL_DIRNAME)
    terminal_file = terminal_directory.create_file(fetcher._TERMINAL_FILENAME)
    result = _valid_terminal_result(reservation)
    result_bytes = fetcher._canonical_json_bytes(result)
    terminal_file.write(result_bytes)
    terminal_file.flush()
    binding_file = terminal_directory.create_file(fetcher._TERMINAL_BINDING_FILENAME)
    binding = {
        "schema_version": "1.0",
        "evidence_type": "B_SOURCE_NETWORK_ONE_SHOT_TERMINAL_BINDING_V1",
        "status": "COMPLETED_BINDING",
        "reviewed_head": reservation["reviewed_head"],
        "reviewed_tree": reservation["reviewed_tree"],
        "lease_identity_sha256": lease.identity.digest,
        "reservation_directory_identity_sha256": reservation_directory.identity.digest,
        "reservation_file_identity_sha256": reservation_file.identity.digest,
        "reservation_sha256": hashlib.sha256(reservation_file.payload).hexdigest(),
        "nonce_sha256": hashlib.sha256(str(reservation["nonce"]).encode("ascii")).hexdigest(),
        "terminal_directory_identity_sha256": terminal_directory.identity.digest,
        "terminal_file_identity_sha256": terminal_file.identity.digest,
        "terminal_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "binding_file_identity_sha256": binding_file.identity.digest,
        "retry_authorized": False,
    }
    binding_file.write(fetcher._canonical_json_bytes(binding))
    binding_file.flush()


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
    _use_memory_staging(monkeypatch)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    class SimulatedCrash(RuntimeError):
        pass

    def crash(stage: str) -> None:
        if stage == "after_lease_staging_created_before_reservation":
            raise SimulatedCrash(stage)

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", crash)
    with pytest.raises(SimulatedCrash):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)

    assert parent.lease is None
    assert ".staging" in parent.list_names()
    assert parent.root.directories[".staging"].list_names()
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


def test_crash_after_staged_reservation_before_lease_publish_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    _use_memory_staging(monkeypatch)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    class SimulatedCrash(RuntimeError):
        pass

    def crash(stage: str) -> None:
        if stage == "after_reservation_publish_before_lease":
            raise SimulatedCrash(stage)

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", crash)
    with pytest.raises(SimulatedCrash):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)

    assert parent.lease is None
    assert ".staging" in parent.list_names()
    staged_parent = parent.root.directories[".staging"]
    assert len(staged_parent.directories) == 1
    staged_lease = next(iter(staged_parent.directories.values()))
    assert fetcher._RESERVATION_DIRNAME in staged_lease.directories

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_crash_after_reservation_before_terminal_is_incomplete_and_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    _use_memory_staging(monkeypatch)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    class SimulatedCrash(RuntimeError):
        pass

    def crash(stage: str) -> None:
        if stage == "after_reservation_publish_before_transport":
            raise SimulatedCrash(stage)

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", crash)
    with pytest.raises(SimulatedCrash):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)

    assert parent.lease is not None
    assert fetcher._RESERVATION_DIRNAME in parent.lease.directories
    assert fetcher._TERMINAL_DIRNAME not in parent.lease.directories
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


def test_existing_reservation_with_wrong_lease_identity_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="d" * 64)
    reservation = _reservation_record(parent.lease)
    reservation["lease_identity_sha256"] = "e" * 64
    parent.lease.records[fetcher._RESERVATION_DIRNAME] = (
        fetcher._RESERVATION_FILENAME,
        reservation,
    )

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_existing_reservation_file_identity_drift_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="d" * 64)
    _install_reservation(parent.lease)
    reservation_file = parent.lease.directories[fetcher._RESERVATION_DIRNAME].files[
        fetcher._RESERVATION_FILENAME
    ]
    reservation_file.identity.digest = "f" * 64

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_existing_reservation_directory_identity_drift_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="d" * 64)
    _install_reservation(parent.lease)
    parent.lease.directories[fetcher._RESERVATION_DIRNAME].identity.digest = "f" * 64

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


@pytest.mark.parametrize("binding_field", ["reviewed_head", "reviewed_tree"])
def test_existing_reservation_review_binding_drift_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    binding_field: str,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="d" * 64)
    _install_reservation(parent.lease)
    reservation_file = parent.lease.directories[fetcher._RESERVATION_DIRNAME].files[
        fetcher._RESERVATION_FILENAME
    ]
    reservation = json.loads(reservation_file.payload.decode("utf-8"))
    reservation[binding_field] = "c" * 40
    reservation_file.payload = fetcher._canonical_json_bytes(reservation)

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_minimal_terminal_without_durable_claim_binding_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory()
    parent.lease.records[fetcher._RESERVATION_DIRNAME] = (
        fetcher._RESERVATION_FILENAME,
        _reservation_record(parent.lease),
    )
    parent.lease.records[fetcher._TERMINAL_DIRNAME] = (
        fetcher._TERMINAL_FILENAME,
        _terminal_record(),
    )

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_terminal_result_digest_drift_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory()
    reservation = _install_reservation(parent.lease)
    _install_valid_terminal_bundle(parent.lease, reservation)
    terminal_file = parent.lease.directories[fetcher._TERMINAL_DIRNAME].files[
        fetcher._TERMINAL_FILENAME
    ]
    terminal_file.payload += b"tampered"

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


@pytest.mark.parametrize(
    "identity_scope",
    ["terminal_directory", "terminal_file", "binding_file"],
)
def test_terminal_object_identity_drift_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    identity_scope: str,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory()
    reservation = _install_reservation(parent.lease)
    _install_valid_terminal_bundle(parent.lease, reservation)
    terminal_directory = parent.lease.directories[fetcher._TERMINAL_DIRNAME]
    if identity_scope == "terminal_directory":
        terminal_directory.identity.digest = "f" * 64
    elif identity_scope == "binding_file":
        terminal_directory.files[fetcher._TERMINAL_BINDING_FILENAME].identity.digest = "f" * 64
    else:
        terminal_directory.files[fetcher._TERMINAL_FILENAME].identity.digest = "f" * 64

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


@pytest.mark.parametrize(
    "directory_name,unexpected_name",
    [
        (fetcher._RESERVATION_DIRNAME, "extra.json"),
        (fetcher._TERMINAL_DIRNAME, "extra.json"),
    ],
)
def test_one_shot_record_directory_rejects_extra_files_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    directory_name: str,
    unexpected_name: str,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory()
    reservation = _install_reservation(parent.lease)
    _install_valid_terminal_bundle(parent.lease, reservation)
    parent.lease.directories[directory_name].create_file(unexpected_name)

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


@pytest.mark.parametrize(
    "binding_field,bad_value",
    [
        ("nonce_sha256", "f" * 64),
        ("reviewed_head", "c" * 40),
        ("reviewed_tree", "c" * 40),
        ("terminal_sha256", "f" * 64),
        ("terminal_directory_identity_sha256", "f" * 64),
        ("terminal_file_identity_sha256", "f" * 64),
        ("binding_file_identity_sha256", "f" * 64),
    ],
)
def test_terminal_binding_field_drift_is_incomplete_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    binding_field: str,
    bad_value: str,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory()
    reservation = _install_reservation(parent.lease)
    _install_valid_terminal_bundle(parent.lease, reservation)
    binding_file = parent.lease.directories[fetcher._TERMINAL_DIRNAME].files[
        fetcher._TERMINAL_BINDING_FILENAME
    ]
    binding = json.loads(binding_file.payload.decode("utf-8"))
    binding[binding_field] = bad_value
    binding_file.payload = fetcher._canonical_json_bytes(binding)

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_persist_terminal_rejects_result_bound_to_another_head(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="d" * 64)
    _install_reservation(parent.lease)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)

    reservation_directory = parent.lease.directories[fetcher._RESERVATION_DIRNAME]
    reservation_file = reservation_directory.files[fetcher._RESERVATION_FILENAME]
    claim = fetcher.OneShotExecutionClaim(
        project_root=project_root,
        reviewed_head="a" * 40,
        reviewed_tree="b" * 40,
        evidence_parent_path=Path("fixed-evidence-parent"),
        lease_identity_sha256="d" * 64,
        reservation_directory_identity_sha256=reservation_directory.identity.digest,
        reservation_file_identity_sha256=reservation_file.identity.digest,
        reservation_sha256=hashlib.sha256(reservation_file.payload).hexdigest(),
        nonce="a" * 32,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="TERMINAL_RESULT_BINDING_MISMATCH",
    ):
        claim.persist_terminal(
            {
                "reviewed_head": "c" * 40,
                "reviewed_tree": "b" * 40,
                "terminal": True,
                "retry_authorized": False,
                "one_shot_state": "CLAIMED",
            }
        )


def test_completed_lease_second_run_is_zero_http_and_does_not_overwrite(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory()
    reservation = _install_reservation(parent.lease)
    _install_valid_terminal_bundle(parent.lease, reservation)
    before = parent.lease.snapshot()

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
    assert parent.lease.snapshot() == before


def test_terminal_rejects_replaced_lease_identity_and_nonce(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="e" * 64)
    _install_reservation(parent.lease, nonce="b" * 32)
    reservation_directory = parent.lease.directories[fetcher._RESERVATION_DIRNAME]
    reservation_file = reservation_directory.files[fetcher._RESERVATION_FILENAME]
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
        reservation_directory_identity_sha256=reservation_directory.identity.digest,
        reservation_file_identity_sha256=reservation_file.identity.digest,
        reservation_sha256=hashlib.sha256(reservation_file.payload).hexdigest(),
        nonce="a" * 32,
    )
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="LEASE_IDENTITY_MISMATCH",
    ):
        claim.persist_terminal(
            {
                "reviewed_head": "a" * 40,
                "reviewed_tree": "b" * 40,
                "terminal": True,
                "retry_authorized": False,
                "one_shot_state": "CLAIMED",
            }
        )


def test_terminal_rejects_reservation_nonce_drift(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    parent.lease = _MemoryLeaseDirectory(identity="d" * 64)
    _install_reservation(parent.lease, nonce="b" * 32)
    reservation_directory = parent.lease.directories[fetcher._RESERVATION_DIRNAME]
    reservation_file = reservation_directory.files[fetcher._RESERVATION_FILENAME]
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
        reservation_directory_identity_sha256=reservation_directory.identity.digest,
        reservation_file_identity_sha256=reservation_file.identity.digest,
        reservation_sha256=hashlib.sha256(reservation_file.payload).hexdigest(),
        nonce="a" * 32,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="RESERVATION_INVALID",
    ):
        claim.persist_terminal(
            {
                "reviewed_head": "a" * 40,
                "reviewed_tree": "b" * 40,
                "terminal": True,
                "retry_authorized": False,
                "one_shot_state": "CLAIMED",
            }
        )


def test_live_claim_publishes_bound_terminal_and_restart_is_completed_zero_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    _use_memory_staging(monkeypatch)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )
    claim = fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)
    assert parent.lease is not None
    reservation = json.loads(
        parent.lease.directories[fetcher._RESERVATION_DIRNAME]
        .files[fetcher._RESERVATION_FILENAME]
        .payload.decode("utf-8")
    )

    references = claim.persist_terminal(_valid_terminal_result(reservation))

    assert (
        references["terminal_evidence_sha256"]
        == hashlib.sha256(
            parent.lease.directories[fetcher._TERMINAL_DIRNAME]
            .files[fetcher._TERMINAL_FILENAME]
            .payload
        ).hexdigest()
    )
    assert set(parent.lease.directories[fetcher._TERMINAL_DIRNAME].files) == {
        fetcher._TERMINAL_FILENAME,
        fetcher._TERMINAL_BINDING_FILENAME,
    }
    before = parent.lease.snapshot()

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

    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_COMPLETED"
    assert result["one_shot_state"] == "COMPLETED"
    assert result["network_request_count"] == 0
    assert transport.calls == []
    assert parent.lease.snapshot() == before


def test_crash_before_terminal_after_first_http_blocks_second_http(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    _use_memory_staging(monkeypatch)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    actual_claim = fetcher.claim_one_shot_execution
    spec = _spec(b"abcd")
    _admit_for_test(monkeypatch, specs=_exact_three_test_specs(spec))
    monkeypatch.setattr(fetcher, "claim_one_shot_execution", actual_claim)

    class SimulatedCrash(RuntimeError):
        pass

    def crash(stage: str) -> None:
        if stage == "after_reservation_validation_before_terminal":
            raise SimulatedCrash(stage)

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", crash)
    first_transport = FakeTransport({})
    with pytest.raises(SimulatedCrash):
        fetcher.run_b_source_network_acquisition(
            project_root,
            Path("review.json"),
            Path("missing.json"),
            transport=first_transport,
            publisher=MemoryPublisher(),
        )
    assert first_transport.calls == [spec.url]
    assert parent.lease is not None
    assert fetcher._RESERVATION_DIRNAME in parent.lease.directories
    assert fetcher._TERMINAL_DIRNAME not in parent.lease.directories
    reservation_file = parent.lease.directories[fetcher._RESERVATION_DIRNAME].files[
        fetcher._RESERVATION_FILENAME
    ]
    reservation_before = reservation_file.payload

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", None)
    second_transport = FakeTransport({})
    second = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=second_transport,
        publisher=MemoryPublisher(),
    )
    assert second["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert second["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert second["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert second["network_request_count"] == 0
    assert second_transport.calls == []
    assert reservation_file.payload == reservation_before


def test_crash_during_terminal_staging_blocks_second_http_and_preserves_reservation(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _MemoryEvidenceParent()
    _use_memory_staging(monkeypatch)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )
    actual_claim = fetcher.claim_one_shot_execution
    spec = _spec(b"abcd")
    _admit_for_test(monkeypatch, specs=_exact_three_test_specs(spec))
    monkeypatch.setattr(fetcher, "claim_one_shot_execution", actual_claim)

    class SimulatedCrash(RuntimeError):
        pass

    def crash(stage: str) -> None:
        if stage == "after_terminal_bundle_staged_before_publish":
            raise SimulatedCrash(stage)

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", crash)
    first_transport = FakeTransport({})
    with pytest.raises(SimulatedCrash):
        fetcher.run_b_source_network_acquisition(
            project_root,
            Path("review.json"),
            Path("missing.json"),
            transport=first_transport,
            publisher=MemoryPublisher(),
        )
    assert first_transport.calls == [spec.url]
    assert parent.lease is not None
    assert fetcher._TERMINAL_DIRNAME not in parent.lease.directories
    reservation_file = parent.lease.directories[fetcher._RESERVATION_DIRNAME].files[
        fetcher._RESERVATION_FILENAME
    ]
    reservation_before = reservation_file.payload

    monkeypatch.setattr(fetcher, "_ONE_SHOT_TEST_HOOK", None)
    second_transport = FakeTransport({})
    second = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=second_transport,
        publisher=MemoryPublisher(),
    )

    assert second["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert second["one_shot_state"] == "INCOMPLETE_CLAIM"
    assert second["network_request_count"] == 0
    assert second_transport.calls == []
    assert reservation_file.payload == reservation_before
