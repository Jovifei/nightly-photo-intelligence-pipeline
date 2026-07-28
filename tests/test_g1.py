"""G1 calibration tests: fixed manifest, EXIF privacy, integrity, and safety."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.authorization import AuthorizationSnapshot
from nightly_photo_intelligence_pipeline.domain.errors import (
    GateNotAuthorizedError,
    SourceChangedDuringReadError,
    SourceRuntimeOverlapError,
    SourceSymlinkEscapeError,
)
from nightly_photo_intelligence_pipeline.ingest.exif import read_exif_from_bytes
from nightly_photo_intelligence_pipeline.ingest.g1_contract import (
    G1ExecutionPermit,
    path_fingerprint,
)
from nightly_photo_intelligence_pipeline.ingest.manifest import (
    G1FrozenManifest,
    require_g1_manifest_member,
)
from nightly_photo_intelligence_pipeline.ingest.read_only_capability import ReadOnlyCapabilityResult
from nightly_photo_intelligence_pipeline.ingest.runner import run_g1_calibration_ingest
from nightly_photo_intelligence_pipeline.persistence.sqlite import StateStore

pytestmark = pytest.mark.acceptance


def _g1_auth(project_root: Path) -> AuthorizationSnapshot:
    return AuthorizationSnapshot(
        phase_id="N1",
        phase_status="AUTHORIZED",
        data_gate_id="G1_CALIBRATION_20",
        data_gate_status="AUTHORIZED",
        real_photo_access="AUTHORIZED",
        large_model_downloads="NOT_AUTHORIZED",
        openclaw_activation="NOT_AUTHORIZED",
        exif_real_data_read="AUTHORIZED",
        project_root=project_root,
        max_assets=20,
        n0_baseline_commit="72a81f5984838b74304d23263ac450ea4b5a3a9a",
        n1_baseline_commit="ca812cb71c4a09d273f64d9a6f2747ac3facf4cc",
        active_execution_phase="G1",
        active_execution_capability="G1_CALIBRATION_20",
        source_photo_content_read="AUTHORIZED",
        sqlite_ingest_write="AUTHORIZED",
    )


def _write_image(path: Path, *, color: tuple[int, int, int], exif: bool = False) -> None:
    from PIL import Image

    img = Image.new("RGB", (32, 24), color)
    if exif:
        exif_data = Image.Exif()
        exif_data[0x0112] = 1
        exif_data[0x010F] = "CameraMaker"
        exif_data[0x0110] = "CameraModel"
        exif_data[0x013B] = "Named Artist"
        img.save(path, format="JPEG", exif=exif_data)
    else:
        img.save(path)


def _make_g1_source(tmp_path: Path) -> tuple[Path, Path, G1FrozenManifest]:
    src = tmp_path / "source"
    src.mkdir()
    names: list[str] = []
    for i in range(20):
        name = f"asset_{i:02d}.jpg"
        names.append(name)
        _write_image(src / name, color=((i * 7) % 255, (i * 11) % 255, (i * 13) % 255))
    shutil.copyfile(src / names[0], src / names[1])
    manifest_path = tmp_path / "g1_selected_20.txt"
    manifest_path.write_text("\n".join(names) + "\n", encoding="utf-8")
    return src, manifest_path, G1FrozenManifest.load(manifest_path)


def _permit(source: Path, runtime: Path, manifest: G1FrozenManifest) -> G1ExecutionPermit:
    return G1ExecutionPermit(
        manifest_sha256=manifest.sha256,
        source_root_fingerprint_sha256=path_fingerprint(source),
        runtime_child_fingerprint_sha256=path_fingerprint(runtime),
        read_only=ReadOnlyCapabilityResult("OS_ENFORCED_READ_ONLY_VERIFIED", 20),
    )


def test_g1_exif_existing_missing_broken_and_sensitive_excluded(
    tmp_path: Path, monkeypatch
) -> None:
    with_exif = tmp_path / "with_exif.jpg"
    without_exif = tmp_path / "without_exif.jpg"
    _write_image(with_exif, color=(1, 2, 3), exif=True)
    _write_image(without_exif, color=(4, 5, 6), exif=False)

    snap = read_exif_from_bytes(with_exif.read_bytes())
    assert snap.present
    assert snap.fields == {"orientation": "1"}
    assert snap.sensitive_fields_excluded >= 3
    dumped = str(snap.to_redacted_dict())
    assert "CameraMaker" not in dumped
    assert "CameraModel" not in dumped
    assert "Named Artist" not in dumped

    absent = read_exif_from_bytes(without_exif.read_bytes())
    assert not absent.present
    assert absent.fields == {}

    broken = read_exif_from_bytes(b"not an image")
    assert broken.parse_error
    assert broken.fields == {}

    class FakeImage:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def getexif(self):
            return {0x0112: 1, 0x8825: "gps-hidden", 0xA430: "owner-hidden"}

    import PIL.Image

    monkeypatch.setattr(PIL.Image, "open", lambda _: FakeImage())
    gps = read_exif_from_bytes(b"fake image bytes")
    assert gps.fields == {"orientation": "1"}
    assert gps.gps_present_but_excluded
    assert gps.sensitive_fields_excluded == 1


def test_g1_manifest_fixed_count_duplicate_and_member_rejection(tmp_path: Path) -> None:
    manifest_path = tmp_path / "g1.txt"
    manifest_path.write_text("\n".join(f"a_{i}.jpg" for i in range(20)) + "\n", encoding="utf-8")
    manifest = G1FrozenManifest.load(manifest_path)
    assert manifest.count == 20
    assert len({e.asset_ref for e in manifest.entries}) == 20

    with pytest.raises(GateNotAuthorizedError):
        require_g1_manifest_member("not_authorized.jpg", manifest)

    manifest_path.write_text("dup.jpg\nDUP.JPG\n", encoding="utf-8")
    with pytest.raises(GateNotAuthorizedError):
        G1FrozenManifest.load(manifest_path, expected_count=2)

    manifest_path.write_text("\n".join(f"a_{i}.jpg" for i in range(21)), encoding="utf-8")
    with pytest.raises(GateNotAuthorizedError):
        G1FrozenManifest.load(manifest_path)


@pytest.mark.parametrize(
    "unsafe_entry",
    [
        r"\root-relative.jpg",
        "C:" + "drive-relative.jpg",
        "C:" + "\\absolute.jpg",
        "../escape.jpg",
    ],
)
def test_g1_manifest_rejects_windows_and_parent_relative_paths(
    tmp_path: Path, unsafe_entry: str
) -> None:
    manifest_path = tmp_path / "g1.txt"
    manifest_path.write_text(unsafe_entry + "\n", encoding="utf-8")
    with pytest.raises(GateNotAuthorizedError, match="source-relative"):
        G1FrozenManifest.load(manifest_path, expected_count=1)


def test_g1_first_ingest_idempotent_duplicates_phash_and_integrity(
    tmp_path: Path, runtime_root: Path, db_path: Path, config, project_root: Path
) -> None:
    src, _, manifest = _make_g1_source(tmp_path)
    auth = _g1_auth(project_root)
    store = StateStore.open(db_path)

    pre_hashes = {
        entry.asset_ref: hashlib.sha256((src / entry.relative_path).read_bytes()).hexdigest()
        for entry in manifest.entries
    }
    result = run_g1_calibration_ingest(
        src,
        runtime_root,
        config,
        auth,
        store,
        manifest,
        permit=_permit(src, runtime_root, manifest),
    )
    post_hashes = {
        entry.asset_ref: hashlib.sha256((src / entry.relative_path).read_bytes()).hexdigest()
        for entry in manifest.entries
    }
    assert result.files_scanned == 20
    assert result.assets_created == 19
    assert result.duplicates_seen == 1
    assert result.exact_duplicate_groups == [["g1-asset-01", "g1-asset-02"]]
    assert pre_hashes == post_hashes
    assert all(asset.integrity_unchanged for asset in result.assets)
    assert all(len(asset.perceptual_hash) == 16 for asset in result.assets)

    second = run_g1_calibration_ingest(
        src,
        runtime_root,
        config,
        auth,
        store,
        manifest,
        permit=_permit(src, runtime_root, manifest),
    )
    assert store.asset_count() == 19
    assert second.assets_created == 0
    assert second.duplicates_seen == 20

    rows = store.connection.execute(
        "SELECT sanitized_source_name, local_path_protected FROM assets "
        "JOIN asset_sources USING(asset_id)"
    ).fetchall()
    for row in rows:
        assert str(src) not in str(row["local_path_protected"])
        assert str(row["sanitized_source_name"]).startswith("g1-asset-")
        assert str(row["local_path_protected"]).startswith("<SOURCE_ROOT>/g1-asset-")
    store.close()

    derived = [
        p
        for p in runtime_root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".npy", ".pt", ".onnx"}
    ]
    assert derived == []


def test_g1_rejects_unauthorized_state_before_source_read(
    tmp_path: Path, runtime_root: Path, db_path: Path, config, project_root: Path
) -> None:
    src, _, manifest = _make_g1_source(tmp_path)
    bad_auth = _g1_auth(project_root)
    bad_auth = AuthorizationSnapshot(
        phase_id=bad_auth.phase_id,
        phase_status=bad_auth.phase_status,
        data_gate_id="G0_THREE_SYNTHETIC_FIXTURES",
        data_gate_status=bad_auth.data_gate_status,
        real_photo_access=bad_auth.real_photo_access,
        large_model_downloads=bad_auth.large_model_downloads,
        openclaw_activation=bad_auth.openclaw_activation,
        exif_real_data_read=bad_auth.exif_real_data_read,
        project_root=bad_auth.project_root,
        max_assets=bad_auth.max_assets,
        n0_baseline_commit=bad_auth.n0_baseline_commit,
    )
    store = StateStore.open(db_path)
    before = hashlib.sha256((src / manifest.entries[0].relative_path).read_bytes()).hexdigest()
    with pytest.raises(GateNotAuthorizedError):
        run_g1_calibration_ingest(
            src,
            runtime_root,
            config,
            bad_auth,
            store,
            manifest,
            permit=_permit(src, runtime_root, manifest),
        )
    after = hashlib.sha256((src / manifest.entries[0].relative_path).read_bytes()).hexdigest()
    assert before == after
    assert store.asset_count() == 0
    store.close()


def test_g1_source_runtime_overlap_rejected(
    tmp_path: Path, db_path: Path, config, project_root: Path
) -> None:
    src, _, manifest = _make_g1_source(tmp_path)
    store = StateStore.open(db_path)
    with pytest.raises(SourceRuntimeOverlapError):
        run_g1_calibration_ingest(
            src,
            src / "runtime",
            config,
            _g1_auth(project_root),
            store,
            manifest,
            permit=_permit(src, src / "runtime", manifest),
        )
    store.close()


def test_g1_toctou_rejected(
    tmp_path: Path, runtime_root: Path, db_path: Path, config, project_root: Path, monkeypatch
) -> None:
    import os

    src, _, manifest = _make_g1_source(tmp_path)
    real_stat = os.stat

    def fake_stat(path, *args, **kwargs):
        st = real_stat(path, *args, **kwargs)
        if Path(path).name == "asset_00.jpg":
            return os.stat_result(
                (
                    st.st_mode,
                    st.st_ino,
                    st.st_dev,
                    999,
                    st.st_uid,
                    st.st_gid,
                    st.st_size + 1,
                    st.st_atime,
                    st.st_mtime,
                    st.st_ctime,
                )
            )
        return st

    monkeypatch.setattr(os, "stat", fake_stat)
    store = StateStore.open(db_path)
    with pytest.raises(SourceChangedDuringReadError):
        run_g1_calibration_ingest(
            src,
            runtime_root,
            config,
            _g1_auth(project_root),
            store,
            manifest,
            permit=_permit(src, runtime_root, manifest),
        )
    assert store.asset_count() == 0
    store.close()


def test_g1_junction_or_symlink_escape_rejected(
    tmp_path: Path, runtime_root: Path, db_path: Path, config, project_root: Path, junction_factory
) -> None:
    src = tmp_path / "source"
    src.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    _write_image(outside / "asset_00.jpg", color=(1, 2, 3))
    link = src / "linked"
    if not junction_factory(link, outside):
        pytest.skip("junction creation unavailable on this platform")
    for i in range(1, 20):
        _write_image(src / f"asset_{i:02d}.jpg", color=(i, i, i))
    manifest_path = tmp_path / "g1.txt"
    lines = ["linked/asset_00.jpg", *(f"asset_{i:02d}.jpg" for i in range(1, 20))]
    manifest_path.write_text("\n".join(lines), encoding="utf-8")
    manifest = G1FrozenManifest.load(manifest_path)
    store = StateStore.open(db_path)
    with pytest.raises(SourceSymlinkEscapeError):
        run_g1_calibration_ingest(
            src,
            runtime_root,
            config,
            _g1_auth(project_root),
            store,
            manifest,
            permit=_permit(src, runtime_root, manifest),
        )
    store.close()


def test_g1_permit_is_bound_to_actual_runtime_child(
    tmp_path: Path, runtime_root: Path, db_path: Path, config, project_root: Path
) -> None:
    src, _, manifest = _make_g1_source(tmp_path)
    other_runtime = tmp_path / "other-runtime"
    other_runtime.mkdir()
    store = StateStore.open(db_path)
    with pytest.raises(GateNotAuthorizedError, match="runtime mismatch"):
        run_g1_calibration_ingest(
            src,
            runtime_root,
            config,
            _g1_auth(project_root),
            store,
            manifest,
            permit=_permit(src, other_runtime, manifest),
        )
    assert store.asset_count() == 0
    store.close()
