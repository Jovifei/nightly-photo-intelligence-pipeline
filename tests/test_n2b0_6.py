"""N2B0.6 bundle evidence must remain closed, complete, and non-authorizing."""

from __future__ import annotations

import copy
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from nightly_photo_intelligence_pipeline.candidate_research import (
    HISTORICAL_ARTIFACT_IDS,
    QUALIFICATION_MATRIX_KEYS,
    READY_STATUS_KEY,
    canonical_artifact_url_basename,
    validate_alternative_candidates,
    validate_candidate_record,
    validate_candidate_record_bytes,
)
from nightly_photo_intelligence_pipeline.domain.errors import GateNotAuthorizedError, NpiError

N2B0_5_SHA = "5ad9f8d7d0d6fa267df02d90ef25957bc679e232"
N2B0_5_TAG = "n2b0-5-approved-2026-07-26"


def _record(project_root: Path) -> dict[str, object]:
    return json.loads(
        (project_root / "research" / "N2B0_6_candidate_records.json").read_text("utf-8")
    )


def _candidate(project_root: Path, index: int = 0) -> dict[str, object]:
    return copy.deepcopy(_record(project_root)["candidates"][index])  # type: ignore[index,return-value]


def _assert_rejected(project_root: Path, mutate: Callable[[dict[str, object]], None]) -> None:
    record = _record(project_root)
    mutate(record["candidates"][0])  # type: ignore[index]
    with pytest.raises(GateNotAuthorizedError):
        validate_candidate_record(record)


def _assert_rejected_with_code(
    project_root: Path, mutate: Callable[[dict[str, object]], None], error_code: str
) -> None:
    record = _record(project_root)
    mutate(record["candidates"][0])  # type: ignore[index]
    with pytest.raises(GateNotAuthorizedError) as raised:
        validate_candidate_record(record)
    assert raised.value.error_code == error_code


def test_n2b0_6_completion_chain_binds_approved_n2b0_5(project_root: Path) -> None:
    approval = yaml.safe_load(
        (project_root / "approvals" / "phase_completion_N2B0_5.yaml").read_text("utf-8")
    )
    schema = json.loads(
        (project_root / "schemas" / "phase_completion_approval_n2b0_5_v1_0.schema.json").read_text(
            "utf-8"
        )
    )
    assert not list(Draft202012Validator(schema).iter_errors(approval))
    assert approval["owner_decision"] == "N2B0_5_OWNER_APPROVED"
    assert approval["baseline"]["n2b0_5_commit"] == N2B0_5_SHA
    assert approval["baseline"]["n2b0_5_tag"] == N2B0_5_TAG
    assert (
        subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", N2B0_5_TAG],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == N2B0_5_SHA
    )


def test_actual_candidate_record_has_closed_schema_and_full_fail_closed_matrix(
    project_root: Path,
) -> None:
    record = _record(project_root)
    schema = json.loads(
        (project_root / "schemas" / "n2b0_6_candidate_record_v2.schema.json").read_text("utf-8")
    )
    assert not list(Draft202012Validator(schema).iter_errors(record))
    validate_candidate_record(record)
    candidates = record["candidates"]
    assert len(candidates) == 4
    assert {candidate["category"] for candidate in candidates} == {"pose", "segmentation"}
    assert sum(len(candidate["artifact_files"]) for candidate in candidates) == 7
    assert all(
        set(candidate["qualification_matrix"]) == set(QUALIFICATION_MATRIX_KEYS)
        for candidate in candidates
    )
    assert all(
        candidate["qualification_matrix"]["OFFICIAL_SHA384_CONFIRMED"] == "PASS"
        for candidate in candidates
    )
    assert all(
        candidate["qualification_matrix"]["OFFICIAL_SHA256_CONFIRMED"] == "FAIL"
        for candidate in candidates
    )
    assert all(
        candidate["qualification_matrix"]["WEIGHTS_LICENSE_CONFIRMED"]
        == {
            "status": "PASS",
            "evidence_ids": ["model_license"],
            "decision_reason": "immutable official model-license evidence applies to every declared payload",
        }
        for candidate in candidates
    )
    assert all(candidate[READY_STATUS_KEY] == "FAIL" for candidate in candidates)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda candidate: candidate["artifact_files"][0].pop("direct_official_url"),  # type: ignore[index]
        lambda candidate: candidate["artifact_files"][0].update({"required": 1}),  # type: ignore[index]
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {"local_bundle_relative_path": "../escape.bin"}
        ),
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {"expected_redirect_count": 1}
        ),
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {"official_checksum": "a" * 64}
        ),
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {"checksum_algorithm": "SHA256"}
        ),
    ],
)
def test_ready_fail_still_rejects_incomplete_required_file_evidence(
    project_root: Path, mutation: Callable[[dict[str, object]], None]
) -> None:
    _assert_rejected(project_root, mutation)


