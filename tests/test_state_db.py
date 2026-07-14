"""AT-N0-DB-01: SQLite schema/reopen. AT-N0-STATE-01: invalid transitions
rejected. AT-N0-REC-01: interrupted run is recoverable."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nightly_photo_intelligence_pipeline.domain.errors import NpiError
from nightly_photo_intelligence_pipeline.domain.states import AssetState, InvalidTransitionError
from nightly_photo_intelligence_pipeline.persistence.sqlite import (
    STAGE_INTERRUPTED,
    STAGE_RUNNING,
    StateStore,
)

pytestmark = pytest.mark.acceptance


def _utc_past(hours: int = 1) -> str:
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="seconds")


def test_at_n0_db_01_schema_created_and_reopens(db_path: Path) -> None:
    """AT-N0-DB-01: schema is created with FK on; reopen preserves data.

    N1 phase-boundary adjustment: the migration runner now stamps schema
    version '1' (N1 migration_history + duplicate_candidates applied on top of
    the N0 v0 schema). Audit strength is unchanged (still verifies schema
    version, FK, reopen, transaction rollback).
    """
    store = StateStore.open(db_path, journal_mode_candidate="WAL")
    assert store.schema_version() == "3"
    assert store.journal_mode == "DELETE", "N0 must not adopt WAL; DELETE is the safe baseline"
    for table in (
        "metadata",
        "assets",
        "asset_sources",
        "stage_runs",
        "state_transitions",
        "outputs",
    ):
        assert store.table_exists(table), f"missing table {table}"
    # Foreign keys must be enabled.
    fk = store.connection.execute("PRAGMA foreign_keys").fetchone()[0]
    assert int(fk) == 1
    aid = store.insert_asset(
        source_sha256="a" * 64, sanitized_source_name="x.png", media_type="image/png"
    )
    assert store.asset_count() == 1
    store.close()

    # Reopen without re-initializing; data must persist.
    store2 = StateStore.open(db_path, initialize=False)
    assert store2.schema_version() == "3"
    assert store2.asset_count() == 1
    assert store2.get_asset(aid)["current_state"] == "NEW"
    store2.close()


def test_at_n0_db_01_pragma_baseline_delete_full_fk(db_path: Path) -> None:
    """AT-N0-DB-01: N0 SQLite baseline is journal_mode=DELETE, synchronous=FULL,
    foreign_keys=ON (no WAL without Owner-approved exception)."""
    store = StateStore.open(db_path, journal_mode_candidate="WAL")
    jm = store.connection.execute("PRAGMA journal_mode").fetchone()[0]
    sync = store.connection.execute("PRAGMA synchronous").fetchone()[0]
    fk = store.connection.execute("PRAGMA foreign_keys").fetchone()[0]
    assert str(jm).lower() == "delete", f"journal_mode must be DELETE, got {jm}"
    assert int(sync) == 2, f"synchronous must be FULL (2), got {sync}"
    assert int(fk) == 1, "foreign_keys must be ON"
    assert store.journal_mode == "DELETE"
    store.close()


def test_at_n0_db_01_transaction_rollback(db_path: Path) -> None:
    """AT-N0-DB-01: a failed transaction rolls back."""
    store = StateStore.open(db_path)
    aid = store.insert_asset(source_sha256="b" * 64, sanitized_source_name="y.png")
    try:
        with store.transaction() as conn:
            conn.execute(
                "INSERT INTO outputs (output_id, asset_id, stage_run_id, role, "
                "relative_path, media_type, sha256, size_bytes) "
                "VALUES ('o1', ?, 'nope', 'r', 'p', 'image/png', 'c', 1)",
                (aid,),
            )
    except Exception:
        pass  # FK violation (stage_run_id does not exist) -> rollback
    rows = store.connection.execute("SELECT COUNT(*) FROM outputs").fetchone()[0]
    assert int(rows) == 0, "transaction should have rolled back"
    store.close()


def test_at_n0_state_01_invalid_transitions_rejected(db_path: Path) -> None:
    """AT-N0-STATE-01: disallowed transitions raise; allowed ones succeed."""
    store = StateStore.open(db_path)
    aid = store.insert_asset(source_sha256="c" * 64, sanitized_source_name="z.png")
    # NEW -> INGESTED is allowed.
    store.record_transition(
        asset_id=aid,
        to_state=AssetState.INGESTED,
        reason_code="ok",
        actor_type="SYSTEM",
        actor_id="npi",
    )
    # INGESTED -> APPROVED is NOT allowed (skips pose/segmentation/etc).
    with pytest.raises(InvalidTransitionError):
        store.record_transition(
            asset_id=aid,
            to_state=AssetState.APPROVED,
            reason_code="skip",
            actor_type="HUMAN",
            actor_id="owner",
        )
    # APPROVED requires a HUMAN actor.
    store.record_transition(
        asset_id=aid,
        to_state=AssetState.NEEDS_REVIEW,
        reason_code="review",
        actor_type="SYSTEM",
        actor_id="npi",
    )
    with pytest.raises(NpiError):
        store.record_transition(
            asset_id=aid,
            to_state=AssetState.APPROVED,
            reason_code="approve",
            actor_type="SYSTEM",
            actor_id="npi",
        )
    store.record_transition(
        asset_id=aid,
        to_state=AssetState.APPROVED,
        reason_code="approve",
        actor_type="HUMAN",
        actor_id="owner",
    )
    assert store.get_asset(aid)["current_state"] == "APPROVED"
    # Terminal state EXPORTED has no outgoing transitions.
    store.record_transition(
        asset_id=aid,
        to_state=AssetState.EXPORTED,
        reason_code="export",
        actor_type="SYSTEM",
        actor_id="npi",
    )
    with pytest.raises(InvalidTransitionError):
        store.record_transition(
            asset_id=aid,
            to_state=AssetState.NEW,
            reason_code="rewind",
            actor_type="SYSTEM",
            actor_id="npi",
        )
    store.close()


def test_at_n0_rec_01_interrupted_run_recoverable(db_path: Path) -> None:
    """AT-N0-REC-01: a RUNNING run with an expired lease is recognized on reopen."""
    store = StateStore.open(db_path)
    aid = store.insert_asset(source_sha256="d" * 64, sanitized_source_name="r.png")
    rid = store.claim_stage_run(
        asset_id=aid, stage_name="pose", lease_owner="worker-1", lease_seconds=60
    )
    store.connection.execute(
        "UPDATE stage_runs SET started_at=?, lease_expires_at=? WHERE stage_run_id=?",
        (_utc_past(2), _utc_past(1), rid),
    )
    # While open, the interrupted run is already identifiable.
    assert len(store.identify_interrupted_runs()) == 1
    store.close()

    # Reopen: the interrupted run must be recognizable without inventing outputs.
    store2 = StateStore.open(db_path, initialize=False)
    interrupted = store2.identify_interrupted_runs()
    assert len(interrupted) == 1
    assert interrupted[0].stage_run_id == rid
    assert interrupted[0].status == STAGE_RUNNING
    # No outputs were invented.
    out_rows = store2.connection.execute("SELECT COUNT(*) FROM outputs").fetchone()[0]
    assert int(out_rows) == 0
    # Recovery marks it INTERRUPTED (does not advance asset state).
    n = store2.recover_interrupted_runs()
    assert n == 1
    runs = store2.recent_stage_runs()
    assert runs[0].status == STAGE_INTERRUPTED
    # Asset state is unchanged (still NEW; no fabricated progression).
    assert store2.get_asset(aid)["current_state"] == "NEW"
    store2.close()
