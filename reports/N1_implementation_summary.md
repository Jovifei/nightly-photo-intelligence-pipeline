# N1 Implementation Summary

- Phase: N1 (AUTHORIZED) on G0_THREE_SYNTHETIC_FIXTURES (3 synthetic fixtures, max_assets=3)
- N0 baseline: `72a81f5984838b74304d23263ac450ea4b5a3a9a` (immutable; tag `n0-approved-2026-07-14`)
- Approval record: `approvals/phase_approval_N1.yaml`
- Test interpreter: CPython 3.12.10 (project-local `.venv`)
- Real photo access: NOT_AUTHORIZED. EXIF real-data read: NOT_AUTHORIZED. Model downloads: NOT_AUTHORIZED.

## Scope delivered (per tasks/phase_n1_ingest_state_machine.yaml + Owner instruction)

1. **Authorization state**: `approvals/phase_approval_N1.yaml` (APPROVED, owner Jovi, scoped exclusions); `PROJECT_STATE.json` updated to N1 AUTHORIZED, N0 APPROVED/COMPLETE baseline, G0 (max_assets=3), G1-G3 LOCKED, real photos/EXIF/models/cloud/OpenClaw/push all NOT_AUTHORIZED; `tasks/index.json` and `tasks/phase_n1_ingest_state_machine.yaml` status set to AUTHORIZED; local tag `n0-approved-2026-07-14` at 72a81f5.

2. **DB migration mechanism** (`persistence/migrations.py`): versioned runner with `migration_history` table; v0 (N0 baseline) + v1 (N1: migration_history + duplicate_candidates); idempotent (re-running is a no-op); schema_version stamped to "1". `StateStore.initialize()` now calls `run_migrations`.

3. **State store extensions** (`persistence/sqlite.py`): idempotent `ingest_asset` (exact-duplicate SHA merges into one asset with multiple sources; re-ingest creates no new row); `add_asset_source`; `claim_stage_run`/`heartbeat`/`release_run` (lease lifecycle in short transactions); `record_retry` (retry_count + last_error_code + last_error_redacted); `insert_duplicate_candidate` (near-duplicate perceptual candidates); `IngestAssetResult` dataclass. SQLite baseline unchanged: DELETE + FULL + FK on (WAL not adopted).

4. **Real ingest** (`ingest/runner.py` + `ingest/manifest.py`): `run_real_ingest` - G0 manifest membership gate (4th/non-manifest asset rejected with NPI_GATE_NOT_AUTHORIZED), asset cap check (max_assets), streaming SHA-256, versioned perceptual hash, single-transaction asset+source+NEW->INGESTED, idempotent, DB stores only redacted source paths (`<SOURCE_ROOT>/<name>`).

5. **Perceptual hash v2** (`ingest/perceptual_hash.py`): `PerceptualHashResult` now carries `algorithm_id`, `algorithm_version`, `hash_size_bits`, `value` + `provenance()`; `hamming_distance`, `is_near_duplicate` with `NEAR_DUPLICATE_THRESHOLD_HAMMING=5` (N1 fixture-level default, NOT a production-claimed threshold - production requires G1 20 calibration images + benchmark). Back-compat aliases (`ALGORITHM`, `IMPLEMENTATION_VERSION`) and properties (`algorithm`, `implementation_version`) preserve N0 callers.

6. **CLI** (`cli.py`): `npi ingest --input <DIR>` (non-dry-run) now works in N1/G0 (manifest-gated, mutating); `npi resume` (reclaim interrupted runs); `npi report --latest` (redacted summary + retry/error audit). `npi ingest --dry-run` unchanged (read-only).

7. **catalog_version** (`preflight.py`): derived from package `__version__` (deterministic, traceable), no longer "unknown".

8. **Git history acceptance** (`tests/test_git.py`): adjusted for the N0-baseline + single-N1-commit structure - verifies the N0 tag points to 72a81f5 (not rewritten), N0 baseline is the root commit, at most one N1 commit beyond N0, no sensitive tracked files. Does not assert `count==1` (legitimate 2-commit phase structure).

## Out of scope (LOCKED)

N2 (Pose/segmentation/VLM/embedding), G1 (20 real images), real photo access, EXIF real-data read, model downloads, cloud, OpenClaw, main-App changes, push/merge. Not started.

## Quality (post-implementation, pre-commit)

See `reports/N1_test_evidence.md` for the full quality-command results. All hard gates PASS on CPython 3.12.10.
