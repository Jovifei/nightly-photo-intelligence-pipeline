"""Stick figures are constructed diagrams, not photo overlays."""

import re

from nightly_photo_intelligence_pipeline.direction.stick_figure import (
    horizontal_slot,
    render_stick_figure_svg,
)


def _point(x: float, y: float, score: float = 0.9) -> dict[str, float]:
    return {"x": x, "y": y, "score": score}


def _person(x_shift: float) -> dict[str, object]:
    blank = _point(0.0, 0.0, 0.0)
    keypoints = [blank for _ in range(17)]

    def put(index: int, x: float, y: float, score: float = 0.9) -> None:
        keypoints[index] = _point(x + x_shift, y, score)

    put(0, 100, 40)
    put(5, 80, 90)
    put(6, 120, 90)
    put(7, 70, 150)
    put(8, 140, 140)
    put(9, 60, 200)
    put(10, 155, 190)
    put(11, 88, 200)
    put(12, 116, 200)
    put(13, 86, 280)
    put(14, 122, 270)
    put(15, 84, 360)
    put(16, 128, 360)
    return {
        "box": {
            "x_min": 50 + x_shift,
            "y_min": 20,
            "x_max": 170 + x_shift,
            "y_max": 380,
        },
        "keypoints": keypoints,
    }


def test_center_figure_has_head_torso_and_limbs() -> None:
    svg = render_stick_figure_svg([_person(90)], 400, 400, case_id="img-03-eb894fac")
    assert 'data-slot="center"' in svg
    assert "<circle " in svg
    assert "<polyline " in svg
    assert "<line " in svg
    assert "img-03-eb894fac" in svg
    assert "不是照片叠图" in svg
    assert ".jpg" not in svg
    assert "score" not in svg


def test_two_people_keep_left_and_right_order() -> None:
    svg = render_stick_figure_svg(
        [_person(220), _person(0)],
        400,
        400,
        case_id="img-02-dbeabf45",
    )
    assert 'data-slot="left"' in svg
    assert 'data-slot="right"' in svg
    left = svg.index('data-slot="left"')
    right = svg.index('data-slot="right"')
    left_cx = svg.index("<circle ", left)
    right_cx = svg.index("<circle ", right)
    assert left_cx < right_cx
    assert svg.count("<circle ") == 2


def test_no_people_does_not_invent_a_body() -> None:
    svg = render_stick_figure_svg([], 320, 240, case_id="img-08-083872b5")
    assert "<circle " not in svg
    assert "<polyline " not in svg
    assert "不编造姿势" in svg


def test_hidden_joints_are_omitted() -> None:
    person = _person(90)
    keypoints = person["keypoints"]
    assert isinstance(keypoints, list)
    for index in (7, 9):
        keypoints[index] = _point(1.0, 1.0, 0.0)
    svg = render_stick_figure_svg([person], 400, 500, case_id="img-10-2c3a4e51")
    assert 'points="1.0,1.0' not in svg
    assert "<circle " in svg


def test_horizontal_slot_thirds() -> None:
    assert horizontal_slot(10, 300) == "left"
    assert horizontal_slot(150, 300) == "center"
    assert horizontal_slot(250, 300) == "right"


def _numbers_in_geometry(svg: str) -> list[float]:
    numbers: list[float] = []
    for group in re.findall('points="([^"]+)"', svg):
        for pair in group.split():
            x_text, y_text = pair.split(",")
            numbers.append(float(x_text))
            numbers.append(float(y_text))
    for name in ("cx", "cy", "x1", "y1", "x2", "y2"):
        for value in re.findall(name + '="([^"]+)"', svg):
            numbers.append(float(value))
    return numbers


def test_edge_person_stays_inside_the_frame() -> None:
    person = _person(0.0)
    person["box"] = {"x_min": 0.0, "y_min": 0.0, "x_max": 8.0, "y_max": 40.0}
    svg = render_stick_figure_svg([person], 1000, 800, case_id="img-09-f90b495c")
    numbers = _numbers_in_geometry(svg)
    assert numbers
    assert all(0.0 <= value <= 720.0 for value in numbers)
    assert 'data-slot="left"' in svg
