"""Schema v0 migration for the NPI SQLite state store.

The SQL is based on blueprints/sqlite_schema_v0.sql, refined with a unique
constraint on assets.source_sha256 (duplicate sources are recorded in
asset_sources) and an index on stage_runs status for recovery scans.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = "0"
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


def apply_schema_v0(conn: sqlite3.Connection) -> None:
    """Apply schema v0 to *conn* (idempotent via IF NOT EXISTS)."""
    conn.executescript(_SCHEMA_V0)
    conn.execute(
        "INSERT INTO metadata(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (SCHEMA_VERSION_KEY, SCHEMA_VERSION),
    )
    conn.commit()
