"""SQLite claim/lease/retry/recovery concurrency and failure semantics."""

from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier

import pytest
import yaml

from nightly_photo_intelligence_pipeline.domain.errors import (
    ERROR_CODE_TO_EXIT,
    NPI_RETRY_EXHAUSTED,
    NPI_SCHEMA_INVALID,
    DatabaseError,
    LeaseLostError,
    NpiError,
    RetryExhaustedError,
    StageClaimConflictError,
)
from nightly_photo_intelligence_pipeline.persistence.migrations import (
    apply_schema_v0,
    apply_schema_v1,
    apply_schema_v2,
    apply_schema_v3,
    run_migrations,
)
from nightly_photo_intelligence_pipeline.persistence.sqlite import (
    STAGE_FAILED,
    STAGE_INTERRUPTED,
    STAGE_SKIPPED,
    STAGE_SUCCEEDED,
    StateStore,
)


def _asset(store: StateStore, token: str = "a") -> str:
    return store.ingest_asset(
        source_sha256=token * 64,
        sanitized_source_name=f"{token}.png",
        local_path_protected=f"<SOURCE_ROOT>/{token}.png",
        observed_size_bytes=1,
        observed_mtime_ns=1,
    ).asset_id


def _past(seconds: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(seconds=seconds)).isoformat(timespec="seconds")


def test_two_connections_only_one_claims_same_asset_stage(db_path: Path) -> None:
    seed = StateStore.open(db_path)
    asset_id = _asset(seed)
    seed.close()
    stores = [StateStore.open(db_path, initialize=False) for _ in range(2)]
    barrier = Barrier(2)

    def claim(index: int) -> tuple[str, str]:
        barrier.wait(timeout=5)
        try:
            run_id = stores[index].claim_stage_run(
                asset_id=asset_id,
                stage_name="pose",
                lease_owner=f"worker-{index}",
            )
            return "success", run_id
        except StageClaimConflictError as exc:
            return exc.error_code, ""

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, range(2)))
    assert sorted(result[0] for result in results) == ["NPI_STAGE_CLAIM_CONFLICT", "success"]
    rows = (
        stores[0]
        .connection.execute(
            "SELECT COUNT(*) FROM stage_runs WHERE asset_id=? AND stage_name=? AND status='RUNNING'",
            (asset_id, "pose"),
        )
        .fetchone()
    )
    assert int(rows[0]) == 1
    for store in stores:
        store.close()


