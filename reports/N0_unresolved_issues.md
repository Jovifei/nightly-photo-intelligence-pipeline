# N0 Unresolved Issues (post-remediation)

Issues are classified by severity. None are blocking for the N0 candidate
commit (all quality gates PASS on Python 3.12.10). Items marked **Owner
decision** require explicit Owner input before N1 may proceed.

## CRITICAL

None. No safety hard-constraint is unproven: source read-only protection,
overlap/symlink-escape rejection, dry-run non-mutation, gate fail-closed,
DELETE+FULL+FK SQLite baseline, and handoff integrity (historical) are all
evidenced.

## HIGH (Owner decision required before N1)

1. **Python 3.11 not verified.** The machine has 3.12.10 (used for N0) and 3.14.2 (not used). 3.11 is the contract's preferred lower bound but is not installed here, so 3.11 compatibility is targeted (`requires-python = ">=3.11,<3.13"`) but NOT verified by test. Owner must decide whether to accept 3.12-only verification or require a 3.11 test run. No 3.13/3.14 compatibility is claimed.

2. **Real photo inputs for N1.** Before N1: Owner must authorize the real photo root, specify the Windows/WSL read-only access method, provide the 20-image G1 calibration list (not a whole directory), confirm whether real EXIF may be read, set the file-extension whitelist, and confirm backup state. None of these were done in N0 (real photo access is NOT_AUTHORIZED).

3. **`tools/verify_handoff.py` exact-set manifest check diverges by design.** The verifier does `ROOT.rglob("*")` exact-set matching (incl. `.git/`) and was meant for the pristine package. Post-implementation it diverges. Original package verified pre-implementation (16 pass - historical). N0 uses a contract-files-unchanged subset check for the quality gate. Owner should confirm this interpretation; N1 could refine `verify_handoff.py` to exclude `.git` and gitignored paths from the exact-set check.

## MEDIUM

4. **Source/runtime separation not configured.** `npi preflight` reports `source_runtime_separation = SKIPPED` because `NPI_SOURCE_ROOT` / `NPI_RUNTIME_ROOT` are unset. N1 must configure these and re-verify. The guard code that enforces separation is tested and passes.

5. **Perceptual hash is a lightweight N0 implementation.** `dhash-8x8 / npi-0.1.0` is used. Per the N0 task contract, the production perceptual hash must NOT be frozen without an N1 decision. N1 must benchmark candidate algorithms (pHash, aHash, improved dHash) before adoption.

6. **WAL is a future candidate, not adopted.** N0 uses the DELETE+FULL+FK baseline (no Owner-approved exception for WAL). `config/execution_defaults.yaml` documents `journal_mode_candidate: "WAL"`; the code does not adopt it. N1 may propose WAL via a Benchmark + ADR + Owner approval. DELETE+FULL may have higher write overhead than WAL; acceptable for N0's tiny fixtures; re-evaluate for N1+ scale.

7. **Symlink privilege.** `os.symlink` fails on this machine (WinError 1314 - needs developer mode or admin). N0 tests use NTFS junctions (`mklink /J`, no admin required) to exercise reparse-point rejection. Real photo directories may contain symlinks; the source guard rejects them by default (`allow_source_symlink=false`, `allow_file_symlink=false`). N1 should confirm the real photo root contains no legitimate symlinks that need allowlisting.

## LOW

8. **`schema_catalog.json` catalog_version.** `npi preflight` reports `catalog_version=unknown` because the catalog file lacks an explicit `catalog_version` field. Cosmetic; the item schema itself validates correctly.

9. **Project-local venv not committed.** `.venv/` is gitignored (correct - it is machine-specific). Reproducibility relies on `pyproject.toml` pinned versions. N1/consumers recreate the venv via `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"`. The pinned versions are: typer 0.26.8, pydantic 2.13.4, pyyaml 6.0.3, pillow 12.3.0, pytest 9.1.1, ruff 0.15.21, mypy 2.3.0, jsonschema 4.26.0, referencing 0.37.0.

## Resolved since first N0 attempt

- ruff and mypy are now installed in the project-local `.venv` and PASS (previously `NOT_AVAILABLE`).
- SQLite WAL was reverted to the DELETE+FULL+FK safe baseline (previously auto-adopted WAL).
- Python 3.12.10 is now the test interpreter (previously 3.14.2); no unverified 3.13/3.14 compatibility is claimed.
- Self-review is no longer described as an independent review pass; N0 is explicitly AWAITING_INDEPENDENT_REVIEW.

## Not done (out of scope, by contract)

- No model download (Pose/Segmentation/VLM/Embedding).
- No real photo access, no 20/100/full-library run.
- No cloud access (only PyPI install of pinned lightweight dev tools into `.venv`).
- No OpenClaw, no main-App modification.
- No push/merge/remote.
