# N0 Test Evidence

- Commit under test: the single isolated local commit created by the N0 agent (SHA reported in the final completion message; `git rev-list --count HEAD` == 1)
- Quality command: `python tools/run_quality.py` (run with the Python 3.12.10 project-local venv)
- Started/finished UTC: 2026-07-13
- Test interpreter: CPython 3.12.10 (project-local `.venv`)

## Independent review status

**Independent review status.** The independent Reviewer's report (`reports/N0_independent_review.md`) is tracked in this same single N0 commit. That report initially reviewed a content-equivalent prior implementation commit (preserved only in a local-only backup branch, NOT part of the delivery history) and returned `PASS_FOR_OWNER_REVIEW` for that prior content. That pass is advisory: it does NOT constitute a final review of this single commit's SHA, does NOT approve N0, does NOT modify `PROJECT_STATE.json`, and does NOT authorize N1. This single final N0 commit still requires a fresh external final independent review of its own SHA before it can be submitted to the Owner. The implementer is NOT the Reviewer and performed implementation and self-verification only.

## Three verification levels (distinct)

1. **Original delivery package integrity** (historical, pre-implementation): `python tools/verify_handoff.py` before any implementation = 16 pass, 0 warn, 0 fail, `HANDOFF_VALID`. The current working directory does NOT match the original `MANIFEST.sha256` (N0 added files; `git init` added `.git/`).
2. **N0 implementation code quality** (this section): pytest, ruff, mypy, schema, security - all on Python 3.12.10.
3. **Current Git commit content**: `git ls-files` sensitive scan (0 violations); one isolated commit; clean working tree; only 3 fixture PNGs tracked as images.

## Quality command result (post-commit, Python 3.12.10)

```
NPI N0 quality gate
============================================================
[PASS] pytest              -> 33 passed, 0 skipped
[PASS] contract_integrity  -> 171 contract files intact (new N0 files allowed)
[PASS] schema_validation   -> valid item passes Draft 2020-12; 3/3 invalid rejected
[PASS] sensitive_scan      -> 0 violation(s)
[PASS] ruff_check          -> All checks passed!
[PASS] ruff_format         -> 33 files already formatted
[PASS] mypy                -> Success: no issues found in 22 source files
------------------------------------------------------------
Summary: 7 pass, 0 fail, 0 not_available, 0 skipped
QUALITY_GATE_PASSED
```

All seven quality checks PASS (hard gates and lint/typecheck). ruff 0.15.21 and mypy 2.3.0 are installed in the project-local `.venv` and were actually executed (not `NOT_AVAILABLE`).

## Acceptance test results (AT-N0-*)