def test_sqlite_busy_is_safely_classified_without_native_error_leak(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    owner = StateStore.open(db_path, busy_timeout_ms=1)
    asset_id = _asset(owner)
    contender = StateStore.open(db_path, busy_timeout_ms=1, initialize=False)
    owner.connection.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(DatabaseError) as caught:
            contender.claim_stage_run(
                asset_id=asset_id,
                stage_name="synthetic-lock",
                lease_owner="contender",
            )
        assert caught.value.error_code == "NPI_DATABASE_ERROR"
        assert caught.value.__cause__ is None
        assert "locked" not in str(caught.value).casefold()
        assert "sqlite" not in str(caught.value).casefold()
    finally:
        owner.connection.rollback()
        contender.close()
        owner.close()


def test_heartbeat_rejects_missing_wrong_expired_and_interrupted(db_path: Path) -> None:
    store = StateStore.open(db_path)
    asset_id = _asset(store)
    run_id = store.claim_stage_run(
        asset_id=asset_id, stage_name="pose", lease_owner="owner", lease_seconds=60
    )
    with pytest.raises(LeaseLostError):
        store.heartbeat("missing", lease_owner="owner")
    with pytest.raises(LeaseLostError):
        store.heartbeat(run_id, lease_owner="other")
    store.connection.execute(
        "UPDATE stage_runs SET lease_expires_at=? WHERE stage_run_id=?", (_past(), run_id)
    )
    with pytest.raises(LeaseLostError):
        store.heartbeat(run_id, lease_owner="owner")
    assert store.recover_interrupted_runs() == 1
    with pytest.raises(LeaseLostError):
        store.heartbeat(run_id, lease_owner="owner")
    store.close()


@pytest.mark.parametrize("terminal", [STAGE_SUCCEEDED, STAGE_FAILED])
def test_heartbeat_rejects_completed_run(db_path: Path, terminal: str) -> None:
    store = StateStore.open(db_path)
    asset_id = _asset(store)
    run_id = store.claim_stage_run(
        asset_id=asset_id, stage_name="pose", lease_owner="owner", lease_seconds=60
    )
    store.release_run(run_id, terminal, lease_owner="owner")
    with pytest.raises(LeaseLostError) as caught:
        store.heartbeat(run_id, lease_owner="owner")
    assert caught.value.error_code == "NPI_LEASE_LOST"
    store.close()


def test_claim_and_heartbeat_reject_non_positive_lease_duration(db_path: Path) -> None:
    store = StateStore.open(db_path)
    asset_id = _asset(store)
    for lease_seconds in (0, -1):
        with pytest.raises(NpiError) as claim_error:
            store.claim_stage_run(
                asset_id=asset_id,
                stage_name=f"pose-{lease_seconds}",
                lease_owner="owner",
                lease_seconds=lease_seconds,
            )
        assert claim_error.value.error_code == NPI_SCHEMA_INVALID
    run_id = store.claim_stage_run(asset_id=asset_id, stage_name="pose", lease_owner="owner")
    for lease_seconds in (0, -1):
        with pytest.raises(NpiError) as heartbeat_error:
            store.heartbeat(run_id, lease_owner="owner", lease_seconds=lease_seconds)
        assert heartbeat_error.value.error_code == NPI_SCHEMA_INVALID
    store.close()


def test_claim_foreign_key_failure_is_not_reported_as_competition(db_path: Path) -> None:
    store = StateStore.open(db_path)
    with pytest.raises(DatabaseError) as caught:
        store.claim_stage_run(asset_id="missing", stage_name="pose", lease_owner="owner")
    assert not isinstance(caught.value, StageClaimConflictError)
    assert caught.value.error_code == "NPI_DATABASE_ERROR"
    assert caught.value.__cause__ is None
    store.close()


def test_retry_ceiling_transitions_to_failed_and_stays_bounded(db_path: Path) -> None:
    store = StateStore.open(db_path)
    asset_id = _asset(store)
    assert (
        store.record_retry(
            asset_id,
            error_code="NPI_MODEL_TIMEOUT",
            error_redacted="synthetic retry",
        )
        == 1
    )
    assert store.get_asset(asset_id)["current_state"] == "RETRY"
    assert (
        store.record_retry(
            asset_id,
            error_code="NPI_MODEL_TIMEOUT",
            error_redacted="synthetic retry",
        )
        == 2
    )
    assert store.get_asset(asset_id)["current_state"] == "FAILED"
    assert store.get_asset(asset_id)["last_error_code"] == NPI_RETRY_EXHAUSTED
    assert "prior_error_code=NPI_MODEL_TIMEOUT" in store.get_asset(asset_id)["last_error_redacted"]
    with pytest.raises(RetryExhaustedError):
        store.record_retry(
            asset_id,
            error_code="NPI_MODEL_TIMEOUT",
            error_redacted="synthetic retry",
        )
    assert store.get_asset(asset_id)["retry_count"] == 2
    store.close()


def test_retry_limit_is_loaded_from_versioned_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    policy_path = config_dir / "retry_policy_v1_1.yaml"
    policy_path.write_text(
        "schema_version: '1.1'\n"
        "defaults:\n  max_attempts: 3\n"
        "errors:\n"
        "  TEST:\n"
        "    retry: true\n"
        "    max_attempts: 1\n"
        "    error_codes: ['NPI_MODEL_TIMEOUT']\n",
        encoding="utf-8",
    )
    import nightly_photo_intelligence_pipeline.persistence.sqlite as sqlite_module

    monkeypatch.setattr(sqlite_module, "find_project_root", lambda: tmp_path)
    monkeypatch.setattr(
        sqlite_module,
        "_RETRY_POLICY_SHA256",
        hashlib.sha256(policy_path.read_bytes()).hexdigest(),
    )
    store = StateStore.open(tmp_path / "state.sqlite")
    asset_id = _asset(store)
    assert (
        store.record_retry(
            asset_id,
            error_code="NPI_MODEL_TIMEOUT",
            error_redacted="synthetic retry",
        )
        == 1
    )
    asset = store.get_asset(asset_id)
    assert asset["current_state"] == "FAILED"
    assert asset["retry_count"] == 1
    assert asset["last_error_code"] == NPI_RETRY_EXHAUSTED
    store.close()


def test_retry_policy_hash_tamper_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "retry_policy_v1_1.yaml").write_text(
        "schema_version: '1.1'\ndefaults:\n  max_attempts: 99\nerrors: {}\n",
        encoding="utf-8",
    )
    import nightly_photo_intelligence_pipeline.persistence.sqlite as sqlite_module

    monkeypatch.setattr(sqlite_module, "find_project_root", lambda: tmp_path)
    with pytest.raises(NpiError, match="integrity"):
        StateStore.open(tmp_path / "state.sqlite")


