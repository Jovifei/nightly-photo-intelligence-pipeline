"""Construct a body diagram from pose keypoints.

Each figure is a head, a torso, arms, and legs. It is not drawn on the
photograph. When several people are present they share one frame, and each
figure sits left, center, or right according to that person's place in the image.
"""

from __future__ import annotations

import html
import math
from collections.abc import Mapping, Sequence
from typing import Any

_VISIBLE = 0.35

_NOSE = 0
_LEFT_EYE = 1
_RIGHT_EYE = 2
_LEFT_EAR = 3
_RIGHT_EAR = 4
_LEFT_SHOULDER = 5
_RIGHT_SHOULDER = 6
_LEFT_ELBOW = 7
_RIGHT_ELBOW = 8
_LEFT_WRIST = 9
_RIGHT_WRIST = 10
_LEFT_HIP = 11
_RIGHT_HIP = 12
_LEFT_KNEE = 13
_RIGHT_KNEE = 14
_LEFT_ANKLE = 15
_RIGHT_ANKLE = 16

# Arms, legs, then the shoulder and hip bars that close the torso.
_CHAINS: tuple[tuple[int, ...], ...] = (
    (_LEFT_SHOULDER, _LEFT_ELBOW, _LEFT_WRIST),
    (_RIGHT_SHOULDER, _RIGHT_ELBOW, _RIGHT_WRIST),
    (_LEFT_HIP, _LEFT_KNEE, _LEFT_ANKLE),
    (_RIGHT_HIP, _RIGHT_KNEE, _RIGHT_ANKLE),
    (_LEFT_SHOULDER, _RIGHT_SHOULDER),
    (_LEFT_HIP, _RIGHT_HIP),
)

_SLOT_TEXT = {"left": "左", "center": "中", "right": "右"}
_PALETTE = ("#1f3a5f", "#8a3d2f", "#2f5d3a", "#5c3d78")

_FRAME_W = 720.0
_FRAME_H = 560.0
_MARGIN_X = 28.0
_TOP = 52.0
_FIG_H = 420.0

_Point = tuple[float, float]
_Indexed = dict[int, _Point]
_Segment = tuple[_Point, _Point]


def horizontal_slot(anchor_x: float, image_width: float) -> str:
    """Return ``left``, ``center``, or ``right`` for a horizontal image position."""
    if not math.isfinite(anchor_x) or image_width <= 0:
        return "center"
    ratio = anchor_x / image_width
    if ratio < 1.0 / 3.0:
        return "left"
    if ratio < 2.0 / 3.0:
        return "center"
    return "right"