def test_sha256_failure_does_not_skip_validation_of_later_candidates(project_root: Path) -> None:
    record = _record(project_root)
    assert record["candidates"][1]["qualification_matrix"]["OFFICIAL_SHA256_CONFIRMED"] == "FAIL"  # type: ignore[index]
    record["candidates"][1]["artifact_files"][0].pop("head_metadata")  # type: ignore[index]
    with pytest.raises(GateNotAuthorizedError):
        validate_candidate_record(record)


def test_license_pass_requires_typed_immutable_evidence(project_root: Path) -> None:
    def remove_model_license_url(candidate: dict[str, object]) -> None:
        model_license = next(
            evidence
            for evidence in candidate["evidence_files"]  # type: ignore[index]
            if evidence["evidence_type"] == "MODEL_LICENSE"
        )
        model_license.pop("official_url")

    _assert_rejected_with_code(
        project_root,
        remove_model_license_url,
        "NPI_CANDIDATE_EVIDENCE_URL_REQUIRED",
    )

    def remove_model_license_reference(candidate: dict[str, object]) -> None:
        candidate["qualification_matrix"]["WEIGHTS_LICENSE_CONFIRMED"]["evidence_ids"] = []  # type: ignore[index]

    _assert_rejected_with_code(
        project_root,
        remove_model_license_reference,
        "NPI_CANDIDATE_LICENSE_EVIDENCE_INSUFFICIENT",
    )


def test_duplicate_file_and_mixed_precision_are_rejected(project_root: Path) -> None:
    record = _record(project_root)
    candidate = record["candidates"][0]  # type: ignore[index]
    candidate["artifact_files"][1]["filename"] = candidate["artifact_files"][0]["filename"]  # type: ignore[index]
    with pytest.raises(GateNotAuthorizedError):
        validate_candidate_record(record)

    record = _record(project_root)
    record["candidates"][0]["artifact_files"][1]["precision"] = "FP16"  # type: ignore[index]
    with pytest.raises(GateNotAuthorizedError):
        validate_candidate_record(record)


def test_modnet_requires_complete_fixed_source_and_conversion_bundle(project_root: Path) -> None:
    record = _record(project_root)
    modnet = record["candidates"][3]  # type: ignore[index]
    dependencies = modnet["bundle_variant"]["conversion_contract"]["dependencies"]  # type: ignore[index]
    assert {dependency["repository_relative_path"] for dependency in dependencies} >= {
        "models/public/modnet-webcam-portrait-matting/model.py",
        "tools/model_tools/src/omz_tools/internal_scripts/pytorch_to_onnx.py",
        "onnx/modnet_onnx.py",
        "src/models/backbones/__init__.py",
        "src/models/backbones/mobilenetv2.py",
        "src/models/backbones/wrapper.py",
    }
    assert {
        output["generated_or_downloaded"]
        for output in modnet["bundle_variant"]["conversion_contract"]["expected_outputs"]  # type: ignore[index]
    } == {"NOT_GENERATED"}

    modnet["bundle_variant"]["conversion_contract"]["dependencies"].pop()  # type: ignore[index]
    with pytest.raises(GateNotAuthorizedError):
        validate_candidate_record(record)


def test_source_git_identity_cannot_replace_model_payload_sha384(project_root: Path) -> None:
    _assert_rejected(
        project_root,
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {"checksum_algorithm": "GIT_BLOB_SHA1", "official_checksum": "a" * 40}
        ),
    )


def test_matrix_is_recomputed_and_ready_requires_official_sha256(project_root: Path) -> None:
    _assert_rejected(
        project_root,
        lambda candidate: (
            candidate["qualification_matrix"].update({"OFFICIAL_SHA256_CONFIRMED": "PASS"}),  # type: ignore[index]
            candidate.update({READY_STATUS_KEY: "PASS"}),
        ),
    )


def test_candidate_cap_and_historical_exclusion_are_rejected(project_root: Path) -> None:
    record = _record(project_root)
    third_pose = copy.deepcopy(record["candidates"][0])  # type: ignore[index]
    third_pose["candidate_id"] = "third-pose"
    with pytest.raises(GateNotAuthorizedError):
        validate_candidate_record(
            {"schema_version": "2.0", "phase_id": "N2B0_6", "candidates": [third_pose] * 4}
        )

    record = _record(project_root)
    record["candidates"][0]["candidate_id"] = next(iter(HISTORICAL_ARTIFACT_IDS))  # type: ignore[index]
    with pytest.raises(GateNotAuthorizedError):
        validate_candidate_record(record)


