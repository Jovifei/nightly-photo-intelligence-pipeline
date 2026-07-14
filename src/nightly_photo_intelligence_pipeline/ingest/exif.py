"""Non-sensitive EXIF reader for G1 calibration.

EXIF is read from the already-open source handle, never by reopening a path.
Only real technical fields are returned; missing values stay missing. GPS,
location-like, device identity, authorship, and comments are excluded. The
output may record that sensitive fields were detected and excluded, but never
their values.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

from .hashing import SupportsReadBytes

_MAX_FIELD_LEN = 80

# Conservative technical tags only. Device make/model/software and timestamps
# are intentionally excluded for G1 because they can identify people/devices.
_ALLOWED_EXIF_TAGS: dict[int, str] = {
    0x0112: "orientation",
    0x011A: "x_resolution",
    0x011B: "y_resolution",
    0x0128: "resolution_unit",
    0xA002: "exif_image_width",
    0xA003: "exif_image_height",
}

_GPS_IFD_TAG = 0x8825
_SENSITIVE_TAGS = {
    0x010F,  # Make
    0x0110,  # Model
    0x0131,  # Software
    0x0132,  # DateTime
    0x013B,  # Artist
    0x8298,  # Copyright
    0x9003,  # DateTimeOriginal
    0x9004,  # DateTimeDigitized
    0x9286,  # UserComment
    0xA420,  # ImageUniqueID
    0xA430,  # CameraOwnerName
    0xA431,  # BodySerialNumber
    0xA432,  # LensSpecification
    0xA433,  # LensMake
    0xA434,  # LensModel
    0xA435,  # LensSerialNumber
}


@dataclass(frozen=True)
class ExifSnapshot:
    """Redacted EXIF snapshot."""

    present: bool
    fields: dict[str, str] = field(default_factory=dict)
    gps_present_but_excluded: bool = False
    sensitive_fields_excluded: int = 0
    parse_error: bool = False

    def to_redacted_dict(self) -> dict[str, object]:
        return {
            "present": self.present,
            "fields": dict(self.fields),
            "gps_excluded": self.gps_present_but_excluded,
            "sensitive_excluded_count": self.sensitive_fields_excluded,
            "parse_error": self.parse_error,
        }


def _stringify(value: object) -> str:
    text = str(value).strip()
    return text[:_MAX_FIELD_LEN]


def read_exif_from_bytes(data: bytes) -> ExifSnapshot:
    """Read non-sensitive EXIF from image bytes.

    No value is inferred. If Pillow cannot parse EXIF, the result records a
    parse error rather than fabricating an absent EXIF block.
    """
    try:
        from PIL import Image
    except ImportError:
        return ExifSnapshot(present=False, parse_error=True)
    try:
        with Image.open(io.BytesIO(data)) as img:
            exif = img.getexif()
    except Exception:  # noqa: BLE001 - malformed EXIF/image metadata
        return ExifSnapshot(present=False, parse_error=True)
    if not exif:
        return ExifSnapshot(present=False)

    fields: dict[str, str] = {}
    gps_present = False
    sensitive_excluded = 0
    for tag_id, value in exif.items():
        if tag_id == _GPS_IFD_TAG:
            gps_present = True
            continue
        if tag_id in _SENSITIVE_TAGS:
            sensitive_excluded += 1
            continue
        name = _ALLOWED_EXIF_TAGS.get(tag_id)
        if name is None:
            continue
        text = _stringify(value)
        if text:
            fields[name] = text
    return ExifSnapshot(
        present=True,
        fields=fields,
        gps_present_but_excluded=gps_present,
        sensitive_fields_excluded=sensitive_excluded,
    )


def read_exif(handle: SupportsReadBytes) -> ExifSnapshot:
    """Read non-sensitive EXIF from the current position of an open handle."""
    data = handle.read()
    if not isinstance(data, bytes):
        return ExifSnapshot(present=False, parse_error=True)
    return read_exif_from_bytes(data)
