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
from nightly_photo_intelligence_pipeline.json_strict import loads_json_strict


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
            "terminal_evidence_ref": (
                "E_CLAUDE_ALLOW_DOWNLOAD/npi-c2c-evidence-20260930/"
                "b-source-network-acquisition-one-shot-v1/terminal/terminal.json"
            ),
            "terminal_evidence_sha256": hashlib.sha256(payload).hexdigest(),
        }

    def close(self) -> None:
        return None


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
        directories: dict[str, _FakeBoundDirectory] | None = None,
    ) -> None:
        self.identity = SimpleNamespace(
            digest=digest,
            final_path=final_path,
            volume_serial_number=volume,
        )
        self._names = names or set()
        self._directories = directories or {}

    def list_names(self) -> set[str]:
        return set(self._names)

    def close(self) -> None:
        return None

    def open_directory(
        self,
        name: str,
        *,
        writable: bool | None = None,
    ) -> _FakeBoundDirectory:
        del writable
        try:
            return self._directories[name]
        except KeyError as exc:
            raise FileNotFoundError(name) from exc

    def __enter__(self) -> _FakeBoundDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class _MemoryBoundFile:
    def __init__(
        self,
        *,
        name: str,
        parent: _MemoryBoundDirectory,
        events: list[tuple[str, str]],
    ) -> None:
        self.name = name
        self.parent = parent
        self.events = events
        self.data = bytearray()
        file_id = hashlib.sha256(
            (parent.identity.final_path + chr(92) + name + ":" + str(len(events))).encode()
        ).hexdigest()[:32]
        self.identity = SimpleNamespace(
            volume_serial_number=1,
            file_id_hex=file_id,
            final_path=parent.identity.final_path + chr(92) + name,
            digest=hashlib.sha256(f"{1:016x}:{file_id}".encode("ascii")).hexdigest(),
        )

    def __enter__(self) -> _MemoryBoundFile:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def write(self, payload: bytes) -> None:
        self.data.extend(payload)
        self.events.append(("write", self.name))

    def flush(self) -> None:
        self.events.append(("flush", self.name))

    def read_all(self, *, max_bytes: int) -> bytes:
        assert len(self.data) <= max_bytes
        return bytes(self.data)

    def sha256_and_size(self) -> tuple[str, int]:
        return hashlib.sha256(self.data).hexdigest(), len(self.data)

    def close(self) -> None:
        return None

    def _verify(self) -> None:
        return None


class _MemoryBoundDirectory:
    def __init__(
        self,
        *,
        path: str,
        events: list[tuple[str, str]],
        parent: _MemoryBoundDirectory | None = None,
        name: str = "root",
        fail_create_files: set[str] | None = None,
    ) -> None:
        self.path = path
        self.events = events
        self.parent = parent
        self.name = name
        self._directories: dict[str, _MemoryBoundDirectory] = {}
        self._files: dict[str, _MemoryBoundFile] = {}
        self.fail_create_files = fail_create_files or set()
        file_id = hashlib.sha256(path.encode()).hexdigest()[:32]
        self.identity = SimpleNamespace(
            digest=hashlib.sha256(f"{1:016x}:{file_id}".encode("ascii")).hexdigest(),
            volume_serial_number=1,
            file_id_hex=file_id,
            final_path=path,
        )

    def __enter__(self) -> _MemoryBoundDirectory:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def close(self) -> None:
        return None

    def _verify(self) -> None:
        return None

    def list_names(self) -> set[str]:
        return set(self._directories) | set(self._files)

    def create_directory(self, name: str) -> _MemoryBoundDirectory:
        if name in self.list_names():
            raise FileExistsError(name)
        child_path = self.path + chr(92) + name
        child = _MemoryBoundDirectory(
            path=child_path,
            events=self.events,
            parent=self,
            name=name,
            fail_create_files=self.fail_create_files.copy(),
        )
        self._directories[name] = child
        self.events.append(("mkdir", name))
        return child

    def open_directory(
        self,
        name: str,
        *,
        writable: bool | None = None,
    ) -> _MemoryBoundDirectory:
        del writable
        return self._directories[name]

    def create_file(self, name: str) -> _MemoryBoundFile:
        if name in self.fail_create_files:
            raise PromotionPathSafetyError("NPI_PROMOTION_RACE_DETECTED")
        if name in self.list_names():
            raise FileExistsError(name)
        file = _MemoryBoundFile(name=name, parent=self, events=self.events)
        self._files[name] = file
        self.events.append(("create_file", name))
        return file

    def open_file(self, name: str) -> _MemoryBoundFile:
        return self._files[name]

    def rename_to(
        self,
        destination_root: _MemoryBoundDirectory,
        destination_name: str,
    ) -> None:
        if destination_name in destination_root.list_names():
            raise FileExistsError(destination_name)
        assert self.parent is not None
        del self.parent._directories[self.name]
        self.name = destination_name
        self.parent = destination_root
        self.path = destination_root.path + chr(92) + destination_name
        self.identity.final_path = self.path
        destination_root._directories[destination_name] = self
        self.events.append(("rename", destination_name))


