"""Label Studio protocol tests; synthetic evaluation JSON and explicit preview URIs."""
from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from nightly_photo_intelligence_pipeline.real20 import review_exchange as bridge


def example() -> tuple[bytes, dict[str, Any]]:
    assets, previews = [], {}
    for index, case_id in enumerate(bridge.CASE_IDS, 1):
        if index == 20:
            assets.append({"case_id": case_id, "action": "REFERENCE_ONLY", "duplicate_of": "real20-019"})
            continue
        image_sha = f"{index:064x}"
        facts = {"schema_version": "1.2", "case_id": case_id, "image_sha256": image_sha,
                 "person_count": 1, "fact_ids": ["fact-person-count"]}
        facts["fact_digest"] = bridge.sha(bridge.canonical(facts)[:-1])
        assets.append({"case_id": case_id, "action": "INFER_ONCE", "source_sha256": image_sha,
                       "facts": facts, "exif": {}, "interpretation": {"advice": "Synthetic advice only"}})
        previews[case_id] = {"image_url": f"/data/local-files/?d=real20-previews/{case_id}.jpg", "source_sha256": image_sha}
    result = {"schema_version": "npi-real20-evaluation-v1", "status": "REAL20_COMPLETE",
              "candidate_commit": "a" * 40, "review_decision": "PENDING_HUMAN_REVIEW",
              "sqlite_write": False, "app_write": False, "production_bundle": False, "assets": assets}
    return bridge.canonical(result), previews


def tasks() -> list[dict[str, Any]]:
    data, previews = example()
    return bridge.export_tasks(data, expected_sha256=bridge.sha(data), previews=previews)


