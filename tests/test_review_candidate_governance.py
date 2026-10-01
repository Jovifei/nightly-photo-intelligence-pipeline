from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from tools import verify_review_candidate as review_candidate
from tools.verify_review_candidate import (
    ReviewEligibilityError,
    main,
    validate_review_candidate,
)

from nightly_photo_intelligence_pipeline.n2b1p_integrity import (
    canonical_json_bytes,
    sha256_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
REVIEW_SCOPE = "B_SOURCE_NETWORK_REACQUISITION_V1_CONTROL_PACKET_ONLY"
TASK_PATH = "tasks/phase_n2b1p_b_source_network_reacquisition_v1.yaml"
OWNER_PATH = "approvals/owner_n2b1p_b_source_network_reacquisition_v1.yaml"
RUNTIME_PATH = "approvals/n2b1p_b_source_network_runtime_configuration_v1.json"
TASK_SCHEMA_PATH = "schemas/n2b1p_b_source_network_reacquisition_v1.schema.json"
OWNER_SCHEMA_PATH = "schemas/owner_n2b1p_b_source_network_reacquisition_v1.schema.json"
RUNTIME_SCHEMA_PATH = "schemas/n2b1p_b_source_network_runtime_configuration_v1.schema.json"
BASELINE_APPROVAL_PATH = "approvals/phase_completion_N2B1P.yaml"
ALLOWED_CHANGE_CATEGORIES = [
    "task_contract",
    "owner_approval",
    "schema",
    "tests",
    "governance_tool",
    "control_plane_code",
    "manifest",
    "todo_status",
    "task_tracking",
]


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _bind_test_baseline_approval_pin(monkeypatch: pytest.MonkeyPatch, root: Path) -> None:
    approval_path = root / BASELINE_APPROVAL_PATH
    digest = hashlib.sha256(approval_path.read_bytes()).hexdigest()
    monkeypatch.setattr(review_candidate, "BASELINE_APPROVAL_SHA256", digest, raising=False)


def _write_root_manifest(root: Path, *, corrupt: bool = False) -> None:
    tracked = _git(root, "ls-files", "-z").split("\0")
    root_paths = sorted(path for path in tracked if path and path != "MANIFEST.sha256")
    root_lines = [
        f"{hashlib.sha256((root / path).read_bytes()).hexdigest()}  {path}" for path in root_paths
    ]
    if corrupt:
        root_lines[0] = f"{'0' * 64}  {root_paths[0]}"
    (root / "MANIFEST.sha256").write_text("\n".join(root_lines) + "\n", encoding="utf-8")
    _git(root, "add", "MANIFEST.sha256")


def _refresh_manifests(root: Path) -> None:
    _git(root, "add", "--all")
    tracked = _git(root, "ls-files", "-z").split("\0")
    overlay_manifest = "review_tools/MANIFEST.sha256"
    overlay_paths = sorted(
        path for path in tracked if path.startswith("review_tools/") and path != overlay_manifest
    )
    overlay_lines = [
        f"{hashlib.sha256((root / path).read_bytes()).hexdigest()}  {path}"
        for path in overlay_paths
    ]
    (root / overlay_manifest).write_text("\n".join(overlay_lines) + "\n", encoding="utf-8")
    _git(root, "add", overlay_manifest)
    _write_root_manifest(root)


def _schema_for_task() -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": [
            "phase",
            "status",
            "owner_authorized",
            "execution_status",
            "execution_authority",
            "network_policy",
            "network_download_before_external_review",
            "approval_ref",
            "runtime_configuration",
            "review_candidate",
        ],
        "properties": {
            "phase": {
                "type": "object",
                "required": ["id"],
                "properties": {"id": {"const": "N2B1P"}},
            },
            "capability": {"const": "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"},
            "status": {"const": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"},
            "owner_authorized": {"const": True},
            "execution_status": {"const": "NOT_RUN"},
            "execution_authority": {"const": "NOT_AUTHORIZED"},
            "network_policy": {"type": "object"},
            "network_download_before_external_review": {"const": False},
            "approval_ref": {"const": OWNER_PATH},
            "runtime_configuration": {"type": "object"},
            "review_candidate": {"type": "object"},
        },
    }