def test_candidate_validator_does_not_mutate_caller_metadata(project_root: Path) -> None:
    record = _record(project_root)
    before = copy.deepcopy(record)
    validate_alternative_candidates(record)
    assert record == before


def test_n2b0_6_state_keeps_photo_model_and_follow_on_stages_locked(project_root: Path) -> None:
    state = json.loads((project_root / "PROJECT_STATE.json").read_text("utf-8"))
    assert state["phase_status"]["N2B0_5"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_6"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_7"] == "APPROVED_COMPLETE"
    assert state["authorization"]["large_model_downloads"] == "AUTHORIZED_RESEARCH_ONLY"
    assert state["authorization"]["real_model_execution"] == "NOT_AUTHORIZED"
    assert [state["phase_status"][f"N{i}"] for i in range(3, 9)] == ["LOCKED"] * 6
    assert state["data_scope"]["G2_PILOT_100"] == "LOCKED"
    assert state["data_scope"]["G3_FULL_LIBRARY"] == "LOCKED"


def test_candidate_evidence_cannot_create_approval_or_unlock_n2b1(project_root: Path) -> None:
    before = json.loads((project_root / "PROJECT_STATE.json").read_text("utf-8"))
    validate_candidate_record(_record(project_root))
    after = json.loads((project_root / "PROJECT_STATE.json").read_text("utf-8"))
    assert after == before
    assert after["phase_status"]["N2B1"] == "LOCKED"
    assert after["authorization"]["capability_gates"]["N2B1_Q_QUARANTINE_DOWNLOAD"] == "LOCKED"
    assert not (project_root / "approvals" / "model_download_approval_N2B1.yaml").exists()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://official.example/path/file.bin?cache=1#fragment", "file.bin"),
        ("https://official.example/path/%C3%A9.bin", "é.bin"),
    ],
)
def test_canonical_artifact_url_basename_ignores_query_fragment_once(
    url: str, expected: str
) -> None:
    assert canonical_artifact_url_basename(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://official.example/path/",
        "https://official.example/path/%2Fescape.bin",
        "https://official.example/path/%5Cescape.bin",
        "https://official.example/path/%00.bin",
        "https://user@official.example/path/file.bin",
        "https://official.example/path/..",
    ],
)
def test_canonical_artifact_url_basename_rejects_unsafe_identity(url: str) -> None:
    with pytest.raises(GateNotAuthorizedError):
        canonical_artifact_url_basename(url)


def test_payload_filename_direct_and_final_url_bindings_are_fail_closed(project_root: Path) -> None:
    _assert_rejected_with_code(
        project_root,
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {"filename": "other.xml"}
        ),
        "NPI_CANDIDATE_FILENAME_URL_MISMATCH",
    )
    _assert_rejected_with_code(
        project_root,
        lambda candidate: candidate["artifact_files"][0]["head_metadata"].update(  # type: ignore[index]
            {"final_url": "https://storage.openvinotoolkit.org/other.xml"}
        ),
        "NPI_CANDIDATE_FINAL_URL_FILENAME_MISMATCH",
    )
    _assert_rejected_with_code(
        project_root,
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {
                "direct_official_url": candidate["artifact_files"][0][
                    "direct_official_url"
                ].replace("/FP32/", "/FP16/")
            }
        ),
        "NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH",
    )
    _assert_rejected_with_code(
        project_root,
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {
                "direct_official_url": candidate["artifact_files"][0][
                    "direct_official_url"
                ].replace(".xml", "%2Fother.xml")
            }
        ),
        "NPI_CANDIDATE_FILENAME_URL_MISMATCH",
    )


def test_model_configuration_requires_exact_omz_model_yml_binding(project_root: Path) -> None:
    def wrong_model_path(candidate: dict[str, object]) -> None:
        evidence = next(
            item
            for item in candidate["evidence_files"]  # type: ignore[index]
            if item["evidence_type"] == "MODEL_CONFIGURATION"
        )
        evidence["official_url"] = evidence["official_url"].replace(  # type: ignore[index]
            "human-pose-estimation-0001", "human-pose-estimation-0005"
        )

    _assert_rejected_with_code(
        project_root, wrong_model_path, "NPI_CANDIDATE_MODEL_CONFIGURATION_REVISION_MISMATCH"
    )

    def wrong_revision(candidate: dict[str, object]) -> None:
        evidence = next(
            item
            for item in candidate["evidence_files"]  # type: ignore[index]
            if item["evidence_type"] == "MODEL_CONFIGURATION"
        )
        wrong = "a" * 40
        evidence["source_revision"]["value"] = wrong  # type: ignore[index]
        evidence["source_revision"]["source_url"] = evidence["source_revision"][  # type: ignore[index]
            "source_url"
        ].replace("7cc29a91472b4cb1289a11e655ba3e188e1d4a31", wrong)
        evidence["official_url"] = evidence["official_url"].replace(  # type: ignore[index]
            "7cc29a91472b4cb1289a11e655ba3e188e1d4a31", wrong
        )

    _assert_rejected_with_code(
        project_root, wrong_revision, "NPI_CANDIDATE_MODEL_CONFIGURATION_REVISION_MISMATCH"
    )


