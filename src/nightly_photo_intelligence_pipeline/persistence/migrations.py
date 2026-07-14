"""Versioned SQLite migrations for the NPI state store.

v0 = N0 baseline schema (metadata, assets, asset_sources, stage_runs,
state_transitions, outputs).
v1 = N1 additions (migration_history, duplicate_candidates) and idempotent
re-application of v0.

The runner is idempotent: re-running ``run_migrations`` is a no-op once all
migrations are recorded in ``migration_history``. Each migration step uses
``CREATE TABLE IF NOT EXISTS`` so partial application is safe to retry.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

SCHEMA_VERSION = "1"
SCHEMA_VERSION_KEY = "schema_version"

_SCHEMA_V0 = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL UNIQUE,
    perceptual_hash TEXT,
    perceptual_hash_algorithm TEXT,
    sanitized_source_name TEXT NOT NULL,
    media_type TEXT,
    width INTEGER,
    height INTEGER,
    current_state TEXT NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0,
    last_error_code TEXT,
    last_error_redacted TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assets_source_sha256 ON assets(source_sha256);
CREATE INDEX IF NOT EXISTS idx_assets_state ON assets(current_state);

CREATE TABLE IF NOT EXISTS asset_sources (
    asset_source_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    local_path_protected TEXT NOT NULL,
    observed_size_bytes INTEGER NOT NULL,
    observed_mtime_ns INTEGER,
    first_seen_at TEXT NOT NULL,
    UNIQUE(asset_id, local_path_protected)
);

CREATE TABLE IF NOT EXISTS stage_runs (
    stage_run_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL,
    attempt INTEGER NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER,
    model_id TEXT,
    model_revision TEXT,
    prompt_version TEXT,
    schema_version TEXT,
    code_commit TEXT,
    config_hash TEXT,
    gpu_peak_vram_mb INTEGER,
    error_code TEXT,
    error_redacted TEXT,
    output_manifest_hash TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_stage_runs_status ON stage_runs(status);
CREATE INDEX IF NOT EXISTS idx_stage_runs_asset ON stage_runs(asset_id);

CREATE TABLE IF NOT EXISTS state_transitions (
    transition_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    from_state TEXT,
    to_state TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    stage_run_id TEXT REFERENCES stage_runs(stage_run_id),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_transitions_asset ON state_transitions(asset_id);

CREATE TABLE IF NOT EXISTS outputs (
    output_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    stage_run_id TEXT NOT NULL REFERENCES stage_runs(stage_run_id),
    role TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    media_type TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    schema_version TEXT,
    UNIQUE(stage_run_id, role, relative_path)
);
"""

_SCHEMA_V1 = """
-- Migration history (self-describing; created in v1 but records v0 too).
CREATE TABLE IF NOT EXISTS migration_history (
    migration_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

-- Near-duplicate (perceptual) candidates. Not auto-deleted; for human review.
CREATE TABLE IF NOT EXISTS duplicate_candidates (
    candidate_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    candidate_asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    distance REAL NOT NULL,
    algorithm_id TEXT NOT NULL,
    algorithm_version TEXT NOT NULL,
    hash_size INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(asset_id, candidate_asset_id)
);

CREATE INDEX IF NOT EXISTS idx_dup_candidates_asset ON duplicate_candidates(asset_id);
"""


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class Migration:
    migration_id: str
    description: str
    apply: Callable[[sqlite3.Connection], None]


def apply_schema_v0(conn: sqlite3.Connection) -> None:
    """Apply schema v0 to *conn* (idempotent via IF NOT EXISTS)."""
    conn.executescript(_SCHEMA_V0)


def apply_schema_v1(conn: sqlite3.Connection) -> None:
    """Apply schema v1 additions (idempotent)."""
    conn.executescript(_SCHEMA_V1)


def _migration_history_exists(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='migration_history'"
    ).fetchone()
    return row is not None


def _is_applied(conn: sqlite3.Connection, migration_id: str) -> bool:
    if not _migration_history_exists(conn):
        return False
    row = conn.execute(
        "SELECT 1 FROM migration_history WHERE migration_id = ?", (migration_id,)
    ).fetchone()
    return row is not None


def _record(conn: sqlite3.Connection, migration_id: str, description: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO migration_history (migration_id, description, applied_at) "
        "VALUES (?,?,?)",
        (migration_id, description, _utc_now_iso()),
    )


MIGRATIONS: list[Migration] = [
    Migration(
        "v0",
        "N0 baseline schema (assets, stage_runs, transitions, outputs)",
        apply_schema_v0,
    ),
    Migration("v1", "N1 migration_history + duplicate_candidates", apply_schema_v1),
]


def run_migrations(conn: sqlite3.Connection) -> str:
    """Apply all pending migrations idempotently; return the latest schema version.

    Safe to call repeatedly. ``migration_history`` is created by v1; before v1 is
    applied, the runner treats already-existing v0 tables as v0-applied so a N0
    database upgrades cleanly.
    """
    # Ensure v0 tables exist (idempotent) so the DB is never left empty.
    apply_schema_v0(conn)
    # Apply v1 (creates migration_history) so we can record history.
    apply_schema_v1(conn)

    # If v0 was applied before migration_history existed, record it now.
    _record(conn, "v0", "N0 baseline schema (pre-history, backfilled)")
    # Record/apply v1.
    if not _is_applied(conn, "v1"):
        apply_schema_v1(conn)
        _record(conn, "v1", "N1 migration_history + duplicate_candidates")
    else:
        _record(conn, "v1", "N1 migration_history + duplicate_candidates")

    # Stamp the latest schema version in metadata.
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (SCHEMA_VERSION_KEY, SCHEMA_VERSION),
    )
    conn.commit()
    return SCHEMA_VERSION


def applied_migrations(conn: sqlite3.Connection) -> list[str]:
    """Return the list of applied migration ids (empty if history absent)."""
    if not _migration_history_exists(conn):
        return []
    rows = conn.execute(
        "SELECT migration_id FROM migration_history ORDER BY migration_id"
    ).fetchall()
    return [str(r[0]) for r in rows]
