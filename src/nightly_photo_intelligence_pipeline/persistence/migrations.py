"""Versioned SQLite migrations for the NPI state store.

v0 = N0 baseline schema (metadata, assets, asset_sources, stage_runs,
state_transitions, outputs).
v1 = N1 additions (migration_history, duplicate_candidates).
v2 = exclusive RUNNING claims and mandatory lease fields.
v3 = immutable stable-error-code catalog and database enforcement triggers.

The runner is idempotent: re-running ``run_migrations`` is a no-op once all
migrations are recorded in ``migration_history``. Each migration step uses
``CREATE TABLE IF NOT EXISTS`` so partial application is safe to retry.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

SCHEMA_VERSION = "3"
SCHEMA_VERSION_KEY = "schema_version"

# This is deliberately frozen in the migration instead of loaded from mutable
# runtime configuration.  A future catalog expansion must be a new migration.
_STABLE_ERROR_CODES_V3 = (
    "NPI_CLI_USAGE_ERROR",
    "NPI_CUDA_OOM",
    "NPI_DATABASE_ERROR",
    "NPI_DISK_LOW",
    "NPI_GATE_NOT_AUTHORIZED",
    "NPI_HANDOFF_INTEGRITY_FAILED",
    "NPI_INTERNAL_ERROR",
    "NPI_INVALID_JSON",
    "NPI_LEASE_LOST",
    "NPI_MODEL_CONFLICT",
    "NPI_MODEL_TIMEOUT",
    "NPI_NETWORK_POLICY_VIOLATION",
    "NPI_PREFLIGHT_UNSATISFIED",
    "NPI_RETRY_EXHAUSTED",
    "NPI_RUN_INTERRUPTED",
    "NPI_RUNTIME_POLICY_INVALID",
    "NPI_SCHEMA_INVALID",
    "NPI_SOURCE_CHANGED_DURING_READ",
    "NPI_SOURCE_READ_ONLY_NOT_VERIFIED",
    "NPI_SOURCE_RUNTIME_OVERLAP",
    "NPI_SOURCE_SYMLINK_ESCAPE",
    "NPI_STAGE_CLAIM_CONFLICT",
    "NPI_UNSUPPORTED_MEDIA",
)

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

_SCHEMA_V2_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_stage_runs_one_running
ON stage_runs(asset_id, stage_name) WHERE status = 'RUNNING'
"""

_SCHEMA_V2_INSERT_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS trg_stage_runs_running_insert_requires_lease
BEFORE INSERT ON stage_runs
WHEN NEW.status = 'RUNNING' AND (
    NEW.started_at IS NULL OR NEW.started_at = '' OR
    NEW.lease_owner IS NULL OR NEW.lease_owner = '' OR
    NEW.lease_expires_at IS NULL OR NEW.lease_expires_at = '' OR
    NEW.heartbeat_at IS NULL OR NEW.heartbeat_at = ''
)
BEGIN
    SELECT RAISE(ABORT, 'NPI_LEASE_REQUIRED');
END;
"""

_SCHEMA_V2_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS trg_stage_runs_running_update_requires_lease
BEFORE UPDATE OF status, started_at, lease_owner, lease_expires_at, heartbeat_at ON stage_runs
WHEN NEW.status = 'RUNNING' AND (
    NEW.started_at IS NULL OR NEW.started_at = '' OR
    NEW.lease_owner IS NULL OR NEW.lease_owner = '' OR
    NEW.lease_expires_at IS NULL OR NEW.lease_expires_at = '' OR
    NEW.heartbeat_at IS NULL OR NEW.heartbeat_at = ''
)
BEGIN
    SELECT RAISE(ABORT, 'NPI_LEASE_REQUIRED');
END;
"""

_SCHEMA_V3_CATALOG = """
CREATE TABLE IF NOT EXISTS error_code_catalog (
    error_code TEXT PRIMARY KEY,
    catalog_version TEXT NOT NULL CHECK (catalog_version = 'v3')
)
"""

