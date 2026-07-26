"""N2B0 approval and N2B0.5 rights closure remain fail-closed."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


def test_n2b0_allowlist_is_a_non_authorizing_valid_draft(project_root: Path) -> None:
    draft = yaml.safe_load(
        (project_root / "config" / "model_artifact_allowlist.draft.yaml").read_text("utf-8")
    )
    schema = json.loads(
        (project_root / "schemas" / "model_artifact_approval.schema.json").read_text("utf-8")
    )
    assert not list(Draft202012Validator(schema).iter_errors(draft))
    assert draft["status"] == "DRAFT_NOT_AUTHORIZED"
    assert all(item["post_download_hash_required"] for item in draft["artifacts"])
    assert len(draft["artifacts"]) == 4
    assert all(item["qualification_status"] == "INCONCLUSIVE" for item in draft["artifacts"])
    assert all(item["weights_license"] == "UNKNOWN" for item in draft["artifacts"])
    pose = next(
        item for item in draft["artifacts"] if item["purpose"] == "whole-body pose candidate"
    )
    segmentation = next(
        item
        for item in draft["artifacts"]
        if item["purpose"] == "lightweight human segmentation candidate"
    )
    assert pose["artifact_filename"].endswith(".pth")
    assert "download.openmmlab.com" in pose["official_download_source"]
    assert segmentation["artifact_filename"].endswith(".zip")
    assert "paddleseg.bj.bcebos.com" in segmentation["official_download_source"]
    media = next(item for item in draft["artifacts"] if item["project_id"] == "mediapipe")
    assert media["artifact_filename"] == "selfie_segmentation.tflite"
    assert media["official_download_source"].startswith("https://storage.googleapis.com/")
    summary = (project_root / "reports" / "N2B0_artifact_qualification_summary.md").read_text(
        "utf-8"
    )
    assert "N2B0_ARTIFACT_QUALIFICATION_BLOCKED" in summary


def test_n2b0_state_authorizes_qualification_but_locks_download_and_execution(
    project_root: Path,
) -> None:
    state = json.loads((project_root / "PROJECT_STATE.json").read_text("utf-8"))
    gates = state["authorization"]["capability_gates"]
    assert state["phase_status"]["N2A"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_5"] == "APPROVED_COMPLETE"
    assert state["phase_status"]["N2B0_6"] == "AUTHORIZED"
    assert state["phase_status"]["N2B1"] == "LOCKED"
    assert state["phase_status"]["N2B1_Q"] == "LOCKED"
    assert state["phase_status"]["N2B1_P"] == "LOCKED"
    assert state["phase_status"]["N2B2"] == "LOCKED"
    assert gates["N2B0_MODEL_ARTIFACT_QUALIFICATION"] == "APPROVED_COMPLETE"
    assert gates["N2B0_5_ARTIFACT_RIGHTS_AND_PROVENANCE_CLOSURE"] == "APPROVED_COMPLETE"
    assert gates["N2B0_6_LICENSE_CLEAR_ALTERNATIVE_CANDIDATE_RESEARCH"] == "AUTHORIZED"
    assert gates["N2B1_MODEL_DOWNLOAD"] == "LOCKED"
    assert gates["N2B1_Q_QUARANTINE_DOWNLOAD"] == "LOCKED"
    assert gates["N2B1_P_CACHE_PROMOTION"] == "LOCKED"
    assert gates["N2B2_REAL_BENCHMARK"] == "LOCKED"
    assert state["authorization"]["large_model_downloads"] == "NOT_AUTHORIZED"
    assert state["authorization"]["real_model_execution"] == "NOT_AUTHORIZED"


def test_rtmw_fallback_metadata_is_corrected_and_remains_fail_closed(project_root: Path) -> None:
    draft = yaml.safe_load(
        (project_root / "config" / "model_artifact_allowlist.draft.yaml").read_text("utf-8")
    )
    fallback = next(
        item
        for item in draft["artifacts"]
        if item["artifact_id"] == "pose-rtmw-m-coco-wholebody-fallback"
    )
    old_filename = "rtmw-dw-l" + "_m_simcc-cocktail14_270e-256x192-20231122.pth"
    new_filename = "rtmw-dw-l-m_simcc-cocktail14_270e-256x192-20231122.pth"
    assert old_filename not in fallback["artifact_filename"]
    assert fallback["artifact_filename"] == new_filename
    assert fallback["official_download_source"].endswith(new_filename)
    assert fallback["artifact_expected_size_bytes"] == 129787113
    assert fallback["weights_license"] == "UNKNOWN"
    assert fallback["qualification_status"] == "INCONCLUSIVE"

    tracked = subprocess.run(
        ["git", "-C", str(project_root), "ls-files"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    text_suffixes = {".csv", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml"}
    tracked_text = "\n".join(
        (project_root / relative).read_text("utf-8", errors="ignore")
        for relative in tracked
        if (project_root / relative).suffix.lower() in text_suffixes
    )
    assert old_filename not in tracked_text
    assert new_filename in tracked_text