def annotated(original: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = copy.deepcopy(original)
    for task in output:
        task["annotations"] = [{"id": f"annotation-{task['id']}", "task": task["id"],
                                "completed_by": 7, "was_cancelled": False,
                                "result": [{"from_name": "decision", "to_name": "photo", "type": "choices",
                                            "value": {"choices": ["ACCEPT"]}}]}]
    return output


def import_review(exported: object, original: list[dict[str, Any]]) -> dict[str, Any]:
    return bridge.import_annotations(
        exported, original_tasks_bytes=bridge.canonical(original),
    )


def test_export_is_deterministic_and_has_no_approval() -> None:
    data, previews = example()
    one = bridge.export_tasks(data, expected_sha256=bridge.sha(data), previews=previews)
    two = bridge.export_tasks(data, expected_sha256=bridge.sha(data), previews=previews)
    assert bridge.canonical(one) == bridge.canonical(two)
    assert len(one) == 20 and all(not task["annotations"] for task in one)
    assert one[-1]["data"]["duplicate_of"] == "real20-019"
    assert one[-1]["data"]["image"] == one[-2]["data"]["image"]
    assert all(result["from_name"] != "decision" for task in one for prediction in task["predictions"] for result in prediction["result"])


def test_roundtrip_records_human_choices_but_never_owner_approval() -> None:
    original = tasks()
    result = import_review(annotated(original), original)
    assert result["review_count"] == 20 and not result["blockers"]
    assert result["status"] == "HUMAN_REVIEW_RECORDED_PENDING_OWNER"
    assert result["records"][0]["annotation_id"] == "annotation-1"
    assert not result["execution_authorized"] and not result["production_bundle_created"]
    assert all(not row["owner_approved"] and not row["bundle_eligible"] for row in result["records"])


def test_predictions_are_not_human_reviews() -> None:
    original = tasks()
    result = import_review(original, original)
    assert result["review_count"] == 0 and len(result["blockers"]) == 20


def test_cancelled_annotation_is_not_accepted() -> None:
    original = tasks()
    output = annotated(original)
    output[0]["annotations"][0]["was_cancelled"] = True
    result = import_review(output, original)
    assert result["review_count"] == 19 and result["status"] == "HUMAN_REVIEW_INCOMPLETE"


def test_multiple_annotations_require_resolution() -> None:
    original = tasks()
    output = annotated(original)
    output[0]["annotations"] *= 2
    assert import_review(output, original)["review_count"] == 19


def test_annotation_task_pointer_must_match_exported_task() -> None:
    original = tasks()
    output = annotated(original)
    output[0]["annotations"][0]["task"] = output[1]["id"]
    with pytest.raises(bridge.ReviewExchangeError, match="ANNOTATION_TASK_MISMATCH"):
        import_review(output, original)


def test_standard_export_uses_containing_task_when_pointer_is_absent() -> None:
    original = tasks()
    output = annotated(original)
    for task in output:
        task["annotations"][0].pop("task")
    assert import_review(output, original)["review_count"] == 20


def test_duplicate_exported_task_ids_are_rejected() -> None:
    original = tasks()
    output = annotated(original)
    output[1]["id"] = output[0]["id"]
    with pytest.raises(bridge.ReviewExchangeError, match="TASK_ID"):
        import_review(output, original)


def test_server_reassigned_task_id_keeps_original_case_binding() -> None:
    original = tasks()
    output = annotated(original)
    replacement_id = 999
    output[0]["id"] = replacement_id
    output[0]["annotations"][0]["task"] = replacement_id
    result = import_review(output, original)
    assert result["records"][0]["case_id"] == "real20-001"
    assert result["records"][0]["annotation_id"] == "annotation-1"


@pytest.mark.parametrize(
    ("field_name", "field_type", "bad_value"),
    [
        ("decision", "choices", []),
        ("issues", "choices", None),
        ("revision", "textarea", ["not-an-object"]),
        ("notes", "textarea", "not-an-object"),
    ],
)
def test_non_object_annotation_value_is_stably_rejected(
    field_name: str, field_type: str, bad_value: Any
) -> None:
    original = tasks()
    output = annotated(original)
    if field_name == "decision":
        output[0]["annotations"][0]["result"][0]["value"] = bad_value
    else:
        output[0]["annotations"][0]["result"].append(
            {"from_name": field_name, "to_name": "photo", "type": field_type, "value": bad_value}
        )
    with pytest.raises(bridge.ReviewExchangeError, match="ANNOTATION_VALUE_INVALID"):
        import_review(output, original)


def test_cli_reports_exact_original_task_bytes_sha(tmp_path: Path) -> None:
    original = tasks()
    raw_tasks = json.dumps(original, ensure_ascii=False, indent=2).encode("utf-8")
    original_path = tmp_path / "original-tasks.json"
    original_path.write_bytes(raw_tasks)
    annotations_path = tmp_path / "annotations.json"
    annotations_path.write_bytes(bridge.canonical(annotated(original)))
    output_path = tmp_path / "review.json"
    source = tmp_path / "unopened-source-boundary"

    result = bridge.main(
        [
            "import",
            "--annotations",
            str(annotations_path),
            "--original-tasks",
            str(original_path),
            "--original-tasks-sha256",
            bridge.sha(raw_tasks),
            "--source-root",
            str(source),
            "--out",
            str(output_path),
        ]
    )

    assert result == 0
    imported = bridge.parse(output_path.read_bytes())
    assert imported["original_tasks_sha256"] == bridge.sha(raw_tasks)
    assert imported["original_tasks_sha256"] != bridge.sha(bridge.canonical(original))


@pytest.mark.parametrize("key", ["facts_text", "advice_text", "image", "npi_binding"])
def test_modified_original_data_rejected(key: str) -> None:
    original = tasks()
    output = annotated(original)
    output[0]["data"][key] = "changed"
    with pytest.raises(bridge.ReviewExchangeError, match="ORIGINAL_DATA_CHANGED"):
        import_review(output, original)


def test_changed_prediction_rejected() -> None:
    original = tasks()
    output = annotated(original)
    output[0]["predictions"] = []
    with pytest.raises(bridge.ReviewExchangeError, match="ORIGINAL_DATA_CHANGED"):
        import_review(output, original)


@pytest.mark.parametrize("url", ["https://remote.invalid/photo.jpg", "file://" + "/private/photo.jpg",
                                "/data/local-files/?d=../photo.jpg", "/data/local-files/?d=%2fprivate.jpg",
                                "/data/local-files/?d=real20-previews/real20-001.jpg&d=x",
                                "/data/local-files/?d=real20-previews/real20-001.jpg:stream",
                                "/data/local-files/?d=real20-previews/real20-002.jpg"])
def test_only_explicit_local_preview_mapping(url: str) -> None:
    data, previews = example()
    previews["real20-001"]["image_url"] = url
    with pytest.raises(ValueError):
        bridge.export_tasks(data, expected_sha256=bridge.sha(data), previews=previews)


def test_wrong_preview_image_binding_denied() -> None:
    data, previews = example()
    previews["real20-001"]["source_sha256"] = "0" * 64
    with pytest.raises(bridge.ReviewExchangeError, match="PREVIEW_BINDING"):
        bridge.export_tasks(data, expected_sha256=bridge.sha(data), previews=previews)


def test_fact_tampering_rejected_even_with_new_result_hash() -> None:
    data, previews = example()
    value = json.loads(data)
    value["assets"][0]["facts"]["person_count"] = 99
    data = bridge.canonical(value)
    with pytest.raises(bridge.ReviewExchangeError, match="FACT_DIGEST"):
        bridge.export_tasks(data, expected_sha256=bridge.sha(data), previews=previews)


def test_wrong_evaluation_hash_rejected() -> None:
    data, previews = example()
    with pytest.raises(bridge.ReviewExchangeError, match="HASH_MISMATCH"):
        bridge.export_tasks(data, expected_sha256="0" * 64, previews=previews)


def test_edit_requires_reason_and_reviewer_not_bool() -> None:
    original = tasks()
    output = annotated(original)
    output[0]["annotations"][0]["result"][0]["value"]["choices"] = ["EDIT"]
    with pytest.raises(bridge.ReviewExchangeError, match="EDIT_REASON"):
        import_review(output, original)
    output = annotated(original)
    output[0]["annotations"][0]["completed_by"] = True
    with pytest.raises(bridge.ReviewExchangeError, match="REVIEWER_ID"):
        import_review(output, original)


@pytest.mark.parametrize("data", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b'{}\\n'])
def test_strict_input_json(data: bytes) -> None:
    with pytest.raises(ValueError):
        bridge.parse(data)