| Test ID | Status | Command | Evidence |
|---|---|---|---|
| AT-N0-HO-01 | PASS | `pytest tests/test_handoff.py` | MANIFEST.sha256 lists 171 contract files, all hash-match (subset); 3 fixtures match fixture_manifest.json; duplicate pair byte-identical |
| AT-N0-ENV-01 | PASS | `pytest tests/test_environment.py` | preflight read-only, prints "No install, update, pull, or system change was performed", creates no unexpected project files |
| AT-N0-CLI-01 | PASS | `pytest tests/test_cli.py`; `npi --help`/`npi <cmd> --help` | all three N0 commands registered; help and status exit 0 (verified on 3.12) |
| AT-N0-HASH-01 | PASS | `pytest tests/test_hash.py::test_at_n0_hash_01_*` | streamed SHA-256 == manifest hash for all 3 fixtures (path + handle APIs); duplicate pair identical |
| AT-N0-HASH-02 | PASS | `pytest tests/test_hash.py::test_at_n0_hash_02_*` | perceptual hash carries `algorithm=dhash-8x8`, `implementation_version=npi-0.1.0`, lowercase-hex value; deterministic |
| AT-N0-IDEM-01 | PASS | `pytest tests/test_cli.py::test_at_n0_idem_01_*` | two dry-runs produce byte-identical stdout; seeded DB asset count stays 0; `files_scanned: 3`, `duplicate_groups: 1` |
| AT-N0-DB-01 | PASS | `pytest tests/test_state_db.py::test_at_n0_db_01_*` | schema v0 with 6 tables; `PRAGMA foreign_keys=1`; **journal_mode=DELETE, synchronous=FULL** (baseline test); reopen preserves data; FK-violating transaction rolls back |
| AT-N0-STATE-01 | PASS | `pytest tests/test_state_db.py::test_at_n0_state_01_*` | INGESTED->APPROVED rejected; non-human APPROVED rejected; terminal EXPORTED has no outgoing transitions |
| AT-N0-REC-01 | PASS | `pytest tests/test_state_db.py::test_at_n0_rec_01_*` | RUNNING run with expired lease identified after reopen; recovery marks INTERRUPTED; no outputs invented; asset state unchanged |
| AT-N0-SCHEMA-01 | PASS | `pytest tests/test_schema.py::test_at_n0_schema_01_*` | valid item passes core rules + jsonschema Draft 2020-12 |
| AT-N0-SCHEMA-02 | PASS | `pytest tests/test_schema.py::test_at_n0_schema_02_*` | absolute-path, auto-approved, vlm-pose items each fail their expected core rule |
| AT-N0-SEC-01 | PASS | `pytest tests/test_security.py` (overlap) | equal roots, runtime-in-source, source-in-runtime all rejected with `NPI_SOURCE_RUNTIME_OVERLAP` |
| AT-N0-SEC-02 | PASS | `pytest tests/test_security.py` (escape) | `..` path escape rejected by containment; NTFS junction (is_symlink()=False, st_file_attributes&0x400=True) rejected; disallowed extension rejected |
| AT-N0-SEC-03 | PASS | `pytest tests/test_security.py::test_at_n0_sec_03_*` | pre/post size, mtime_ns, sha256 identical for all 3 fixtures after read-only open |
| AT-N0-SEC-04 | PASS | `pytest tests/test_security.py::test_at_n0_sec_04_*` | `tools/sensitive_file_scan.py` exits 0 with "0 violation(s)" |
| AT-N0-LOG-01 | PASS | `pytest tests/test_security.py::test_at_n0_log_01_*` | log file under runtime/logs; fixture root absolute path absent; `<SOURCE_ROOT>` token present |
| AT-N0-GATE-01 | PASS | `pytest tests/test_cli.py::test_at_n0_gate_01_*` | `npi ingest --input <fixtures>` (no --dry-run) exits 8 with `error_code: NPI_GATE_NOT_AUTHORIZED` (verified on 3.12) |
| AT-N0-GATE-02 | PASS | `pytest tests/test_handoff.py` (gate_02) | PROJECT_STATE locks N1-N8 + G1-G3; only N0/G0 AUTHORIZED; 8 N1-N8 task files LOCKED |
| AT-N0-GIT-01 | PASS | `pytest tests/test_git.py` (post-commit) | exactly 1 commit; working tree clean; `git ls-files` has no db/log/weight/secret/personal-path; only 3 fixture PNGs tracked as images |

AT-N0-GIT-01 was SKIPPED before the single commit was created (no HEAD). After the one isolated commit it PASSes. The skip was not relabeled as PASS.

## Source integrity before/after

The 3 synthetic fixtures under `fixtures/three_image_smoke_set/` were read (binary, read-only) by the test suite and the dry-run. Pre/post evidence (per AT-N0-SEC-03):

| Fixture | size_bytes (pre==post) | sha256 (matches manifest) | mtime_ns unchanged |
|---|---|---|---|
| fixture_a_corridor_abstract.png | 2702 | ff0ec4d4baeb0a83495afaa62b65dc58110d83f9e2da14fd19e4d50959430157 | yes |
| fixture_a_exact_copy.png | 2702 | ff0ec4d4baeb0a83495afaa62b65dc58110d83f9e2da14fd19e4d50959430157 | yes |
| fixture_b_tonal_abstract.png | 2439 | 9544c610264418316c22143442e8a3e308e076eca2f19d0e51cf67baa3489097 | yes |