_SCHEMA_V3_GUARDS = (
    """
    CREATE TRIGGER IF NOT EXISTS trg_assets_error_code_insert_cataloged
    BEFORE INSERT ON assets
    WHEN NEW.last_error_code IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM error_code_catalog WHERE error_code = NEW.last_error_code
    )
    BEGIN
        SELECT RAISE(ABORT, 'NPI_ERROR_CODE_NOT_CATALOGED');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_assets_error_code_update_cataloged
    BEFORE UPDATE OF last_error_code ON assets
    WHEN NEW.last_error_code IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM error_code_catalog WHERE error_code = NEW.last_error_code
    )
    BEGIN
        SELECT RAISE(ABORT, 'NPI_ERROR_CODE_NOT_CATALOGED');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_stage_runs_error_code_insert_cataloged
    BEFORE INSERT ON stage_runs
    WHEN NEW.error_code IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM error_code_catalog WHERE error_code = NEW.error_code
    )
    BEGIN
        SELECT RAISE(ABORT, 'NPI_ERROR_CODE_NOT_CATALOGED');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_stage_runs_error_code_update_cataloged
    BEFORE UPDATE OF error_code ON stage_runs
    WHEN NEW.error_code IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM error_code_catalog WHERE error_code = NEW.error_code
    )
    BEGIN
        SELECT RAISE(ABORT, 'NPI_ERROR_CODE_NOT_CATALOGED');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_error_code_catalog_insert_immutable
    BEFORE INSERT ON error_code_catalog
    BEGIN
        SELECT RAISE(ABORT, 'NPI_ERROR_CODE_CATALOG_IMMUTABLE');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_error_code_catalog_update_immutable
    BEFORE UPDATE ON error_code_catalog
    BEGIN
        SELECT RAISE(ABORT, 'NPI_ERROR_CODE_CATALOG_IMMUTABLE');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS trg_error_code_catalog_delete_immutable
    BEFORE DELETE ON error_code_catalog
    BEGIN
        SELECT RAISE(ABORT, 'NPI_ERROR_CODE_CATALOG_IMMUTABLE');
    END
    """,
)

_SCHEMA_V3_GUARD_NAMES = (
    "trg_assets_error_code_insert_cataloged",
    "trg_assets_error_code_update_cataloged",
    "trg_stage_runs_error_code_insert_cataloged",
    "trg_stage_runs_error_code_update_cataloged",
    "trg_error_code_catalog_insert_immutable",
    "trg_error_code_catalog_update_immutable",
    "trg_error_code_catalog_delete_immutable",
)


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


def apply_schema_v2(conn: sqlite3.Connection) -> None:
    """Recover invalid expired leases, then install exclusive-claim constraints."""
    now = _utc_now_iso()
    conn.execute(
        "UPDATE stage_runs SET status='INTERRUPTED', finished_at=?, "
        "duration_ms=CASE WHEN started_at IS NULL THEN 0 ELSE "
        "MAX(0, CAST((julianday(?) - julianday(started_at)) * 86400000 AS INTEGER)) END, "
        "error_code='NPI_RUN_INTERRUPTED', error_redacted='lease expired during migration', "
        "lease_owner=NULL, lease_expires_at=NULL "
        "WHERE status='RUNNING' AND ("
        "started_at IS NULL OR started_at='' OR lease_owner IS NULL OR lease_owner='' OR "
        "lease_expires_at IS NULL OR lease_expires_at='' OR heartbeat_at IS NULL OR "
        "heartbeat_at='' OR lease_expires_at <= ?)",
        (now, now, now),
    )
    duplicate = conn.execute(
        "SELECT 1 FROM stage_runs WHERE status='RUNNING' "
        "GROUP BY asset_id, stage_name HAVING COUNT(*) > 1 LIMIT 1"
    ).fetchone()
    if duplicate is not None:
        raise sqlite3.IntegrityError("NPI_DUPLICATE_RUNNING_CLAIM")
    conn.execute(_SCHEMA_V2_INDEX)
    conn.execute(_SCHEMA_V2_INSERT_TRIGGER)
    conn.execute(_SCHEMA_V2_UPDATE_TRIGGER)


def apply_schema_v3(conn: sqlite3.Connection) -> None:
    """Install the frozen stable-error-code catalog and write guards."""
    conn.execute(_SCHEMA_V3_CATALOG)
    existing_rows = conn.execute(
        "SELECT error_code, catalog_version FROM error_code_catalog"
    ).fetchall()
    existing = {(str(row[0]), str(row[1])) for row in existing_rows}
    expected = {(code, "v3") for code in _STABLE_ERROR_CODES_V3}
    unexpected = existing - expected
    if unexpected:
        raise sqlite3.IntegrityError("NPI_ERROR_CODE_CATALOG_INVALID")
    missing = sorted(expected - existing)
    conn.executemany(
        "INSERT INTO error_code_catalog(error_code, catalog_version) VALUES(?, ?)",
        missing,
    )

    invalid_asset = conn.execute(
        "SELECT 1 FROM assets AS a WHERE a.last_error_code IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM error_code_catalog AS c "
        "WHERE c.error_code = a.last_error_code) LIMIT 1"
    ).fetchone()
    invalid_run = conn.execute(
        "SELECT 1 FROM stage_runs AS r WHERE r.error_code IS NOT NULL "
        "AND NOT EXISTS (SELECT 1 FROM error_code_catalog AS c "
        "WHERE c.error_code = r.error_code) LIMIT 1"
    ).fetchone()
    if invalid_asset is not None or invalid_run is not None:
        raise sqlite3.IntegrityError("NPI_ERROR_CODE_NOT_CATALOGED")

    for statement in _SCHEMA_V3_GUARDS:
        conn.execute(statement)