def _schema_for_owner() -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": [
            "status",
            "owner_authorized",
            "scope_status",
            "execution_status",
            "execution_authority",
            "network_access",
            "contract_ref",
            "runtime_configuration_ref",
            "runtime_configuration_digest",
        ],
        "properties": {
            "status": {"const": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"},
            "owner_authorized": {"const": True},
            "scope_status": {"const": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW"},
            "execution_status": {"const": "NOT_RUN"},
            "execution_authority": {"const": "NOT_AUTHORIZED"},
            "network_access": {"const": "DENY"},
            "contract_ref": {"const": TASK_PATH},
            "runtime_configuration_ref": {"const": RUNTIME_PATH},
            "runtime_configuration_digest": {"pattern": "^[0-9a-f]{64}$"},
        },
    }


def _make_candidate_repo(
    root: Path,
    *,
    corrupt_root_manifest: bool = False,
    corrupt_overlay_manifest: bool = False,
    trailing_whitespace: bool = False,
    invalid_owner_authority: bool = False,
    invalid_runtime_digest: bool = False,
    baseline_ancestor: bool = True,
) -> tuple[Path, str]:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.name", "Review Governance Test")
    _git(root, "config", "user.email", "review-governance@example.invalid")
    (root / "README.md").write_text("baseline\n", encoding="utf-8")
    (root / "review_tools" / "verify.py").parent.mkdir(parents=True, exist_ok=True)
    (root / "review_tools" / "verify.py").write_text(
        "def verify():\n    return True\n", encoding="utf-8"
    )
    _git(root, "add", "--all")
    _git(root, "commit", "-m", "immutable N2B1P baseline")
    baseline = _git(root, "rev-parse", "HEAD")

    (root / "schemas").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "PROJECT_STATE.json", root / "PROJECT_STATE.json")
    shutil.copyfile(
        ROOT / "schemas/project_state_v1_7.schema.json",
        root / "schemas/project_state_v1_7.schema.json",
    )
    project_state_sha256 = hashlib.sha256((root / "PROJECT_STATE.json").read_bytes()).hexdigest()

    approved_baseline = baseline if baseline_ancestor else "a" * 40
    baseline_approval = {
        "status": "APPROVED",
        "phase_id": "N2B1P",
        "baseline": {
            "candidate_commit": approved_baseline,
            "project_state_sha256": project_state_sha256,
            "immutable": True,
        },
    }
    baseline_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["status", "phase_id", "baseline"],
        "properties": {
            "status": {"const": "APPROVED"},
            "phase_id": {"const": "N2B1P"},
            "baseline": {
                "type": "object",
                "required": ["candidate_commit", "project_state_sha256", "immutable"],
                "properties": {
                    "candidate_commit": {"const": approved_baseline},
                    "project_state_sha256": {"const": project_state_sha256},
                    "immutable": {"const": True},
                },
            },
        },
    }
    _write_yaml(root / BASELINE_APPROVAL_PATH, baseline_approval)
    _write_json(root / "schemas/phase_completion_n2b1p_v1_0.schema.json", baseline_schema)
    _refresh_manifests(root)
    _git(root, "commit", "-m", "record immutable baseline governance")

    runtime_configuration = {
        "execution_authority": "NOT_AUTHORIZED",
        "network_access": "DENY",
        "download_before_external_review": False,
    }
    runtime_digest = sha256_bytes(canonical_json_bytes(runtime_configuration))
    if invalid_runtime_digest:
        runtime_digest = "f" * 64
    runtime_configuration["configuration_digest"] = runtime_digest
    runtime_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["configuration_digest", "execution_authority", "network_access"],
        "properties": {
            "configuration_digest": {"pattern": "^[0-9a-f]{64}$"},
            "execution_authority": {"const": "NOT_AUTHORIZED"},
            "network_access": {"const": "DENY"},
        },
    }
    owner = {
        "status": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW",
        "owner_authorized": True,
        "scope_status": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW",
        "execution_status": "NOT_RUN",
        "execution_authority": "AUTHORIZED" if invalid_owner_authority else "NOT_AUTHORIZED",
        "network_access": "DENY",
        "contract_ref": TASK_PATH,
        "runtime_configuration_ref": RUNTIME_PATH,
        "runtime_configuration_digest": runtime_digest,
    }
    task = {
        "contract_version": "1.0",
        "phase": {"id": "N2B1P", "status": "LOCKED"},
        "capability": "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1",
        "status": "OWNER_AUTHORIZED_AWAITING_EXTERNAL_REVIEW",
        "owner_authorized": True,
        "execution_status": "NOT_RUN",
        "execution_authority": "NOT_AUTHORIZED",
        "network_policy": {"access": "DENY"},
        "network_download_before_external_review": False,
        "approval_ref": OWNER_PATH,
        "runtime_configuration": {"path": RUNTIME_PATH, "configuration_digest": runtime_digest},
        "review_candidate": {
            "status": "REVIEW_CANDIDATE",
            "class": "CONTROL_PLANE_ONLY",
            "task_id": TASK_ID,
            "review_scope": REVIEW_SCOPE,
            "task_schema_ref": TASK_SCHEMA_PATH,
            "owner_approval_ref": OWNER_PATH,
            "owner_approval_schema_ref": OWNER_SCHEMA_PATH,
            "runtime_configuration_ref": RUNTIME_PATH,
            "runtime_configuration_schema_ref": RUNTIME_SCHEMA_PATH,
            "baseline_approval_ref": BASELINE_APPROVAL_PATH,
            "immutable_baseline_ref": BASELINE_APPROVAL_PATH,
            "external_exact_sha_review_required": True,
            "execution_before_review": False,
            "allowed_change_categories": list(ALLOWED_CHANGE_CATEGORIES),
        },
    }

    _write_yaml(root / BASELINE_APPROVAL_PATH, baseline_approval)
    _write_json(root / "schemas/phase_completion_n2b1p_v1_0.schema.json", baseline_schema)
    _write_json(root / TASK_SCHEMA_PATH, _schema_for_task())
    _write_json(root / OWNER_SCHEMA_PATH, _schema_for_owner())
    _write_json(root / RUNTIME_SCHEMA_PATH, runtime_schema)
    _write_yaml(root / OWNER_PATH, owner)
    _write_json(root / RUNTIME_PATH, runtime_configuration)
    _write_yaml(root / TASK_PATH, task)
    candidate_code = (
        root / "src" / "nightly_photo_intelligence_pipeline" / "n2b1p_b_source_network.py"
    )
    candidate_code.parent.mkdir(parents=True, exist_ok=True)
    source = "def candidate():\n    return True\n"
    if trailing_whitespace:
        source = "def candidate(): \n    return True\n"
    candidate_code.write_text(source, encoding="utf-8")

    _refresh_manifests(
        root,
    )
    _git(root, "commit", "-m", "review candidate")
    # Two ordinary successors demonstrate that acceptance does not depend on a
    # frozen direct-parent SHA or a fixed commit count.
    for number in range(2):
        candidate_code.write_text(
            candidate_code.read_text(encoding="utf-8") + f"# linear successor {number}\n",
            encoding="utf-8",
        )
        _refresh_manifests(root)
        _git(root, "commit", "-m", f"linear successor {number}")
    if corrupt_overlay_manifest:
        overlay_path = root / "review_tools/MANIFEST.sha256"
        rows = overlay_path.read_text(encoding="utf-8").splitlines()
        _digest, relative = rows[0].split("  ", 1)
        rows[0] = f"{'0' * 64}  {relative}"
        overlay_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        _git(root, "add", "review_tools/MANIFEST.sha256")
        _write_root_manifest(root)
        _git(root, "commit", "-m", "malformed overlay manifest")
    if corrupt_root_manifest:
        _write_root_manifest(root, corrupt=True)
        _git(root, "commit", "-m", "malformed root manifest")
    return root, baseline