def test_unknown_future_migration_fails_closed_before_schema_stamp(tmp_path: Path) -> None:
    db_path = tmp_path / "state.sqlite"
    store = StateStore.open(db_path)
    before_version = store.schema_version()
    store.connection.execute(
        "INSERT INTO migration_history(migration_id, description, applied_at) "
        "VALUES('v999', 'synthetic future migration', '2099-01-01T00:00:00Z')"
    )
    store.connection.commit()
    store.close()

    with pytest.raises(DatabaseError) as caught:
        StateStore.open(db_path)
    assert caught.value.error_code == "NPI_DATABASE_ERROR"
    assert caught.value.__cause__ is None
    conn = sqlite3.connect(db_path)
    try:
        after_version = conn.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert after_version == before_version


def test_retry_last_error_is_fail_closed_redacted(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.sqlite")
    asset_id = _asset(store)
    sensitive = (
        "C:\\private\\source\\real-photo.jpg "
        "\\\\host\\share\\secret.png "
        "/mnt/c/private/source/hidden.heic "
        "毕业季真实文件名.jpeg"
    )
    store.record_retry(
        asset_id,
        error_code="NPI_MODEL_TIMEOUT",
        error_redacted=sensitive,
    )
    pending_run = store.insert_stage_run(asset_id=asset_id, stage_name="synthetic")
    store.update_stage_run_status(
        pending_run,
        STAGE_SKIPPED,
        error_code="NPI_INTERNAL_ERROR",
        error_redacted=sensitive,
    )
    stage_error = store.connection.execute(
        "SELECT error_redacted FROM stage_runs WHERE stage_run_id=?", (pending_run,)
    ).fetchone()[0]
    stored_values = (str(store.get_asset(asset_id)["last_error_redacted"]), str(stage_error))
    for forbidden in (
        "C:\\private",
        "host",
        "/mnt/c",
        "real-photo.jpg",
        "secret.png",
        "hidden.heic",
        "毕业季真实文件名.jpeg",
    ):
        assert all(forbidden not in stored for stored in stored_values)
    store.close()


def test_stage_error_codes_reject_paths_and_filenames(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.sqlite")
    asset_id = _asset(store)
    pending = store.insert_stage_run(asset_id=asset_id, stage_name="synthetic")
    running = store.claim_stage_run(
        asset_id=asset_id,
        stage_name="running",
        lease_owner="owner",
    )
    for unsafe in ("C:\\private\\real name.jpg", "真实 姓名.jpg", "/mnt/f/private/a.jpg"):
        with pytest.raises(NpiError) as update_error:
            store.update_stage_run_status(
                pending,
                STAGE_SKIPPED,
                error_code=unsafe,
                error_redacted="synthetic",
            )
        assert update_error.value.error_code == NPI_SCHEMA_INVALID
        with pytest.raises(NpiError) as release_error:
            store.release_run(
                running,
                STAGE_FAILED,
                lease_owner="owner",
                error_code=unsafe,
                error_redacted="synthetic",
            )
        assert release_error.value.error_code == NPI_SCHEMA_INVALID
    assert (
        store.connection.execute(
            "SELECT error_code FROM stage_runs WHERE stage_run_id=?", (pending,)
        ).fetchone()[0]
        is None
    )
    assert (
        store.connection.execute(
            "SELECT status FROM stage_runs WHERE stage_run_id=?", (running,)
        ).fetchone()[0]
        == "RUNNING"
    )
    store.close()


def test_non_retryable_and_unknown_errors_fail_closed(tmp_path: Path) -> None:
    store = StateStore.open(tmp_path / "state.sqlite")
    non_retryable_asset = _asset(store)
    assert (
        store.record_retry(
            non_retryable_asset,
            error_code="NPI_SOURCE_CHANGED_DURING_READ",
            error_redacted="source integrity changed",
        )
        == 0
    )
    terminal = store.get_asset(non_retryable_asset)
    assert terminal["current_state"] == "FAILED"
    assert terminal["retry_count"] == 0
    assert terminal["last_error_code"] == "NPI_SOURCE_CHANGED_DURING_READ"

    unknown_asset = _asset(store, "b")
    with pytest.raises(NpiError) as caught:
        store.record_retry(
            unknown_asset,
            error_code="NPI_UNKNOWN_RETRY",
            error_redacted="unknown",
        )
    assert caught.value.error_code == NPI_SCHEMA_INVALID
    assert store.get_asset(unknown_asset)["retry_count"] == 0
    assert store.get_asset(unknown_asset)["current_state"] == "INGESTED"
    store.close()


def test_two_recoveries_only_one_reports_reclaimed(db_path: Path) -> None:
    seed = StateStore.open(db_path)
    asset_id = _asset(seed)
    run_id = seed.claim_stage_run(
        asset_id=asset_id, stage_name="pose", lease_owner="owner", lease_seconds=60
    )
    seed.connection.execute(
        "UPDATE stage_runs SET lease_expires_at=? WHERE stage_run_id=?", (_past(), run_id)
    )
    seed.close()
    stores = [StateStore.open(db_path, initialize=False) for _ in range(2)]
    barrier = Barrier(2)

    def recover(index: int) -> int:
        barrier.wait(timeout=5)
        return stores[index].recover_interrupted_runs()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(recover, range(2)))
    assert sorted(results) == [0, 1]
    row = (
        stores[0]
        .connection.execute(
            "SELECT status, duration_ms, lease_owner, lease_expires_at FROM stage_runs "
            "WHERE stage_run_id=?",
            (run_id,),
        )
        .fetchone()
    )
    assert row["status"] == STAGE_INTERRUPTED
    assert int(row["duration_ms"]) >= 0
    assert row["lease_owner"] is None and row["lease_expires_at"] is None
    for store in stores:
        store.close()


@pytest.mark.parametrize("terminal", [STAGE_SUCCEEDED, STAGE_FAILED])
def test_release_is_owned_atomic_and_records_duration(db_path: Path, terminal: str) -> None:
    seed = StateStore.open(db_path)
    asset_id = _asset(seed)
    run_id = seed.claim_stage_run(
        asset_id=asset_id, stage_name="pose", lease_owner="owner", lease_seconds=60
    )
    seed.close()
    stores = [StateStore.open(db_path, initialize=False) for _ in range(2)]
    barrier = Barrier(2)

    def release(index: int) -> str:
        barrier.wait(timeout=5)
        owner = "owner" if index == 0 else "other"
        try:
            stores[index].release_run(run_id, terminal, lease_owner=owner)
            return "success"
        except LeaseLostError as exc:
            return exc.error_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(release, range(2)))
    assert sorted(results) == ["NPI_LEASE_LOST", "success"]
    row = (
        stores[0]
        .connection.execute(
            "SELECT status, finished_at, duration_ms, lease_owner, lease_expires_at "
            "FROM stage_runs WHERE stage_run_id=?",
            (run_id,),
        )
        .fetchone()
    )
    assert row["status"] == terminal and row["finished_at"] is not None
    assert int(row["duration_ms"]) >= 0
    assert row["lease_owner"] is None and row["lease_expires_at"] is None
    with pytest.raises(LeaseLostError):
        stores[0].release_run(run_id, terminal, lease_owner="owner")
    for store in stores:
        store.close()