No source fixture content, size, or mtime was changed. No write/move/delete/chmod API exists in the source guard.

## SQLite baseline evidence (DELETE + FULL + FK)

`tests/test_state_db.py::test_at_n0_db_01_pragma_baseline_delete_full_fk` asserts:
- `PRAGMA journal_mode` == `delete`
- `PRAGMA synchronous` == `2` (FULL)
- `PRAGMA foreign_keys` == `1` (ON)

WAL is NOT adopted (no Owner-approved exception). The store is single-writer with short transactions (`BEGIN`/`COMMIT` via `StateStore.transaction()`). Reopen preserves data; an FK-violating transaction rolls back; an interrupted RUNNING run with an expired lease is identified and marked INTERRUPTED without fabricated outputs.

## Git commit content evidence (post-commit)

- `git rev-list --count HEAD` == 1 (one isolated commit).
- `git status --porcelain` clean.
- `git ls-files` contains no `.db`, `.sqlite*`, `.log`, `.pem/.key/.p12/.pfx`, `.pt/.pth/.ckpt/.safetensors/.onnx/.engine/.npy/.npz`, `.env`, or other sensitive patterns.
- Only the 3 fixture PNGs are tracked as image files.
- `.gitignore` excludes `runtime/`, `state/`, `*.db`, `*.sqlite*`, `*.log`, model weights, image derivatives, `.venv/`, `__pycache__/`, `reports/generated/`, and secrets.

## Independent Reviewer checklist (for the independent Reviewer)

The independent Reviewer should verify against `CLAUDE_REVIEW_CHECKLIST.md`:

1. **Scope**: only N0 changes; no model/cloud/OpenClaw/App; PROJECT_STATE unchanged (N0 only, N1-N8 LOCKED); one commit.
2. **Source safety**: no write/move/delete/chmod API in `ingest/source_guard.py`; source/runtime overlap rejected; symlink/reparse escape rejected (verify `is_reparse_point` checks `st_file_attributes & 0x400` on win32); pre/post integrity; path redaction.
3. **State and recovery**: state enum/transition guards; SQLite transactions; interrupted run; dry-run no DB mutation; idempotency; DELETE+FULL+FK baseline.
4. **Quality/evidence**: pytest/ruff/mypy (all PASS on 3.12); valid/invalid Schema; stable exit codes; Git sensitive scan; reports truthful; skips not passes.
5. **Exit codes**: `cli.py` and `domain/errors.py` match `docs/11_cli_contract.md` (0/2/3/4/5/6/7/8/9/10).
6. **Gate ordering**: non-dry-run ingest fails closed with exit 8 before any source/DB access.

Commands for the Reviewer (run from the project root with the 3.12 venv):
```bash
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check src tests tools/run_quality.py tools/sensitive_file_scan.py
.venv/Scripts/python.exe -m ruff format --check src tests tools/run_quality.py tools/sensitive_file_scan.py
.venv/Scripts/python.exe -m mypy src/nightly_photo_intelligence_pipeline
.venv/Scripts/python.exe tools/run_quality.py
.venv/Scripts/python.exe tools/verify_handoff.py   # historical; expect manifest-set divergence post-impl
git -C . log --oneline
git -C . status --porcelain
git -C . ls-files | grep -iE '\.(db|sqlite|log|pem|key|pt|pth|ckpt|safetensors|onnx|engine|npy|npz)$|token|secret'
```

A fresh `PASS_FOR_OWNER_REVIEW` from an independent Reviewer on this single commit's SHA is required before N0 is submitted to the Owner. The prior `PASS_FOR_OWNER_REVIEW` recorded in `N0_independent_review.md` applied to content-equivalent prior content, not to this commit's SHA.

## Failures and skips

- No FAIL results in the post-commit quality gate.
- AT-N0-GIT-01: SKIPPED pre-commit, PASS post-commit.
- GPU container execution: SKIPPED (must not pull an image in N0).
- Python 3.11: not available on this machine; 3.12.10 used (3.11 is the targeted lower bound, not verified here).

Skips were not rewritten as PASS. The implementer's self-verification is NOT an independent review pass.
