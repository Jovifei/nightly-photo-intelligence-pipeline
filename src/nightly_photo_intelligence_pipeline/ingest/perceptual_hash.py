"""Versioned perceptual hash interface.

N0 uses a lightweight dHash (8x8 -> 64-bit) implementation. The result always
carries the algorithm name and implementation version so downstream consumers
never confuse it with a frozen production algorithm. Per docs/03 and the N0
task contract, the production perceptual hash must not be frozen without an N1
decision.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from ..domain.errors import NPI_INTERNAL_ERROR, NPI_UNSUPPORTED_MEDIA, NpiError
from .hashing import SupportsReadBytes

ALGORITHM = "dhash-8x8"
IMPLEMENTATION_VERSION = "npi-0.1.0"


@dataclass(frozen=True)
class PerceptualHashResult:
    """Immutable perceptual-hash result with full provenance."""

    algorithm: str
    implementation_version: str
    value: str  # 16-char lowercase hex (64 bits) for dHash-8x8.


@dataclass(frozen=True)
class ImageFacts:
    """Perceptual hash plus basic image dimensions, from a single PIL open."""

    perceptual_hash: PerceptualHashResult
    width: int
    height: int


class PerceptualHashUnavailableError(NpiError):
    error_code = NPI_UNSUPPORTED_MEDIA


def _dhash_from_bytes(data: bytes) -> tuple[str, int, int]:
    """Compute dHash-8x8 hex and image dimensions from raw image bytes."""
    try:
        from PIL import Image  # local import: PIL is a soft runtime dep.
    except ImportError as exc:  # pragma: no cover - exercised only without PIL
        raise PerceptualHashUnavailableError(
            "Pillow is required for perceptual hashing but is not installed",
        ) from exc
    with Image.open(io.BytesIO(data)) as img:
        width, height = img.size
        gray = img.convert("L").resize((9, 8))
        # tobytes() is the stable, non-deprecated way to read 8-bit grayscale
        # pixels (getdata() is deprecated in newer Pillow).
        pixels = list(gray.tobytes())
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}", width, height


def compute_perceptual_hash(path: Path) -> PerceptualHashResult:
    """Compute the N0 perceptual hash of an image file."""
    data = Path(path).read_bytes()
    return compute_perceptual_hash_from_bytes(data)


def analyze_image_bytes(data: bytes) -> ImageFacts:
    """Return perceptual hash plus width/height from a single PIL open."""
    value, width, height = _dhash_from_bytes(data)
    return ImageFacts(
        perceptual_hash=PerceptualHashResult(
            algorithm=ALGORITHM,
            implementation_version=IMPLEMENTATION_VERSION,
            value=value,
        ),
        width=width,
        height=height,
    )


def compute_perceptual_hash_from_bytes(data: bytes) -> PerceptualHashResult:
    """Compute the N0 perceptual hash from in-memory image bytes."""
    return analyze_image_bytes(data).perceptual_hash


def compute_perceptual_hash_from_handle(handle: SupportsReadBytes) -> PerceptualHashResult:
    """Read all bytes from *handle* (current position to EOF) and hash them."""
    data = handle.read()
    if not isinstance(data, bytes):
        raise NpiError("perceptual hash handle did not yield bytes", error_code=NPI_INTERNAL_ERROR)
    return compute_perceptual_hash_from_bytes(data)


def analyze_image_from_handle(handle: SupportsReadBytes) -> ImageFacts:
    """Read all bytes from *handle* (current position to EOF) and analyze."""
    data = handle.read()
    if not isinstance(data, bytes):
        raise NpiError("image handle did not yield bytes", error_code=NPI_INTERNAL_ERROR)
    return analyze_image_bytes(data)