def test_review_eligibility_accepts_clean_linear_candidate_without_claiming_handoff(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, baseline = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)

    validate_review_candidate(candidate_root)
    assert main(["--root", str(candidate_root)]) == 0
    captured = capsys.readouterr()

    assert _git(candidate_root, "merge-base", "--is-ancestor", baseline, "HEAD") == ""
    assert _git(candidate_root, "rev-list", "--merges", f"{baseline}..HEAD") == ""
    assert captured.out == "REVIEW_ELIGIBILITY=PASS\n"
    assert captured.err == ""
    assert not (candidate_root / "approvals/external_exact_sha_review_receipt_v1.json").exists()


@pytest.mark.parametrize(
    ("option", "message"),
    [
        ("corrupt_root_manifest", "MANIFEST.sha256"),
        ("corrupt_overlay_manifest", "review_tools/MANIFEST.sha256"),
        ("trailing_whitespace", "diff --check"),
        ("invalid_owner_authority", "owner approval"),
        ("invalid_runtime_digest", "runtime configuration digest"),
    ],
)
def test_review_eligibility_rejects_invalid_integrity_or_authority(
    tmp_path: Path, option: str, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate", **{option: True})
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)

    with pytest.raises(ReviewEligibilityError, match=message):
        validate_review_candidate(candidate_root)


