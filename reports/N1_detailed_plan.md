# N1 Detailed Plan (updated from N0 remediation findings)

N0 is a candidate commit awaiting independent Reviewer pass and Owner approval.
This plan is forward-looking only; N1 is LOCKED until the Owner updates
`PROJECT_STATE.json` and provides the required N1 inputs. No N1 work is started.

## Goal

Extend the N0 scaffold into a persistent, idempotent, recoverable single-machine
task engine: real ingest, dedup, lease/heartbeat, failure isolation, and
`npi resume` / `npi report --latest`, still on synthetic fixtures until G1 is
authorized.

## Prerequisites (Owner decisions - see N0_unresolved_issues.md)

1. Python 3.11 verification decision (accept 3.12-only, or require a 3.11 test run).
2. Real photo root authorization + Windows/WSL read-only access method.
3. 20-image G1 calibration manifest (explicit list, not a directory).
4. File-extension whitelist confirmation.
5. Whether real EXIF may be read (reading != inferring).
6. Disk budget for runtime/work/artifacts.
7. `NPI_SOURCE_ROOT` / `NPI_RUNTIME_ROOT` configuration.
8. Backup state of the source library confirmed.
9. WAL decision: keep DELETE+FULL, or approve a WAL Benchmark + ADR.

## Environment baseline established in N0 (carry into N1)

- Project-local `.venv` with Python 3.12.10 and pinned deps (see `pyproject.toml`).
- SQLite baseline: `journal_mode=DELETE`, `synchronous=FULL`, `foreign_keys=ON`, single writer, short transactions. WAL is a future candidate requiring Benchmark + ADR + Owner approval.
- `tools/verify_handoff.py` is a pristine-package tool; N1 should add a post-implementation integrity check that excludes `.git` and gitignored paths (or refine the verifier with Owner approval).
- Source guard: read-only, no write/move/delete/chmod API; NTFS junction detection via `st_file_attributes & 0x400`; overlap and `..` escape rejected.

## Work packages

1. **DB migration mechanism.** Generalize `persistence/migrations.py` to a versioned migration runner (v0 -> v1 ...). Record migration history in `metadata`. Keep v0 schema as the baseline. Preserve DELETE+FULL+FK unless WAL is approved.

2. **Real ingest (non-dry-run).** Lift the N0 gate (`require_ingest_authorized` already returns True once phase >= N1). Implement: enumerate manifest assets, open via `source_guard`, stream SHA-256, perceptual hash, insert asset + asset_sources + NEW->INGESTED transition in one transaction. Enforce the G1 manifest membership check (a `--limit` only caps count; it does not enlarge permission).

3. **Exact-duplicate handling.** Reuse the N0 duplicate-grouping logic. On duplicate SHA-256, record the additional source in `asset_sources` and set `current_state=DUPLICATE` for the duplicate entry. Never delete or move sources.

4. **Near-duplicate (perceptual) candidates.** Surface near-duplicate candidates by perceptual-hash hamming distance for human review. Do NOT auto-delete. Record the N0 `dhash-8x8/npi-0.1.0` provenance; benchmark before freezing a production algorithm.

5. **Lease / heartbeat.** `stage_runs.lease_owner`, `lease_expires_at`, `heartbeat_at` are already in the schema. Implement claim/heartbeat/release in short transactions. A worker claims one asset-stage at a time.

6. **Retry / error taxonomy.** Map domain errors to `last_error_code` + redacted `last_error_redacted` on the asset; increment `retry_count`; use `RETRY` state per the state machine. Honor `config/retry_policy.yaml`.

7. **`npi resume`.** Call `identify_interrupted_runs()` (N0-implemented) and reclaim INTERRUPTED runs: re-queue the asset's pending stage. Do not invent outputs.

8. **`npi report --latest`.** Summarize the most recent run: assets by state, failures, durations, schema pass rate, source-integrity spot-check. Redact all absolute paths.

9. **DB backup / integrity.** Periodic `PRAGMA integrity_check`; offline backup to runtime; restore drill. See `docs/36_database_backup_and_recovery.md`.

10. **N1 security and fault-injection tests.** Extend the N0 negative suite: manifest-over-permission refusal (an asset not in the G1 manifest is rejected), DB fault injection, lease-expiry reclaim, double-claim refusal, and source-integrity check after a simulated crash.

## N1 still forbids

- Model downloads (Pose/Segmentation/VLM/Embedding).
- Pose/VLM fake implementations standing in for real models.
- 100 / full-library runs (G2/G3 locked).
- OpenClaw.
- Main-App modification.
- Cloud access / image upload.
- Push/merge/remote without separate Owner approval.
- Adopting WAL without Benchmark + ADR + Owner approval.

## Exit evidence for N1

- Tasks are not lost across restarts (lease recovery).
- Exact-duplicate ingest is idempotent (re-running adds no new asset row).
- Interrupted runs recover without fabricated outputs.
- DB backup + restore drill passes.
- Source integrity spot-check passes (pre/post SHA/size/mtime).
- Manifest-over-permission is refused (an asset outside the G1 manifest is rejected even with `--limit` raised).
- G1 (20 images) remains LOCKED unless the Owner separately authorizes it.
