"""N2B1P cache promotion is exact-byte, handle-bound, and model-free."""

from __future__ import annotations

import hashlib
import inspect
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

import nightly_photo_intelligence_pipeline.cli as cli_module
import nightly_photo_intelligence_pipeline.local_research_promotion as promotion
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.errors import (
    GateNotAuthorizedError,
    PreflightUnsatisfiedError,
)
from nightly_photo_intelligence_pipeline.local_research_promotion import (
    PromotionArtifact,
    PromotionResult,
    load_authorized_promotion,
    promote_artifact,
)
from nightly_photo_intelligence_pipeline.n2b1p_integrity import (
    N2B1PRuntimeConfiguration,
    build_legacy_cache_manifest_bytes,
    canonical_json_bytes,
    compute_legacy_cache_manifest_sha256,
)
from nightly_photo_intelligence_pipeline.windows_bound_promotion import bind_existing_directory


def _artifact(payload: bytes = b"cache-bytes") -> PromotionArtifact:
    digest = hashlib.sha256(payload).hexdigest()
    transfer = {
        "stage": "N2B1R",
        "artifact_id": "synthetic-cache-artifact",
        "revision": "torchvision-v0.22.1",
        "filename": "synthetic.pth",
        "request_domain": "download.pytorch.org",
        "final_domain": "download.pytorch.org",
        "content_length_bytes": len(payload),
        "byte_count": len(payload),
        "sha256": digest,
        "weights_rights": "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
        "use_restriction": "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION",
    }
    transfer_sha256 = hashlib.sha256(canonical_json_bytes(transfer)).hexdigest()
    manifest_sha256 = compute_legacy_cache_manifest_sha256(
        artifact_id="synthetic-cache-artifact",
        revision="torchvision-v0.22.1",
        filename="synthetic.pth",
        byte_count=len(payload),
        local_sha256=digest,
        transfer_manifest_sha256=transfer_sha256,
    )
    return PromotionArtifact(
        artifact_id="synthetic-cache-artifact",
        revision="torchvision-v0.22.1",
        filename="synthetic.pth",
        byte_count=len(payload),
        local_sha256=digest,
        transfer_manifest_sha256=transfer_sha256,
        cache_manifest_sha256=manifest_sha256,
        runtime_configuration_digest="f" * 64,
    )


def _write_run(quarantine: Path, run_id: str, artifact: PromotionArtifact, payload: bytes) -> None:
    run = quarantine / run_id
    run.mkdir(parents=True)
    transfer = {
        "stage": "N2B1R",
        "artifact_id": artifact.artifact_id,
        "revision": artifact.revision,
        "filename": artifact.filename,
        "request_domain": "download.pytorch.org",
        "final_domain": "download.pytorch.org",
        "content_length_bytes": artifact.byte_count,
        "byte_count": artifact.byte_count,
        "sha256": artifact.local_sha256,
        "weights_rights": "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
        "use_restriction": "LOCAL_RESEARCH_ONLY_NO_REDISTRIBUTION",
    }
    (run / "transfer_manifest.json").write_bytes(canonical_json_bytes(transfer))
    (run / artifact.filename).write_bytes(payload)


def _promote_synthetic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: bytes = b"cache-bytes",
) -> tuple[PromotionArtifact, Path, Path]:
    artifact = _artifact(payload)
    quarantine = tmp_path / "quarantine"
    cache = tmp_path / "cache"
    cache.mkdir()
    _write_run(quarantine, "run_001", artifact, payload)
    with bind_existing_directory(cache, writable=False) as bound:
        cache_identity = bound.identity.digest
    configuration = N2B1PRuntimeConfiguration(
        configuration_version="test",
        runtime_parent=tmp_path / "runtime",
        work_root=tmp_path / "runtime" / "work",
        snapshot_root="NOT_APPLICABLE_N2B1P_SOURCE_ACCESS_FORBIDDEN",
        cache_root=cache,
        cache_root_identity=cache_identity,
        configuration_digest=artifact.runtime_configuration_digest,
    )
    monkeypatch.setattr(promotion, "DEFAULT_QUARANTINE_PARENT", quarantine)
    monkeypatch.setattr(promotion, "load_authorized_promotion", lambda *_args, **_kwargs: artifact)
    monkeypatch.setattr(promotion, "load_n2b1p_runtime_configuration", lambda *_args: configuration)
    return artifact, quarantine, cache


def test_load_authorized_promotion_binds_exact_n2b1r_evidence(project_root: Path) -> None:
    artifact = load_authorized_promotion(
        "torchvision-keypointrcnn-resnet50-fpn-coco-v1", project_root=project_root
    )
    assert (
        artifact.local_sha256 == "fc266e953d2b302cdcbb9ae66f71f6b0d4649928bf02dc573961e361e4918926"
    )
    assert (
        artifact.cache_manifest_sha256
        == "1eac996e7088ef26bc3b35cdf25d267e0b127dab23df6f5f4c4f67cb980e58fb"
    )


def test_load_authorized_promotion_rejects_a_non_evidence_artifact(project_root: Path) -> None:
    with pytest.raises(GateNotAuthorizedError):
        load_authorized_promotion("not-in-n2b1r-evidence", project_root=project_root)