def test_nested_transaction_rollback_and_restart_consistency(db_path: Path) -> None:
    store = StateStore.open(db_path)
    with pytest.raises(RuntimeError), store.transaction():
        _asset(store, "z")
        raise RuntimeError("synthetic rollback")
    assert store.asset_count() == 0
    asset_id = _asset(store, "y")
    run_id = store.claim_stage_run(
        asset_id=asset_id, stage_name="pose", lease_owner="owner", lease_seconds=60
    )
    store.release_run(run_id, STAGE_SUCCEEDED, lease_owner="owner")
    store.close()

    reopened = StateStore.open(db_path, initialize=False)
    assert reopened.schema_version() == "3"
    row = reopened.connection.execute(
        "SELECT status, duration_ms FROM stage_runs WHERE stage_run_id=?", (run_id,)
    ).fetchone()
    assert row["status"] == STAGE_SUCCEEDED
    assert int(row["duration_ms"]) >= 0
    reopened.close()


def test_v1_database_migrates_expired_running_lease_to_v2(db_path: Path) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
        ("v0", "synthetic v1 baseline", now),
    )
    conn.execute(
        "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
        ("v1", "synthetic v1 baseline", now),
    )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '1')")
    conn.execute(
        "INSERT INTO assets(asset_id, source_sha256, sanitized_source_name, current_state, "
        "created_at, updated_at) VALUES(?,?,?,?,?,?)",
        ("asset-v1", "a" * 64, "synthetic", "INGESTED", now, now),
    )
    conn.execute(
        "INSERT INTO stage_runs(stage_run_id, asset_id, stage_name, status, attempt, "
        "started_at, lease_owner, lease_expires_at, heartbeat_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            "run-v1",
            "asset-v1",
            "pose",
            "RUNNING",
            1,
            _past(10),
            "old-worker",
            _past(5),
            _past(6),
        ),
    )
    conn.close()

    migrated = StateStore.open(db_path)
    assert migrated.schema_version() == "3"
    assert migrated.applied_migrations() == ["v0", "v1", "v2", "v3"]
    row = migrated.connection.execute(
        "SELECT status, duration_ms, lease_owner, lease_expires_at FROM stage_runs "
        "WHERE stage_run_id='run-v1'"
    ).fetchone()
    assert row["status"] == STAGE_INTERRUPTED
    assert int(row["duration_ms"]) >= 0
    assert row["lease_owner"] is None and row["lease_expires_at"] is None
    migrated.claim_stage_run(asset_id="asset-v1", stage_name="pose", lease_owner="new-worker")
    with pytest.raises(StageClaimConflictError):
        migrated.claim_stage_run(
            asset_id="asset-v1", stage_name="pose", lease_owner="second-worker"
        )
    migrated.close()