def _completed_one_shot_state(
    *,
    corrupt_result_binding: bool = False,
) -> _MemoryBoundDirectory:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    lease = evidence_parent.create_directory(fetcher._LEASE_DIRNAME)
    head = "a" * 40
    tree = "b" * 40
    nonce = "c" * 64
    with lease.create_file(fetcher._RESERVATION_FILENAME) as target:
        reservation_file_identity_sha256 = target.identity.digest
        reservation = {
            "schema_version": "1.0",
            "evidence_type": "B_SOURCE_NETWORK_ONE_SHOT_RESERVATION_V1",
            "state": "CLAIMED",
            "reviewed_head": head,
            "reviewed_tree": tree,
            "lease_identity_sha256": lease.identity.digest,
            "reservation_file_identity_sha256": reservation_file_identity_sha256,
            "nonce": nonce,
            "claimed_at_utc": "2026-10-01T00:00:00Z",
            "retry_authorized": False,
        }
        target.write(fetcher._canonical_json_bytes(reservation))
    result: dict[str, object] = {
        "schema_version": "1.0",
        "evidence_type": "B_SOURCE_NETWORK_ACQUISITION_RESULT_V1",
        "status": "B_SOURCE_NETWORK_ACQUISITION_BLOCKED",
        "failure_code": "NPI_B_SOURCE_NOT_ADMITTED",
        "reviewed_head": head,
        "reviewed_tree": tree,
        "quarantine_root_ref": (
            "E_CLAUDE_ALLOW_DOWNLOAD/npi-n2b1p-b-source-quarantine-20260930-e9110783"
        ),
        "quarantine_root_identity_sha256": "UNBOUND",
        "network_request_count": 0,
        "artifact_results": [],
        "terminal": True,
        "retry_authorized": False,
        "cache_promotion": "NOT_AUTHORIZED",
        "model_cuda_photo_exif_sqlite_real20": "NOT_AUTHORIZED",
        "mandatory_stop": "EXTERNAL_REVIEW_B_SOURCE_ACQUISITION_FAILURE",
    }
    result_bytes = fetcher._canonical_json_bytes(result)
    terminal = lease.create_directory(fetcher._TERMINAL_DIRNAME)
    with terminal.create_file(fetcher._TERMINAL_FILENAME) as target:
        target.write(result_bytes)
    binding = {
        "schema_version": "1.0",
        "evidence_type": "B_SOURCE_NETWORK_ONE_SHOT_TERMINAL_V1",
        "state": "COMPLETED",
        "reviewed_head": head,
        "reviewed_tree": tree,
        "lease_identity_sha256": lease.identity.digest,
        "reservation_file_identity_sha256": reservation_file_identity_sha256,
        "nonce_sha256": hashlib.sha256(nonce.encode("ascii")).hexdigest(),
        "terminal_result_sha256": "0" * 64
        if corrupt_result_binding
        else hashlib.sha256(result_bytes).hexdigest(),
        "retry_authorized": False,
    }
    with terminal.create_file(fetcher._TERMINAL_BINDING_FILENAME) as target:
        target.write(fetcher._canonical_json_bytes(binding))
    return evidence_parent


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
            "b-source-network-acquisition-one-shot-v1/terminal/terminal.json"
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


