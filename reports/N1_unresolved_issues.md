# N1 Unresolved Issues

None are blocking for the N1 candidate commit (all quality gates PASS on 3.12.10). Items marked **Owner decision** require Owner input before N2/G1.

## HIGH (Owner decision required before G1/N2)

1. **Real photo inputs for G1.** Before G1: Owner must authorize the real photo root, specify the Windows/WSL read-only access method, provide the 20-image G1 calibration manifest (explicit list), confirm whether real EXIF may be read, set the file-extension whitelist, and confirm backup state. See `reports/G1_owner_input_checklist.md`. None done in N1 (real photo access NOT_AUTHORIZED).

2. **Perceptual hash production threshold.** N1 uses `dhash-8x8/npi-0.2.0` with a fixture-level `NEAR_DUPLICATE_THRESHOLD_HAMMING=5`. Per the N0/N1 task contract, the production threshold must NOT be frozen without G1 (20 calibration images) + a benchmark. N2/N6 must benchmark candidate algorithms (pHash, aHash, improved dHash) before adoption.

3. **WAL decision.** N1 keeps the DELETE+FULL+FK baseline. WAL remains a future candidate requiring Benchmark + ADR + Owner approval. DELETE+FULL has higher write overhead; acceptable for G0 (3 fixtures); re-evaluate for G1+ scale.

## MEDIUM

4. **Source/runtime separation not configured for real photos.** `npi preflight` reports `source_runtime_separation = SKIPPED` (NPI_SOURCE_ROOT/NPI_RUNTIME_ROOT unset). N1 tests prove separation via fixtures + temp dirs (overlap/output-in-source rejected). N1/G1 must configure real paths and re-verify.

5. **Python 3.11 not verified.** Only 3.12.10 (used) and 3.14.2 (not used) are installed. 3.11 is the targeted lower bound (`requires-python = ">=3.11,<3.13"`) but not tested. No 3.13/3.14 compatibility claimed.

6. **`tools/verify_handoff.py` exact-set divergence (by design).** The verifier does `ROOT.rglob("*")` exact-set matching (incl. `.git/`, `.venv/`); diverges post-implementation. Original package verified pre-implementation (16 pass - historical). N1 quality gate uses `contract_integrity` (immutable contract files intact; 11 auth-state files excluded). Owner accepted this separation (instruction IV.2).

7. **Symlink privilege.** `os.symlink` fails on this machine (WinError 1314). N1/N0 tests use NTFS junctions (`mklink /J`, no admin) to exercise reparse-point rejection. Real photo dirs may contain symlinks; the guard rejects them by default. G1 should confirm the real photo root has no legitimate symlinks needing allowlisting.

## LOW

8. **Near-duplicate candidates not yet surfaced in CLI.** `insert_duplicate_candidate` and `hamming_distance`/`is_near_duplicate` are implemented and tested, but the ingest flow does not yet write near-duplicate candidates to the table (only exact duplicates are handled in N1). Surfacing near-duplicates for human review is an N2/N6 concern (needs the production threshold first).

9. **DB backup/restore drill.** `docs/36_database_backup_and_recovery.md` describes backup; N1 did not implement an automated backup/restore drill (the N1 task contract mentions backup/recovery; the reopen/recovery + migration-idempotency evidence covers the recovery slice). A full backup/restore drill is an N1+ operational task before G1 nightly runs.

## Resolved since N0

- catalog_version: now derived from the package version (was "unknown").
- Real ingest: implemented (was N0 dry-run-only).
- Lease/heartbeat/retry/resume: implemented.
- Migration mechanism: versioned + idempotent (was v0-only).
- Git history acceptance: adjusted for N0-baseline + single-N1-commit (was `count==1`).

## Not done (out of scope, by contract)

- N2 Pose/segmentation/VLM/embedding. G1 20 real images. Real photo access. EXIF real-data read. Model downloads. Cloud. OpenClaw. Main-App changes. Push/merge.