@pytest.mark.parametrize(
    "missing_field", ["started_at", "lease_owner", "lease_expires_at", "heartbeat_at"]
)
def test_v1_database_recovers_running_run_with_incomplete_lease(
    db_path: Path, missing_field: str
) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
        ("v0", "synthetic v1 baseline", now),
    )
    conn.execute(
        "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
        ("v1", "synthetic v1 baseline", now),
    )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '1')")
    conn.execute(
        "INSERT INTO assets(asset_id, source_sha256, sanitized_source_name, current_state, "
        "created_at, updated_at) VALUES(?,?,?,?,?,?)",
        ("asset-v1", "a" * 64, "synthetic", "INGESTED", now, now),
    )
    fields: dict[str, str | None] = {
        "started_at": now,
        "lease_owner": "old-worker",
        "lease_expires_at": future,
        "heartbeat_at": now,
    }
    fields[missing_field] = None
    conn.execute(
        "INSERT INTO stage_runs(stage_run_id, asset_id, stage_name, status, attempt, "
        "started_at, lease_owner, lease_expires_at, heartbeat_at) VALUES(?,?,?,?,?,?,?,?,?)",
        (
            "run-v1",
            "asset-v1",
            "pose",
            "RUNNING",
            1,
            fields["started_at"],
            fields["lease_owner"],
            fields["lease_expires_at"],
            fields["heartbeat_at"],
        ),
    )
    conn.close()

    migrated = StateStore.open(db_path)
    row = migrated.connection.execute(
        "SELECT status, error_code, lease_owner, lease_expires_at FROM stage_runs "
        "WHERE stage_run_id='run-v1'"
    ).fetchone()
    assert row["status"] == STAGE_INTERRUPTED
    assert row["error_code"] == "NPI_RUN_INTERRUPTED"
    assert row["lease_owner"] is None and row["lease_expires_at"] is None
    migrated.close()


