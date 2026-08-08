"""Canonical manifest and runtime-configuration boundaries for N2B1P."""

from __future__ import annotations

import copy
import inspect
from pathlib import Path

import pytest
import yaml

import nightly_photo_intelligence_pipeline.local_research_promotion as promotion
import nightly_photo_intelligence_pipeline.n2b1p_integrity as integrity
from nightly_photo_intelligence_pipeline.domain.errors import GateNotAuthorizedError
from nightly_photo_intelligence_pipeline.json_strict import load_json_strict
from nightly_photo_intelligence_pipeline.n2b1p_integrity import (
    canonical_json_bytes,
    load_canonical_json_bytes,
    load_n2b1p_runtime_configuration,
    sha256_bytes,
)


def _controls(project_root: Path) -> dict[str, object]:
    runtime = load_n2b1p_runtime_configuration(project_root)
    return {
        "state": load_json_strict(project_root / "PROJECT_STATE.json"),
        "approval": yaml.safe_load(
            (project_root / "approvals" / "owner_n2b1p_cache_promotion.yaml").read_text(
                encoding="utf-8"
            )
        ),
        "task": yaml.safe_load(
            (project_root / "tasks" / "phase_n2b1p_local_research_cache_promotion.yaml").read_text(
                encoding="utf-8"
            )
        ),
        "evidence": load_json_strict(project_root / "research" / "N2B1R_acquisition_evidence.json"),
        "promotion_evidence": load_json_strict(
            project_root / "research" / "N2B1P_cache_promotion_evidence.json"
        ),
        "register": load_json_strict(
            project_root / "research" / "N2B1R_local_research_artifact_register.json"
        ),
        "runtime_configuration_digest": runtime.configuration_digest,
        "cache_root_identity": runtime.cache_root_identity,
    }


def _validate(project_root: Path, controls: dict[str, object]) -> None:
    promotion._validate_authorization(project_root=project_root, **controls)  # type: ignore[arg-type]


def test_canonical_manifest_bytes_reject_noncanonical_and_ambiguous_forms() -> None:
    canonical = canonical_json_bytes({"a": "value", "z": 1})
    assert load_canonical_json_bytes(canonical) == {"a": "value", "z": 1}
    for raw in (
        b'{"z":1,"a":"value"}\n',
        b'{"a":"value","z":1}',
        b'\xef\xbb\xbf{"a":"value","z":1}\n',
        b'{"a":"value","a":"changed","z":1}\n',
        b'{"a":NaN,"z":1}\n',
        b'{"a":Infinity,"z":1}\n',
    ):
        with pytest.raises(GateNotAuthorizedError):
            load_canonical_json_bytes(raw)


def test_authorization_recomputes_every_manifest_binding_field(project_root: Path) -> None:
    controls = _controls(project_root)
    _validate(project_root, controls)
    for field, replacement in (
        ("cache_manifest_sha256", "0" * 64),
        ("artifact_id", "other-artifact"),
        ("approved_evidence_id", "0" * 64),
        ("approved_payload_sha256", "0" * 64),
        ("payload_size_bytes", 1),
        ("cache_relative_path", "0" * 64 + "/other.pth"),
        ("cache_filename", "other.pth"),
        ("runtime_configuration_digest", "0" * 64),
    ):
        tampered = copy.deepcopy(controls)
        artifacts = tampered["promotion_evidence"]["artifacts"]
        assert isinstance(artifacts, list)
        target = artifacts[0]
        assert isinstance(target, dict)
        if field == "cache_manifest_sha256":
            target[field] = replacement
        else:
            target["legacy_cache_manifest_binding"]["payload"][field] = replacement
        with pytest.raises(GateNotAuthorizedError):
            _validate(project_root, tampered)


def test_runtime_configuration_digest_and_overlap_are_strict(
    project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    schema = load_json_strict(
        project_root / "schemas" / "n2b1p_runtime_configuration_v1_0.schema.json"
    )

    def load_config(raw: dict[str, object]) -> None:
        monkeypatch.setattr(
            integrity,
            "load_json_strict",
            lambda path: raw if Path(path).name == "n2b1p_runtime_configuration.json" else schema,
        )
        load_n2b1p_runtime_configuration(project_root)

    raw = {
        "schema_version": "1.0",
        "configuration_version": "N2B1P_RUNTIME_CONFIGURATION_V1",
        "runtime_parent": "F" + ":" + "\\moved-runtime",
        "work_root": "F" + ":" + "\\moved-runtime\\work",
        "snapshot_root": "NOT_APPLICABLE_N2B1P_SOURCE_ACCESS_FORBIDDEN",
        "cache_root": "E" + ":" + "\\independent-cache",
        "cache_root_identity": "a" * 64,
    }
    raw["configuration_digest"] = sha256_bytes(canonical_json_bytes(raw))
    load_config(raw)

    for cache_root in (
        "F" + ":" + "\\moved-runtime",
        "F" + ":" + "\\moved-runtime\\cache",
        "f" + ":" + "\\MOVED-RUNTIME\\",
        "\\\\?\\F" + ":" + "\\moved-runtime\\.\\cache\\..",
    ):
        drifted = copy.deepcopy(raw)
        drifted["cache_root"] = cache_root
        drifted["configuration_digest"] = sha256_bytes(
            canonical_json_bytes(
                {key: value for key, value in drifted.items() if key != "configuration_digest"}
            )
        )
        with pytest.raises(GateNotAuthorizedError):
            load_config(drifted)

    stale_digest = copy.deepcopy(raw)
    stale_digest["runtime_parent"] = "G" + ":" + "\\moved-runtime"
    with pytest.raises(GateNotAuthorizedError):
        load_config(stale_digest)


def test_direct_public_api_has_no_runtime_or_cache_override() -> None:
    parameters = inspect.signature(promotion.verify_promoted_artifact).parameters
    assert set(parameters) == {"artifact_id", "project_root"}