def _normalized_ddl(sql: str) -> str:
    normalized = " ".join(sql.strip().rstrip(";").split()).casefold()
    return normalized.replace(" if not exists ", " ")


def _require_schema_object(
    conn: sqlite3.Connection,
    *,
    object_type: str,
    name: str,
    expected_sql: str,
) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type=? AND name=?", (object_type, name)
    ).fetchone()
    if row is None or row[0] is None:
        raise sqlite3.IntegrityError("NPI_MIGRATION_INTEGRITY_FAILED")
    if _normalized_ddl(str(row[0])) != _normalized_ddl(expected_sql):
        raise sqlite3.IntegrityError("NPI_MIGRATION_INTEGRITY_FAILED")


def verify_schema_v2(conn: sqlite3.Connection) -> None:
    """Fail closed unless every v2 index/trigger matches its frozen DDL."""
    _require_schema_object(
        conn,
        object_type="index",
        name="uq_stage_runs_one_running",
        expected_sql=_SCHEMA_V2_INDEX,
    )
    _require_schema_object(
        conn,
        object_type="trigger",
        name="trg_stage_runs_running_insert_requires_lease",
        expected_sql=_SCHEMA_V2_INSERT_TRIGGER,
    )
    _require_schema_object(
        conn,
        object_type="trigger",
        name="trg_stage_runs_running_update_requires_lease",
        expected_sql=_SCHEMA_V2_UPDATE_TRIGGER,
    )


def verify_schema_v3(conn: sqlite3.Connection) -> None:
    """Fail closed unless the v3 catalog and all guards match exactly."""
    _require_schema_object(
        conn,
        object_type="table",
        name="error_code_catalog",
        expected_sql=_SCHEMA_V3_CATALOG,
    )
    for name, expected_sql in zip(_SCHEMA_V3_GUARD_NAMES, _SCHEMA_V3_GUARDS, strict=True):
        _require_schema_object(
            conn,
            object_type="trigger",
            name=name,
            expected_sql=expected_sql,
        )
    actual = {
        (str(row[0]), str(row[1]))
        for row in conn.execute(
            "SELECT error_code, catalog_version FROM error_code_catalog"
        ).fetchall()
    }
    expected = {(code, "v3") for code in _STABLE_ERROR_CODES_V3}
    if actual != expected:
        raise sqlite3.IntegrityError("NPI_MIGRATION_INTEGRITY_FAILED")


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
    Migration("v2", "exclusive RUNNING claims and complete leases", apply_schema_v2),
    Migration("v3", "stable error-code catalog and database write guards", apply_schema_v3),
]


def _reject_unknown_migrations(conn: sqlite3.Connection) -> None:
    """Fail closed when a database was created by an unknown future runner."""
    known_ids = {migration.migration_id for migration in MIGRATIONS}
    rows = conn.execute("SELECT migration_id FROM migration_history").fetchall()
    if any(str(row[0]) not in known_ids for row in rows):
        raise sqlite3.IntegrityError("NPI_MIGRATION_INTEGRITY_FAILED")


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
    _reject_unknown_migrations(conn)

    # If v0 was applied before migration_history existed, record it now.
    _record(conn, "v0", "N0 baseline schema (pre-history, backfilled)")
    # Record/apply v1.
    if not _is_applied(conn, "v1"):
        apply_schema_v1(conn)
        _record(conn, "v1", "N1 migration_history + duplicate_candidates")
    else:
        _record(conn, "v1", "N1 migration_history + duplicate_candidates")

    if not _is_applied(conn, "v2"):
        conn.execute("BEGIN IMMEDIATE")
        try:
            apply_schema_v2(conn)
            verify_schema_v2(conn)
            _record(conn, "v2", "exclusive RUNNING claims and complete leases")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    else:
        verify_schema_v2(conn)

    if not _is_applied(conn, "v3"):
        conn.execute("BEGIN IMMEDIATE")
        try:
            apply_schema_v3(conn)
            verify_schema_v3(conn)
            _record(conn, "v3", "stable error-code catalog and database write guards")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    else:
        verify_schema_v3(conn)

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
