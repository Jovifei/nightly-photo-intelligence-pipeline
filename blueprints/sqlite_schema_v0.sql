-- DESIGN BASELINE ONLY. N0 implementation may refine with tests,
-- but must preserve the semantic fields and record the migration.

PRAGMA foreign_keys = ON;

CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE assets (
    asset_id TEXT PRIMARY KEY,
    source_sha256 TEXT NOT NULL,
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

CREATE INDEX idx_assets_source_sha256 ON assets(source_sha256);
CREATE INDEX idx_assets_state ON assets(current_state);

CREATE TABLE asset_sources (
    asset_source_id TEXT PRIMARY KEY,
    asset_id TEXT NOT NULL REFERENCES assets(asset_id),
    local_path_protected TEXT NOT NULL,
    observed_size_bytes INTEGER NOT NULL,
    observed_mtime_ns INTEGER,
    first_seen_at TEXT NOT NULL,
    UNIQUE(asset_id, local_path_protected)
);

CREATE TABLE stage_runs (
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

CREATE TABLE state_transitions (
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

CREATE TABLE outputs (
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
