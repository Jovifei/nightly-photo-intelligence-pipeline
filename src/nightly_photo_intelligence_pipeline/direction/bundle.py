"""Versioned producer bundle: one spoken pose direction and one stick figure.

This is not Photo Intelligence Bundle v1, not the synthetic PKB1 fixture, and
not a T14 golden vector.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from nightly_photo_intelligence_pipeline.direction.spoken import internal_field_name
from nightly_photo_intelligence_pipeline.direction.stick_figure import render_stick_figure_svg

SCHEMA_ID = "pose-direction-bundle"
SCHEMA_VERSION = "1"
PRODUCER_NOTE = (
    "Authority is false. This file is a producer output the phone app can read later. "
    "It is not a T14 golden vector, not PKB1, and not a production unlock. "
    "The phone app tap screen is still unbuilt. "
    "It is not Photo Intelligence Bundle v1."
)
WHY_FIELDS = ("composition", "light", "gaze", "clothing")
_ID_RE = re.compile(r"^img-[0-9]{2}-[0-9a-f]{8}$")
_SVG_FILE_RE = re.compile(r"^[A-Za-z0-9._-]+\.svg$")
_FIGURE_MARKERS = ("<circle ", "<polyline ", "<line ")


class PoseDirectionBundleError(ValueError):
    """The record cannot become one pose-direction item."""


def build_pose_direction_bundle(
    records: Sequence[Mapping[str, Any]],
    *,
    figure: str = "svg",
) -> dict[str, Any]:
    """Build a pose-direction bundle from in-memory records.

    Each record needs ``id``, ``spoken_direction``, and either ``svg`` or
    ``people`` plus ``image_width`` and ``image_height``. ``figure`` is
    ``svg`` (markup in the item) or ``svg_file`` (a relative name only).
    A missing spoken line or a missing drawn figure fails closed.
    """

    if figure not in {"svg", "svg_file"}:
        raise PoseDirectionBundleError("figure must be 'svg' or 'svg_file'")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise PoseDirectionBundleError("records must be a sequence")
    if len(records) == 0:
        raise PoseDirectionBundleError("bundle has no items")
    seen: set[str] = set()
    items = [_item(record, figure=figure, seen=seen) for record in records]
    return {
        "schema_id": SCHEMA_ID,
        "schema_version": SCHEMA_VERSION,
        "authority": False,
        "producer_note": PRODUCER_NOTE,
        "items": items,
    }


def _item(record: Mapping[str, Any], *, figure: str, seen: set[str]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise PoseDirectionBundleError("item is not a record")
    case_id = _case_id(record.get("id"))
    if case_id in seen:
        raise PoseDirectionBundleError(f"duplicate id {case_id}")
    seen.add(case_id)
    spoken = _spoken(record.get("spoken_direction"), case_id)
    svg = _figure_svg(record, case_id)
    item: dict[str, Any] = {
        "id": case_id,
        "spoken_direction": spoken,
        "stick_figure": _stick_figure(svg, case_id, figure),
    }
    why = _why(record.get("why_it_works"), case_id)
    if why is not None:
        item["why_it_works"] = why
    return item


def _case_id(value: Any) -> str:
    if not isinstance(value, str) or _ID_RE.fullmatch(value) is None:
        raise PoseDirectionBundleError("id must be a hash id like img-04-aabebf45")
    return value


def _spoken(value: Any, case_id: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PoseDirectionBundleError(f"{case_id}: item lacks a spoken line")
    text = value.strip()
    if _leaks(text):
        raise PoseDirectionBundleError(f"{case_id}: spoken line contains a path or photo name")
    found = internal_field_name(text)
    if found is not None:
        raise PoseDirectionBundleError(f"{case_id}: spoken line contains internal field {found}")
    return text


def _figure_svg(record: Mapping[str, Any], case_id: str) -> str:
    raw_svg = record.get("svg")
    if raw_svg is not None:
        if not isinstance(raw_svg, str) or not raw_svg.strip():
            raise PoseDirectionBundleError(f"{case_id}: item lacks a figure")
        svg = raw_svg.strip()
    else:
        svg = _render(record, case_id)
    if not _svg_has_figure(svg):
        raise PoseDirectionBundleError(f"{case_id}: item lacks a figure")
    if _leaks(svg):
        raise PoseDirectionBundleError(f"{case_id}: stick figure contains a path or photo name")
    return svg if svg.endswith("\n") else svg + "\n"


def _render(record: Mapping[str, Any], case_id: str) -> str:
    people = record.get("people")
    width = record.get("image_width")
    height = record.get("image_height")
    if not isinstance(people, Sequence) or isinstance(people, (str, bytes)):
        raise PoseDirectionBundleError(f"{case_id}: item lacks a figure")
    if isinstance(width, bool) or isinstance(height, bool):
        raise PoseDirectionBundleError(f"{case_id}: item lacks a figure")
    if not isinstance(width, (int, float)) or not isinstance(height, (int, float)):
        raise PoseDirectionBundleError(f"{case_id}: item lacks a figure")
    try:
        return render_stick_figure_svg(people, float(width), float(height), case_id=case_id)
    except ValueError as exc:
        raise PoseDirectionBundleError(f"{case_id}: item lacks a figure") from exc


def _svg_has_figure(svg: str) -> bool:
    return any(marker in svg for marker in _FIGURE_MARKERS)


def _stick_figure(svg: str, case_id: str, figure: str) -> dict[str, str]:
    if figure == "svg":
        return {"svg": svg}
    name = f"{case_id}.svg"
    if _SVG_FILE_RE.fullmatch(name) is None:
        raise PoseDirectionBundleError(f"{case_id}: svg filename is not relative")
    return {"svg_file": name}


def _why(value: Any, case_id: str) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise PoseDirectionBundleError(f"{case_id}: why_it_works must be an object")
    unknown = set(value) - set(WHY_FIELDS)
    if unknown:
        raise PoseDirectionBundleError(f"{case_id}: unknown why field")
    out: dict[str, str] = {}
    for key in WHY_FIELDS:
        if key not in value or value[key] is None:
            continue
        raw = value[key]
        if not isinstance(raw, str) or not raw.strip():
            raise PoseDirectionBundleError(f"{case_id}: why field {key} is empty")
        text = raw.strip()
        if len(text) > 600:
            raise PoseDirectionBundleError(f"{case_id}: why field {key} is too long")
        if _leaks(text):
            raise PoseDirectionBundleError(f"{case_id}: why field contains a path or photo name")
        out[key] = text
    return out or None


def _leaks(text: str) -> bool:
    lowered = text.lower()
    if ".jpg" in lowered or ".jpeg" in lowered or ".png" in lowered:
        return True
    if "file:" in lowered or "exif" in lowered:
        return True
    return ":\\" in text or "npi_g1" in lowered
