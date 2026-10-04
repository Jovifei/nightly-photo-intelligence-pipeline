"""Pose-direction bundle v1 is a producer file, not a T14 golden."""

import json
from pathlib import Path

import jsonschema
import pytest

from nightly_photo_intelligence_pipeline.direction.bundle import (
    PRODUCER_NOTE,
    SCHEMA_ID,
    SCHEMA_VERSION,
    PoseDirectionBundleError,
    build_pose_direction_bundle,
)
from nightly_photo_intelligence_pipeline.direction.stick_figure import render_stick_figure_svg

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "pose_direction_bundle_v1.schema.json"
SPOKEN = (
    "站在画面中间，侧窗的光落在脸上。左臂微弯，右手自然下垂，眼睛看向镜头左侧，穿浅色衬衫。"
    "因为留白，这张照片才成立。"
)


def _point(x: float, y: float, score: float = 0.9) -> dict[str, float]:
    return {"x": x, "y": y, "score": score}


def _person() -> dict[str, object]:
    keypoints = [_point(0.0, 0.0, 0.0) for _ in range(17)]
    keypoints[0] = _point(100, 40)
    keypoints[5] = _point(80, 90)
    keypoints[6] = _point(120, 90)
    keypoints[7] = _point(70, 150)
    keypoints[8] = _point(140, 140)
    keypoints[9] = _point(60, 200)
    keypoints[10] = _point(155, 190)
    keypoints[11] = _point(88, 200)
    keypoints[12] = _point(116, 200)
    keypoints[13] = _point(86, 280)
    keypoints[14] = _point(122, 270)
    keypoints[15] = _point(84, 360)
    keypoints[16] = _point(128, 360)
    return {
        "box": {"x_min": 50, "y_min": 20, "x_max": 170, "y_max": 380},
        "keypoints": keypoints,
    }


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "img-04-aabebf45",
        "spoken_direction": SPOKEN,
        "people": [_person()],
        "image_width": 400,
        "image_height": 400,
    }
    record.update(overrides)
    return record


def _schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_keypoints_become_one_inline_figure() -> None:
    bundle = build_pose_direction_bundle([_record()])
    jsonschema.validate(bundle, _schema())
    assert bundle["schema_id"] == SCHEMA_ID
    assert bundle["schema_version"] == SCHEMA_VERSION
    assert bundle["authority"] is False
    assert bundle["producer_note"] == PRODUCER_NOTE
    assert "ready_for_t14" not in bundle
    item = bundle["items"][0]
    assert item["id"] == "img-04-aabebf45"
    assert item["spoken_direction"] == SPOKEN
    assert "why_it_works" not in item
    svg = item["stick_figure"]["svg"]
    assert "<circle " in svg
    assert "img-04-aabebf45" in svg
    assert ".jpg" not in svg
    assert "F:" not in svg


def test_existing_svg_and_short_why_fields() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><line x1="1" y1="1" x2="4" y2="8"/></svg>'
    bundle = build_pose_direction_bundle(
        [
            _record(
                people=None,
                svg=svg,
                why_it_works={"composition": "人在画面中间", "light": "侧光落在脸上"},
            )
        ]
    )
    jsonschema.validate(bundle, _schema())
    item = bundle["items"][0]
    assert item["stick_figure"]["svg"].startswith("<svg")
    assert item["why_it_works"] == {"composition": "人在画面中间", "light": "侧光落在脸上"}
    assert "gaze" not in item["why_it_works"]
    assert "clothing" not in item["why_it_works"]


def test_svg_file_is_only_a_relative_name() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><polyline points="1,1 2,3"/></svg>'
    bundle = build_pose_direction_bundle([_record(svg=svg)], figure="svg_file")
    jsonschema.validate(bundle, _schema())
    dumped = json.dumps(bundle, ensure_ascii=False)
    assert bundle["items"][0]["stick_figure"] == {"svg_file": "img-04-aabebf45.svg"}
    assert "<polyline" not in dumped
    assert "\\" not in bundle["items"][0]["stick_figure"]["svg_file"]


def test_missing_spoken_line_fails_closed() -> None:
    with pytest.raises(PoseDirectionBundleError, match="spoken"):
        build_pose_direction_bundle([_record(spoken_direction="  ")])


def test_missing_figure_fails_closed() -> None:
    with pytest.raises(PoseDirectionBundleError, match="figure"):
        build_pose_direction_bundle([_record(people=None)])
    empty = render_stick_figure_svg([], 320, 240, case_id="img-08-083872b5")
    with pytest.raises(PoseDirectionBundleError, match="figure"):
        build_pose_direction_bundle([_record(id="img-08-083872b5", people=None, svg=empty)])


def test_private_filename_and_internal_field_are_rejected() -> None:
    with pytest.raises(PoseDirectionBundleError):
        build_pose_direction_bundle([_record(id="photo.jpg")])
    with pytest.raises(PoseDirectionBundleError):
        build_pose_direction_bundle([_record(id=r"F:\npi_g1_source_ro\a.jpg")])
    with pytest.raises(PoseDirectionBundleError, match="internal field"):
        build_pose_direction_bundle([_record(spoken_direction=SPOKEN + " pose_score")])
    with pytest.raises(PoseDirectionBundleError, match="path or photo"):
        build_pose_direction_bundle([_record(spoken_direction=SPOKEN + " see shot.jpg")])


def test_duplicate_id_and_unknown_why_field_fail() -> None:
    with pytest.raises(PoseDirectionBundleError, match="duplicate"):
        build_pose_direction_bundle([_record(), _record(id="img-04-aabebf45")])
    with pytest.raises(PoseDirectionBundleError, match="unknown why"):
        build_pose_direction_bundle([_record(why_it_works={"exif": "dump"})])