def test_error_taxonomy_exactly_matches_domain_error_codes(project_root: Path) -> None:
    taxonomy_v11 = yaml.safe_load(
        (project_root / "config/error_taxonomy_v1_1.yaml").read_text(encoding="utf-8")
    )
    taxonomy_v12 = yaml.safe_load(
        (project_root / "config/error_taxonomy_v1_2.yaml").read_text(encoding="utf-8")
    )
    taxonomy_v13 = yaml.safe_load(
        (project_root / "config/error_taxonomy_v1_3.yaml").read_text(encoding="utf-8")
    )
    configured = {**taxonomy_v11["errors"], **taxonomy_v12["errors"], **taxonomy_v13["errors"]}
    assert set(configured) == set(ERROR_CODE_TO_EXIT)
    assert {code: int(spec["exit_code"]) for code, spec in configured.items()} == {
        code: int(exit_code) for code, exit_code in ERROR_CODE_TO_EXIT.items()
    }


def test_v2_database_upgrades_atomically_to_v3_with_legal_codes(db_path: Path) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    apply_schema_v2(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for migration_id in ("v0", "v1", "v2"):
        conn.execute(
            "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
            (migration_id, "synthetic v2 baseline", now),
        )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '2')")
    conn.execute(
        "INSERT INTO assets(asset_id, source_sha256, sanitized_source_name, current_state, "
        "last_error_code, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
        ("asset-v2", "a" * 64, "synthetic", "INGESTED", "NPI_MODEL_TIMEOUT", now, now),
    )
    conn.execute(
        "INSERT INTO stage_runs(stage_run_id, asset_id, stage_name, status, attempt, "
        "error_code) VALUES(?,?,?,?,?,?)",
        ("run-v2", "asset-v2", "synthetic", "FAILED", 1, "NPI_INTERNAL_ERROR"),
    )
    conn.close()

    migrated = StateStore.open(db_path)
    assert migrated.schema_version() == "3"
    assert migrated.applied_migrations() == ["v0", "v1", "v2", "v3"]
    assert migrated.table_exists("error_code_catalog")
    assert (
        migrated.connection.execute("SELECT COUNT(*) FROM error_code_catalog").fetchone()[0] == 23
    )
    assert migrated.get_asset("asset-v2")["last_error_code"] == "NPI_MODEL_TIMEOUT"
    migrated.close()


def test_v3_migration_rolls_back_atomically_for_uncataloged_v2_data(db_path: Path) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    apply_schema_v2(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for migration_id in ("v0", "v1", "v2"):
        conn.execute(
            "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
            (migration_id, "synthetic v2 baseline", now),
        )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '2')")
    conn.execute(
        "INSERT INTO assets(asset_id, source_sha256, sanitized_source_name, current_state, "
        "last_error_code, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
        ("asset-v2", "a" * 64, "synthetic", "INGESTED", "真实文件名.jpg", now, now),
    )

    with pytest.raises(sqlite3.IntegrityError, match="NPI_ERROR_CODE_NOT_CATALOGED"):
        run_migrations(conn)

    assert (
        conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "2"
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM migration_history WHERE migration_id='v3'").fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='error_code_catalog'"
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' "
            "AND name LIKE 'trg_%_error_code_%cataloged'"
        ).fetchone()[0]
        == 0
    )
    conn.close()


