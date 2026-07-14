"""Versioned perceptual hash interface (N1 v2).

N0 introduced a lightweight dHash (8x8 -> 64-bit). N1 v2 enriches the result
with ``algorithm_id``, ``algorithm_version``, ``hash_size_bits``, a hamming
distance function, and a near-duplicate threshold constant. The result is its
own provenance record.

IMPORTANT: the production perceptual-hash threshold must NOT be frozen without
20 calibration images (G1). The default threshold here is a N1 fixture-level
convenience, not a production-claimed value.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

from ..domain.errors import NPI_INTERNAL_ERROR, NPI_UNSUPPORTED_MEDIA, NpiError
from .hashing import SupportsReadBytes

ALGORITHM_ID = "dhash-8x8"
ALGORITHM_VERSION = "npi-0.2.0"
HASH_SIZE_BITS = 64
HASH_HEX_LEN = 16  # 64 bits -> 16 hex chars

# Back-compat aliases (N0 names).
ALGORITHM = ALGORITHM_ID
IMPLEMENTATION_VERSION = ALGORITHM_VERSION

# N1 fixture-level near-duplicate threshold (hamming bits). NOT a production
# threshold: production requires G1 (20 calibration images) + a benchmark.
NEAR_DUPLICATE_THRESHOLD_HAMMING = 5


@dataclass(frozen=True)
class PerceptualHashResult:
    """Immutable perceptual-hash result carrying full provenance."""

    algorithm_id: str
    algorithm_version: str
    hash_size_bits: int
    value: str  # 16-char lowercase hex (64 bits) for dHash-8x8.

    @property
    def algorithm(self) -> str:
        """Back-compat alias for the schema's perceptual_hash_algorithm field."""
        return self.algorithm_id

    @property
    def implementation_version(self) -> str:
        """Back-compat alias for the N0 field name."""
        return self.algorithm_version

    def provenance(self) -> dict[str, str | int]:
        return {
            "algorithm_id": self.algorithm_id,
            "algorithm_version": self.algorithm_version,
            "hash_size_bits": self.hash_size_bits,
        }


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
    except ImportError:  # pragma: no cover - exercised only without PIL
        raise PerceptualHashUnavailableError(
            "Pillow is required for perceptual hashing but is not installed",
        ) from None
    try:
        with Image.open(io.BytesIO(data)) as img:
            width, height = img.size
            gray = img.convert("L").resize((9, 8))
            pixels = list(gray.tobytes())
    except Exception:  # noqa: BLE001 - Pillow exceptions may contain decoder details
        raise PerceptualHashUnavailableError("image metadata analysis failed") from None
    bits = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            bits = (bits << 1) | (1 if left > right else 0)
    return f"{bits:016x}", width, height


def _make_result(value: str) -> PerceptualHashResult:
    return PerceptualHashResult(
        algorithm_id=ALGORITHM_ID,
        algorithm_version=ALGORITHM_VERSION,
        hash_size_bits=HASH_SIZE_BITS,
        value=value,
    )


def compute_perceptual_hash(path: Path) -> PerceptualHashResult:
    """Compute the N1 perceptual hash of an image file."""
    try:
        data = Path(path).read_bytes()
    except OSError:
        raise PerceptualHashUnavailableError("image source read failed") from None
    return compute_perceptual_hash_from_bytes(data)


def analyze_image_bytes(data: bytes) -> ImageFacts:
    """Return perceptual hash plus width/height from a single PIL open."""
    value, width, height = _dhash_from_bytes(data)
    return ImageFacts(perceptual_hash=_make_result(value), width=width, height=height)


def compute_perceptual_hash_from_bytes(data: bytes) -> PerceptualHashResult:
    """Compute the N1 perceptual hash from in-memory image bytes."""
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


def hamming_distance(a: PerceptualHashResult | str, b: PerceptualHashResult | str) -> int:
    """Hamming distance (bit differences) between two dHash-8x8 values.

    Both values must be equal-length lowercase-hex strings of HASH_HEX_LEN.
    """
    av = a.value if isinstance(a, PerceptualHashResult) else a
    bv = b.value if isinstance(b, PerceptualHashResult) else b
    if len(av) != len(bv):
        raise NpiError(
            f"hamming distance requires equal-length hashes: {len(av)} != {len(bv)}",
            error_code=NPI_UNSUPPORTED_MEDIA,
        )
    return bin(int(av, 16) ^ int(bv, 16)).count("1")


def is_near_duplicate(
    a: PerceptualHashResult | str,
    b: PerceptualHashResult | str,
    *,
    threshold: int = NEAR_DUPLICATE_THRESHOLD_HAMMING,
) -> bool:
    """True if the hamming distance is <= threshold (N1 fixture-level default)."""
    return hamming_distance(a, b) <= threshold