def test_existing_empty_one_shot_lease_is_incomplete_claim(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = _FakeBoundDirectory(
        digest="f" * 64,
        final_path="approved-evidence-parent/lease",
    )
    parent = _FakeBoundDirectory(
        digest="e" * 64,
        final_path="approved-evidence-parent",
        names={fetcher._LEASE_DIRNAME},
        directories={fetcher._LEASE_DIRNAME: lease},
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)


def test_existing_one_shot_lease_with_reservation_is_not_retried(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = _FakeBoundDirectory(
        digest="f" * 64,
        final_path="approved-evidence-parent/lease",
        names={fetcher._RESERVATION_FILENAME},
    )
    parent = _FakeBoundDirectory(
        digest="e" * 64,
        final_path="approved-evidence-parent",
        names={fetcher._LEASE_DIRNAME},
        directories={fetcher._LEASE_DIRNAME: lease},
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)


def test_completed_one_shot_lease_is_classified_completed(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _completed_one_shot_state()
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_ALREADY_COMPLETED",
    ):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)


def test_corrupt_terminal_binding_is_incomplete_and_not_retried(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _completed_one_shot_state(corrupt_result_binding=True)
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)


def test_claim_staging_after_crash_is_incomplete_and_not_retried(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = _FakeBoundDirectory(
        digest="e" * 64,
        final_path="approved-evidence-parent",
        names={"b-source-network-acquisition-one-shot-staging-v1"},
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)


def test_claim_crash_after_staging_create_is_incomplete_and_not_retried(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
        fail_create_files={fetcher._RESERVATION_FILENAME},
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)

    with pytest.raises(PromotionPathSafetyError):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)
    assert fetcher._LEASE_STAGING_DIRNAME in evidence_parent.list_names()

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)


def test_terminal_write_crash_leaves_incomplete_lease_and_blocks_retry(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)
    claim = fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)
    claim.lease.fail_create_files.add(fetcher._TERMINAL_BINDING_FILENAME)
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="TERMINAL_PERSIST_FAILED",
    ):
        claim.persist_terminal(
            {
                "reviewed_head": "a" * 40,
                "reviewed_tree": "b" * 40,
                "status": "B_SOURCE_NETWORK_ACQUISITION_FAILED",
                "network_request_count": 1,
            }
        )
    claim.lease.fail_create_files.clear()
    claim.close()

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)


def test_claim_flushes_reservation_before_atomic_lease_publish(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)

    claim = fetcher.claim_one_shot_execution(
        project_root,
        "a" * 40,
        "b" * 40,
    )
    try:
        flush_index = events.index(("flush", fetcher._RESERVATION_FILENAME))
        publish_index = events.index(("rename", fetcher._LEASE_DIRNAME))
        assert flush_index < publish_index
        assert fetcher._LEASE_DIRNAME in evidence_parent.list_names()
    finally:
        close = getattr(claim, "close", None)
        if close is not None:
            close()