@pytest.mark.parametrize("replacement", ["README.md", "model.py"])
def test_model_configuration_rejects_wrong_document_path(
    project_root: Path, replacement: str
) -> None:
    def wrong_document(candidate: dict[str, object]) -> None:
        evidence = next(
            item
            for item in candidate["evidence_files"]  # type: ignore[index]
            if item["evidence_type"] == "MODEL_CONFIGURATION"
        )
        evidence["official_url"] = evidence["official_url"].replace("model.yml", replacement)  # type: ignore[index]

    _assert_rejected_with_code(
        project_root, wrong_document, "NPI_CANDIDATE_MODEL_CONFIGURATION_REVISION_MISMATCH"
    )


def test_model_configuration_rejects_main_and_short_revision(project_root: Path) -> None:
    def floating_main(candidate: dict[str, object]) -> None:
        evidence = next(
            item
            for item in candidate["evidence_files"]  # type: ignore[index]
            if item["evidence_type"] == "MODEL_CONFIGURATION"
        )
        evidence["source_revision"]["value"] = "main"  # type: ignore[index]
        evidence["source_revision"]["source_url"] = (  # type: ignore[index]
            "https://github.com/openvinotoolkit/open_model_zoo/commit/main"
        )
        evidence["official_url"] = evidence["official_url"].replace(  # type: ignore[index]
            "7cc29a91472b4cb1289a11e655ba3e188e1d4a31", "main"
        )

    _assert_rejected_with_code(
        project_root, floating_main, "NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED"
    )

    def short_revision(candidate: dict[str, object]) -> None:
        evidence = next(
            item
            for item in candidate["evidence_files"]  # type: ignore[index]
            if item["evidence_type"] == "MODEL_CONFIGURATION"
        )
        evidence["source_revision"]["value"] = "7cc29a9"  # type: ignore[index]
        evidence["source_revision"]["source_url"] = (  # type: ignore[index]
            "https://github.com/openvinotoolkit/open_model_zoo/commit/7cc29a9"
        )
        evidence["official_url"] = evidence["official_url"].replace(  # type: ignore[index]
            "7cc29a91472b4cb1289a11e655ba3e188e1d4a31", "7cc29a9"
        )

    _assert_rejected_with_code(
        project_root, short_revision, "NPI_CANDIDATE_EVIDENCE_REVISION_REQUIRED"
    )


def test_evidence_cross_references_and_checksum_assertions_are_bi_directional(
    project_root: Path,
) -> None:
    _assert_rejected_with_code(
        project_root,
        lambda candidate: candidate["artifact_files"][0].update(  # type: ignore[index]
            {"license_evidence_ids": ["missing"]}
        ),
        "NPI_CANDIDATE_EVIDENCE_REFERENCE_MISSING",
    )

    def change_checksum_assertion(candidate: dict[str, object]) -> None:
        evidence = next(
            item
            for item in candidate["evidence_files"]  # type: ignore[index]
            if item["evidence_type"] == "CHECKSUM_METADATA"
        )
        evidence["artifact_assertions"][0]["size_bytes"] += 1  # type: ignore[index]

    _assert_rejected_with_code(
        project_root, change_checksum_assertion, "NPI_CANDIDATE_EVIDENCE_SOURCE_MISMATCH"
    )


def test_public_entrypoints_reject_duplicate_json_and_partial_list_bypass(
    project_root: Path,
) -> None:
    raw = (project_root / "research" / "N2B0_6_candidate_records.json").read_text("utf-8")
    duplicate = raw.replace(
        '"schema_version": "2.0",',
        '"schema_version": "2.0",\n  "schema_version": "2.0",',
        1,
    )
    with pytest.raises(NpiError) as raised:
        validate_candidate_record_bytes(duplicate)
    assert raised.value.error_code == "NPI_DUPLICATE_JSON_MEMBER"

    with pytest.raises(GateNotAuthorizedError):
        validate_alternative_candidates([_candidate(project_root)])  # type: ignore[arg-type]


def test_archival_n0_mode_is_explicitly_not_a_current_stage_pass(project_root: Path) -> None:
    result = subprocess.run(
        [".venv\\Scripts\\python.exe", "tools\\verify_handoff.py", "--archival-n0"],
        cwd=project_root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 8
    assert "N0_ARCHIVAL_SUPERSEDED" in result.stdout
