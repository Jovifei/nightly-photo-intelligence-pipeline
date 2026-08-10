#!/usr/bin/env python3
"""Verify the current governed handoff without performing work.

This verifier never opens a source photo, sends a network request, installs a
wheel, or writes repository/runtime state.  It binds the exact local-research
authorization, the immutable approved baselines, and every tracked file.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
CURRENT_PHASE = "N2B1P"
CURRENT_TASK = "tasks/phase_n2b1p_local_research_cache_promotion.yaml"
CURRENT_CAPABILITY = "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION"
N2B1R_SHA = "d3628e27334e819ba2d5944151447595e03f39f9"
N2B1P_SHA = "9b3d5a1cc4a6f81467ad98034ca8994d1ebab043"
N2B2_REVIEW_TASK = "tasks/phase_n2b2_runtime_gpu_validation_and_s20_preparation.yaml"
N2B2_REVIEW_RECEIPT = "approvals/owner_n2b2_runtime_gpu_validation_receipt.yaml"
N2B2_S20_TASK = "tasks/phase_n2b2_s20_synthetic_validation.yaml"
N2B2_S20_RECEIPT = "approvals/owner_n2b2_s20_synthetic_validation_receipt.yaml"
N2B2_QWEN_TASK = "tasks/phase_n2b2_qwen_fact_binding_remediation.yaml"
N2B2_QWEN_RECEIPT = "approvals/owner_n2b2_qwen_fact_binding_remediation_receipt.yaml"
N2B2_S20_INTEGRITY_TASK = "tasks/phase_n2b2_s20_artifact_integrity_remediation.yaml"
N2B2_S20_INTEGRITY_RECEIPT = "approvals/owner_n2b2_s20_artifact_integrity_remediation_receipt.yaml"

errors: list[str] = []
passes: list[str] = []


def fail(message: str) -> None:
    errors.append(message)


def ok(message: str) -> None:
    passes.append(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON member")
        result[key] = value
    return result


def load_json(rel: str) -> Any:
    try:
        return json.loads(
            (ROOT / rel).read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicate_pairs
        )
    except Exception as exc:  # noqa: BLE001 - verifier must report instead of crash
        fail(f"{rel}: cannot strict-parse JSON: {type(exc).__name__}")
        return {}


def load_yaml(rel: str) -> Any:
    try:
        import yaml

        return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - verifier must report instead of crash
        fail(f"{rel}: cannot parse YAML: {type(exc).__name__}")
        return {}


def git(*args: str) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, type(exc).__name__
    return result.returncode, result.stdout.strip()


def _validate(schema_rel: str, value: object) -> bool:
    try:
        from jsonschema import Draft202012Validator, FormatChecker

        schema = load_json(schema_rel)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        return not list(validator.iter_errors(value))
    except Exception:  # noqa: BLE001 - a schema failure is a verification failure
        return False


def check_required_files() -> None:
    required = (
        "MASTER_EXECUTION_CONTRACT.md",
        "AGENTS.md",
        "PROJECT_STATE.json",
        CURRENT_TASK,
        "tasks/index.json",
        "MANIFEST.sha256",
        "approvals/phase_completion_N2B0_7.yaml",
        "approvals/phase_completion_N2B0_7.sha256",
        "approvals/owner_n2b1p_cache_promotion.yaml",
        "approvals/n2b1p_runtime_configuration.json",
        "research/N2B1R_acquisition_evidence.json",
        "research/N2B1P_cache_promotion_evidence.json",
        "research/N2B1P_remediation_cache_baseline.json",
        "research/N2B1P_remediation_cache_revalidation.json",
        "reports/N2B1P_cache_promotion_report.md",
        "research/N2B1R_local_research_artifact_register.json",
        "schemas/project_state_v1_7.schema.json",
        "schemas/phase_completion_approval_n2b0_7_v1_0.schema.json",
        "schemas/owner_n2b1p_cache_promotion_v1_0.schema.json",
        "schemas/task_contract_n2b1p_v1_0.schema.json",
        "schemas/n2b1r_acquisition_evidence_v1.schema.json",
        "schemas/n2b1p_cache_promotion_evidence_v1.schema.json",
        "schemas/n2b1p_runtime_configuration_v1_0.schema.json",
        "schemas/n2b1r_artifact_register_v1.schema.json",
        N2B2_REVIEW_TASK,
        N2B2_REVIEW_RECEIPT,
        N2B2_S20_TASK,
        N2B2_S20_RECEIPT,
        N2B2_QWEN_TASK,
        N2B2_QWEN_RECEIPT,
        N2B2_S20_INTEGRITY_TASK,
        N2B2_S20_INTEGRITY_RECEIPT,
        "schemas/n2b2_s20_fixture_manifest.schema.json",
        "schemas/n2b2_s20_independent_review.schema.json",
        "schemas/n2b2_gpu_runtime_metrics.schema.json",
    )
    missing = [rel for rel in required if not (ROOT / rel).is_file()]
    if missing:
        fail("missing required current-stage files: " + ", ".join(missing))
    else:
        ok("required N2B1P contracts, evidence, register, and approval files exist")


def check_current_authorization() -> None:
    state = load_json("PROJECT_STATE.json")
    completion = load_yaml("approvals/phase_completion_N2B0_7.yaml")
    promotion_approval = load_yaml("approvals/owner_n2b1p_cache_promotion.yaml")
    task = load_yaml(CURRENT_TASK)
    evidence = load_json("research/N2B1R_acquisition_evidence.json")
    promotion_evidence = load_json("research/N2B1P_cache_promotion_evidence.json")
    cache_baseline = load_json("research/N2B1P_remediation_cache_baseline.json")
    cache_revalidation = load_json("research/N2B1P_remediation_cache_revalidation.json")
    runtime_configuration = load_json("approvals/n2b1p_runtime_configuration.json")
    register = load_json("research/N2B1R_local_research_artifact_register.json")
    index = load_json("tasks/index.json")
    documents = (
        ("schemas/project_state_v1_7.schema.json", state),
        ("schemas/phase_completion_approval_n2b0_7_v1_0.schema.json", completion),
        ("schemas/owner_n2b1p_cache_promotion_v1_0.schema.json", promotion_approval),
        ("schemas/task_contract_n2b1p_v1_0.schema.json", task),
        ("schemas/n2b1r_acquisition_evidence_v1.schema.json", evidence),
        ("schemas/n2b1p_cache_promotion_evidence_v1.schema.json", promotion_evidence),
        ("schemas/n2b1p_runtime_configuration_v1_0.schema.json", runtime_configuration),
        ("schemas/n2b1r_artifact_register_v1.schema.json", register),
        ("schemas/task_index_v1_2.schema.json", index),
    )
    if not all(_validate(schema, document) for schema, document in documents):
        fail("current N2B1P authorization schema validation failed")
        return
    auth = state.get("authorization", {})
    phase_status = state.get("phase_status", {})
    gates = auth.get("capability_gates", {}) if isinstance(auth, dict) else {}
    active = auth.get("active_execution", {}) if isinstance(auth, dict) else {}
    current_index = next(
        (
            item
            for item in index.get("authorized", [])
            if isinstance(item, dict) and item.get("phase") == CURRENT_PHASE
        ),
        None,
    )
    evidence_bindings = {
        item.get("id"): (
            item.get("revision"),
            item.get("filename"),
            item.get("byte_count"),
            item.get("local_sha256"),
            item.get("transfer_manifest_sha256"),
        )
        for item in evidence.get("artifacts", [])
        if isinstance(item, dict)
    }
    approval_bindings = {
        item.get("id"): (
            item.get("revision"),
            item.get("filename"),
            item.get("byte_count"),
            item.get("local_sha256"),
            item.get("transfer_manifest_sha256"),
        )
        for item in promotion_approval.get("allowed_artifacts", [])
        if isinstance(item, dict)
    }
    promotion_bindings = {
        item.get("id"): (
            item.get("byte_count"),
            item.get("local_sha256"),
            item.get("transfer_manifest_sha256"),
        )
        for item in promotion_evidence.get("artifacts", [])
        if isinstance(item, dict)
    }
    expected_promotion_bindings = {
        artifact_id: (binding[2], binding[3], binding[4])
        for artifact_id, binding in evidence_bindings.items()
    }
    try:
        from nightly_photo_intelligence_pipeline.local_research_promotion import (
            load_authorized_promotion,
            verify_promoted_artifact,
        )

        artifact_ids = (
            "torchvision-keypointrcnn-resnet50-fpn-coco-v1",
            "torchvision-lraspp-mobilenet-v3-large-coco-voc-v1",
            "torchvision-deeplabv3-mobilenet-v3-large-coco-voc-v1",
        )
        cache_results = {
            verify_promoted_artifact(artifact_id, project_root=ROOT).status
            for artifact_id in artifact_ids
        }
        authorized_hashes = {
            load_authorized_promotion(artifact_id, project_root=ROOT).local_sha256
            for artifact_id in artifact_ids
        }
    except Exception as exc:  # noqa: BLE001 - verification remains fail closed
        fail(f"N2B1P canonical cache verification failed: {type(exc).__name__}")
        return
    locked = (
        "N2B",
        "N2B1",
        "N2B1_Q",
        "N2B1_P",
        "N2B2",
        "N3",
        "N4",
        "N5",
        "N6",
        "N7",
        "N8",
    )
    valid = all(
        (
            state.get("schema_version") == "1.7",
            completion.get("owner_decision") == "N2B0_7_OWNER_APPROVED",
            completion.get("baseline", {}).get("n2b0_7_commit")
            == "f2b1c38301d71da52b855f73de8a67908cb525ef",
            (ROOT / "approvals" / "phase_completion_N2B0_7.sha256")
            .read_text(encoding="utf-8")
            .strip()
            == sha256(ROOT / "approvals" / "phase_completion_N2B0_7.yaml"),
            phase_status.get("N2B0_7") == "APPROVED_COMPLETE",
            phase_status.get("N2B1R") == "ACQUISITION_COMPLETE",
            phase_status.get(CURRENT_PHASE) == "AUTHORIZED",
            task.get("phase", {}).get("id") == CURRENT_PHASE,
            task.get("phase", {}).get("status") == "AUTHORIZED",
            task.get("capability") == CURRENT_CAPABILITY,
            task.get("mandatory_stop", {}).get("value") is True,
            gates.get(CURRENT_CAPABILITY) == "AUTHORIZED",
            gates.get("N2B1R_LOCAL_RESEARCH_MODEL_ACQUISITION") == "ACQUISITION_COMPLETE",
            auth.get("large_model_downloads") == "AUTHORIZED_RESEARCH_ONLY",
            auth.get("real_model_execution") == "NOT_AUTHORIZED",
            active
            == {
                "phase": "N2B1P",
                "capability": "N2B1P_LOCAL_RESEARCH_CACHE_PROMOTION",
                "source_photo_content_read": "NOT_AUTHORIZED",
                "source_photo_exif_read": "NOT_AUTHORIZED",
                "sqlite_ingest_write": "NOT_AUTHORIZED",
            },
            all(phase_status.get(phase) == "LOCKED" for phase in locked),
            isinstance(current_index, dict),
            current_index.get("file") == Path(CURRENT_TASK).name,
            current_index.get("capability") == CURRENT_CAPABILITY,
            register.get("weights_rights", {}).get("status") == "UNKNOWN_NOT_COMMERCIAL_CLEARANCE",
            len(register.get("artifacts", [])) == 3,
            evidence.get("result") == "N2B1R_ACQUISITION_COMPLETE_AWAITING_LOCAL_VERIFICATION",
            evidence.get("prohibited_actions", {}).get("cache_promotion") == "NOT_PERFORMED",
            promotion_evidence.get("result")
            == "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
            promotion_evidence.get("prohibited_actions")
            == {
                "source_photo_or_exif_read": "NOT_PERFORMED",
                "sqlite_ingest_write": "NOT_PERFORMED",
                "model_load_or_inference": "NOT_PERFORMED",
                "cuda_execution": "NOT_PERFORMED",
                "dependency_install": "NOT_PERFORMED",
                "derived_image_or_model_output": "NOT_PERFORMED",
                "network_request_or_download": "NOT_PERFORMED",
                "cache_or_quarantine_delete": "NOT_PERFORMED",
            },
            cache_baseline.get("result") == "CACHE_BASELINE_PASS",
            cache_revalidation.get("result") == "N2B1P_REMEDIATION_CACHE_REVALIDATION_PASS",
            {
                item.get("status")
                for item in cache_revalidation.get("artifacts", [])
                if isinstance(item, dict)
            }
            == {"CACHE_HIT"},
            cache_revalidation.get("mutation_counts")
            == {
                "CACHE_PAYLOAD_MUTATION_COUNT": 0,
                "CACHE_MANIFEST_MUTATION_COUNT": 0,
                "CACHE_NEW_FILE_COUNT": 0,
                "CACHE_DELETED_FILE_COUNT": 0,
            },
            promotion_approval.get("n2b1r_commit") == "d3628e27334e819ba2d5944151447595e03f39f9",
            promotion_approval.get("n2b1r_evidence", {}).get("sha256")
            == sha256(ROOT / "research" / "N2B1R_acquisition_evidence.json"),
            auth.get("n2b1p_promotion_evidence") == "research/N2B1P_cache_promotion_evidence.json",
            auth.get("n2b1p_runtime_configuration") == "approvals/n2b1p_runtime_configuration.json",
            len(evidence_bindings) == len(approval_bindings) == 3,
            approval_bindings == evidence_bindings,
            promotion_bindings == expected_promotion_bindings,
            authorized_hashes == {binding[3] for binding in evidence_bindings.values()},
            cache_results == {"CACHE_HIT"},
            state.get("required_stop_after")
            == {
                "condition": "N2B1P_REMEDIATION_COMPLETE_AWAITING_EXTERNAL_REVIEW",
                "next_action": "EXTERNAL_REVIEW_N2B1P_REMEDIATION",
            },
        )
    )
    if not valid:
        fail("current N2B1P authorization boundary is inconsistent or broadened")
    else:
        ok("N2B1P is promotion-only; inference and real-photo entry points remain locked")


def check_bounded_n2b2_review_contract() -> None:
    """Validate the direct Owner receipt without changing PROJECT_STATE."""

    task = load_yaml(N2B2_REVIEW_TASK)
    receipt = load_yaml(N2B2_REVIEW_RECEIPT)
    index = load_json("tasks/index.json")
    state = load_json("PROJECT_STATE.json")
    candidate = next(
        (
            item
            for item in index.get("review_candidates", [])
            if isinstance(item, dict) and item.get("phase") == "N2B2_RUNTIME_GPU_VALIDATION"
        ),
        None,
    )
    phase = task.get("phase", {}) if isinstance(task, dict) else {}
    authorization = task.get("owner_authorization", {}) if isinstance(task, dict) else {}
    allowed = receipt.get("allowed", []) if isinstance(receipt, dict) else []
    forbidden = receipt.get("not_allowed", []) if isinstance(receipt, dict) else []
    valid = all(
        (
            isinstance(candidate, dict),
            candidate.get("capability")
            == "N2B2_RUNTIME_GPU_VALIDATION_AND_SYNTHETIC_S20_PREPARATION",
            candidate.get("project_state") == "N2B2_LOCKED",
            candidate.get("execution_status") == "SYNTHETIC_GPU_ONLY",
            phase.get("status") == "AUTHORIZED_SYNTHETIC_RUNTIME_ONLY_REVIEW_CANDIDATE",
            phase.get("project_state_status") == "N2B2_LOCKED",
            authorization.get("reviewed_baseline") == N2B1P_SHA,
            authorization.get("synthetic_only") is True,
            authorization.get("cuda_runtime_validation") is True,
            authorization.get("s20_execution") == "NOT_AUTHORIZED_THIS_RUN",
            receipt.get("reviewed_baseline") == N2B1P_SHA,
            receipt.get("mandatory_stop") is True,
            "real photos" in forbidden,
            "PROJECT_STATE mutation" in forbidden,
            "S20 execution" in forbidden,
            "explicit CUDA validation for cached TorchVision models" in allowed,
            "qwen3.5:9b local GPU residency validation" in allowed,
            "create S20 schema and validation plan only" in allowed,
            state.get("phase_status", {}).get("N2B2") == "LOCKED",
            state.get("phase_status", {}).get("N2B1P") == "AUTHORIZED",
        )
    )
    candidate_is_s20 = git("rev-parse", "HEAD^")[1] == "49e653b27884f9ba09d15ca17682e496687dc59f"
    if valid and not candidate_is_s20:
        ok("bounded N2B2 synthetic GPU review receipt is valid; production N2B2 remains locked")
    else:
        s20_task = load_yaml(N2B2_S20_TASK)
        s20_receipt = load_yaml(N2B2_S20_RECEIPT)
        qwen_task = load_yaml(N2B2_QWEN_TASK)
        qwen_receipt = load_yaml(N2B2_QWEN_RECEIPT)
        integrity_task = load_yaml(N2B2_S20_INTEGRITY_TASK)
        integrity_receipt = load_yaml(N2B2_S20_INTEGRITY_RECEIPT)
        s20_candidate = next(
            (
                item
                for item in index.get("review_candidates", [])
                if isinstance(item, dict) and item.get("phase") == "N2B2_S20_SYNTHETIC_VALIDATION"
            ),
            None,
        )
        qwen_candidate = next(
            (
                item
                for item in index.get("review_candidates", [])
                if isinstance(item, dict)
                and item.get("phase") == "N2B2_QWEN_FACT_BINDING_CONTRACT_REMEDIATION"
            ),
            None,
        )
        integrity_candidate = next(
            (
                item
                for item in index.get("review_candidates", [])
                if isinstance(item, dict)
                and item.get("phase") == "N2B2_S20_ARTIFACT_INTEGRITY_REMEDIATION"
            ),
            None,
        )
        s20_phase = s20_task.get("phase", {}) if isinstance(s20_task, dict) else {}
        s20_prerequisite = s20_task.get("prerequisite", {}) if isinstance(s20_task, dict) else {}
        s20_valid = all(
            (
                isinstance(s20_candidate, dict),
                s20_candidate.get("project_state") == "N2B2_LOCKED",
                s20_candidate.get("execution_status") == "CONDITIONAL_SYNTHETIC_ONLY",
                s20_phase.get("status") == "AUTHORIZED_SYNTHETIC_S20_REVIEW_CANDIDATE",
                s20_phase.get("project_state_status") == "N2B2_LOCKED",
                s20_prerequisite.get("reviewed_commit")
                == "49e653b27884f9ba09d15ca17682e496687dc59f",
                s20_prerequisite.get("review_verdict") == "PASS_FOR_OWNER_REVIEW",
                s20_receipt.get("reviewed_commit") == "49e653b27884f9ba09d15ca17682e496687dc59f",
                s20_receipt.get("review_verdict") == "PASS_FOR_OWNER_REVIEW",
                s20_receipt.get("s20_execution") == "CONDITIONAL_OWNER_AUTHORIZED",
                s20_receipt.get("project_state_mutation") is False,
                s20_receipt.get("production_n2b2_unlock") is False,
                isinstance(qwen_candidate, dict),
                qwen_candidate.get("project_state") == "N2B2_LOCKED",
                qwen_candidate.get("execution_status") == "SYNTHETIC_QWEN_CONTRACT_ONLY",
                isinstance(qwen_task, dict),
                qwen_task.get("phase", {}).get("status")
                == "AUTHORIZED_SYNTHETIC_REMEDIATION_REVIEW_CANDIDATE",
                qwen_task.get("phase", {}).get("project_state_status") == "N2B2_LOCKED",
                isinstance(qwen_receipt, dict),
                qwen_receipt.get("status") == "AUTHORIZED_FOR_BOUNDED_SYNTHETIC_RETRY",
                qwen_receipt.get("reviewed_commit") == "49e653b27884f9ba09d15ca17682e496687dc59f",
                qwen_receipt.get("project_state_mutation") is False,
                qwen_receipt.get("production_n2b2_unlock") is False,
                state.get("phase_status", {}).get("N2B2") == "LOCKED",
            )
        )
        if s20_valid:
            integrity_valid = all(
                (
                    isinstance(integrity_candidate, dict),
                    integrity_candidate.get("project_state") == "N2B2_LOCKED",
                    integrity_candidate.get("execution_status")
                    == "SYNTHETIC_ARTIFACT_INTEGRITY_ONLY",
                    isinstance(integrity_task, dict),
                    integrity_task.get("phase", {}).get("status")
                    == "AUTHORIZED_SYNTHETIC_REMEDIATION_REVIEW_CANDIDATE",
                    integrity_task.get("phase", {}).get("project_state_status") == "N2B2_LOCKED",
                    integrity_task.get("prerequisite", {}).get("required_final_parent")
                    == "49e653b27884f9ba09d15ca17682e496687dc59f",
                    isinstance(integrity_receipt, dict),
                    integrity_receipt.get("receipt_type")
                    == "OWNER_S20_ARTIFACT_INTEGRITY_REMEDIATION",
                    integrity_receipt.get("status") == "AUTHORIZED_FOR_BOUNDED_SYNTHETIC_RETRY",
                    integrity_receipt.get("required_final_parent")
                    == "49e653b27884f9ba09d15ca17682e496687dc59f",
                    integrity_receipt.get("fixture_manifest_sha256")
                    == "b59446550e81499aaac9be17bebfd675f403869767a16318ce1a1a8904e4eec0",
                    integrity_receipt.get("project_state_mutation") is False,
                    integrity_receipt.get("production_n2b2_unlock") is False,
                )
            )
            if integrity_valid:
                ok(
                    "bounded N2B2 S20 artifact-integrity review receipt is valid; "
                    "production N2B2 remains locked"
                )
            else:
                fail("bounded N2B2 S20 artifact-integrity receipt or lock boundary is invalid")
        else:
            fail("bounded N2B2 review-candidate receipt or lock boundary is invalid")


def check_baselines() -> None:
    expected = {
        "n0-approved-2026-07-14": "72a81f5984838b74304d23263ac450ea4b5a3a9a",
        "n1-approved-2026-07-14": "ca812cb71c4a09d273f64d9a6f2747ac3facf4cc",
        "g1-approved-2026-07-19": "4a807dbbcd147a106b02b7e3899aa701c2028d83",
        "n2a-approved-2026-07-22": "f79d2df504622ff82aa5e53d1486310bbea9985a",
        "n2b0-approved-2026-07-24": "f331621c84905aef921c612908d01d3a8a2f577a",
        "n2b0-5-approved-2026-07-26": "5ad9f8d7d0d6fa267df02d90ef25957bc679e232",
        "n2b0-6-approved-2026-07-29": "eb2eaeb61f1c21923d131a115d63edbcdebd8cb2",
        "n2b0-7-approved-2026-07-29": "f2b1c38301d71da52b855f73de8a67908cb525ef",
    }
    mismatched = [tag for tag, commit in expected.items() if git("rev-parse", tag) != (0, commit)]
    if mismatched:
        fail("immutable baseline tag mismatch: " + ", ".join(mismatched))
    elif git("merge-base", "--is-ancestor", expected["n2b0-7-approved-2026-07-29"], "HEAD")[0] != 0:
        fail("N2B0.7 approved baseline is not an ancestor of HEAD")
    elif git("merge-base", "--is-ancestor", N2B1R_SHA, "HEAD")[0] != 0:
        fail("N2B1R evidence commit is not an ancestor of HEAD")
    elif git("rev-parse", "HEAD") == (0, N2B1P_SHA) and git(
        "rev-list", "--count", f"{N2B1R_SHA}..HEAD"
    ) != (0, "1"):
        fail("N2B1P baseline must contain exactly one post-N2B1R commit")
    elif git("rev-parse", "HEAD") != (0, N2B1P_SHA) and not (
        (
            git("rev-parse", "HEAD^") == (0, N2B1P_SHA)
            and git("rev-list", "--count", f"{N2B1R_SHA}..HEAD") == (0, "2")
            and git("rev-list", "--count", f"{N2B1P_SHA}..HEAD") == (0, "1")
        )
        or (
            git("rev-parse", "HEAD^") == (0, "49e653b27884f9ba09d15ca17682e496687dc59f")
            and git("rev-list", "--count", f"{N2B1R_SHA}..HEAD") == (0, "3")
            and git("rev-list", "--count", f"{N2B1P_SHA}..HEAD") == (0, "2")
        )
    ):
        fail("N2B2 review candidate must be exactly one direct child of N2B1P")
    elif git("rev-list", "--merges", "HEAD") != (0, ""):
        fail("current candidate contains a merge commit")
    elif git("rev-parse", "HEAD^") == (0, "49e653b27884f9ba09d15ca17682e496687dc59f"):
        print(
            "HANDOFF_VALID: bounded N2B2 S20 artifact-integrity review candidate; "
            "production N2B2 remains LOCKED"
        )
    else:
        ok("all immutable approved tags and the bounded no-merge ancestry are intact")


def check_manifest() -> None:
    listed: dict[str, str] = {}
    try:
        for line in (ROOT / "MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, rel = line.split("  ", 1)
            if not re.fullmatch(r"[0-9a-f]{64}", digest) or rel in listed:
                raise ValueError("invalid digest or duplicate path")
            listed[rel] = digest
    except (OSError, ValueError) as exc:
        fail(f"MANIFEST.sha256 is invalid: {type(exc).__name__}")
        return
    rc, tracked_text = git("ls-files")
    tracked = {rel for rel in tracked_text.splitlines() if rel and rel != "MANIFEST.sha256"}
    if rc != 0 or set(listed) != tracked:
        fail("MANIFEST.sha256 does not bind exactly the tracked current-stage file set")
        return
    mismatches = [rel for rel, digest in listed.items() if sha256(ROOT / rel) != digest]
    if mismatches:
        fail("MANIFEST.sha256 hash mismatch: " + ", ".join(sorted(mismatches)))
    elif git("status", "--porcelain", "--untracked-files=all") != (0, ""):
        fail("worktree is not clean")
    else:
        ok("MANIFEST.sha256 binds every tracked current-stage file; worktree is clean")


def check_sensitive_paths() -> None:
    rc, tracked_text = git("ls-files")
    if rc != 0:
        fail("cannot inspect tracked paths")
        return
    suffixes = (".db", ".sqlite", ".sqlite3", ".pth", ".pt", ".onnx", ".safetensors")
    violations: list[str] = []
    for rel in (line for line in tracked_text.splitlines() if line):
        if rel.casefold().endswith(suffixes):
            violations.append(rel)
    if violations:
        fail("tracked model or runtime artifact: " + ", ".join(sorted(violations)))
    else:
        ok("no tracked model, cache, database, or source-image artifact")


def archival_n0_notice() -> int:
    """Retain the historical verifier mode as an explicit non-passing result."""
    print("N0_ARCHIVAL_SUPERSEDED")
    print("The original N0-only verifier cannot validate the governed current-stage tree.")
    print("Use `python tools/verify_handoff.py` for the current N2B1P integrity gate.")
    return 8


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--archival-n0":
        return archival_n0_notice()
    if len(sys.argv) != 1:
        print("usage: verify_handoff.py [--archival-n0]", file=sys.stderr)
        return 2
    check_required_files()
    check_current_authorization()
    check_bounded_n2b2_review_contract()
    check_baselines()
    check_manifest()
    check_sensitive_paths()
    print("NPI current-stage handoff verification")
    print("======================================")
    for message in passes:
        print(f"PASS: {message}")
    for message in errors:
        print(f"FAIL: {message}")
    print(f"Summary: {len(passes)} pass, {len(errors)} fail")
    if errors:
        print("HANDOFF_INVALID: current-stage work must not continue")
        return 1
    if git("rev-parse", "HEAD") == (0, N2B1P_SHA):
        print(
            "HANDOFF_VALID: N2B1P local-research cache promotion only; "
            "inference and photos remain locked"
        )
    else:
        print(
            "HANDOFF_VALID: bounded N2B2 S20 artifact-integrity review candidate; "
            "production N2B2 remains LOCKED"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
