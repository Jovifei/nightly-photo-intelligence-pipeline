"""N2B0.5 composed approval and transport metadata contract tests.

All inputs are synthetic JSON bytes and metadata. These tests perform no
network request, model operation, payload read, cache write, or photo read.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker

import nightly_photo_intelligence_pipeline.model_artifact_policy as policy
from nightly_photo_intelligence_pipeline.domain.errors import (
    ArtifactFilenameMismatchError,
    ArtifactRevisionMismatchError,
    ArtifactSizeLimitExceededError,
    DuplicateJsonMemberError,
    GateNotAuthorizedError,
    OfficialArtifactHashMismatchError,
    ProjectStateSchemaInvalidError,
    QualificationSnapshotSchemaInvalidError,
    QuarantineApprovalExpiredError,
    QuarantineApprovalNotYetValidError,
    QuarantineApprovalSchemaInvalidError,
    QuarantineApprovalStateMismatchError,
    QuarantineApprovalTimeRangeInvalidError,
    QuarantineRightsNotQualifiedError,
    UnsupportedDocumentSchemaVersionError,
)
from nightly_photo_intelligence_pipeline.model_artifact_policy import (
    TransportMetadata,
    ValidatedN2B1QuarantineApproval,
    ValidatedQuarantineRequest,
    require_cache_promotion_authorized,
    require_real_model_execution_authorized,
    validate_n2b1_quarantine_request,
)

ARTIFACT_ID = "future-pose-artifact"
BASELINE_SHA = "b" * 40
FINGERPRINT = "c" * 64
OFFICIAL_SHA256 = "a" * 64
ARTIFACT_REVISION = {
    "kind": "GIT_COMMIT",
    "value": "f" * 40,
    "source_url": "https://official.example/evidence",
}
NOW = datetime(2026, 7, 26, tzinfo=UTC)
RIGHTS_FIELDS = (
    "code_license_status",
    "weights_license_status",
    "commercial_use_status",
    "artifact_identity_status",
    "immutable_revision_status",
    "official_hash_status",
    "ready_for_quarantine_download",
)


def _digest(value: dict[str, object]) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _bytes(value: dict[str, object]) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def _future_state() -> dict[str, object]:
    def baseline(commit: str, tag: str) -> dict[str, object]:
        return {
            "commit": commit,
            "tag": tag,
            "status": "APPROVED_COMPLETE",
            "immutable": True,
        }

    return {
        "schema_version": "1.3",
        "project": {
            "slug": "nightly-photo-intelligence-pipeline",
            "repository_relationship": "INDEPENDENT_FROM_ai-photography-director-app",
        },
        "baselines": {
            "N0": baseline("0" * 40, "n0-approved"),
            "N1": baseline("1" * 40, "n1-approved"),
            "G1": baseline("2" * 40, "g1-approved"),
            "N2A": baseline("3" * 40, "n2a-approved"),
            "N2B0": baseline("4" * 40, "n2b0-approved"),
            "N2B0_5": baseline(BASELINE_SHA, "n2b0-5-approved"),
        },
        "n2b0_5_baseline_sha": BASELINE_SHA,
        "authorization": {
            "phase": {"id": "N1", "status": "APPROVED_COMPLETE"},
            "data_gate": {"id": "G1_CALIBRATION_20", "status": "AUTHORIZED"},
            "large_model_downloads": "AUTHORIZED",
            "real_model_execution": "NOT_AUTHORIZED",
            "capability_gates": {
                "G1_COMPLETION": "APPROVED_COMPLETE",
                "N2A_POSE_SEGMENTATION_BENCHMARK_PREPARATION": "APPROVED_COMPLETE",
                "N2B0_MODEL_ARTIFACT_QUALIFICATION": "APPROVED_COMPLETE",
                "N2B0_5_ARTIFACT_RIGHTS_AND_PROVENANCE_CLOSURE": "APPROVED_COMPLETE",
                "N2B_MODEL_DOWNLOAD_AND_INFERENCE": "AUTHORIZED",
                "N2B1_MODEL_DOWNLOAD": "AUTHORIZED",
                "N2B1_Q_QUARANTINE_DOWNLOAD": "AUTHORIZED",
                "N2B1_P_CACHE_PROMOTION": "LOCKED",
                "N2B2_REAL_BENCHMARK": "LOCKED",
            },
        },
        "data_scope": {
            "max_assets": 20,
            "allowed_assets": "owner-frozen manifest entries only",
            "G1_CALIBRATION_20": "AUTHORIZED",
            "N2B1_Q_QUARANTINE_DOWNLOAD": "AUTHORIZED",
            "N2B1_P_CACHE_PROMOTION": "LOCKED",
            "N2B2_REAL_BENCHMARK": "LOCKED",
            "G2_PILOT_100": "LOCKED",
            "G3_FULL_LIBRARY": "LOCKED",
        },
        "phase_status": {
            "N0": "APPROVED_COMPLETE",
            "N1": "APPROVED_COMPLETE",
            "G1": "APPROVED_COMPLETE",
            "N2": "AUTHORIZED",
            "N2A": "APPROVED_COMPLETE",
            "N2B0": "APPROVED_COMPLETE",
            "N2B0_5": "APPROVED_COMPLETE",
            "N2B": "AUTHORIZED",
            "N2B1": "AUTHORIZED",
            "N2B1_Q": "AUTHORIZED",
            "N2B1_P": "LOCKED",
            "N2B2": "LOCKED",
            "N3": "LOCKED",
            "N4": "LOCKED",
            "N5": "LOCKED",
            "N6": "LOCKED",
            "N7": "LOCKED",
            "N8": "LOCKED",
        },
        "required_stop_after": {
            "condition": "N2B1_Q_AWAITING_OWNER_APPROVAL",
            "next_action": "WAIT_FOR_OWNER_APPROVAL",
        },
    }


def _rights_snapshot(**overrides: object) -> dict[str, object]:
    snapshot: dict[str, object] = {
        "schema_version": "1.0",
        "snapshot_id": "future-test-only-snapshot",
        "artifact_id": ARTIFACT_ID,
        "expected_artifact_filename": "model.pth",
        "qualification_status": "QUALIFIED",
        **dict.fromkeys(RIGHTS_FIELDS, "PASS"),
        "artifact_revision": dict(ARTIFACT_REVISION),
        "official_artifact_sha256": OFFICIAL_SHA256,
        "official_sha256_source_url": "https://official.example/evidence",
        "official_request_url": "https://official.example/model.pth",
        "allowed_request_domains": ["official.example"],
        "allowed_final_domains": ["official.example"],
        "expected_size_bytes": 42,
        "evidence_digest": "d" * 64,
        "source_snapshot_digest": "e" * 64,
        "n2b0_5_baseline_sha": BASELINE_SHA,
        "generated_at": "2026-07-26T00:00:00+00:00",
    }
    snapshot.update(overrides)
    if snapshot["immutable_revision_status"] != "PASS" and "artifact_revision" not in overrides:
        snapshot["artifact_revision"] = None
    if snapshot["official_hash_status"] != "PASS":
        if "official_artifact_sha256" not in overrides:
            snapshot["official_artifact_sha256"] = None
        if "official_sha256_source_url" not in overrides:
            snapshot["official_sha256_source_url"] = None
    return snapshot


def _transport(**overrides: object) -> TransportMetadata:
    values: dict[str, object] = {
        "artifact_id": ARTIFACT_ID,
        "request_url": "https://official.example/model.pth",
        "redirect_chain": (),
        "redirect_count": 0,
        "final_url": "https://official.example/model.pth",
        "http_status": 200,
        "content_length_bytes": 42,
        "content_type": "application/octet-stream",
        "etag": 'W/"transport-only"',
        "last_modified": "2026-07-26T00:00:00Z",
        "quarantine_destination_fingerprint": FINGERPRINT,
    }
    values.update(overrides)
    return TransportMetadata(**values)  # type: ignore[arg-type]


def _case(
    *,
    approval_overrides: dict[str, object] | None = None,
    state_overrides: dict[str, object] | None = None,
    snapshot_overrides: dict[str, object] | None = None,
    transport_overrides: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, object], dict[str, object], TransportMetadata]:
    state = _future_state()
    if state_overrides:
        state.update(state_overrides)
    snapshot = _rights_snapshot(**(snapshot_overrides or {}))
    approval: dict[str, object] = {
        "schema_version": "1.0",
        "approval_id": "future-test-only-approval",
        "status": "APPROVED",
        "owner": "test-owner",
        "owner_decision_reference": "future-test-only-decision",
        "issued_at": "2026-07-01T00:00:00+00:00",
        "not_before": "2026-07-01T00:00:00+00:00",
        "expires_at": "2026-08-01T00:00:00+00:00",
        "revoked": False,
        "stage": "N2B1_Q",
        "artifact_id": ARTIFACT_ID,
        "expected_artifact_filename": "model.pth",
        "official_request_url": "https://official.example/model.pth",
        "allowed_request_domains": ["official.example"],
        "allowed_final_domains": ["official.example"],
        "redirect_limit": 0,
        "expected_size_bytes": 42,
        "owner_max_bytes": 42,
        "quarantine_destination_fingerprint": FINGERPRINT,
        **dict.fromkeys(RIGHTS_FIELDS, "PASS"),
        "artifact_revision": dict(ARTIFACT_REVISION),
        "expected_sha256": OFFICIAL_SHA256,
        "rights_snapshot_digest": _digest(snapshot),
        "project_state_digest": _digest(state),
        "n2b0_5_baseline_sha": BASELINE_SHA,
    }
    if approval_overrides:
        approval.update(approval_overrides)
    return approval, state, snapshot, _transport(**(transport_overrides or {}))


def _validate(
    approval: dict[str, object],
    state: dict[str, object],
    snapshot: dict[str, object],
    transport: TransportMetadata,
    *,
    now: datetime = NOW,
) -> ValidatedQuarantineRequest:
    return validate_n2b1_quarantine_request(
        approval_document_bytes=_bytes(approval),
        qualification_snapshot_document_bytes=_bytes(snapshot),
        project_state_document_bytes=_bytes(state),
        transport_metadata=transport,
        now=now,
    )


def test_composed_gate_returns_non_authorizing_immutable_metadata_request(
    project_root: Path,
) -> None:
    approval, state, snapshot, transport = _case()
    schema = json.loads(
        (project_root / "schemas" / "n2b1_quarantine_approval_v1_0.schema.json").read_text("utf-8")
    )
    assert not list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(approval)
    )
    request = _validate(approval, state, snapshot, transport)
    assert request.approval.artifact_id == ARTIFACT_ID
    assert request.approval.expected_size_bytes == 42
    assert request.transport.final_url == transport.final_url
    with pytest.raises(FrozenInstanceError):
        request.approval.owner_max_bytes = 1000  # type: ignore[misc]
    forged = ValidatedN2B1QuarantineApproval(
        approval_id="forged",
        artifact_id=ARTIFACT_ID,
        expected_artifact_filename="model.pth",
        official_request_url="https://official.example/model.pth",
        allowed_request_domains=(),
        allowed_final_domains=(),
        redirect_limit=0,
        expected_size_bytes=42,
        owner_max_bytes=42,
        quarantine_destination_fingerprint=FINGERPRINT,
        artifact_revision=policy.ArtifactRevisionEvidence(
            kind="GIT_COMMIT",
            value="f" * 40,
            source_url="https://official.example/evidence",
        ),
        expected_sha256=OFFICIAL_SHA256,
        rights_snapshot_digest="d" * 64,
        project_state_digest="e" * 64,
        n2b0_5_baseline_sha=BASELINE_SHA,
        issued_at=NOW,
        not_before=NOW,
        expires_at=NOW,
        owner_decision_reference="forged",
    )
    assert isinstance(
        ValidatedQuarantineRequest(approval=forged, transport=request.transport),
        ValidatedQuarantineRequest,
    )


def test_public_api_has_no_approval_derived_override_parameters() -> None:
    parameters = inspect.signature(validate_n2b1_quarantine_request).parameters
    forbidden = {
        "expected_artifact_filename",
        "official_request_url",
        "allowed_request_domains",
        "allowed_final_domains",
        "expected_size_bytes",
        "owner_max_bytes",
        "redirect_limit",
        "rights_snapshot_digest",
    }
    assert not forbidden.intersection(parameters)
    assert "validate_transport_metadata" not in policy.__all__
    assert "require_quarantine_download_authorized" not in policy.__all__
    approval, state, snapshot, transport = _case()
    with pytest.raises(TypeError):
        validate_n2b1_quarantine_request(
            approval_document_bytes=_bytes(approval),
            qualification_snapshot_document_bytes=_bytes(snapshot),
            project_state_document_bytes=_bytes(state),
            transport_metadata=transport,
            now=NOW,
            owner_max_bytes=1000,  # type: ignore[call-arg]
        )


@pytest.mark.parametrize(
    "transport_overrides",
    [
        {"final_url": "https://official.example/other.pth"},
        {
            "request_url": "https://official.example/other.pth",
            "final_url": "https://official.example/other.pth",
        },
        {"artifact_id": "other-artifact"},
        {"quarantine_destination_fingerprint": "d" * 64},
        {"content_length_bytes": 1000},
        {"redirect_count": 1, "redirect_chain": ("https://official.example/model.pth",)},
    ],
)
def test_composed_gate_rejects_approval_transport_mismatches(
    transport_overrides: dict[str, object],
) -> None:
    approval, state, snapshot, transport = _case(transport_overrides=transport_overrides)
    with pytest.raises(GateNotAuthorizedError):
        _validate(approval, state, snapshot, transport)


def test_final_filename_mismatch_uses_stable_redacted_error() -> None:
    approval, state, snapshot, transport = _case(
        approval_overrides={"redirect_limit": 1},
        transport_overrides={
            "final_url": "https://official.example/other.pth",
            "redirect_count": 1,
            "redirect_chain": ("https://official.example/other.pth",),
        },
    )
    with pytest.raises(ArtifactFilenameMismatchError) as error:
        _validate(approval, state, snapshot, transport)
    assert "https://" not in str(error.value)


def test_owner_cap_is_derived_from_approval_and_cannot_be_raised_by_transport() -> None:
    approval, state, snapshot, transport = _case(transport_overrides={"content_length_bytes": 1000})
    with pytest.raises(ArtifactSizeLimitExceededError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize("owner_max_bytes", [None, 0, -1, 1.5, "42", True])
def test_schema_rejects_missing_or_invalid_owner_cap(owner_max_bytes: object) -> None:
    approval, state, snapshot, transport = _case(
        approval_overrides={"owner_max_bytes": owner_max_bytes}
    )
    with pytest.raises((GateNotAuthorizedError, QuarantineApprovalSchemaInvalidError)):
        _validate(approval, state, snapshot, transport)


def test_expected_size_over_cap_and_short_final_length_are_rejected() -> None:
    approval, state, snapshot, transport = _case(
        approval_overrides={"expected_size_bytes": 43, "owner_max_bytes": 42}
    )
    with pytest.raises(ArtifactSizeLimitExceededError):
        _validate(approval, state, snapshot, transport)
    approval, state, snapshot, transport = _case(transport_overrides={"content_length_bytes": 41})
    with pytest.raises((GateNotAuthorizedError, QuarantineApprovalSchemaInvalidError)):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "approval_overrides,final_url",
    [
        ({}, "https://official.example/model.pth?cache=ignored#fragment"),
        ({}, "https://official.example/model%2Epth"),
        ({"expected_artifact_filename": "café.pth"}, "https://official.example/cafe%CC%81.pth"),
    ],
)
def test_final_filename_uses_final_path_once_decoded_and_unicode_normalized(
    approval_overrides: dict[str, object], final_url: str
) -> None:
    approval_overrides = {"redirect_limit": 1, **approval_overrides}
    approval, state, snapshot, transport = _case(
        approval_overrides=approval_overrides,
        snapshot_overrides={
            "expected_artifact_filename": approval_overrides.get(
                "expected_artifact_filename", "model.pth"
            )
        },
        transport_overrides={
            "final_url": final_url,
            "redirect_count": 1,
            "redirect_chain": (final_url,),
        },
    )
    request = _validate(approval, state, snapshot, transport)
    assert request.transport.final_url == final_url


@pytest.mark.parametrize(
    "final_url",
    [
        "https://official.example/directory/",
        "https://official.example/.",
        "https://official.example/..",
        "https://official.example/model%2Fescape.pth",
        "https://official.example/model%5Cescape.pth",
        "https://official.example/%00model.pth",
        "https://official.example/Model.pth",
    ],
)
def test_final_filename_rejects_directory_encoded_escape_and_case_mismatch(final_url: str) -> None:
    approval, state, snapshot, transport = _case(
        approval_overrides={"redirect_limit": 1},
        transport_overrides={
            "final_url": final_url,
            "redirect_count": 1,
            "redirect_chain": (final_url,),
        },
    )
    with pytest.raises(ArtifactFilenameMismatchError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "approval_overrides,transport_overrides",
    [
        ({"allowed_request_domains": ["other.example"]}, {}),
        (
            {"allowed_final_domains": ["other.example"], "redirect_limit": 1},
            {"redirect_count": 1, "redirect_chain": ("https://official.example/model.pth",)},
        ),
        (
            {"redirect_limit": 0},
            {"redirect_count": 1, "redirect_chain": ("https://official.example/model.pth",)},
        ),
        (
            {"redirect_limit": 2},
            {
                "redirect_count": 2,
                "redirect_chain": (
                    "https://blocked.example/model.pth",
                    "https://official.example/model.pth",
                ),
            },
        ),
    ],
)
def test_request_final_and_each_redirect_domain_are_bound_to_approval(
    approval_overrides: dict[str, object], transport_overrides: dict[str, object]
) -> None:
    approval, state, snapshot, transport = _case(
        approval_overrides=approval_overrides,
        transport_overrides=transport_overrides,
    )
    with pytest.raises((GateNotAuthorizedError, QuarantineApprovalSchemaInvalidError)):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "approval_overrides",
    [
        {"official_request_url": "http://official.example/model.pth"},
        {"official_request_url": "https://user@official.example/model.pth"},
        {"official_request_url": "https://official.example:443/model.pth"},
        {"official_request_url": "https://official.example./model.pth"},
        {"official_request_url": "https://caf\u00e9.example/model.pth"},
        {"official_request_url": "https://sub.official.example/model.pth"},
    ],
)
def test_request_url_rejects_downgrade_userinfo_port_trailing_dot_unicode_and_subdomain(
    approval_overrides: dict[str, object],
) -> None:
    approval, state, snapshot, transport = _case(approval_overrides=approval_overrides)
    with pytest.raises((GateNotAuthorizedError, QuarantineApprovalSchemaInvalidError)):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "approval_overrides,now,error_type",
    [
        ({"expires_at": "2026-07-26T00:00:00+00:00"}, NOW, QuarantineApprovalExpiredError),
        ({"expires_at": "2026-07-25T00:00:00+00:00"}, NOW, QuarantineApprovalExpiredError),
        (
            {
                "issued_at": "2026-07-27T00:00:00+00:00",
                "not_before": "2026-07-27T00:00:00+00:00",
            },
            NOW,
            QuarantineApprovalNotYetValidError,
        ),
        (
            {
                "not_before": "2026-07-27T00:00:00+00:00",
                "expires_at": "2026-08-02T00:00:00+00:00",
            },
            NOW,
            QuarantineApprovalNotYetValidError,
        ),
        (
            {"issued_at": "2026-08-02T00:00:00+00:00"},
            NOW,
            QuarantineApprovalTimeRangeInvalidError,
        ),
    ],
)
def test_expiry_and_activation_are_deterministic(
    approval_overrides: dict[str, object], now: datetime, error_type: type[GateNotAuthorizedError]
) -> None:
    approval, state, snapshot, transport = _case(approval_overrides=approval_overrides)
    with pytest.raises(error_type):
        _validate(approval, state, snapshot, transport, now=now)


@pytest.mark.parametrize(
    "approval_overrides",
    [
        {"expires_at": "2026-08-01T00:00:00"},
        {"revoked": True},
        {"expires_at": None},
    ],
)
def test_schema_rejects_naive_revoked_or_missing_expiry(
    approval_overrides: dict[str, object],
) -> None:
    approval, state, snapshot, transport = _case(approval_overrides=approval_overrides)
    with pytest.raises((GateNotAuthorizedError, QuarantineApprovalSchemaInvalidError)):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "snapshot_overrides",
    [
        {"weights_license_status": "UNKNOWN"},
        {"commercial_use_status": "UNKNOWN"},
        {"commercial_use_status": "REQUIRES_OWNER_DECISION"},
        {"ready_for_quarantine_download": "FAIL"},
    ],
)
def test_rights_snapshot_unknown_or_not_ready_rejects_even_when_approval_says_approved(
    snapshot_overrides: dict[str, object],
) -> None:
    approval, state, snapshot, transport = _case(snapshot_overrides=snapshot_overrides)
    with pytest.raises(QuarantineRightsNotQualifiedError):
        _validate(approval, state, snapshot, transport)


def test_rights_snapshot_and_project_state_changes_invalidate_approval() -> None:
    approval, state, snapshot, transport = _case()
    changed_snapshot = dict(snapshot, snapshot_id="future-test-only-snapshot-v2")
    with pytest.raises(QuarantineApprovalStateMismatchError):
        _validate(approval, state, changed_snapshot, transport)
    changed_state = dict(state, n2b0_5_baseline_sha="e" * 40)
    with pytest.raises(QuarantineApprovalStateMismatchError):
        _validate(approval, changed_state, snapshot, transport)


def test_duplicate_approval_member_is_rejected_before_schema_or_semantics() -> None:
    _, state, snapshot, transport = _case()
    duplicate_approval = b'{"status":"APPROVED","status":"APPROVED"}'
    with pytest.raises(DuplicateJsonMemberError):
        validate_n2b1_quarantine_request(
            approval_document_bytes=duplicate_approval,
            qualification_snapshot_document_bytes=_bytes(snapshot),
            project_state_document_bytes=_bytes(state),
            transport_metadata=transport,
            now=NOW,
        )


def test_current_production_state_remains_locked_and_draft_cannot_authorize(
    project_root: Path,
) -> None:
    draft = yaml.safe_load(
        (project_root / "config" / "model_artifact_allowlist.draft.yaml").read_text("utf-8")
    )
    assert draft["status"] == "DRAFT_NOT_AUTHORIZED"
    approval, _, snapshot, transport = _case()
    production_state = json.loads((project_root / "PROJECT_STATE.json").read_text("utf-8"))
    approval["project_state_digest"] = _digest(production_state)
    with pytest.raises(QuarantineApprovalStateMismatchError):
        _validate(approval, production_state, snapshot, transport)


def test_validation_result_contains_no_token_and_cannot_be_used_as_a_gate_credential() -> None:
    assert not hasattr(policy, "_VALIDATION_TOKEN")
    assert (
        "validated_request" not in inspect.signature(require_cache_promotion_authorized).parameters
    )
    assert (
        "validated_request"
        not in inspect.signature(require_real_model_execution_authorized).parameters
    )
    direct = ValidatedQuarantineRequest(
        approval=object.__new__(ValidatedN2B1QuarantineApproval),
        transport=object.__new__(policy.ValidatedTransportMetadata),
    )
    forged = object.__new__(ValidatedQuarantineRequest)
    object.__setattr__(forged, "approval", direct.approval)
    object.__setattr__(forged, "transport", direct.transport)
    assert isinstance(direct, ValidatedQuarantineRequest)
    assert isinstance(forged, ValidatedQuarantineRequest)
    promotion_state = {
        "phase_status": {"N2B1_P": "AUTHORIZED"},
        "authorization": {"capability_gates": {"N2B1_P_CACHE_PROMOTION": "AUTHORIZED"}},
    }
    with pytest.raises(GateNotAuthorizedError):
        require_cache_promotion_authorized(
            state=promotion_state,
            artifact_id=ARTIFACT_ID,
            expected_sha256="a" * 64,
            local_sha256="a" * 64,
            owner_approval=direct,  # type: ignore[arg-type]
        )
    with pytest.raises(GateNotAuthorizedError):
        require_cache_promotion_authorized(
            state=promotion_state,
            artifact_id=ARTIFACT_ID,
            expected_sha256="a" * 64,
            local_sha256="a" * 64,
            owner_approval=forged,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda snapshot: snapshot.clear(),
        lambda snapshot: snapshot.pop("snapshot_id"),
        lambda snapshot: snapshot.__setitem__("schema_version", "9.9"),
        lambda snapshot: snapshot.__setitem__("expected_size_bytes", True),
        lambda snapshot: snapshot.__setitem__("qualification_status", "READY"),
        lambda snapshot: snapshot.__setitem__("unexpected", "rejected"),
    ],
)
def test_qualification_snapshot_schema_rejects_missing_bad_type_enum_and_extra_fields(
    mutate: object,
) -> None:
    approval, state, snapshot, transport = _case()
    assert callable(mutate)
    mutate(snapshot)
    approval["rights_snapshot_digest"] = _digest(snapshot)
    with pytest.raises(
        (QualificationSnapshotSchemaInvalidError, UnsupportedDocumentSchemaVersionError)
    ):
        _validate(approval, state, snapshot, transport)


def test_qualification_snapshot_schema_precedes_digest_and_rights_semantics() -> None:
    approval, state, snapshot, transport = _case(
        snapshot_overrides={"weights_license_status": "UNKNOWN", "unexpected": "rejected"}
    )
    approval["rights_snapshot_digest"] = "0" * 64
    with pytest.raises(QualificationSnapshotSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "snapshot_overrides",
    [
        {"artifact_id": "different-artifact"},
        {"expected_artifact_filename": "different.pth"},
        {"qualification_status": "QUALIFIED", "weights_license_status": "UNKNOWN"},
    ],
)
def test_qualification_snapshot_semantics_bind_identity_filename_and_ready_rights(
    snapshot_overrides: dict[str, object],
) -> None:
    approval, state, snapshot, transport = _case(snapshot_overrides=snapshot_overrides)
    approval["rights_snapshot_digest"] = _digest(snapshot)
    expected = (
        QuarantineRightsNotQualifiedError
        if snapshot.get("weights_license_status") == "UNKNOWN"
        else QuarantineApprovalStateMismatchError
    )
    with pytest.raises(expected):
        _validate(approval, state, snapshot, transport)


def test_duplicate_qualification_snapshot_is_rejected_before_its_schema() -> None:
    approval, state, _, transport = _case()
    duplicate_snapshot = b'{"schema_version":"1.0","schema_version":"1.0"}'
    with pytest.raises(DuplicateJsonMemberError):
        validate_n2b1_quarantine_request(
            approval_document_bytes=_bytes(approval),
            qualification_snapshot_document_bytes=duplicate_snapshot,
            project_state_document_bytes=_bytes(state),
            transport_metadata=transport,
            now=NOW,
        )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: state.clear(),
        lambda state: state.pop("baselines"),
        lambda state: state.pop("schema_version"),
        lambda state: state.__setitem__("schema_version", "9.9"),
        lambda state: state["data_scope"].__setitem__("max_assets", True),
        lambda state: state["phase_status"].__setitem__("N2B1_Q", "INVALID"),
        lambda state: state.__setitem__("unexpected", "rejected"),
    ],
)
def test_project_state_schema_rejects_fake_missing_unknown_bad_type_enum_and_extra_fields(
    mutate: object,
) -> None:
    approval, state, snapshot, transport = _case()
    assert callable(mutate)
    mutate(state)
    approval["project_state_digest"] = _digest(state)
    with pytest.raises((ProjectStateSchemaInvalidError, UnsupportedDocumentSchemaVersionError)):
        _validate(approval, state, snapshot, transport)


def test_project_state_schema_precedes_semantics_and_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval, state, snapshot, transport = _case()
    state["data_scope"]["max_assets"] = True  # type: ignore[index]
    approval["project_state_digest"] = _digest(state)
    monkeypatch.setattr(policy, "_validated_transport", lambda *_: pytest.fail("transport called"))
    with pytest.raises(ProjectStateSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


def test_schema_valid_locked_project_state_reaches_semantic_gate_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval, state, snapshot, transport = _case()
    state["authorization"]["large_model_downloads"] = "NOT_AUTHORIZED"  # type: ignore[index]
    approval["project_state_digest"] = _digest(state)
    monkeypatch.setattr(policy, "_validated_transport", lambda *_: pytest.fail("transport called"))
    with pytest.raises(GateNotAuthorizedError):
        _validate(approval, state, snapshot, transport)


def test_approval_schema_precedes_other_document_semantics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval, state, snapshot, transport = _case(approval_overrides={"owner": ""})
    monkeypatch.setattr(policy, "_require_rights_snapshot", lambda *_: pytest.fail("rights called"))
    monkeypatch.setattr(
        policy, "_require_state_and_capability", lambda *_: pytest.fail("state called")
    )
    with pytest.raises(QuarantineApprovalSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda snapshot: snapshot.pop("artifact_revision"),
        lambda snapshot: snapshot.__setitem__("artifact_revision", None),
        lambda snapshot: snapshot["artifact_revision"].__setitem__("value", ""),
        lambda snapshot: snapshot["artifact_revision"].__setitem__("kind", "LATEST"),
    ],
)
def test_snapshot_schema_requires_closed_revision_when_status_is_pass(mutate: object) -> None:
    approval, state, snapshot, transport = _case()
    assert callable(mutate)
    mutate(snapshot)
    with pytest.raises(QualificationSnapshotSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "floating_value", ["LATEST", "MAIN", "MASTER", "FLOATING_URL", "2026-07-26"]
)
def test_snapshot_rejects_floating_or_date_revision_values(floating_value: str) -> None:
    approval, state, snapshot, transport = _case(
        snapshot_overrides={
            "artifact_revision": {**ARTIFACT_REVISION, "value": floating_value},
        }
    )
    approval["artifact_revision"] = dict(snapshot["artifact_revision"])  # type: ignore[arg-type]
    approval["rights_snapshot_digest"] = _digest(snapshot)
    with pytest.raises(GateNotAuthorizedError):
        _validate(approval, state, snapshot, transport)


def test_snapshot_rejects_nonofficial_revision_source() -> None:
    approval, state, snapshot, transport = _case(
        snapshot_overrides={
            "artifact_revision": {
                **ARTIFACT_REVISION,
                "source_url": "https://other.example/evidence",
            },
        }
    )
    approval["artifact_revision"] = dict(snapshot["artifact_revision"])  # type: ignore[arg-type]
    approval["rights_snapshot_digest"] = _digest(snapshot)
    with pytest.raises(GateNotAuthorizedError):
        _validate(approval, state, snapshot, transport)


def test_nonpass_revision_status_must_not_carry_revision_evidence() -> None:
    approval, state, snapshot, transport = _case(
        snapshot_overrides={
            "immutable_revision_status": "UNKNOWN",
            "artifact_revision": dict(ARTIFACT_REVISION),
        }
    )
    with pytest.raises(QualificationSnapshotSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


def test_nonpass_hash_status_must_not_carry_hash_evidence() -> None:
    approval, state, snapshot, transport = _case(
        snapshot_overrides={
            "official_hash_status": "UNKNOWN",
            "official_artifact_sha256": OFFICIAL_SHA256,
            "official_sha256_source_url": "https://official.example/evidence",
        }
    )
    with pytest.raises(QualificationSnapshotSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


def test_approval_revision_must_exactly_match_snapshot() -> None:
    approval, state, snapshot, transport = _case()
    approval["artifact_revision"] = {**ARTIFACT_REVISION, "value": "e" * 40}
    with pytest.raises(ArtifactRevisionMismatchError):
        _validate(approval, state, snapshot, transport)


def test_revision_change_is_bound_by_snapshot_digest() -> None:
    approval, state, snapshot, transport = _case()
    changed = {**ARTIFACT_REVISION, "value": "e" * 40}
    snapshot["artifact_revision"] = changed
    approval["artifact_revision"] = dict(changed)
    with pytest.raises(QuarantineApprovalStateMismatchError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda snapshot: snapshot.pop("official_artifact_sha256"),
        lambda snapshot: snapshot.__setitem__("official_artifact_sha256", None),
        lambda snapshot: snapshot.__setitem__("official_artifact_sha256", "a" * 63),
        lambda snapshot: snapshot.__setitem__("official_artifact_sha256", "a" * 65),
        lambda snapshot: snapshot.__setitem__("official_artifact_sha256", "g" * 64),
        lambda snapshot: snapshot.__setitem__("official_artifact_sha256", "A" * 64),
        lambda snapshot: snapshot.__setitem__("official_artifact_sha256", 'W/"etag"'),
        lambda snapshot: snapshot.__setitem__(
            "official_artifact_sha256", "d41d8cd98f00b204e9800998ecf8427e"
        ),
    ],
)
def test_snapshot_schema_requires_canonical_official_sha256_when_status_is_pass(
    mutate: object,
) -> None:
    approval, state, snapshot, transport = _case()
    assert callable(mutate)
    mutate(snapshot)
    with pytest.raises(QualificationSnapshotSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


def test_snapshot_rejects_quarantine_or_nonofficial_hash_source() -> None:
    approval, state, snapshot, transport = _case(
        snapshot_overrides={"official_sha256_source_url": "https://quarantine.example/local-hash"}
    )
    approval["rights_snapshot_digest"] = _digest(snapshot)
    with pytest.raises(GateNotAuthorizedError):
        _validate(approval, state, snapshot, transport)


def test_approval_hash_must_exactly_match_snapshot() -> None:
    approval, state, snapshot, transport = _case()
    approval["expected_sha256"] = "b" * 64
    with pytest.raises(OfficialArtifactHashMismatchError):
        _validate(approval, state, snapshot, transport)


def test_hash_change_is_bound_by_snapshot_digest() -> None:
    approval, state, snapshot, transport = _case()
    snapshot["official_artifact_sha256"] = "b" * 64
    approval["expected_sha256"] = "b" * 64
    with pytest.raises(QuarantineApprovalStateMismatchError):
        _validate(approval, state, snapshot, transport)


def test_ready_pass_requires_revision_and_hash_evidence() -> None:
    approval, state, snapshot, transport = _case(
        snapshot_overrides={"ready_for_quarantine_download": "PASS", "artifact_revision": None}
    )
    with pytest.raises(QualificationSnapshotSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "snapshot_overrides",
    [
        {"artifact_revision": None},
        {"official_artifact_sha256": None},
    ],
)
def test_evidence_schema_precedes_digest_and_transport(
    monkeypatch: pytest.MonkeyPatch, snapshot_overrides: dict[str, object]
) -> None:
    approval, state, snapshot, transport = _case(snapshot_overrides=snapshot_overrides)
    approval["rights_snapshot_digest"] = "0" * 64
    monkeypatch.setattr(policy, "_require_rights_snapshot", lambda *_: pytest.fail("rights called"))
    monkeypatch.setattr(policy, "_validated_transport", lambda *_: pytest.fail("transport called"))
    with pytest.raises(QualificationSnapshotSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda approval: approval.pop("not_before"),
        lambda approval: approval.__setitem__("not_before", None),
        lambda approval: approval.__setitem__("not_before", ""),
        lambda approval: approval.__setitem__("not_before", "2026-07-01T00:00:00"),
        lambda approval: approval.__setitem__("not_before", "not-a-timestamp"),
    ],
)
def test_approval_schema_requires_timezone_aware_not_before(mutate: object) -> None:
    approval, state, snapshot, transport = _case()
    assert callable(mutate)
    mutate(approval)
    with pytest.raises(QuarantineApprovalSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


@pytest.mark.parametrize(
    "approval_overrides",
    [
        {"issued_at": "2026-07-02T00:00:00+00:00"},
        {"not_before": "2026-08-01T00:00:00+00:00"},
        {"not_before": "2026-08-02T00:00:00+00:00"},
    ],
)
def test_not_before_time_range_is_fail_closed(approval_overrides: dict[str, object]) -> None:
    approval, state, snapshot, transport = _case(approval_overrides=approval_overrides)
    with pytest.raises(QuarantineApprovalTimeRangeInvalidError):
        _validate(approval, state, snapshot, transport)


def test_not_before_boundaries_and_equivalent_timezone_are_deterministic() -> None:
    approval, state, snapshot, transport = _case(
        approval_overrides={
            "issued_at": "2026-07-25T20:00:00-04:00",
            "not_before": "2026-07-25T20:00:00-04:00",
        }
    )
    assert _validate(approval, state, snapshot, transport, now=NOW).approval.not_before == NOW
    with pytest.raises(QuarantineApprovalExpiredError):
        _validate(
            approval,
            state,
            snapshot,
            transport,
            now=datetime(2026, 8, 1, tzinfo=UTC),
        )


def test_not_before_schema_precedes_digest_rights_state_and_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approval, state, snapshot, transport = _case()
    approval.pop("not_before")
    approval["rights_snapshot_digest"] = "0" * 64
    monkeypatch.setattr(policy, "_require_rights_snapshot", lambda *_: pytest.fail("rights called"))
    monkeypatch.setattr(
        policy, "_require_state_and_capability", lambda *_: pytest.fail("state called")
    )
    monkeypatch.setattr(policy, "_validated_transport", lambda *_: pytest.fail("transport called"))
    with pytest.raises(QuarantineApprovalSchemaInvalidError):
        _validate(approval, state, snapshot, transport)


def test_public_gate_requires_explicit_now_and_rejects_not_before_override() -> None:
    approval, state, snapshot, transport = _case()
    with pytest.raises(TypeError):
        validate_n2b1_quarantine_request(  # type: ignore[call-arg]
            approval_document_bytes=_bytes(approval),
            qualification_snapshot_document_bytes=_bytes(snapshot),
            project_state_document_bytes=_bytes(state),
            transport_metadata=transport,
        )
    with pytest.raises(TypeError):
        validate_n2b1_quarantine_request(  # type: ignore[call-arg]
            approval_document_bytes=_bytes(approval),
            qualification_snapshot_document_bytes=_bytes(snapshot),
            project_state_document_bytes=_bytes(state),
            transport_metadata=transport,
            now=NOW,
            not_before=NOW,
        )


def test_four_real_draft_candidates_remain_not_ready(project_root: Path) -> None:
    draft = yaml.safe_load(
        (project_root / "config" / "model_artifact_allowlist.draft.yaml").read_text("utf-8")
    )
    assert draft["status"] == "DRAFT_NOT_AUTHORIZED"
    assert len(draft["artifacts"]) == 4
    for artifact in draft["artifacts"]:
        assert artifact["qualification_status"] == "INCONCLUSIVE"
        assert artifact["expected_sha256"] == "UNKNOWN"
        assert artifact["sha256_source"] == "NOT_PUBLISHED"