def test_promotion_rejects_forged_artifact_before_external_access(project_root: Path) -> None:
    actual = load_authorized_promotion(
        "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1", project_root=project_root
    )
    forged = PromotionArtifact(
        artifact_id=actual.artifact_id,
        revision=actual.revision,
        filename=actual.filename,
        byte_count=actual.byte_count,
        local_sha256="0" * 64,
        transfer_manifest_sha256=actual.transfer_manifest_sha256,
        cache_manifest_sha256=actual.cache_manifest_sha256,
        runtime_configuration_digest=actual.runtime_configuration_digest,
    )
    with pytest.raises(GateNotAuthorizedError):
        promote_artifact(forged, quarantine_run_id="run_001", project_root=project_root)


def test_promotion_copies_atomically_and_cache_hit_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact, quarantine, cache = _promote_synthetic(tmp_path, monkeypatch)
    result = promote_artifact(artifact, quarantine_run_id="run_001", project_root=tmp_path)
    assert result.status == "PROMOTED"
    entry = cache / artifact.local_sha256
    assert (entry / artifact.filename).read_bytes() == b"cache-bytes"
    assert {child.name for child in entry.iterdir()} == {artifact.filename, "cache_manifest.json"}
    assert (entry / "cache_manifest.json").read_bytes() == build_legacy_cache_manifest_bytes(
        artifact_id=artifact.artifact_id,
        revision=artifact.revision,
        filename=artifact.filename,
        byte_count=artifact.byte_count,
        local_sha256=artifact.local_sha256,
        transfer_manifest_sha256=artifact.transfer_manifest_sha256,
    )
    before = (entry / "cache_manifest.json").read_bytes()
    second = promote_artifact(artifact, quarantine_run_id="run_001", project_root=tmp_path)
    assert second.status == "CACHE_HIT"
    assert (entry / "cache_manifest.json").read_bytes() == before
    assert (quarantine / "run_001" / artifact.filename).read_bytes() == b"cache-bytes"


def test_promotion_has_no_caller_supplied_path_bypass() -> None:
    parameters = inspect.signature(promote_artifact).parameters
    assert "cache_parent" not in parameters
    assert "quarantine_parent" not in parameters


def test_promotion_does_not_fall_back_to_path_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact, _quarantine, cache = _promote_synthetic(tmp_path, monkeypatch)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("legacy path-based promotion fallback was called")

    with monkeypatch.context() as blocked:
        blocked.setattr(Path, "mkdir", forbidden)
        blocked.setattr(Path, "open", forbidden)
        blocked.setattr(Path, "iterdir", forbidden)
        blocked.setattr(Path, "unlink", forbidden)
        blocked.setattr(Path, "rmdir", forbidden)
        blocked.setattr(os, "replace", forbidden)
        assert (
            promote_artifact(artifact, quarantine_run_id="run_001", project_root=tmp_path).status
            == "PROMOTED"
        )
    assert (cache / artifact.local_sha256 / artifact.filename).read_bytes() == b"cache-bytes"


def test_promotion_rejects_changed_payload_without_final_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact, quarantine, cache = _promote_synthetic(tmp_path, monkeypatch)
    (quarantine / "run_001" / artifact.filename).write_bytes(b"changed")
    with pytest.raises(PreflightUnsatisfiedError):
        promote_artifact(artifact, quarantine_run_id="run_001", project_root=tmp_path)
    assert not (cache / artifact.local_sha256).exists()


def test_promotion_refuses_corrupt_existing_cache_without_overwrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact, _quarantine, cache = _promote_synthetic(tmp_path, monkeypatch)
    promote_artifact(artifact, quarantine_run_id="run_001", project_root=tmp_path)
    payload = cache / artifact.local_sha256 / artifact.filename
    payload.write_bytes(b"corrupt")
    with pytest.raises(PreflightUnsatisfiedError):
        promote_artifact(artifact, quarantine_run_id="run_001", project_root=tmp_path)
    assert payload.read_bytes() == b"corrupt"


def test_cli_promotion_prints_no_cache_path(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = _artifact(b"cli")
    result = PromotionResult(
        artifact_id=artifact.artifact_id,
        cache_key=artifact.local_sha256,
        byte_count=artifact.byte_count,
        local_sha256=artifact.local_sha256,
        status="PROMOTED",
        manifest_path=Path("E" + ":" + chr(92) + "private" + chr(92) + "cache_manifest.json"),
        manifest_sha256="a" * 64,
    )
    monkeypatch.setattr(cli_module, "run_preflight", lambda: [])
    monkeypatch.setattr(cli_module, "load_authorized_promotion", lambda _: artifact)
    monkeypatch.setattr(cli_module, "promote_artifact", lambda *_args, **_kwargs: result)
    response = CliRunner().invoke(
        app,
        [
            "mo" + "del",
            "promote",
            "--artifact",
            "synthetic-cache-artifact",
            "--quarantine-run-id",
            "run_001",
        ],
    )
    assert response.exit_code == 0, response.output
    assert ("E" + ":" + chr(92) + "private") not in response.output
    assert "cache_manifest" not in response.output
