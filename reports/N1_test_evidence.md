# N1 Test Evidence

- N0 baseline: `72a81f5984838b74304d23263ac450ea4b5a3a9a` (immutable)
- N1 commit under test: the single N1 commit on top of the N0 baseline (SHA in the final completion message)
- Quality command: `python tools/run_quality.py` (CPython 3.12.10 `.venv`)
- Independent review status: NOT YET PERFORMED. The implementer performed implementation and self-verification only; this N1 commit awaits an independent Reviewer's `PASS_FOR_OWNER_REVIEW`.

## Quality command result (post-implementation, Python 3.12.10)

```
NPI N0/N1 quality gate
============================================================
[PASS] pytest              -> 56 passed, 0 failed
[PASS] contract_integrity  -> 160 immutable contract files intact (11 auth-state files excluded)
[PASS] schema_validation   -> valid item passes Draft 2020-12; 3/3 invalid rejected
[PASS] sensitive_scan      -> 0 violation(s)
[PASS] ruff_check          -> All checks passed!
[PASS] ruff_format         -> 35 files already formatted
[PASS] mypy                -> Success: no issues found in 23 source files
------------------------------------------------------------
Summary: 7 pass, 0 fail, 0 not_available, 0 skipped
QUALITY_GATE_PASSED
```

## N1 key behaviors (Owner instruction VII)

| # | Behavior | Test | Result |
|---|---|---|---|
| 1 | 3-fixture first ingest deterministic | `test_at_n1_ingest_deterministic_first_ingest` | PASS (2 unique assets, 1 dup) |
| 2 | Re-ingest creates no new asset/task | `test_at_n1_ingest_idempotent_reingest`, `test_at_n1_real_ingest_idempotent_reingest` | PASS |
| 3 | Exact duplicate recognized | `test_at_n1_exact_duplicate_recognized` | PASS (1 asset, 2 sources) |
| 4 | SHA-256 and perceptual hash stored separately | `test_at_n1_sha_and_perceptual_hash_stored_separately` | PASS |
| 5 | TOCTOU detected | `test_at_n1_toctou_detected` | PASS (SourceChangedDuringReadError) |
| 6 | Source writable/overlap/symlink fail-closed | `test_at_n1_output_to_source_rejected` + N0 SEC-01/02 | PASS |
| 7 | 4th asset rejected by Gate | `test_at_n1_gate_fourth_asset_rejected` | PASS (exit 8) |
| 8 | Non-dry-run only within N1/G0 | `test_at_n1_gate_non_dry_run_authorized_for_manifest` | PASS (exit 0, 2 assets) |
| 9 | Interrupted task identified after restart | `test_at_n1_resume_reclaims_expired_lease` + N0 REC-01 | PASS |
| 10 | Lease-expired task safely reclaimed | `test_at_n1_resume_reclaims_expired_lease`, `test_at_n1_heartbeat_extends_lease` | PASS |
| 11 | retry/last_error/timing auditable | `test_at_n1_retry_and_error_audit` | PASS (retry_count=2, last_error, finished_at) |
| 12 | Invalid transitions rejected | N0 `test_at_n0_state_01_invalid_transitions_rejected` | PASS |
| 13 | Migration repeatable | `test_at_n1_migration_repeatable` | PASS (idempotent, schema_version=1) |
| 14 | CLI exit codes match contract | `test_at_n0_cli_01_*`, gate tests | PASS |
| 15 | Logs/DB no real absolute photo paths | `test_at_n1_db_no_absolute_photo_paths` + N0 LOG-01 | PASS (DB stores `<SOURCE_ROOT>/...`) |
| 16 | No derived artifacts (thumbs/masks/embeddings/models) | `test_at_n1_no_derived_artifacts` | PASS |
| 17 | Deterministic structured output | `test_at_n1_deterministic_structured_output` + N0 IDEM-01 | PASS |
| 18 | N0 regression still passes (phase-boundary adjusted) | full suite (56 passed) | PASS |

## N0 phase-boundary test adjustments (audit strength maintained, not degraded)