def test_terminal_record_is_staged_and_atomically_published(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)
    claim = fetcher.claim_one_shot_execution(
        project_root,
        "a" * 40,
        "b" * 40,
    )
    try:
        result: dict[str, object] = {
            "reviewed_head": "a" * 40,
            "reviewed_tree": "b" * 40,
            "status": "B_SOURCE_NETWORK_ACQUISITION_FAILED",
            "network_request_count": 1,
        }
        claim.persist_terminal(result)
        terminal_publish_index = events.index(("rename", fetcher._TERMINAL_DIRNAME))
        terminal_flush_index = events.index(("flush", fetcher._TERMINAL_FILENAME))
        assert terminal_flush_index < terminal_publish_index
        lease = evidence_parent._directories[fetcher._LEASE_DIRNAME]
        assert fetcher._TERMINAL_DIRNAME in lease.list_names()
        terminal = lease._directories[fetcher._TERMINAL_DIRNAME]
        assert fetcher._TERMINAL_FILENAME in terminal.list_names()
        assert fetcher._TERMINAL_BINDING_FILENAME in terminal.list_names()
        binding = loads_json_strict(
            terminal._files[fetcher._TERMINAL_BINDING_FILENAME].read_all(max_bytes=64 * 1024)
        )
        assert binding["lease_identity_sha256"] == claim.lease_identity.digest
        assert binding["reservation_file_identity_sha256"] == claim.reservation_identity.digest
        assert binding["nonce_sha256"] == hashlib.sha256(claim.nonce.encode("ascii")).hexdigest()
    finally:
        close = getattr(claim, "close", None)
        if close is not None:
            close()


def test_terminal_result_must_match_claimed_head_and_tree(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)
    claim = fetcher.claim_one_shot_execution(project_root, "a" * 40, "b" * 40)
    try:
        result = {
            "reviewed_head": "c" * 40,
            "reviewed_tree": "d" * 40,
        }
        with pytest.raises(
            fetcher.BSourceAcquisitionError,
            match="TERMINAL_RESULT_BINDING_MISMATCH",
        ):
            claim.persist_terminal(result)
        assert fetcher._TERMINAL_STAGING_DIRNAME not in claim.lease.list_names()
    finally:
        claim.close()


def test_claim_reservation_binds_review_and_lease_identity_with_nonce(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)
    claim = fetcher.claim_one_shot_execution(
        project_root,
        "a" * 40,
        "b" * 40,
    )
    try:
        reservation = loads_json_strict(claim.reservation_file.read_all(max_bytes=64 * 1024))
        assert reservation["state"] == "CLAIMED"
        assert reservation["reviewed_head"] == "a" * 40
        assert reservation["reviewed_tree"] == "b" * 40
        assert reservation["lease_identity_sha256"] == claim.lease_identity.digest
        assert reservation["reservation_file_identity_sha256"] == claim.reservation_identity.digest
        assert reservation["nonce"] == claim.nonce
        assert reservation["retry_authorized"] is False
    finally:
        claim.close()