def test_review_eligibility_rejects_dirty_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)
    (candidate_root / "untracked.txt").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(ReviewEligibilityError, match="clean"):
        validate_review_candidate(candidate_root)


def test_review_eligibility_rejects_non_ancestor_approved_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate", baseline_ancestor=False)
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)

    with pytest.raises(ReviewEligibilityError, match="immutable baseline is not an ancestor"):
        validate_review_candidate(candidate_root)


def test_review_eligibility_rejects_project_state_byte_drift_after_manifest_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)
    state_path = candidate_root / "PROJECT_STATE.json"
    state_path.write_bytes(b"\n" + state_path.read_bytes())
    _refresh_manifests(candidate_root)
    _git(candidate_root, "commit", "-m", "reformat project state")

    with pytest.raises(ReviewEligibilityError, match="PROJECT_STATE"):
        validate_review_candidate(candidate_root)


def test_review_eligibility_rejects_mutated_project_state_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)
    state_path = candidate_root / "PROJECT_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["authorization"]["git_remote_write"] = "AUTHORIZED"
    _write_json(state_path, state)
    _refresh_manifests(candidate_root)
    _git(candidate_root, "commit", "-m", "authorize remote writes")

    with pytest.raises(ReviewEligibilityError, match="PROJECT_STATE"):
        validate_review_candidate(candidate_root)


def test_review_eligibility_rejects_changed_baseline_approval_after_manifest_refresh(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)
    approval_path = candidate_root / BASELINE_APPROVAL_PATH
    approval = yaml.safe_load(approval_path.read_text(encoding="utf-8"))
    approval["reviewer_note"] = "changed after the immutable approval"
    _write_yaml(approval_path, approval)
    _refresh_manifests(candidate_root)
    _git(candidate_root, "commit", "-m", "change baseline approval")

    with pytest.raises(ReviewEligibilityError, match="baseline approval digest"):
        validate_review_candidate(candidate_root)


def test_review_eligibility_rejects_merge_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, baseline = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)
    _git(candidate_root, "checkout", "-b", "side")
    (candidate_root / "side.py").write_text("side = True\n", encoding="utf-8")
    _refresh_manifests(candidate_root)
    _git(candidate_root, "commit", "-m", "side change")
    _git(candidate_root, "checkout", "main")
    (candidate_root / "main.py").write_text("main = True\n", encoding="utf-8")
    _refresh_manifests(candidate_root)
    _git(candidate_root, "commit", "-m", "main change")
    _git(candidate_root, "merge", "--no-ff", "side", "-m", "merge side")

    with pytest.raises(ReviewEligibilityError, match="merge"):
        validate_review_candidate(candidate_root)

    assert _git(candidate_root, "merge-base", "--is-ancestor", baseline, "HEAD") == ""


