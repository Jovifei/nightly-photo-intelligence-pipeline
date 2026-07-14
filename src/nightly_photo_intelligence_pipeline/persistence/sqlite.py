"""SQLite state store with transactions, append-only history, and recovery.

N0 scope (see docs/09_data_model_and_state_machine.md and the N0 task contract):
  * schema v0 with foreign keys enabled;
  * context-managed transactions;
  * append-only state_transitions (never updated or deleted);
  * reopen/recovery: RUNNING stage runs with an expired lease are identified
    and can be marked INTERRUPTED without inventing outputs;
  * dry-run ingest never calls any write method here, so asset count is stable.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Any

import yaml

from .._paths import find_project_root
from ..domain.errors import (
    ERROR_CODE_TO_EXIT,
    NPI_RETRY_EXHAUSTED,
    NPI_RUN_INTERRUPTED,
    NPI_SCHEMA_INVALID,
    DatabaseError,
    LeaseLostError,
    NpiError,
    RetryExhaustedError,
    StageClaimConflictError,
)
from ..domain.states import AssetState, parse_state, validate_transition
from ..redaction import redact_text
from .migrations import SCHEMA_VERSION_KEY, applied_migrations, run_migrations

# stage_runs.status values.
STAGE_PENDING = "PENDING"
STAGE_RUNNING = "RUNNING"
STAGE_SUCCEEDED = "SUCCEEDED"
STAGE_FAILED = "FAILED"
STAGE_INTERRUPTED = "INTERRUPTED"
STAGE_SKIPPED = "SKIPPED"

_NEW_RUN_STATES = {
    STAGE_PENDING,
    STAGE_RUNNING,
    STAGE_SUCCEEDED,
    STAGE_FAILED,
    STAGE_INTERRUPTED,
    STAGE_SKIPPED,
}

_RETRY_POLICY_SCHEMA_VERSION = "1.1"
_RETRY_POLICY_SHA256 = "316df5c98fa81a0ae2facf8bcb3ac4914e363eedf219ee2a48f547830b2afafe"
_FILENAME_RE = re.compile(r"(?iu)(?<![<\w])[^\s\\/<>]+\.(?:jpe?g|png|heic|webp|tiff?)\b")
_NON_ASCII_RE = re.compile(r"[^\x20-\x7e]+")
_ERROR_CODE_RE = re.compile(r"^NPI_[A-Z0-9_]+$")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


def _safe_error_detail(value: str | None) -> str | None:
    """Fail closed when persisting caller-provided diagnostic text."""
    if not value:
        return None
    safe = redact_text(value)
    safe = _FILENAME_RE.sub("<REDACTED_FILENAME>", safe)
    safe = _NON_ASCII_RE.sub("<REDACTED_TEXT>", safe)
    return safe or None


def _validated_error_code(value: str | None, *, allowed: frozenset[str]) -> str | None:
    if value is None:
        return None
    if not _ERROR_CODE_RE.fullmatch(value) or value not in allowed:
        raise NpiError("error code is invalid", error_code=NPI_SCHEMA_INVALID)
    return value


@dataclass(frozen=True)
class RetryPolicy:
    """Validated, versioned retry limits loaded from the repository contract."""

    schema_version: str
    default_max_attempts: int
    limits_by_error_code: dict[str, int]
    non_retryable_error_codes: frozenset[str]

    def max_attempts_for(self, error_code: str) -> int:
        if error_code not in self.limits_by_error_code:
            raise NpiError("retry error code is not configured", error_code=NPI_SCHEMA_INVALID)
        return self.limits_by_error_code[error_code]

    def is_non_retryable(self, error_code: str) -> bool:
        if error_code in self.non_retryable_error_codes:
            return True
        if error_code in self.limits_by_error_code:
            return False
        raise NpiError("retry error code is not configured", error_code=NPI_SCHEMA_INVALID)

    @property
    def configured_error_codes(self) -> frozenset[str]:
        return frozenset(self.limits_by_error_code) | self.non_retryable_error_codes


def load_retry_policy(path: Path | str | None = None) -> RetryPolicy:
    """Load and validate the explicit retry policy without exposing its path."""
    policy_path = (
        Path(path) if path is not None else find_project_root() / "config/retry_policy_v1_1.yaml"
    )
    try:
        policy_bytes = policy_path.read_bytes()
        if hashlib.sha256(policy_bytes).hexdigest() != _RETRY_POLICY_SHA256:
            raise NpiError("retry policy integrity check failed", error_code=NPI_SCHEMA_INVALID)
        payload = yaml.safe_load(policy_bytes.decode("utf-8"))
    except NpiError:
        raise
    except (OSError, UnicodeError, yaml.YAMLError):
        raise NpiError("retry policy could not be loaded", error_code=NPI_SCHEMA_INVALID) from None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != _RETRY_POLICY_SCHEMA_VERSION
    ):
        raise NpiError("retry policy schema version is unsupported", error_code=NPI_SCHEMA_INVALID)
    defaults = payload.get("defaults")
    if not isinstance(defaults, dict):
        raise NpiError("retry policy defaults are invalid", error_code=NPI_SCHEMA_INVALID)
    default_limit = defaults.get("max_attempts")
    if not isinstance(default_limit, int) or isinstance(default_limit, bool) or default_limit < 1:
        raise NpiError("retry policy default limit is invalid", error_code=NPI_SCHEMA_INVALID)
    raw_errors = payload.get("errors", {})
    if not isinstance(raw_errors, dict):
        raise NpiError("retry policy errors are invalid", error_code=NPI_SCHEMA_INVALID)
    limits: dict[str, int] = {}
    non_retryable: set[str] = set()
    for rule in raw_errors.values():
        if not isinstance(rule, dict):
            raise NpiError("retry policy rule is invalid", error_code=NPI_SCHEMA_INVALID)
        retry = rule.get("retry")
        codes = rule.get("error_codes")
        if not isinstance(retry, bool):
            raise NpiError("retry policy retry flag is invalid", error_code=NPI_SCHEMA_INVALID)
        if (
            not isinstance(codes, list)
            or not codes
            or not all(isinstance(code, str) and _ERROR_CODE_RE.fullmatch(code) for code in codes)
        ):
            raise NpiError("retry policy error codes are invalid", error_code=NPI_SCHEMA_INVALID)
        limit = rule.get("max_attempts", default_limit)
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            raise NpiError("retry policy rule limit is invalid", error_code=NPI_SCHEMA_INVALID)
        for code in codes:
            if code in limits or code in non_retryable:
                raise NpiError(
                    "retry policy error code is duplicated", error_code=NPI_SCHEMA_INVALID
                )
            if retry:
                limits[code] = limit
            else:
                non_retryable.add(code)
    return RetryPolicy(
        schema_version=_RETRY_POLICY_SCHEMA_VERSION,
        default_max_attempts=default_limit,
        limits_by_error_code=limits,
        non_retryable_error_codes=frozenset(non_retryable),
    )


@dataclass(frozen=True)
class StageRunRecord:
    stage_run_id: str
    asset_id: str
    stage_name: str
    status: str
    attempt: int
    started_at: str | None
    lease_expires_at: str | None


@dataclass(frozen=True)
class IngestAssetResult:
    """Outcome of an idempotent ingest_asset call."""

    asset_id: str
    created: bool
    duplicate: bool  # True when the SHA already existed (exact duplicate)


def _now_plus_iso(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat(timespec="seconds")


class StateStore:
    """Thin, typed wrapper around the NPI SQLite state database."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        *,
        journal_mode: str = "DELETE",
        retry_policy: RetryPolicy,
    ) -> None:
        self._conn = conn
        self._journal_mode = journal_mode
        self._retry_policy = retry_policy
        self._known_error_codes = (
            frozenset(ERROR_CODE_TO_EXIT) | retry_policy.configured_error_codes
        )

    # ---- construction -------------------------------------------------

    @classmethod
    def open(
        cls,
        db_path: Path | str,
        *,
        busy_timeout_ms: int = 5000,
        journal_mode_candidate: str = "WAL",  # noqa: ARG002 - documented future candidate, NOT adopted in N0
        initialize: bool = True,
    ) -> StateStore:
        """Open (and by default initialize) the state store at *db_path*.

        N0 safe baseline (no Owner-approved exception to use WAL exists):
        ``journal_mode=DELETE``, ``synchronous=FULL``, ``foreign_keys=ON``,
        single writer + short transactions. ``journal_mode_candidate`` is
        accepted for API symmetry but is NOT adopted; WAL is a future candidate
        that requires a Benchmark, an ADR, and explicit Owner approval.
        """
        retry_policy = load_retry_policy()
        path = Path(db_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        except sqlite3.Error:
            raise DatabaseError("cannot open sqlite database") from None
        conn.row_factory = sqlite3.Row
        # PRAGMAs execute in autocommit (isolation_level=None).
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        # N0 baseline: DELETE journal + FULL synchronous. Do NOT adopt WAL.
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA synchronous = FULL")
        store = cls(conn, journal_mode="DELETE", retry_policy=retry_policy)
        if initialize:
            try:
                store.initialize()
            except sqlite3.Error:
                store.close()
                raise DatabaseError("sqlite initialization failed") from None
        return store

    def initialize(self) -> None:
        """Run all pending migrations (idempotent) and stamp schema version."""
        with self._conn:
            run_migrations(self._conn)

    def applied_migrations(self) -> list[str]:
        """Return the ordered list of applied migration ids."""
        return applied_migrations(self._conn)

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @property
    def journal_mode(self) -> str:
        return self._journal_mode

    def close(self) -> None:
        with suppress(sqlite3.Error):
            self._conn.close()

    def __enter__(self) -> StateStore:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # ---- introspection ------------------------------------------------

    def schema_version(self) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM metadata WHERE key = ?", (SCHEMA_VERSION_KEY,)
        ).fetchone()
        return str(row[0]) if row is not None else None

    def table_exists(self, name: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        return row is not None

    def asset_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM assets").fetchone()
        return int(row["n"])

    def count_assets_by_state(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT current_state, COUNT(*) AS n FROM assets GROUP BY current_state"
        ).fetchall()
        return {str(r["current_state"]): int(r["n"]) for r in rows}

    def recent_stage_runs(self, limit: int = 10) -> list[StageRunRecord]:
        rows = self._conn.execute(
            "SELECT stage_run_id, asset_id, stage_name, status, attempt, "
            "started_at, lease_expires_at FROM stage_runs "
            "ORDER BY started_at DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [
            StageRunRecord(
                stage_run_id=str(r["stage_run_id"]),
                asset_id=str(r["asset_id"]),
                stage_name=str(r["stage_name"]),
                status=str(r["status"]),
                attempt=int(r["attempt"]),
                started_at=str(r["started_at"]) if r["started_at"] is not None else None,
                lease_expires_at=(
                    str(r["lease_expires_at"]) if r["lease_expires_at"] is not None else None
                ),
            )
            for r in rows
        ]

    # ---- writes -------------------------------------------------------

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Yield a BEGIN IMMEDIATE transaction; nest safely with a SAVEPOINT."""
        if self._conn.in_transaction:
            savepoint = "sp_" + uuid.uuid4().hex
            self._conn.execute(f"SAVEPOINT {savepoint}")
            try:
                yield self._conn
                self._conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                self._conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                self._conn.execute(f"RELEASE SAVEPOINT {savepoint}")
                raise
            return
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError:
            raise DatabaseError("database transaction is unavailable") from None
        try:
            yield self._conn
            try:
                self._conn.commit()
            except sqlite3.OperationalError:
                self._conn.rollback()
                raise DatabaseError("database transaction could not commit") from None
        except Exception:
            self._conn.rollback()
            raise

    def insert_asset(
        self,
        *,
        asset_id: str | None = None,
        source_sha256: str,
        perceptual_hash: str | None = None,
        perceptual_hash_algorithm: str | None = None,
        sanitized_source_name: str,
        media_type: str | None = None,
        width: int | None = None,
        height: int | None = None,
        current_state: AssetState = AssetState.NEW,
    ) -> str:
        """Insert a new asset. Raises on duplicate source_sha256."""
        aid = asset_id or _new_id("asset")
        now = _utc_now_iso()
        try:
            with self.transaction() as conn:
                conn.execute(
                    "INSERT INTO assets (asset_id, source_sha256, perceptual_hash, "
                    "perceptual_hash_algorithm, sanitized_source_name, media_type, "
                    "width, height, current_state, retry_count, created_at, updated_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,0,?,?)",
                    (
                        aid,
                        source_sha256,
                        perceptual_hash,
                        perceptual_hash_algorithm,
                        sanitized_source_name,
                        media_type,
                        width,
                        height,
                        current_state.value,
                        now,
                        now,
                    ),
                )
                self._append_transition(
                    conn,
                    asset_id=aid,
                    from_state=None,
                    to_state=current_state,
                    reason_code="asset_created",
                    actor_type="SYSTEM",
                    actor_id="npi-ingest",
                    stage_run_id=None,
                )
        except sqlite3.IntegrityError:
            raise DatabaseError("asset insert constraint failed") from None
        return aid

    def _append_transition(
        self,
        conn: sqlite3.Connection,
        *,
        asset_id: str,
        from_state: AssetState | None,
        to_state: AssetState,
        reason_code: str,
        actor_type: str,
        actor_id: str,
        stage_run_id: str | None,
    ) -> None:
        """Insert a state_transitions row. Append-only: never UPDATE/DELETE."""
        conn.execute(
            "INSERT INTO state_transitions (transition_id, asset_id, from_state, "
            "to_state, reason_code, actor_type, actor_id, stage_run_id, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                _new_id("txn"),
                asset_id,
                from_state.value if from_state is not None else None,
                to_state.value,
                reason_code,
                actor_type,
                actor_id,
                stage_run_id,
                _utc_now_iso(),
            ),
        )

    def record_transition(
        self,
        *,
        asset_id: str,
        to_state: AssetState,
        reason_code: str,
        actor_type: str = "SYSTEM",
        actor_id: str = "npi",
        stage_run_id: str | None = None,
        require_human_for_approval: bool = True,
    ) -> None:
        """Validate and append a state transition; update the asset's current_state."""
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT current_state FROM assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
            if row is None:
                raise DatabaseError("asset not found")
            from_state = parse_state(str(row["current_state"]))
            if (
                to_state == AssetState.APPROVED
                and require_human_for_approval
                and actor_type != "HUMAN"
            ):
                raise NpiError(
                    "transition to APPROVED requires a HUMAN actor",
                    error_code=NPI_SCHEMA_INVALID,
                )
            validate_transition(from_state, to_state)
            self._append_transition(
                conn,
                asset_id=asset_id,
                from_state=from_state,
                to_state=to_state,
                reason_code=reason_code,
                actor_type=actor_type,
                actor_id=actor_id,
                stage_run_id=stage_run_id,
            )
            conn.execute(
                "UPDATE assets SET current_state = ?, updated_at = ? WHERE asset_id = ?",
                (to_state.value, _utc_now_iso(), asset_id),
            )

    def insert_stage_run(
        self,
        *,
        asset_id: str,
        stage_name: str,
        status: str = STAGE_PENDING,
        attempt: int = 1,
        started_at: str | None = None,
        lease_owner: str | None = None,
        lease_expires_at: str | None = None,
        schema_version: str | None = None,
        code_commit: str | None = None,
        prompt_version: str | None = None,
        stage_run_id: str | None = None,
    ) -> str:
        if status not in _NEW_RUN_STATES:
            raise NpiError(f"unknown stage run status: {status}", error_code=NPI_SCHEMA_INVALID)
        if status != STAGE_PENDING:
            raise NpiError(
                "RUNNING and terminal runs require claim/release APIs",
                error_code=NPI_SCHEMA_INVALID,
            )
        rid = stage_run_id or _new_id("run")
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO stage_runs (stage_run_id, asset_id, stage_name, status, "
                "attempt, started_at, lease_owner, lease_expires_at, schema_version, "
                "code_commit, prompt_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    rid,
                    asset_id,
                    stage_name,
                    status,
                    int(attempt),
                    started_at,
                    lease_owner,
                    lease_expires_at,
                    schema_version,
                    code_commit,
                    prompt_version,
                ),
            )
        return rid

    def update_stage_run_status(
        self,
        stage_run_id: str,
        status: str,
        *,
        finished_at: str | None = None,
        error_code: str | None = None,
        error_redacted: str | None = None,
    ) -> None:
        if status not in _NEW_RUN_STATES:
            raise NpiError(f"unknown stage run status: {status}", error_code=NPI_SCHEMA_INVALID)
        if status in {STAGE_RUNNING, STAGE_SUCCEEDED, STAGE_FAILED, STAGE_INTERRUPTED}:
            raise NpiError(
                "protected run status requires claim/release/recovery API",
                error_code=NPI_SCHEMA_INVALID,
            )
        safe_error_code = _validated_error_code(error_code, allowed=self._known_error_codes)
        with self.transaction() as conn:
            conn.execute(
                "UPDATE stage_runs SET status = ?, finished_at = ?, error_code = ?, "
                "error_redacted = ? WHERE stage_run_id = ?",
                (
                    status,
                    finished_at,
                    safe_error_code,
                    _safe_error_detail(error_redacted),
                    stage_run_id,
                ),
            )

    def insert_output(
        self,
        *,
        asset_id: str,
        stage_run_id: str,
        role: str,
        relative_path: str,
        media_type: str,
        sha256: str,
        size_bytes: int,
        schema_version: str | None = None,
        output_id: str | None = None,
    ) -> str:
        oid = output_id or _new_id("out")
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO outputs (output_id, asset_id, stage_run_id, role, "
                "relative_path, media_type, sha256, size_bytes, schema_version) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    oid,
                    asset_id,
                    stage_run_id,
                    role,
                    relative_path,
                    media_type,
                    sha256,
                    size_bytes,
                    schema_version,
                ),
            )
        return oid

    # ---- recovery -----------------------------------------------------

    def identify_interrupted_runs(self, now_iso: str | None = None) -> list[StageRunRecord]:
        """Return RUNNING stage runs whose lease has expired (or has no lease).

        Does not mutate state. Used by ``npi status`` to surface recoverable
        work and by ``npi resume`` (N1) to reclaim it.
        """
        now = now_iso or _utc_now_iso()
        rows = self._conn.execute(
            "SELECT stage_run_id, asset_id, stage_name, status, attempt, started_at, "
            "lease_expires_at FROM stage_runs WHERE status = ? "
            "AND (lease_expires_at IS NULL OR lease_expires_at < ?) "
            "ORDER BY started_at ASC",
            (STAGE_RUNNING, now),
        ).fetchall()
        return [
            StageRunRecord(
                stage_run_id=str(r["stage_run_id"]),
                asset_id=str(r["asset_id"]),
                stage_name=str(r["stage_name"]),
                status=str(r["status"]),
                attempt=int(r["attempt"]),
                started_at=str(r["started_at"]) if r["started_at"] is not None else None,
                lease_expires_at=(
                    str(r["lease_expires_at"]) if r["lease_expires_at"] is not None else None
                ),
            )
            for r in rows
        ]

    def recover_interrupted_runs(self, now_iso: str | None = None) -> int:
        """Mark expired RUNNING stage runs as INTERRUPTED. Returns count.

        Does not invent outputs or advance asset state; recovery merely flags
        the run so a later resume can reclaim it.
        """
        now = now_iso or _utc_now_iso()
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE stage_runs SET status=?, finished_at=?, "
                "duration_ms=CASE WHEN started_at IS NULL THEN 0 ELSE "
                "MAX(0, CAST((julianday(?) - julianday(started_at)) * 86400000 AS INTEGER)) END, "
                "error_code=?, error_redacted=?, lease_owner=NULL, lease_expires_at=NULL "
                "WHERE status=? AND (lease_expires_at IS NULL OR lease_expires_at <= ?)",
                (
                    STAGE_INTERRUPTED,
                    now,
                    now,
                    NPI_RUN_INTERRUPTED,
                    "lease expired during recovery",
                    STAGE_RUNNING,
                    now,
                ),
            )
            return int(cursor.rowcount)

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
        return dict(row) if row is not None else None

    def get_asset_by_sha(self, source_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM assets WHERE source_sha256 = ?", (source_sha256,)
        ).fetchone()
        return dict(row) if row is not None else None

    # ---- N1: idempotent ingest, sources, lease, retry, duplicates --------

    def add_asset_source(
        self,
        *,
        asset_id: str,
        local_path_protected: str,
        observed_size_bytes: int,
        observed_mtime_ns: int | None,
    ) -> bool:
        """Record an additional source for an asset. Returns True if newly added."""
        now = _utc_now_iso()
        cur = self._conn.execute(
            "INSERT OR IGNORE INTO asset_sources "
            "(asset_source_id, asset_id, local_path_protected, observed_size_bytes, "
            "observed_mtime_ns, first_seen_at) VALUES (?,?,?,?,?,?)",
            (
                _new_id("src"),
                asset_id,
                local_path_protected,
                observed_size_bytes,
                observed_mtime_ns,
                now,
            ),
        )
        return cur.rowcount > 0

    def ingest_asset(
        self,
        *,
        source_sha256: str,
        sanitized_source_name: str,
        local_path_protected: str,
        observed_size_bytes: int,
        observed_mtime_ns: int | None,
        perceptual_hash: str | None = None,
        perceptual_hash_algorithm: str | None = None,
        media_type: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> IngestAssetResult:
        """Idempotent real ingest.

        If an asset with the same source_sha256 already exists, this records
        the additional source (exact duplicate) and returns created=False. No
        second asset row is created; the unique-SHA invariant is preserved.
        """
        existing = self.get_asset_by_sha(source_sha256)
        if existing is not None:
            aid = str(existing["asset_id"])
            self.add_asset_source(
                asset_id=aid,
                local_path_protected=local_path_protected,
                observed_size_bytes=observed_size_bytes,
                observed_mtime_ns=observed_mtime_ns,
            )
            return IngestAssetResult(asset_id=aid, created=False, duplicate=True)
        aid = _new_id("asset")
        now = _utc_now_iso()
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO assets (asset_id, source_sha256, perceptual_hash, "
                "perceptual_hash_algorithm, sanitized_source_name, media_type, "
                "width, height, current_state, retry_count, created_at, updated_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,0,?,?)",
                (
                    aid,
                    source_sha256,
                    perceptual_hash,
                    perceptual_hash_algorithm,
                    sanitized_source_name,
                    media_type,
                    width,
                    height,
                    AssetState.INGESTED.value,
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO asset_sources "
                "(asset_source_id, asset_id, local_path_protected, observed_size_bytes, "
                "observed_mtime_ns, first_seen_at) VALUES (?,?,?,?,?,?)",
                (
                    _new_id("src"),
                    aid,
                    local_path_protected,
                    observed_size_bytes,
                    observed_mtime_ns,
                    now,
                ),
            )
            self._append_transition(
                conn,
                asset_id=aid,
                from_state=AssetState.NEW,
                to_state=AssetState.INGESTED,
                reason_code="ingested",
                actor_type="SYSTEM",
                actor_id="npi-ingest",
                stage_run_id=None,
            )
        return IngestAssetResult(asset_id=aid, created=True, duplicate=False)

    def claim_stage_run(
        self,
        *,
        asset_id: str,
        stage_name: str,
        lease_owner: str,
        lease_seconds: int = 300,
        attempt: int = 1,
    ) -> str:
        """Create a RUNNING stage run with a lease. Single-writer short transaction."""
        if lease_seconds <= 0:
            raise NpiError("lease duration must be positive", error_code=NPI_SCHEMA_INVALID)
        rid = _new_id("run")
        now = _utc_now_iso()
        expires = _now_plus_iso(lease_seconds)
        if not lease_owner:
            raise StageClaimConflictError("stage claim requires a lease owner")
        try:
            with self.transaction() as conn:
                conn.execute(
                    "INSERT INTO stage_runs (stage_run_id, asset_id, stage_name, status, "
                    "attempt, started_at, lease_owner, lease_expires_at, heartbeat_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        rid,
                        asset_id,
                        stage_name,
                        STAGE_RUNNING,
                        int(attempt),
                        now,
                        lease_owner,
                        expires,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            if getattr(exc, "sqlite_errorname", "") == "SQLITE_CONSTRAINT_UNIQUE":
                raise StageClaimConflictError("stage already has an active claim") from None
            raise DatabaseError("stage claim constraint failed") from None
        return rid

    def heartbeat(
        self,
        stage_run_id: str,
        *,
        lease_owner: str,
        lease_seconds: int = 300,
    ) -> None:
        """Refresh heartbeat_at and lease_expires_at for a running stage run."""
        if lease_seconds <= 0:
            raise NpiError("lease duration must be positive", error_code=NPI_SCHEMA_INVALID)
        now = _utc_now_iso()
        expires = _now_plus_iso(lease_seconds)
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE stage_runs SET heartbeat_at = ?, lease_expires_at = ? "
                "WHERE stage_run_id = ? AND status = ? AND lease_owner = ? "
                "AND lease_expires_at > ? AND finished_at IS NULL",
                (now, expires, stage_run_id, STAGE_RUNNING, lease_owner, now),
            )
            if cursor.rowcount != 1:
                raise LeaseLostError("heartbeat rejected because the lease is not active")

    def release_run(
        self,
        stage_run_id: str,
        status: str,
        *,
        lease_owner: str,
        error_code: str | None = None,
        error_redacted: str | None = None,
    ) -> None:
        """Atomically finalize an owned, active RUNNING stage run exactly once."""
        if status not in {STAGE_SUCCEEDED, STAGE_FAILED}:
            raise NpiError("release status must be terminal", error_code=NPI_SCHEMA_INVALID)
        safe_error_code = _validated_error_code(error_code, allowed=self._known_error_codes)
        now = _utc_now_iso()
        with self.transaction() as conn:
            cursor = conn.execute(
                "UPDATE stage_runs SET status = ?, finished_at = ?, error_code = ?, "
                "error_redacted = ?, duration_ms=CASE WHEN started_at IS NULL THEN 0 ELSE "
                "MAX(0, CAST((julianday(?) - julianday(started_at)) * 86400000 AS INTEGER)) END, "
                "lease_owner=NULL, lease_expires_at=NULL "
                "WHERE stage_run_id = ? AND status = ? AND lease_owner = ? "
                "AND lease_expires_at > ? AND finished_at IS NULL",
                (
                    status,
                    now,
                    safe_error_code,
                    _safe_error_detail(error_redacted),
                    now,
                    stage_run_id,
                    STAGE_RUNNING,
                    lease_owner,
                    now,
                ),
            )
            if cursor.rowcount != 1:
                raise LeaseLostError("release rejected because the lease is not active")

    def record_retry(
        self,
        asset_id: str,
        *,
        error_code: str,
        error_redacted: str,
    ) -> int:
        """Record a bounded retry; reaching the ceiling atomically enters FAILED."""
        if not _ERROR_CODE_RE.fullmatch(error_code):
            raise NpiError("retry error code is invalid", error_code=NPI_SCHEMA_INVALID)
        non_retryable = self._retry_policy.is_non_retryable(error_code)
        max_attempts = (
            self._retry_policy.default_max_attempts
            if non_retryable
            else self._retry_policy.max_attempts_for(error_code)
        )
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT retry_count, current_state FROM assets WHERE asset_id = ?", (asset_id,)
            ).fetchone()
            if row is None:
                raise DatabaseError("asset not found")
            current_count = int(row["retry_count"])
            from_state = parse_state(str(row["current_state"]))
            if from_state == AssetState.FAILED:
                raise RetryExhaustedError("retry limit already exhausted")
            if non_retryable:
                validate_transition(from_state, AssetState.FAILED)
                self._append_transition(
                    conn,
                    asset_id=asset_id,
                    from_state=from_state,
                    to_state=AssetState.FAILED,
                    reason_code=error_code,
                    actor_type="SYSTEM",
                    actor_id="npi-retry",
                    stage_run_id=None,
                )
                conn.execute(
                    "UPDATE assets SET last_error_code = ?, last_error_redacted = ?, "
                    "current_state = ?, updated_at = ? WHERE asset_id = ?",
                    (
                        error_code,
                        _safe_error_detail(error_redacted),
                        AssetState.FAILED.value,
                        _utc_now_iso(),
                        asset_id,
                    ),
                )
                return current_count
            if current_count >= max_attempts:
                raise RetryExhaustedError("retry limit already exhausted")
            new_count = current_count + 1
            to_state = AssetState.FAILED if new_count >= max_attempts else AssetState.RETRY
            persisted_error_code = (
                NPI_RETRY_EXHAUSTED if to_state == AssetState.FAILED else error_code
            )
            if to_state == AssetState.FAILED:
                persisted_error_detail = _safe_error_detail(
                    f"retry exhausted after {new_count} attempts; "
                    f"prior_error_code={error_code}; prior_detail={error_redacted}"
                )
            else:
                persisted_error_detail = _safe_error_detail(error_redacted)
            if from_state != to_state:
                validate_transition(from_state, to_state)
                self._append_transition(
                    conn,
                    asset_id=asset_id,
                    from_state=from_state,
                    to_state=to_state,
                    reason_code=persisted_error_code,
                    actor_type="SYSTEM",
                    actor_id="npi-retry",
                    stage_run_id=None,
                )
            conn.execute(
                "UPDATE assets SET retry_count = ?, last_error_code = ?, "
                "last_error_redacted = ?, current_state = ?, updated_at = ? WHERE asset_id = ?",
                (
                    new_count,
                    persisted_error_code,
                    persisted_error_detail,
                    to_state.value,
                    _utc_now_iso(),
                    asset_id,
                ),
            )
        return new_count

    def insert_duplicate_candidate(
        self,
        *,
        asset_id: str,
        candidate_asset_id: str,
        distance: float,
        algorithm_id: str,
        algorithm_version: str,
        hash_size: int,
    ) -> str:
        """Record a near-duplicate (perceptual) candidate for human review."""
        cid = _new_id("dup")
        with self.transaction() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO duplicate_candidates "
                "(candidate_id, asset_id, candidate_asset_id, distance, algorithm_id, "
                "algorithm_version, hash_size, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    cid,
                    asset_id,
                    candidate_asset_id,
                    distance,
                    algorithm_id,
                    algorithm_version,
                    hash_size,
                    _utc_now_iso(),
                ),
            )
        return cid