def test_ui_control_names_match_exported_results() -> None:
    root = Path(__file__).resolve().parents[1]
    path = root / "integrations/label_studio/review_config.xml"
    if not path.is_file():
        path = Path(bridge.__file__).resolve().parents[3] / "integrations/label_studio/review_config.xml"
    tree = ET.parse(path)
    controls = {element.attrib["name"]: element for element in tree.iter() if "name" in element.attrib}
    assert set(controls) == {"photo", "facts", "advice", "decision", "issues", "revision", "notes"}
    assert controls["decision"].attrib["toName"] == "photo"
    assert {c.attrib["value"] for c in controls["decision"]} == bridge.DECISIONS
    for task in tasks():
        for result in task["predictions"][0]["result"]:
            assert result["from_name"] in controls and result["to_name"] in controls


def test_server_prediction_metadata_is_not_a_model_edit() -> None:
    original = tasks()
    output = annotated(original)
    for task in output:
        task["predictions"][0].update(id=990, created_at="2026-09-23T00:00:00Z", task=task["id"])
    assert import_review(output, original)["review_count"] == 20


def test_cli_export_import_and_source_boundary(tmp_path: Path) -> None:
    data, previews = example()
    source = tmp_path / "originals-must-not-exist"
    evaluation = tmp_path / "evaluation.json"
    mapping = tmp_path / "mapping.json"
    output = tmp_path / "tasks.json"
    evaluation.write_bytes(data)
    mapping.write_bytes(bridge.canonical(previews))
    before = {p.name: p.read_bytes() for p in (evaluation, mapping)}
    argv = ["export", "--evaluation", str(evaluation), "--evaluation-sha256", bridge.sha(data),
            "--preview-map", str(mapping), "--source-root", str(source), "--out", str(output)]
    assert bridge.main(argv) == 0
    assert not source.exists()
    original = bridge.parse(output.read_bytes())
    annotation_file = tmp_path / "annotations.json"
    annotation_file.write_bytes(bridge.canonical(annotated(original)))
    result = tmp_path / "review.json"
    assert bridge.main(["import", "--annotations", str(annotation_file),
                        "--original-tasks", str(output), "--original-tasks-sha256", bridge.sha(output.read_bytes()),
                        "--source-root", str(source), "--out", str(result)]) == 0
    assert bridge.parse(result.read_bytes())["review_count"] == 20
    assert not bridge.parse(result.read_bytes())["production_bundle_created"]
    original_output = output.read_bytes()
    assert bridge.main(argv) == 1
    assert output.read_bytes() == original_output
    assert {p.name: p.read_bytes() for p in (evaluation, mapping)} == before
    # Source exclusion checked lexically BEFORE reading controls or writing files.
    blocked = argv.copy()
    blocked[-1] = str(source / "bad.json")
    assert bridge.main(blocked) == 1
    assert not source.exists()
