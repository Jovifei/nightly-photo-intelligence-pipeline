"""Model-free bbox-union empty-area proxy; NOT an aesthetic negative-space measure.

Coordinates are pixel edge coordinates. Directional ratios use their own half
frame as denominator. Thus (left + right) / 2 == total, and likewise for top
and bottom, up to rounding. Boxes are clipped and overlaps counted once.
The new v1.2 repair producer uses this proxy; frozen historical N2B2 code is unchanged.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

METHOD = "bbox-union-half-frame-empty-area-v1"
MAX_BOXES = 256
Box = tuple[float, float, float, float]


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError("NPI_GEOMETRY_INVALID_NUMBER")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError("NPI_GEOMETRY_INVALID_NUMBER") from None
    if not math.isfinite(number):
        raise ValueError("NPI_GEOMETRY_NONFINITE")
    return number


def _union_area(boxes: list[Box]) -> float:
    """Integrate the merged y intervals in each x slab, without rasterization."""
    xs = sorted({x for box in boxes for x in (box[0], box[2])})
    slabs: list[float] = []
    for left, right in zip(xs, xs[1:], strict=False):
        intervals = sorted((y0, y1) for x0, y0, x1, y1 in boxes if x0 < right and x1 > left)
        lengths: list[float] = []
        if intervals:
            start, end = intervals[0]
            for low, high in intervals[1:]:
                if low > end:
                    lengths.append(end - start)
                    start, end = low, high
                else:
                    end = max(end, high)
            lengths.append(end - start)
        slabs.append((right - left) * math.fsum(lengths))
    return math.fsum(slabs)


def measure_bbox_empty_area(
    boxes: Sequence[Mapping[str, object]], width: object, height: object
) -> dict[str, object]:
    """Return normalized empty-area ratios and explicit proxy provenance.

    Invalid/inverted/nonfinite boxes fail rather than fabricating a zero value.
    Degenerate and entirely off-frame boxes occupy no area. The bounded input
    size prevents accidental quadratic work on untrusted detection payloads.
    """
    w, h = _number(width), _number(height)
    if w <= 0 or h <= 0 or not math.isfinite(w * h):
        raise ValueError("NPI_GEOMETRY_INVALID_FRAME")
    if len(boxes) > MAX_BOXES:
        raise ValueError("NPI_GEOMETRY_BOX_LIMIT")
    normalized: list[Box] = []
    for box in boxes:
        try:
            x0, y0, x1, y1 = (_number(box[key]) for key in ("x_min", "y_min", "x_max", "y_max"))
        except (KeyError, TypeError):
            raise ValueError("NPI_GEOMETRY_INVALID_BOX") from None
        if x0 > x1 or y0 > y1:
            raise ValueError("NPI_GEOMETRY_INVERTED_BOX")
        x0, x1 = max(0.0, min(w, x0)), max(0.0, min(w, x1))
        y0, y1 = max(0.0, min(h, y0)), max(0.0, min(h, y1))
        if x0 < x1 and y0 < y1:
            normalized.append((x0 / w, y0 / h, x1 / w, y1 / h))

    def empty(region: Box) -> float:
        rx0, ry0, rx1, ry1 = region
        clipped = [
            (max(x0, rx0), max(y0, ry0), min(x1, rx1), min(y1, ry1))
            for x0, y0, x1, y1 in normalized
        ]
        occupied = _union_area([b for b in clipped if b[0] < b[2] and b[1] < b[3]])
        area = (rx1 - rx0) * (ry1 - ry0)
        return round(max(0.0, min(1.0, 1.0 - occupied / area)), 6)

    return {
        "method": METHOD,
        "measurement_kind": "BBOX_EMPTY_AREA_PROXY_NOT_AESTHETIC_NEGATIVE_SPACE",
        "coordinate_system": "pixel_edges",
        "directional_denominator": "corresponding_half_frame_area",
        "left_ratio": empty((0.0, 0.0, 0.5, 1.0)),
        "right_ratio": empty((0.5, 0.0, 1.0, 1.0)),
        "top_ratio": empty((0.0, 0.0, 1.0, 0.5)),
        "bottom_ratio": empty((0.0, 0.5, 1.0, 1.0)),
        "total_negative_ratio": empty((0.0, 0.0, 1.0, 1.0)),
    }