def render_stick_figure_svg(
    people: Sequence[Mapping[str, Any]],
    image_width: float,
    image_height: float,
    *,
    case_id: str = "",
) -> str:
    """Return one SVG frame of constructed stick figures.

    ``people`` entries may carry ``keypoints`` (COCO order, each point
    ``x`` / ``y`` / ``score``) and an optional ``box`` with ``x_min`` and
    ``x_max``. Missing joints are left out; they are not guessed.
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image size must be positive")
    title = _safe_label(case_id)
    heading = f"{title} 姿态示意图" if title else "姿态示意图"
    ranked = sorted(
        ((_anchor_x(person, image_width), person) for person in people),
        key=lambda item: item[0],
    )
    body = _empty_note() if not ranked else _draw_people(ranked, image_width)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {_num(_FRAME_W)} {_num(_FRAME_H)}" '
        f'width="{_num(_FRAME_W)}" height="{_num(_FRAME_H)}" role="img">\n'
        f"  <title>{_xml(heading)}</title>\n"
        "  <desc>构造的简笔身体（头、躯干、手臂、腿），不是照片叠图。</desc>\n"
        '  <rect width="100%" height="100%" fill="#fbf8f3"/>\n'
        f"{body}"
        "</svg>\n"
    )


def _draw_people(ranked: list[tuple[float, Mapping[str, Any]]], image_width: float) -> str:
    anchors = [anchor for anchor, _person in ranked]
    centers = _separate_centers(anchors, image_width)
    min_sep = _min_separation(len(ranked))
    chunks: list[str] = []
    placed = zip(ranked, centers, strict=True)
    for index, ((anchor, person), center_x) in enumerate(placed):
        slot = horizontal_slot(anchor, image_width)
        color = _PALETTE[index % len(_PALETTE)]
        fig_w = _figure_width(center_x, min_sep)
        chunks.append(_person_svg(person, color, center_x, fig_w, slot, index + 1))
    return "".join(chunks)


def _person_svg(
    person: Mapping[str, Any],
    color: str,
    center_x: float,
    fig_w: float,
    slot: str,
    person_index: int,
) -> str:
    points = _index_points(_keypoint_rows(person))
    chains = _chains(points)
    extras = _spine(points)
    head = _head(points)
    cloud = [point for chain in chains for point in chain]
    cloud.extend(point for segment in extras for point in segment)
    if head is not None:
        cloud.append(head[0])
    if not cloud:
        return _unclear_slot(center_x, slot, color, person_index)
    mapper = _fit(cloud, head, center_x, fig_w)
    parts = [_segment_svg(segment, mapper, color, 7.0) for segment in extras]
    parts.extend(_chain_svg(chain, mapper, color) for chain in chains)
    if head is not None:
        parts.append(_head_svg(head, mapper, color))
    parts.append(_slot_label(center_x, slot, color))
    body = "\n".join(part for part in parts if part)
    return (
        f'  <g data-slot="{slot}" data-person="{person_index}" fill="none" '
        f'stroke="{color}" stroke-linecap="round" stroke-linejoin="round">\n'
        f"{body}\n"
        "  </g>\n"
    )


def _empty_note() -> str:
    return (
        '  <text x="360" y="280" text-anchor="middle" fill="#5c564c" '
        'font-family="sans-serif" font-size="18">'
        "没有可用的人体关键点，不编造姿势。"
        "</text>\n"
    )


def _unclear_slot(center_x: float, slot: str, color: str, person_index: int) -> str:
    label = _SLOT_TEXT[slot]
    return (
        f'  <g data-slot="{slot}" data-person="{person_index}">\n'
        f'    <text x="{_num(center_x)}" y="250" text-anchor="middle" fill="{color}" '
        'font-family="sans-serif" font-size="14">关键点不足，不编造姿势</text>\n'
        f"{_slot_label(center_x, slot, color)}\n"
        f"    <!-- {label} -->\n"
        "  </g>\n"
    )


def _slot_label(center_x: float, slot: str, color: str) -> str:
    return (
        f'    <text x="{_num(center_x)}" y="530" text-anchor="middle" fill="{color}" '
        'stroke="none" font-family="sans-serif" font-size="16">'
        f"{_SLOT_TEXT[slot]}</text>"
    )


def _chain_svg(chain: list[_Point], mapper: _Mapper, color: str) -> str:
    mapped = [mapper.map(point) for point in chain]
    if _span(mapped) < 1.5:
        return ""
    coords = " ".join(f"{_num(x)},{_num(y)}" for x, y in mapped)
    return f'    <polyline points="{coords}" stroke="{color}" stroke-width="4"/>'


def _segment_svg(segment: _Segment, mapper: _Mapper, color: str, width: float) -> str:
    start = mapper.map(segment[0])
    end = mapper.map(segment[1])
    if _distance(start, end) < 1.5:
        return ""
    return (
        f'    <line x1="{_num(start[0])}" y1="{_num(start[1])}" '
        f'x2="{_num(end[0])}" y2="{_num(end[1])}" '
        f'stroke="{color}" stroke-width="{_num(width)}"/>'
    )


def _head_svg(head: tuple[_Point, float], mapper: _Mapper, color: str) -> str:
    center = mapper.map(head[0])
    radius = max(head[1] * mapper.scale, 6.0)
    return (
        f'    <circle cx="{_num(center[0])}" cy="{_num(center[1])}" r="{_num(radius)}" '
        f'fill="#fbf8f3" stroke="{color}" stroke-width="4"/>'
    )


class _Mapper:
    def __init__(self, scale: float, origin_x: float, origin_y: float) -> None:
        self.scale = scale
        self._origin_x = origin_x
        self._origin_y = origin_y

    def map(self, point: _Point) -> _Point:
        return (point[0] * self.scale + self._origin_x, point[1] * self.scale + self._origin_y)


def _fit(
    cloud: list[_Point],
    head: tuple[_Point, float] | None,
    center_x: float,
    fig_w: float,
) -> _Mapper:
    xs = [point[0] for point in cloud]
    ys = [point[1] for point in cloud]
    if head is not None:
        (hx, hy), radius = head
        xs.extend((hx - radius, hx + radius))
        ys.extend((hy - radius, hy + radius))
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)
    pad = 12.0
    scale = min((fig_w - 2 * pad) / span_x, (_FIG_H - 2 * pad) / span_y)
    content_w = span_x * scale
    content_h = span_y * scale
    left = center_x - fig_w / 2.0
    origin_x = left + (fig_w - content_w) / 2.0 - min_x * scale
    origin_y = _TOP + (_FIG_H - content_h) / 2.0 - min_y * scale
    return _Mapper(scale, origin_x, origin_y)


def _chains(points: _Indexed) -> list[list[_Point]]:
    chains: list[list[_Point]] = []
    for indexes in _CHAINS:
        run: list[_Point] = []
        for index in indexes:
            point = points.get(index)
            if point is None:
                if len(run) >= 2:
                    chains.append(run)
                run = []
                continue
            run.append(point)
        if len(run) >= 2:
            chains.append(run)
    return chains


def _spine(points: _Indexed) -> list[_Segment]:
    segments: list[_Segment] = []
    shoulder = _pair_mid(points, _LEFT_SHOULDER, _RIGHT_SHOULDER)
    hip = _pair_mid(points, _LEFT_HIP, _RIGHT_HIP)
    head = _head(points)
    if shoulder is not None and hip is not None:
        segments.append((shoulder, hip))
    if head is not None and shoulder is not None:
        segments.append((head[0], shoulder))
    elif head is not None and hip is not None:
        segments.append((head[0], hip))
    return segments


def _head(points: _Indexed) -> tuple[_Point, float] | None:
    facial = [
        points[index]
        for index in (_NOSE, _LEFT_EYE, _RIGHT_EYE, _LEFT_EAR, _RIGHT_EAR)
        if index in points
    ]
    shoulders = [points[index] for index in (_LEFT_SHOULDER, _RIGHT_SHOULDER) if index in points]
    if facial:
        center = (_mean(facial, 0), _mean(facial, 1))
    elif len(shoulders) == 2:
        span = _distance(shoulders[0], shoulders[1])
        center = (_mean(shoulders, 0), _mean(shoulders, 1) - max(span, 8.0))
        return center, max(span * 0.42, 4.0)
    else:
        return None
    if len(shoulders) == 2:
        radius = _distance(shoulders[0], shoulders[1]) * 0.42
    elif shoulders:
        radius = _distance(center, shoulders[0]) * 0.55
    else:
        radius = 12.0
    return center, max(radius, 4.0)


def _pair_mid(points: _Indexed, left: int, right: int) -> _Point | None:
    if left not in points or right not in points:
        return None
    return (_mean([points[left], points[right]], 0), _mean([points[left], points[right]], 1))


def _mean(points: Sequence[_Point], axis: int) -> float:
    return sum(point[axis] for point in points) / len(points)


def _distance(a: _Point, b: _Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _index_points(rows: Sequence[Mapping[str, Any]]) -> _Indexed:
    indexed: _Indexed = {}
    for index, row in enumerate(rows):
        point = _visible_point(row)
        if point is not None:
            indexed[index] = point
    return indexed


def _visible_point(row: Mapping[str, Any]) -> _Point | None:
    try:
        score = float(row.get("score", 0.0))
        x = float(row["x"])
        y = float(row["y"])
    except (TypeError, ValueError, KeyError):
        return None
    if score < _VISIBLE or not math.isfinite(x) or not math.isfinite(y):
        return None
    return (x, y)


def _keypoint_rows(person: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = person.get("keypoints")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    return [row for row in raw if isinstance(row, Mapping)]


def _anchor_x(person: Mapping[str, Any], image_width: float) -> float:
    box = person.get("box")
    if isinstance(box, Mapping):
        anchor = _box_center_x(box)
        if anchor is not None:
            return anchor
    points = _index_points(_keypoint_rows(person))
    if points:
        return sum(point[0] for point in points.values()) / len(points)
    return image_width / 2.0


def _box_center_x(box: Mapping[str, Any]) -> float | None:
    try:
        left = float(box["x_min"])
        right = float(box["x_max"])
    except (TypeError, ValueError, KeyError):
        return None
    if not math.isfinite(left) or not math.isfinite(right):
        return None
    return (left + right) / 2.0


def _figure_width(center_x: float, min_sep: float) -> float:
    """Keep each figure inside the frame, including people at the edge."""
    room = 2.0 * min(center_x - 4.0, _FRAME_W - 4.0 - center_x)
    return min(200.0, min_sep * 0.88, max(room, 1.0))


def _span(points: list[_Point]) -> float:
    if len(points) < 2:
        return 0.0
    return max(_distance(points[0], point) for point in points[1:])


def _min_separation(count: int) -> float:
    drawable = _FRAME_W - 2 * _MARGIN_X
    if count <= 1:
        return drawable
    return min(180.0, drawable / count)


def _separate_centers(anchors: list[float], image_width: float) -> list[float]:
    drawable_low = _MARGIN_X
    drawable_high = _FRAME_W - _MARGIN_X
    if image_width <= 0:
        ratios = [0.5 for _anchor in anchors]
    else:
        ratios = [min(1.0, max(0.0, anchor / image_width)) for anchor in anchors]
    span = drawable_high - drawable_low
    centers = [drawable_low + ratio * span for ratio in ratios]
    return _push_apart(centers, _min_separation(len(centers)), drawable_low, drawable_high)


def _push_apart(centers: list[float], min_sep: float, low: float, high: float) -> list[float]:
    if not centers:
        return []
    ordered = sorted(centers)
    for index in range(1, len(ordered)):
        if ordered[index] - ordered[index - 1] < min_sep:
            ordered[index] = ordered[index - 1] + min_sep
    if ordered[-1] > high:
        shift = ordered[-1] - high
        ordered = [center - shift for center in ordered]
    if ordered[0] < low:
        shift = low - ordered[0]
        ordered = [center + shift for center in ordered]
    room = high - low
    needed = min_sep * (len(ordered) - 1)
    if len(ordered) > 1 and needed > room:
        step = room / (len(ordered) - 1)
        return [low + index * step for index in range(len(ordered))]
    return ordered


def _safe_label(case_id: str) -> str:
    cleaned = case_id.replace("\\", " ").replace("/", " ").replace("\n", " ").strip()
    return cleaned[:80]


def _xml(text: str) -> str:
    return html.escape(text, quote=True)


def _num(value: float) -> str:
    return f"{value:.1f}"