def test_exact_sha_review_receipt_schema_binds_candidate_and_evidence() -> None:
    schema = json.loads(
        (ROOT / "schemas/external_exact_sha_review_receipt_v1.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = {
        "schema_version": "1.0",
        "receipt_type": "EXTERNAL_EXACT_SHA_REVIEW_RECEIPT_V1",
        "task_id": TASK_ID,
        "review_scope": REVIEW_SCOPE,
        "verdict": "DONE",
        "reviewed_head": "a" * 40,
        "reviewed_tree": "b" * 40,
        "immutable_baseline_commit": "c" * 40,
        "current_manifest_sha256": "d" * 64,
        "task_sha256": "e" * 64,
        "owner_approval_sha256": "f" * 64,
        "runtime_configuration_sha256": "1" * 64,
        "review_report_ref": "review_tools/NEXT_LOCAL_CODEX_PROMPT.md",
        "review_report_sha256": "2" * 64,
        "reviewed_at_utc": "2026-09-30T00:00:00Z",
    }
    validator = Draft202012Validator(schema, format_checker=FormatChecker())

    assert list(validator.iter_errors(receipt)) == []
    stale_receipt = {**receipt, "reviewed_head": "not-a-commit"}
    assert list(validator.iter_errors(stale_receipt))
    unbound_receipt = {
        key: value for key, value in receipt.items() if key != "review_report_sha256"
    }
    assert list(validator.iter_errors(unbound_receipt))


def test_review_eligibility_rejects_duplicate_yaml_members(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)
    task_path = candidate_root / TASK_PATH
    task_path.write_text(
        task_path.read_text(encoding="utf-8") + "\nowner_authorized: true\n",
        encoding="utf-8",
    )
    _refresh_manifests(candidate_root)
    _git(candidate_root, "commit", "-m", "duplicate yaml member")
    with pytest.raises(ReviewEligibilityError, match="duplicate YAML member"):
        validate_review_candidate(candidate_root)


def test_review_eligibility_rejects_unrelated_candidate_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate_root, _ = _make_candidate_repo(tmp_path / "candidate")
    _bind_test_baseline_approval_pin(monkeypatch, candidate_root)
    readme = candidate_root / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "unrelated change\n", encoding="utf-8")
    _refresh_manifests(candidate_root)
    _git(candidate_root, "commit", "-m", "unrelated path")
    with pytest.raises(ReviewEligibilityError, match="outside the declared control-packet scope"):
        validate_review_candidate(candidate_root)


def test_active_b_source_review_metadata_and_schemas_are_coherent() -> None:
    task = yaml.safe_load((ROOT / TASK_PATH).read_text(encoding="utf-8"))
    metadata = task["review_candidate"]
    assert metadata["task_id"] == TASK_ID
    assert task["phase"]["id"] == "N2B1P"
    assert task["capability"] == "N2B1P_B_SOURCE_NETWORK_REACQUISITION_V1"
    assert metadata["review_scope"] == REVIEW_SCOPE
    assert metadata["status"] == "REVIEW_CANDIDATE"
    assert metadata["baseline_approval_ref"] == BASELINE_APPROVAL_PATH
    assert metadata["class"] == "CONTROL_PLANE_ONLY"
    assert metadata["external_exact_sha_review_required"] is True
    assert metadata["execution_before_review"] is False

    for document_ref, schema_ref, yaml_document in (
        (TASK_PATH, metadata["task_schema_ref"], True),
        (OWNER_PATH, metadata["owner_approval_schema_ref"], True),
        (RUNTIME_PATH, metadata["runtime_configuration_schema_ref"], False),
    ):
        schema = json.loads((ROOT / schema_ref).read_text(encoding="utf-8"))
        path = ROOT / document_ref
        document = (
            yaml.safe_load(path.read_text(encoding="utf-8"))
            if yaml_document
            else json.loads(path.read_text(encoding="utf-8"))
        )
        assert list(Draft202012Validator(schema).iter_errors(document)) == []