def test_replaced_reservation_identity_is_rejected_before_terminal_publish(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(fetcher, "_validate_document", lambda *_args, **_kwargs: None)
    claim = fetcher.claim_one_shot_execution(
        project_root,
        "a" * 40,
        "b" * 40,
    )
    claim.reservation_file.identity = SimpleNamespace(
        volume_serial_number=1,
        file_id_hex="0" * 32,
        final_path="approved-evidence-parent/lease/reservation.json",
    )
    try:
        with pytest.raises(
            fetcher.BSourceAcquisitionError,
            match="RESERVATION_IDENTITY_MISMATCH",
        ):
            claim.persist_terminal(
                {
                    "reviewed_head": "a" * 40,
                    "reviewed_tree": "b" * 40,
                    "status": "B_SOURCE_NETWORK_ACQUISITION_FAILED",
                    "network_request_count": 1,
                }
            )
        assert ("mkdir", fetcher._TERMINAL_STAGING_DIRNAME) not in events
    finally:
        claim.close()


def test_terminal_staging_crash_blocks_second_claim(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lease = _FakeBoundDirectory(
        digest="f" * 64,
        final_path="approved-evidence-parent/lease",
        names={
            fetcher._RESERVATION_FILENAME,
            fetcher._TERMINAL_STAGING_DIRNAME,
        },
    )
    parent = _FakeBoundDirectory(
        digest="e" * 64,
        final_path="approved-evidence-parent",
        names={fetcher._LEASE_DIRNAME},
        directories={fetcher._LEASE_DIRNAME: lease},
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: parent,
    )

    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(
            project_root,
            "a" * 40,
            "b" * 40,
        )


def test_real_one_shot_second_invocation_makes_zero_http_requests(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_spec = _spec(b"abcd", artifact_id="artifact-one")
    specs = _exact_three_test_specs(first_spec)
    _admit_for_test(monkeypatch, specs=specs)
    events: list[tuple[str, str]] = []
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=events,
    )
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(
        fetcher,
        "claim_one_shot_execution",
        lambda _root, head, tree: fetcher.OneShotExecutionClaim.claim(
            project_root,
            head,
            tree,
        ),
    )
    first_transport = FakeTransport(
        {
            first_spec.url: [
                FakeResponse(b"abcd", content_length=4),
            ]
        }
    )
    first = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=first_transport,
        publisher=MemoryPublisher(),
    )
    second_transport = FakeTransport({})
    second = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=second_transport,
        publisher=MemoryPublisher(),
    )

    assert first["status"] == "B_SOURCE_NETWORK_ACQUISITION_FAILED"
    assert first["network_request_count"] == 2
    assert first["terminal_evidence_ref"].endswith("terminal/terminal.json")
    assert second["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert second["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_ALREADY_COMPLETED"
    assert second["network_request_count"] == 0
    assert second_transport.calls == []


def test_replaced_reservation_after_restart_blocks_network_request(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = _spec(b"four", artifact_id="artifact-one")
    _admit_for_test(monkeypatch, specs=_exact_three_test_specs(spec))
    evidence_parent = _completed_one_shot_state()
    lease = evidence_parent._directories[fetcher._LEASE_DIRNAME]
    original = lease._files[fetcher._RESERVATION_FILENAME]
    original_bytes = original.read_all(max_bytes=16 * 1024)
    replacement = _MemoryBoundFile(
        name=fetcher._RESERVATION_FILENAME,
        parent=lease,
        events=original.events,
    )
    replacement.write(original_bytes)
    assert replacement.identity.digest != original.identity.digest
    lease._files[fetcher._RESERVATION_FILENAME] = replacement
    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    monkeypatch.setattr(
        fetcher,
        "claim_one_shot_execution",
        lambda _root, head, tree: fetcher.OneShotExecutionClaim.claim(
            project_root,
            head,
            tree,
        ),
    )
    transport = FakeTransport({})

    result = fetcher.run_b_source_network_acquisition(
        project_root,
        Path("review.json"),
        Path("missing.json"),
        transport=transport,
        publisher=MemoryPublisher(),
    )

    assert result["status"] == "B_SOURCE_NETWORK_ACQUISITION_BLOCKED"
    assert result["failure_code"] == "NPI_B_SOURCE_ONE_SHOT_INCOMPLETE_CLAIM"
    assert result["network_request_count"] == 0
    assert transport.calls == []


def test_existing_one_shot_marker_rejects_claim(
    project_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evidence_parent = _MemoryBoundDirectory(
        path="approved-evidence-parent",
        events=[],
    )
    evidence_parent.create_directory(fetcher._LEASE_DIRNAME)

    monkeypatch.setattr(fetcher.os, "name", "nt")
    monkeypatch.setattr(
        fetcher,
        "bind_existing_directory",
        lambda *_args, **_kwargs: evidence_parent,
    )
    with pytest.raises(
        fetcher.BSourceAcquisitionError,
        match="ONE_SHOT_INCOMPLETE_CLAIM",
    ):
        fetcher.claim_one_shot_execution(
            project_root,
            "a" * 40,
            "b" * 40,
        )