@pytest.mark.parametrize(
    "unsafe",
    (
        r"C:\private\real-photo.jpg",
        r"\\server\share\secret.png",
        "/mnt/c/private/hidden.heic",
        "真实姓名.jpeg",
        "NPI_NOT_IN_FIXED_CATALOG",
    ),
)
def test_v3_database_guards_reject_direct_connection_bypass(db_path: Path, unsafe: str) -> None:
    store = StateStore.open(db_path)
    asset_id = _asset(store)
    run_id = store.insert_stage_run(asset_id=asset_id, stage_name="synthetic")
    conn = store.connection

    with pytest.raises(sqlite3.IntegrityError, match="NPI_ERROR_CODE_NOT_CATALOGED"):
        conn.execute("UPDATE assets SET last_error_code=? WHERE asset_id=?", (unsafe, asset_id))
    with pytest.raises(sqlite3.IntegrityError, match="NPI_ERROR_CODE_NOT_CATALOGED"):
        conn.execute("UPDATE stage_runs SET error_code=? WHERE stage_run_id=?", (unsafe, run_id))
    with pytest.raises(sqlite3.IntegrityError, match="NPI_ERROR_CODE_NOT_CATALOGED"):
        conn.execute(
            "INSERT INTO assets(asset_id, source_sha256, sanitized_source_name, current_state, "
            "last_error_code, created_at, updated_at) VALUES(?,?,?,?,?,?,?)",
            (
                "unsafe-asset",
                "f" * 64,
                "synthetic",
                "NEW",
                unsafe,
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            ),
        )
    with pytest.raises(sqlite3.IntegrityError, match="NPI_ERROR_CODE_NOT_CATALOGED"):
        conn.execute(
            "INSERT INTO stage_runs(stage_run_id, asset_id, stage_name, status, attempt, "
            "error_code) VALUES(?,?,?,?,?,?)",
            ("unsafe-run", asset_id, "synthetic", "FAILED", 1, unsafe),
        )
    with pytest.raises(sqlite3.IntegrityError, match="NPI_ERROR_CODE_CATALOG_IMMUTABLE"):
        conn.execute(
            "INSERT INTO error_code_catalog(error_code, catalog_version) VALUES(?, 'v3')",
            (unsafe,),
        )

    assert store.get_asset(asset_id)["last_error_code"] is None
    assert (
        conn.execute(
            "SELECT error_code FROM stage_runs WHERE stage_run_id=?", (run_id,)
        ).fetchone()[0]
        is None
    )
    store.close()


def test_v3_catalog_preserves_all_legal_codes_and_migration_restart(db_path: Path) -> None:
    store = StateStore.open(db_path)
    asset_id = _asset(store)
    run_id = store.insert_stage_run(asset_id=asset_id, stage_name="synthetic")
    codes = [
        str(row[0])
        for row in store.connection.execute(
            "SELECT error_code FROM error_code_catalog ORDER BY error_code"
        ).fetchall()
    ]
    for code in codes:
        store.connection.execute(
            "UPDATE assets SET last_error_code=? WHERE asset_id=?", (code, asset_id)
        )
        store.connection.execute(
            "UPDATE stage_runs SET error_code=? WHERE stage_run_id=?", (code, run_id)
        )

    store.connection.execute("DELETE FROM migration_history WHERE migration_id='v3'")
    store.connection.execute("UPDATE metadata SET value='2' WHERE key='schema_version'")
    assert run_migrations(store.connection) == "3"
    assert run_migrations(store.connection) == "3"
    assert store.applied_migrations() == ["v0", "v1", "v2", "v3"]
    assert (
        store.connection.execute(
            "SELECT COUNT(*) FROM migration_history WHERE migration_id='v3'"
        ).fetchone()[0]
        == 1
    )
    assert store.connection.execute("SELECT COUNT(*) FROM error_code_catalog").fetchone()[0] == 23
    store.close()


@pytest.mark.parametrize(
    ("object_type", "object_name"),
    (
        ("index", "uq_stage_runs_one_running"),
        ("trigger", "trg_stage_runs_running_insert_requires_lease"),
        ("trigger", "trg_stage_runs_running_update_requires_lease"),
    ),
)
def test_forged_v2_history_fails_closed_when_schema_object_is_missing(
    db_path: Path, object_type: str, object_name: str
) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    apply_schema_v2(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for migration_id in ("v0", "v1", "v2"):
        conn.execute(
            "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
            (migration_id, "forged history", now),
        )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '2')")
    conn.execute(f"DROP {object_type.upper()} {object_name}")

    with pytest.raises(sqlite3.IntegrityError, match="NPI_MIGRATION_INTEGRITY_FAILED"):
        run_migrations(conn)

    assert (
        conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "2"
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM migration_history WHERE migration_id='v3'").fetchone()[0]
        == 0
    )
    conn.close()


