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

import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from ..domain.errors import NPI_SCHEMA_INVALID, DatabaseError, NpiError
from ..domain.states import AssetState, parse_state, validate_transition
from .migrations import SCHEMA_VERSION_KEY, apply_schema_v0

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


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


@dataclass(frozen=True)
class StageRunRecord:
    stage_run_id: str
    asset_id: str
    stage_name: str
    status: str
    attempt: int
    started_at: str | None
    lease_expires_at: str | None


class StateStore:
    """Thin, typed wrapper around the NPI SQLite state database."""

    def __init__(self, conn: sqlite3.Connection, *, journal_mode: str = "DELETE") -> None:
        self._conn = conn
        self._journal_mode = journal_mode

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
        path = Path(db_path)
        if path.parent and not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn = sqlite3.connect(str(path), isolation_level=None, check_same_thread=False)
        except sqlite3.Error as exc:
            raise DatabaseError(f"cannot open sqlite db: {exc}") from exc
        conn.row_factory = sqlite3.Row
        # PRAGMAs execute in autocommit (isolation_level=None).
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)}")
        # N0 baseline: DELETE journal + FULL synchronous. Do NOT adopt WAL.
        conn.execute("PRAGMA journal_mode = DELETE")
        conn.execute("PRAGMA synchronous = FULL")
        store = cls(conn, journal_mode="DELETE")
        if initialize:
            store.initialize()
        return store

    def initialize(self) -> None:
        """Apply schema v0 if absent and stamp metadata."""
        with self._conn:
            apply_schema_v0(self._conn)

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
        """Yield the connection inside a transaction (commit/rollback on exit)."""
        with suppress(sqlite3.Error):
            # BEGIN is a no-op (and errors) if already in a transaction.
            self._conn.execute("BEGIN")
        try:
            yield self._conn
            self._conn.commit()
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
        except sqlite3.IntegrityError as exc:
            raise DatabaseError(
                f"asset already exists or constraint violated: {exc}",
            ) from exc
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
        row = self._conn.execute(
            "SELECT current_state FROM assets WHERE asset_id = ?", (asset_id,)
        ).fetchone()
        if row is None:
            raise DatabaseError(f"asset not found: {asset_id}")
        from_state = parse_state(str(row["current_state"]))
        if to_state == AssetState.APPROVED and require_human_for_approval and actor_type != "HUMAN":
            raise NpiError(
                "transition to APPROVED requires a HUMAN actor",
                error_code=NPI_SCHEMA_INVALID,
            )
        validate_transition(from_state, to_state)  # raises InvalidTransitionError
        with self.transaction() as conn:
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
        with self.transaction() as conn:
            conn.execute(
                "UPDATE stage_runs SET status = ?, finished_at = ?, error_code = ?, "
                "error_redacted = ? WHERE stage_run_id = ?",
                (status, finished_at, error_code, error_redacted, stage_run_id),
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
        runs = self.identify_interrupted_runs(now_iso=now_iso)
        for run in runs:
            self.update_stage_run_status(
                run.stage_run_id,
                STAGE_INTERRUPTED,
                finished_at=_utc_now_iso(),
                error_code="NPI_RUN_INTERRUPTED",
                error_redacted="lease expired or missing during reopen",
            )
        return len(runs)

    def get_asset(self, asset_id: str) -> dict[str, Any] | None:
        row = self._conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
        return dict(row) if row is not None else None

    def get_asset_by_sha(self, source_sha256: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM assets WHERE source_sha256 = ?", (source_sha256,)
        ).fetchone()
        return dict(row) if row is not None else None
