"""N2B0.5 duplicate-member and future-artifact governance tests.

Every artifact test below is metadata-only. No test opens a model payload,
performs a request, creates a cache, or runs a model.
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

import nightly_photo_intelligence_pipeline.preflight as preflight_module
from nightly_photo_intelligence_pipeline.cli import app
from nightly_photo_intelligence_pipeline.domain.authorization import load_authorization
from nightly_photo_intelligence_pipeline.domain.errors import (
    NPI_DUPLICATE_JSON_MEMBER,
    DuplicateJsonMemberError,
    GateNotAuthorizedError,
)
from nightly_photo_intelligence_pipeline.json_strict import load_json_strict, loads_json_strict
from nightly_photo_intelligence_pipeline.model_artifact_policy import (
    ArchiveEntry,
    _validate_candidate_rights,
    require_cache_promotion_authorized,
    require_pth_quarantine_operation,
    require_real_model_execution_authorized,
    validate_zip_entries,
)

INVALID_JSON_FIXTURES = Path(__file__).parent / "fixtures" / "invalid_json"
ARTIFACT_ID = "pose-preferred"
SHA256 = "a" * 64


def _candidate() -> dict[str, object]:
    return {
        "artifact_id": ARTIFACT_ID,
        "code_license": "Apache-2.0",
        "weights_license": "Proprietary license explicitly permits redistribution",
        "commercial_use_status": "PERMITTED",
        "artifact_revision": "revision-2026-07-26",
        "expected_sha256": SHA256,
    }


def _state(project_root: Path) -> dict[str, object]:
    return copy.deepcopy(load_json_strict(project_root / "PROJECT_STATE.json"))


def _enable_promotion(state: dict[str, object]) -> None:
    authorization = state["authorization"]
    assert isinstance(authorization, dict)
    phase_status = state["phase_status"]
    assert isinstance(phase_status, dict)
    gates = authorization["capability_gates"]
    assert isinstance(gates, dict)
    phase_status["N2B1_P"] = "AUTHORIZED"
    gates["N2B1_P_CACHE_PROMOTION"] = "AUTHORIZED"


def _enable_execution(state: dict[str, object]) -> None:
    authorization = state["authorization"]
    assert isinstance(authorization, dict)
    phase_status = state["phase_status"]
    assert isinstance(phase_status, dict)
    gates = authorization["capability_gates"]
    assert isinstance(gates, dict)
    authorization["real_model_execution"] = "AUTHORIZED"
    phase_status["N2B2"] = "AUTHORIZED"
    gates["N2B2_REAL_BENCHMARK"] = "AUTHORIZED"


def _approval(stage: str) -> dict[str, object]:
    approval: dict[str, object] = {
        "status": "APPROVED",
        "artifact_id": ARTIFACT_ID,
        "stage": stage,
    }
    if stage == "N2B1_Q":
        approval.update(
            {
                "schema_version": "1.0",
                "expected_artifact_filename": "model.pth",
                "official_request_url": "https://official.example/model.pth",
                "allowed_final_domains": ["official.example"],
                "expected_size_bytes": 42,
                "owner_max_bytes": 42,
                "max_redirects": 0,
                "quarantine_destination_fingerprint": "a" * 64,
                "expires_at": "2030-01-01T00:00:00+00:00",
                "owner_decision_reference": "owner-decision-example",
            }
        )
    return approval


@pytest.mark.parametrize(
    "path",
    [
        INVALID_JSON_FIXTURES / "duplicate_top_level.json",
        INVALID_JSON_FIXTURES / "duplicate_nested_data_scope.json",
    ],
)
def test_strict_json_rejects_explicit_invalid_duplicate_fixtures(path: Path) -> None:
    with pytest.raises(DuplicateJsonMemberError) as error:
        load_json_strict(path)
    assert error.value.error_code == NPI_DUPLICATE_JSON_MEMBER
    assert "'" in str(error.value)


@pytest.mark.parametrize(
    "payload",
    [
        '{"status":"APPROVED","status":"AUTHORIZED"}',
        '{"artifact_id":"one","artifact_id":"two"}',
        '{"allowlist":{"status":"DRAFT","status":"READY"}}',
        '{"data_scope":{"N2B0_MODEL_ARTIFACT_QUALIFICATION":"APPROVED_COMPLETE","N2B0_MODEL_ARTIFACT_QUALIFICATION":"AUTHORIZED"}}',
    ],
)
def test_strict_json_rejects_approval_artifact_allowlist_and_nested_duplicates(
    payload: str,
) -> None:
    with pytest.raises(DuplicateJsonMemberError) as error:
        loads_json_strict(payload)
    assert error.value.error_code == NPI_DUPLICATE_JSON_MEMBER


def test_strict_json_accepts_normal_objects_array_members_and_case_distinct_names() -> None:
    document = loads_json_strict(
        '{"items":[{"status":"one"},{"status":"two"}],"status":"root","Status":"distinct"}'
    )
    assert document["items"][0]["status"] == "one"
    assert document["items"][1]["status"] == "two"
    assert document["status"] == "root"
    assert document["Status"] == "distinct"


def test_duplicate_state_member_cannot_silently_authorize(tmp_path: Path) -> None:
    (tmp_path / "PROJECT_STATE.json").write_text(
        '{"authorization":{"phase":{"id":"N1","status":"APPROVED_COMPLETE"},'
        '"data_gate":{"id":"G1","status":"AUTHORIZED"}},'
        '"data_scope":{"N2B0_MODEL_ARTIFACT_QUALIFICATION":"APPROVED_COMPLETE",'
        '"N2B0_MODEL_ARTIFACT_QUALIFICATION":"AUTHORIZED"}}',
        encoding="utf-8",
    )
    with pytest.raises(DuplicateJsonMemberError) as error:
        load_authorization(tmp_path)
    assert error.value.error_code == NPI_DUPLICATE_JSON_MEMBER


def test_preflight_duplicate_state_exits_nonzero_before_semantic_authorization(
    project_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("approvals", "config", "schemas", "tasks"):
        shutil.copytree(project_root / name, tmp_path / name)
    state = (project_root / "PROJECT_STATE.json").read_text(encoding="utf-8")
    duplicate = '"schema_version": "1.5",\n  "schema_version": "1.5",'
    (tmp_path / "PROJECT_STATE.json").write_text(
        state.replace('"schema_version": "1.5",', duplicate, 1), encoding="utf-8"
    )
    monkeypatch.setattr(preflight_module, "find_project_root", lambda: tmp_path)
    monkeypatch.setattr(preflight_module, "_BASE_CHECKS", (preflight_module._check_authorization,))
    result = CliRunner().invoke(app, ["preflight"])
    assert result.exit_code != 0
    assert NPI_DUPLICATE_JSON_MEMBER in result.output


def test_project_state_has_one_approved_n2b0_member_and_explicit_locked_substages(
    project_root: Path,
) -> None:
    state = load_json_strict(project_root / "PROJECT_STATE.json")
    assert state["data_scope"]["N2B0_MODEL_ARTIFACT_QUALIFICATION"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B1_Q"] == "LOCKED"
    assert state["phase_status"]["N2B1_P"] == "LOCKED"
    gates = state["authorization"]["capability_gates"]
    assert gates["N2B1_Q_QUARANTINE_DOWNLOAD"] == "LOCKED"
    assert gates["N2B1_P_CACHE_PROMOTION"] == "LOCKED"


@pytest.mark.parametrize(
    "field,value",
    [
        ("weights_license", "UNKNOWN"),
        ("weights_license", ""),
        ("commercial_use_status", "UNKNOWN"),
        ("commercial_use_status", "REQUIRES_OWNER_DECISION"),
        ("artifact_revision", "UNKNOWN"),
        ("expected_sha256", "UNKNOWN"),
        ("expected_sha256", ""),
    ],
)
def test_rights_policy_rejects_unknown_or_incomplete_weight_commercial_identity_fields(
    field: str, value: str
) -> None:
    candidate = _candidate()
    candidate[field] = value
    with pytest.raises(GateNotAuthorizedError):
        _validate_candidate_rights(candidate)


def test_apache_code_license_etag_and_last_modified_never_replace_weights_rights_or_sha() -> None:
    candidate = _candidate()
    candidate.update(
        {
            "weights_license": "UNKNOWN",
            "expected_sha256": "UNKNOWN",
            "etag": 'W/"transport-only"',
            "last_modified": "2026-07-24T00:00:00Z",
        }
    )
    with pytest.raises(GateNotAuthorizedError):
        _validate_candidate_rights(candidate)


def test_cache_promotion_requires_matching_local_hash_and_second_owner_approval(
    project_root: Path,
) -> None:
    state = _state(project_root)
    _enable_promotion(state)
    for local_hash, approval in (
        (None, _approval("N2B1_P")),
        ("b" * 64, _approval("N2B1_P")),
        (SHA256, None),
    ):
        with pytest.raises(GateNotAuthorizedError):
            require_cache_promotion_authorized(
                state=state,
                artifact_id=ARTIFACT_ID,
                expected_sha256=SHA256,
                local_sha256=local_hash,
                owner_approval=approval,
            )
    require_cache_promotion_authorized(
        state=state,
        artifact_id=ARTIFACT_ID,
        expected_sha256=SHA256,
        local_sha256=SHA256,
        owner_approval=_approval("N2B1_P"),
    )


def test_cache_promotion_does_not_authorize_n2b2_execution(project_root: Path) -> None:
    state = _state(project_root)
    _enable_promotion(state)
    with pytest.raises(GateNotAuthorizedError):
        require_real_model_execution_authorized(
            state=state, artifact_id=ARTIFACT_ID, owner_approval=_approval("N2B2")
        )
    _enable_execution(state)
    require_real_model_execution_authorized(
        state=state, artifact_id=ARTIFACT_ID, owner_approval=_approval("N2B2")
    )


@pytest.mark.parametrize(
    "entries,max_entries,max_size",
    [
        ([ArchiveEntry("/absolute/model.pdmodel", 1)], 1, 1),
        ([ArchiveEntry("../escape.pdmodel", 1)], 1, 1),
        ([ArchiveEntry("C" + ":/escape.pdmodel", 1)], 1, 1),
        ([ArchiveEntry("linked.pdmodel", 1, is_symlink=True)], 1, 1),
        ([ArchiveEntry("payload.exe", 1)], 1, 1),
        ([ArchiveEntry("checkpoint.pth", 1)], 1, 1),
        ([ArchiveEntry("one.pdmodel", 1), ArchiveEntry("two.pdiparams", 1)], 1, 2),
        ([ArchiveEntry("oversize.pdmodel", 2)], 1, 1),
    ],
)
def test_zip_policy_rejects_escape_symlink_executable_pth_count_and_expansion(
    entries: list[ArchiveEntry], max_entries: int, max_size: int
) -> None:
    with pytest.raises(GateNotAuthorizedError):
        validate_zip_entries(entries, max_entries=max_entries, max_expanded_bytes=max_size)


def test_zip_policy_allows_only_safe_metadata_and_pth_quarantine_forbids_deserialization() -> None:
    validate_zip_entries(
        [ArchiveEntry("model.pdmodel", 1), ArchiveEntry("weights.pdiparams", 2)],
        max_entries=2,
        max_expanded_bytes=3,
    )
    with pytest.raises(GateNotAuthorizedError):
        require_pth_quarantine_operation("torch_load")
    require_pth_quarantine_operation("byte_hash_and_metadata")
