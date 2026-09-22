"""Explicitly allowlisted, redacted Real20 EXIF reader."""

from __future__ import annotations

import io
import math
from numbers import Real
from typing import Any

from .contracts import EXIF_ALLOWLIST

_TAGS = {
    33434: "ExposureTime",
    33437: "FNumber",
    34855: "ISOSpeedRatings",
    37385: "Flash",
    37386: "FocalLength",
    41987: "WhiteBalance",
}
_GPS = 34853
_SENSITIVE = {
    271,
    272,
    305,
    306,
    315,
    37510,
    42016,
    42032,
    42033,
    42034,
    42035,
    42036,
    42037,
}


def read_real20_exif(data: bytes) -> dict[str, Any]:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            exif = image.getexif()
            values = dict(exif)
            if 34665 in exif:
                values.update(exif.get_ifd(34665))
    except Exception:  # noqa: BLE001
        return {
            "present": False,
            "fields": {},
            "gps_excluded": False,
            "sensitive_excluded_count": 0,
            "parse_error": True,
        }
    if not exif:
        return {
            "present": False,
            "fields": {},
            "gps_excluded": False,
            "sensitive_excluded_count": 0,
            "parse_error": False,
        }
    fields: dict[str, str] = {}
    gps = False
    excluded = 0
    for tag_id, value in values.items():
        if tag_id == _GPS:
            gps = True
            excluded += 1
            continue
        name = _TAGS.get(tag_id)
        if name is None:
            if tag_id in _SENSITIVE or tag_id not in _TAGS:
                excluded += 1
            continue
        if isinstance(value, bool) or not isinstance(value, Real):
            continue
        try:
            number = float(value)
        except (ValueError, TypeError, OverflowError, ZeroDivisionError):
            continue
        if math.isfinite(number) and 0 <= number <= 1_000_000:
            fields[name] = str(number)
    return {
        "present": True,
        "fields": {name: fields[name] for name in EXIF_ALLOWLIST if name in fields},
        "gps_excluded": gps,
        "sensitive_excluded_count": excluded,
        "parse_error": False,
    }
