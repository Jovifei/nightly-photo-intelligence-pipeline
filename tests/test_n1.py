"""N1 acceptance tests: ingest, lease, retry, resume, migration, security.

Covers the N1 key behaviors required by the Owner authorization: deterministic
first ingest, idempotent re-ingest, exact-duplicate recognition, separate
SHA-256/perceptual-hash storage, TOCTOU detection, fail-closed source guard,
lease expiry reclaim, retry/error audit, repeatable migration, no absolute
paths in DB, no derived artifacts, deterministic structured output.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.authorization import load_authorization
from nightly_photo_intelligence_pipeline.ingest.manifest import load_manifest
from nightly_photo_intelligence_pipeline.ingest.perceptual_hash import (
    ALGORITHM_ID,
    ALGORITHM_VERSION,
    HASH_SIZE_BITS,
    analyze_image_from_handle,
    hamming_distance,
    is_near_duplicate,
)
from nightly_photo_intelligence_pipeline.ingest.runner import run_real_ingest
from nightly_photo_intelligence_pipeline.ingest.source_guard import open_source_file
from nightly_photo_intelligence_pipeline.persistence.sqlite import (
    STAGE_INTERRUPTED,
    StateStore,
)

pytestmark = pytest.mark.acceptance

N0_BASELINE = "72a81f5984838b74304d23263ac450ea4b5a3a9a"


def _utc_past(hours: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="seconds")


# ---- 1/2/3: deterministic first ingest, idempotent re-ingest, exact dup ----


def test_at_n1_ingest_deterministic_first_ingest(
    fixture_dir: Path, runtime_root: Path, db_path: Path, config
) -> None:
    """First ingest of the 3 fixtures is deterministic: 2 unique assets, 1 dup."""
    auth = load_authorization()
    manifest = load_manifest(fixture_dir.parent / "fixture_manifest.json")
    store = StateStore.open(db_path)
    result = run_real_ingest(fixture_dir, runtime_root, config, auth, store, manifest)
    assert result.files_scanned == 3
    assert result.assets_created == 2  # the exact-dup pair collapses to one
    assert result.duplicates_seen == 1
    assert store.asset_count() == 2
    store.close()


def test_at_n1_ingest_idempotent_reingest(
    fixture_dir: Path, runtime_root: Path, db_path: Path, config
) -> None:
    """Re-ingesting the same fixtures creates no new asset rows."""
    auth = load_authorization()
    manifest = load_manifest(fixture_dir.parent / "fixture_manifest.json")
    store = StateStore.open(db_path)
    run_real_ingest(fixture_dir, runtime_root, config, auth, store, manifest)
    first = store.asset_count()
    result2 = run_real_ingest(fixture_dir, runtime_root, config, auth, store, manifest)
    assert store.asset_count() == first
    assert result2.assets_created == 0
    assert result2.duplicates_seen == 3  # all 3 are now duplicates
    store.close()


def test_at_n1_exact_duplicate_recognized(
    fixture_dir: Path, runtime_root: Path, db_path: Path, config
) -> None:
    """The exact-duplicate pair (same SHA) is one asset with two sources."""
    auth = load_authorization()
    manifest = load_manifest(fixture_dir.parent / "fixture_manifest.json")
    store = StateStore.open(db_path)
    run_real_ingest(fixture_dir, runtime_root, config, auth, store, manifest)
    # Find the asset that has the duplicate-pair SHA.
    dup_sha = "ff0ec4d4baeb0a83495afaa62b65dc58110d83f9e2da14fd19e4d50959430157"
    asset = store.get_asset_by_sha(dup_sha)
    assert asset is not None
    # Two sources recorded for the one asset.
    rows = store.connection.execute(
        "SELECT COUNT(*) AS n FROM asset_sources WHERE asset_id = ?", (asset["asset_id"],)
    ).fetchone()
    assert int(rows["n"]) == 2
    store.close()


# ---- 4: SHA-256 and perceptual hash stored separately ----


def test_at_n1_sha_and_perceptual_hash_stored_separately(
    fixture_dir: Path, runtime_root: Path, db_path: Path, config
) -> None:
    auth = load_authorization()
    manifest = load_manifest(fixture_dir.parent / "fixture_manifest.json")
    store = StateStore.open(db_path)
    run_real_ingest(fixture_dir, runtime_root, config, auth, store, manifest)
    rows = store.connection.execute(
        "SELECT source_sha256, perceptual_hash, perceptual_hash_algorithm FROM assets"
    ).fetchall()
    assert len(rows) == 2
    for r in rows:
        assert r["source_sha256"] and len(r["source_sha256"]) == 64
        assert r["perceptual_hash"] and len(r["perceptual_hash"]) == 16
        assert r["perceptual_hash_algorithm"] == ALGORITHM_ID
        assert r["source_sha256"] != r["perceptual_hash"]
    store.close()


# ---- 5: TOCTOU detection ----


def test_at_n1_toctou_detected(tmp_path: Path, config) -> None:
    """A file swapped between stat and open is rejected (TOCTOU)."""
    from nightly_photo_intelligence_pipeline.domain.errors import SourceChangedDuringReadError

    src = tmp_path / "src"
    src.mkdir()
    p = src / "x.png"
    p.write_bytes(b"original")
    # Patch os.stat to return a different size than the actual file -> TOCTOU.
    import os

    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        # Return a size mismatch to simulate a swap between stat and open.
        return os.stat_result(
            (
                st.st_mode,
                st.st_ino,
                st.st_dev,
                999,
                st.st_uid,
                st.st_gid,
                st.st_size + 999,
                st.st_atime,
                st.st_mtime,
                st.st_ctime,
            )
        )

    os.stat = fake_stat
    try:
        with (
            pytest.raises(SourceChangedDuringReadError),
            open_source_file(p, src, allowed_extensions=config.allowed_extensions),
        ):
            pass
    finally:
        os.stat = real_stat


# ---- 6: source guard fail-closed (overlap, escape, junction) - N0 covers; add output-to-source ----


def test_at_n1_output_to_source_rejected(tmp_path: Path, config) -> None:
    """Runtime/output inside source is rejected (output must not write to source)."""
    from nightly_photo_intelligence_pipeline.domain.errors import SourceRuntimeOverlapError
    from nightly_photo_intelligence_pipeline.ingest.source_guard import validate_roots

    src = tmp_path / "src"
    src.mkdir()
    runtime_inside_source = src / "runtime"
    runtime_inside_source.mkdir()
    with pytest.raises(SourceRuntimeOverlapError):
        validate_roots(src, runtime_inside_source)


# ---- 9/10: interrupted run identified + lease expiry reclaim ----


def test_at_n1_resume_reclaims_expired_lease(db_path: Path) -> None:
    """An interrupted RUNNING run with an expired lease is reclaimed by resume."""
    store = StateStore.open(db_path)
    res = store.ingest_asset(
        source_sha256="a" * 64,
        sanitized_source_name="a.png",
        local_path_protected="<SOURCE_ROOT>/a.png",
        observed_size_bytes=1,
        observed_mtime_ns=1,
    )
    rid = store.claim_stage_run(
        asset_id=res.asset_id, stage_name="pose", lease_owner="w1", lease_seconds=60
    )
    # Force the lease into the past.
    store.connection.execute(
        "UPDATE stage_runs SET lease_expires_at = ? WHERE stage_run_id = ?",
        (_utc_past(1), rid),
    )
    store.connection.commit()
    store.close()

    store2 = StateStore.open(db_path, initialize=False)
    interrupted = store2.identify_interrupted_runs()
    assert len(interrupted) == 1
    assert interrupted[0].stage_run_id == rid
    n = store2.recover_interrupted_runs()
    assert n == 1
    runs = store2.recent_stage_runs()
    assert runs[0].status == STAGE_INTERRUPTED
    store2.close()


def test_at_n1_heartbeat_extends_lease(db_path: Path) -> None:
    """A heartbeat refreshes lease_expires_at so the run is not interrupted."""
    store = StateStore.open(db_path)
    res = store.ingest_asset(
        source_sha256="b" * 64,
        sanitized_source_name="b.png",
        local_path_protected="<SOURCE_ROOT>/b.png",
        observed_size_bytes=1,
        observed_mtime_ns=1,
    )
    rid = store.claim_stage_run(
        asset_id=res.asset_id, stage_name="pose", lease_owner="w1", lease_seconds=60
    )
    store.heartbeat(rid, lease_owner="w1", lease_seconds=3600)
    interrupted = store.identify_interrupted_runs()
    assert len(interrupted) == 0, "heartbeat should keep the lease valid"
    store.close()


# ---- 11: retry / last_error / timing audit ----


def test_at_n1_retry_and_error_audit(db_path: Path) -> None:
    """retry_count, last_error_code, and last_error_redacted are auditable."""
    store = StateStore.open(db_path)
    res = store.ingest_asset(
        source_sha256="c" * 64,
        sanitized_source_name="c.png",
        local_path_protected="<SOURCE_ROOT>/c.png",
        observed_size_bytes=1,
        observed_mtime_ns=1,
    )
    rid = store.claim_stage_run(
        asset_id=res.asset_id, stage_name="pose", lease_owner="w1", lease_seconds=60
    )
    store.release_run(
        rid,
        "FAILED",
        lease_owner="w1",
        error_code="NPI_MODEL_TIMEOUT",
        error_redacted="pose model timeout",
    )
    n = store.record_retry(
        res.asset_id,
        error_code="NPI_MODEL_TIMEOUT",
        error_redacted="pose model timeout",
    )
    assert n == 1
    n2 = store.record_retry(
        res.asset_id,
        error_code="NPI_MODEL_TIMEOUT",
        error_redacted="pose model timeout",
    )
    assert n2 == 2
    asset = store.get_asset(res.asset_id)
    assert asset["retry_count"] == 2
    assert asset["last_error_code"] == "NPI_RETRY_EXHAUSTED"
    # Stage run timing audit.
    row = store.connection.execute(
        "SELECT finished_at, error_code FROM stage_runs WHERE stage_run_id = ?", (rid,)
    ).fetchone()
    assert row["finished_at"] is not None
    assert row["error_code"] == "NPI_MODEL_TIMEOUT"
    store.close()


# ---- 13: migration repeatable ----


def test_at_n1_migration_repeatable(db_path: Path) -> None:
    """Running migrations twice is a no-op (idempotent)."""
    store = StateStore.open(db_path)
    assert store.schema_version() == "3"
    applied = store.applied_migrations()
    assert {"v0", "v1", "v2"}.issubset(set(applied))
    # Re-run initialize (calls run_migrations again).
    store.initialize()
    assert store.schema_version() == "3"
    applied2 = store.applied_migrations()
    assert applied2 == applied
    store.close()


# ---- 15: DB stores no real absolute photo paths ----


def test_at_n1_db_no_absolute_photo_paths(
    fixture_dir: Path, runtime_root: Path, db_path: Path, config
) -> None:
    """The DB stores only redacted source paths, never absolute photo paths."""
    auth = load_authorization()
    manifest = load_manifest(fixture_dir.parent / "fixture_manifest.json")
    store = StateStore.open(db_path)
    run_real_ingest(fixture_dir, runtime_root, config, auth, store, manifest)
    rows = store.connection.execute("SELECT local_path_protected FROM asset_sources").fetchall()
    for r in rows:
        path = str(r["local_path_protected"])
        assert str(fixture_dir) not in path, "absolute fixture path leaked into DB"
        assert path.startswith("<SOURCE_ROOT>"), f"source path not redacted: {path}"
    store.close()


# ---- 16: no derived artifacts (thumbnails/masks/embeddings/models) ----


def test_at_n1_no_derived_artifacts(
    fixture_dir: Path, runtime_root: Path, db_path: Path, config
) -> None:
    """Real ingest creates no thumbnails, masks, embeddings, or model artifacts."""
    auth = load_authorization()
    manifest = load_manifest(fixture_dir.parent / "fixture_manifest.json")
    store = StateStore.open(db_path)
    run_real_ingest(fixture_dir, runtime_root, config, auth, store, manifest)
    store.close()
    # No outputs written; runtime contains only the DB (and logs dir if created).
    outputs = list(runtime_root.rglob("*"))
    derived = [
        p
        for p in outputs
        if p.suffix.lower()
        in {
            ".jpg",
            ".jpeg",
            ".webp",
            ".npy",
            ".npz",
            ".pt",
            ".pth",
            ".ckpt",
            ".safetensors",
            ".onnx",
            ".engine",
            ".mask",
            ".png",
        }
        and p.is_file()
    ]
    assert derived == [], f"unexpected derived artifacts: {derived}"


# ---- 17: deterministic structured output ----


def test_at_n1_deterministic_structured_output(
    fixture_dir: Path, runtime_root: Path, db_path: Path, config
) -> None:
    """Two separate ingests (fresh DBs) produce identical asset SHA sets."""
    auth = load_authorization()
    manifest = load_manifest(fixture_dir.parent / "fixture_manifest.json")

    def shas() -> set[str]:
        s = StateStore.open(db_path)
        run_real_ingest(fixture_dir, runtime_root, config, auth, s, manifest)
        rows = s.connection.execute(
            "SELECT source_sha256 FROM assets ORDER BY source_sha256"
        ).fetchall()
        out = {str(r["source_sha256"]) for r in rows}
        s.close()
        db_path.unlink()
        return out

    a = shas()
    b = shas()
    assert a == b
    assert a == {
        "ff0ec4d4baeb0a83495afaa62b65dc58110d83f9e2da14fd19e4d50959430157",
        "9544c610264418316c22143442e8a3e308e076eca2f19d0e51cf67baa3489097",
    }


# ---- perceptual hash v2: provenance + distance ----


def test_at_n1_perceptual_hash_v2_provenance(fixture_dir: Path, config) -> None:
    """The perceptual hash result carries algorithm_id, version, and hash_size."""
    p = fixture_dir / "fixture_b_tonal_abstract.png"
    with open_source_file(p, fixture_dir, allowed_extensions=config.allowed_extensions) as h:
        from nightly_photo_intelligence_pipeline.ingest.perceptual_hash import (
            analyze_image_from_handle,
        )

        facts = analyze_image_from_handle(h)
    ph = facts.perceptual_hash
    assert ph.algorithm_id == ALGORITHM_ID
    assert ph.algorithm_version == ALGORITHM_VERSION
    assert ph.hash_size_bits == HASH_SIZE_BITS
    prov = ph.provenance()
    assert prov["algorithm_id"] == ALGORITHM_ID
    assert prov["hash_size_bits"] == HASH_SIZE_BITS


def test_at_n1_hamming_distance_and_near_duplicate(fixture_dir: Path, config) -> None:
    """hamming_distance and is_near_duplicate work; identical hashes have distance 0."""
    p = fixture_dir / "fixture_a_corridor_abstract.png"
    with open_source_file(p, fixture_dir, allowed_extensions=config.allowed_extensions) as h:
        ph = analyze_image_from_handle(h).perceptual_hash
    assert hamming_distance(ph, ph) == 0
    assert is_near_duplicate(ph, ph)
    # A one-bit-flipped hex string has hamming distance 1.
    flipped = f"{int(ph.value, 16) ^ 1:016x}"
    assert hamming_distance(ph, flipped) == 1
    assert is_near_duplicate(ph, flipped)


# ---- N0 baseline + authorization ----


def test_at_n1_n0_baseline_immutable(project_root: Path) -> None:
    """The N0 baseline commit and tag are present and unchanged."""
    import subprocess

    tag = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "n0-approved-2026-07-14"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert tag.returncode == 0
    assert tag.stdout.strip() == N0_BASELINE


def test_at_n1_authorization_n1_g0_no_real_photos() -> None:
    auth = load_authorization()
    assert auth.phase_id == "N1" and auth.phase_authorized
    assert auth.data_gate_id == "G1_CALIBRATION_20"
    assert auth.max_assets == 20
    assert auth.real_photo_access == "AUTHORIZED"
    assert auth.exif_real_data_read == "AUTHORIZED_NON_SENSITIVE_ONLY"
    assert auth.large_model_downloads == "NOT_AUTHORIZED"