def test_forged_v3_history_fails_closed_when_catalog_is_missing(db_path: Path) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    apply_schema_v2(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for migration_id in ("v0", "v1", "v2", "v3"):
        conn.execute(
            "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
            (migration_id, "forged history", now),
        )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '2')")

    with pytest.raises(sqlite3.IntegrityError, match="NPI_MIGRATION_INTEGRITY_FAILED"):
        run_migrations(conn)

    assert (
        conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "2"
    )
    conn.close()


@pytest.mark.parametrize(
    "trigger_name",
    (
        "trg_assets_error_code_insert_cataloged",
        "trg_assets_error_code_update_cataloged",
        "trg_stage_runs_error_code_insert_cataloged",
        "trg_stage_runs_error_code_update_cataloged",
        "trg_error_code_catalog_insert_immutable",
        "trg_error_code_catalog_update_immutable",
        "trg_error_code_catalog_delete_immutable",
    ),
)
def test_forged_v3_history_fails_closed_when_guard_is_missing(
    db_path: Path, trigger_name: str
) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    apply_schema_v2(conn)
    apply_schema_v3(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for migration_id in ("v0", "v1", "v2", "v3"):
        conn.execute(
            "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
            (migration_id, "forged history", now),
        )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '2')")
    conn.execute(f"DROP TRIGGER {trigger_name}")

    with pytest.raises(sqlite3.IntegrityError, match="NPI_MIGRATION_INTEGRITY_FAILED"):
        run_migrations(conn)

    assert (
        conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "2"
    )
    conn.close()


def test_forged_v3_history_fails_closed_for_same_name_trigger_tampering(
    db_path: Path,
) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    run_migrations(conn)
    conn.execute("UPDATE metadata SET value='2' WHERE key='schema_version'")
    conn.execute("DROP TRIGGER trg_assets_error_code_insert_cataloged")
    conn.execute(
        "CREATE TRIGGER trg_assets_error_code_insert_cataloged "
        "BEFORE INSERT ON assets BEGIN SELECT RAISE(ABORT, 'FORGED'); END"
    )

    with pytest.raises(sqlite3.IntegrityError, match="NPI_MIGRATION_INTEGRITY_FAILED"):
        run_migrations(conn)

    assert (
        conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "2"
    )
    conn.close()


@pytest.mark.parametrize("mutation", ("missing", "extra"))
def test_forged_v3_history_fails_closed_for_tampered_catalog(db_path: Path, mutation: str) -> None:
    conn = sqlite3.connect(db_path, isolation_level=None)
    apply_schema_v0(conn)
    apply_schema_v1(conn)
    apply_schema_v2(conn)
    apply_schema_v3(conn)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for migration_id in ("v0", "v1", "v2", "v3"):
        conn.execute(
            "INSERT INTO migration_history(migration_id, description, applied_at) VALUES(?,?,?)",
            (migration_id, "forged history", now),
        )
    conn.execute("INSERT INTO metadata(key, value) VALUES('schema_version', '2')")

    operation = "delete" if mutation == "missing" else "insert"
    immutable_trigger = f"trg_error_code_catalog_{operation}_immutable"
    trigger_sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",
        (immutable_trigger,),
    ).fetchone()[0]
    conn.execute(f"DROP TRIGGER {immutable_trigger}")
    if mutation == "missing":
        conn.execute("DELETE FROM error_code_catalog WHERE error_code='NPI_MODEL_TIMEOUT'")
    else:
        conn.execute(
            "INSERT INTO error_code_catalog(error_code, catalog_version) VALUES(?, 'v3')",
            ("NPI_NOT_IN_FIXED_CATALOG",),
        )
    conn.execute(str(trigger_sql))

    with pytest.raises(sqlite3.IntegrityError, match="NPI_MIGRATION_INTEGRITY_FAILED"):
        run_migrations(conn)

    assert (
        conn.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0] == "2"
    )
    conn.close()