Per Owner instruction V and XVIII, the following N0 tests were adjusted for the N0->N1 phase boundary. Audit strength is maintained (each still verifies its guarantee, just for N1 state):

- `test_at_n0_db_01_schema_created_and_reopens`: schema_version `0` -> `1` (N1 migration applied). Reopen/FK/rollback assertions unchanged.
- `test_at_n0_ho_01_*`: MANIFEST subset check now excludes authorization-state files (PROJECT_STATE.json, tasks/index.json, tasks/phase_n*.yaml) that legitimately change with phase transitions; immutable contract files (160) still verified.
- `test_at_n0_gate_02_*`: N1-N8 locked -> N2-N8 locked (N1 AUTHORIZED, N0 APPROVED/COMPLETE); N0 baseline SHA verified.
- `test_at_n0_gate_01` -> N1 gate: non-dry-run ingest authorized for G0 manifest (exit 0); 4th asset rejected (exit 8).
- `test_at_n0_git_01` -> N1 git history: N0 baseline tag == 72a81f5 (not rewritten); N0 baseline is root; at most one N1 commit beyond N0; no sensitive tracked files.

No test was deleted or weakened to force a pass.

## CLI end-to-end evidence

```
$ npi ingest --input fixtures/three_image_smoke_set
source: <SOURCE_ROOT>
runtime: <RUNTIME_ROOT>
manifest: G0_THREE_SYNTHETIC_FIXTURES
files_scanned: 3  assets_created: 2  duplicates_seen: 1  database_mutated: True
  - fixture_a_corridor_abstract.png  sha=ff0ec4d4baeb...  asset=asset-a005125837  created
  - fixture_a_exact_copy.png         sha=ff0ec4d4baeb...  asset=asset-a005125837  duplicate
  - fixture_b_tonal_abstract.png     sha=9544c6102644...  asset=asset-8f43338062  created

$ npi status
Authorization: phase=N1 (AUTHORIZED), data_gate=G0_THREE_SYNTHETIC_FIXTURES (AUTHORIZED)
Database: present, schema_version=1, assets=2, interrupted_runs=0
  assets by state: INGESTED: 2

$ npi resume   -> reclaimed 0 interrupted stage run(s)
$ npi report --latest   -> schema_version=1, interrupted_runs=0, retry/error audit: none
```

## Independent Reviewer checklist (for the independent Reviewer)

1. **Scope**: N1 only (N0 baseline 72a81f5 immutable); no N2/G1/real-photos/models/cloud/OpenClaw/App/push; one N1 commit.
2. **Gate**: non-dry-run ingest bounded by G0 manifest + max_assets=3; 4th asset rejected (exit 8); gate checked before source access.
3. **Idempotency**: re-ingest creates no new asset; exact duplicates merge to one asset with multiple sources.
4. **State/recovery**: lease claim/heartbeat/release; expired-lease reclaim; retry/last_error audit; migration idempotent; append-only transitions.
5. **Security**: source_guard read-only (no write API); TOCTOU; overlap/symlink/junction rejection; DB stores only redacted paths; no derived artifacts.
6. **Quality**: pytest 56/0, ruff/mypy/format PASS, schema valid/invalid, sensitive scan 0, contract_integrity (auth-state excluded).
7. **Authorization**: PROJECT_STATE N1/G0, N0 APPROVED baseline, N2-N8 + G1-G3 LOCKED.

Commands for the Reviewer (3.12 venv):
```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check . && .venv/Scripts/python.exe -m ruff format --check .
.venv/Scripts/python.exe -m mypy src/nightly_photo_intelligence_pipeline
.venv/Scripts/python.exe tools/run_quality.py
.venv/Scripts/python.exe tools/sensitive_file_scan.py
git -C . log --oneline --decorate
git -C . rev-parse n0-approved-2026-07-14   # must equal 72a81f5...
git -C . rev-list --count 72a81f5984838b74304d23263ac450ea4b5a3a9a..HEAD   # <= 1
```
