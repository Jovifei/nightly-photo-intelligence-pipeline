"""AT-N0-HASH-01: streaming SHA-256 matches manifest.
AT-N0-HASH-02: perceptual hash interface exposes algorithm + version."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.ingest.hashing import (
    stream_sha256,
    stream_sha256_from_handle,
)
from nightly_photo_intelligence_pipeline.ingest.perceptual_hash import (
    ALGORITHM,
    IMPLEMENTATION_VERSION,
    analyze_image_from_handle,
    compute_perceptual_hash,
    compute_perceptual_hash_from_bytes,
)
from nightly_photo_intelligence_pipeline.ingest.source_guard import open_source_file

pytestmark = pytest.mark.acceptance


def test_at_n0_hash_01_streaming_sha_matches_manifest(
    project_root: Path, fixture_dir: Path, fixture_manifest: dict, config
) -> None:
    """AT-N0-HASH-01: streamed SHA-256 equals the manifest hash for each fixture."""
    exts = config.allowed_extensions
    for entry in fixture_manifest["files"]:
        p = fixture_dir / entry["name"]
        # Via path-based streaming API.
        assert stream_sha256(p) == entry["sha256"]
        # Via handle-based streaming API (exercises chunked reads).
        with open_source_file(p, fixture_dir, allowed_extensions=exts) as handle:
            assert stream_sha256_from_handle(handle) == entry["sha256"]
        # Independent stdlib recompute for cross-check.
        assert hashlib.sha256(p.read_bytes()).hexdigest() == entry["sha256"]


def test_at_n0_hash_01_duplicate_pair_identical(fixture_dir: Path, fixture_manifest: dict) -> None:
    """AT-N0-HASH-01: the duplicate pair shares the same SHA-256."""
    names = [
        e["name"]
        for e in fixture_manifest["files"]
        if e["expected_exact_duplicate_group"] == "dup-a"
    ]
    assert len(names) == 2
    hashes = {stream_sha256(fixture_dir / n) for n in names}
    assert len(hashes) == 1, "duplicate pair must be byte-identical"


def test_at_n0_hash_02_perceptual_hash_has_algorithm_and_version(fixture_dir: Path, config) -> None:
    """AT-N0-HASH-02: perceptual hash result carries algorithm + implementation version."""
    exts = config.allowed_extensions
    p = fixture_dir / "fixture_b_tonal_abstract.png"
    with open_source_file(p, fixture_dir, allowed_extensions=exts) as handle:
        facts = analyze_image_from_handle(handle)
    ph = facts.perceptual_hash
    assert ph.algorithm == ALGORITHM
    assert ph.implementation_version == IMPLEMENTATION_VERSION
    assert len(ph.value) >= 8
    assert all(c in "0123456789abcdef" for c in ph.value), "value must be lowercase hex"
    assert ph.algorithm and ph.implementation_version, "algorithm and version must be non-empty"


def test_at_n0_hash_02_perceptual_hash_deterministic(fixture_dir: Path) -> None:
    """AT-N0-HASH-02: the same bytes produce the same perceptual hash."""
    p = fixture_dir / "fixture_a_corridor_abstract.png"
    data = p.read_bytes()
    r1 = compute_perceptual_hash_from_bytes(data)
    r2 = compute_perceptual_hash(p)
    assert r1 == r2
